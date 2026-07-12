from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np

from .history import GlobalUndoManager, UndoAction
from .layers import Layer, LayerRole
from .regions import RegionMap, build_region_map
from .selection import Selection, SelectionSet
from rp_restore.core.color_correction import apply_color_correction
from rp_restore.core.texture_brush import Texture
from rp_restore.io.image_io import load_image


class Project:
    """
    Reprezentuje jeden otvorený projekt aplikácie
    uchováva vrstvy, damage masky, nastavenia kreslenia, paletu, textúry a undo/redo stav
    """

    def __init__(self, project_name: str) -> None:
        self.project_name: str = project_name

        #informácie o pôvodnom obraze a pracovnej kópii
        self.base_image_path: Path | None = None
        self.is_dirty: bool = False
        self.base_image_scale: float = 1.0  #working_size / original_size
        self.base_image_working: np.ndarray | None = None  #obraz, s ktorým aplikácia reálne pracuje

        #všetky vrstvy v projekte (BACKGROUND, EDGE, PAINT)
        self.layers: list[Layer] = []

        #globálna maska poškodenia a z nej odvodená maska vyplnených pixelov
        self.damage_original_mask: np.ndarray | None = None
        self.damage_filled_mask: np.ndarray | None = None

        #záznamy pre neskorší PDF report
        self.history_for_report: list[dict] = []

        #undo/redo manažér
        self.undo_manager: GlobalUndoManager = GlobalUndoManager()

        #paleta farieb a aktuálna farba (RGBA)
        self.palette_colors: list[tuple[int, int, int, int]] = []
        self.current_color_rgba: tuple[int, int, int, int] = (0, 0, 0, 255)

        #nastavenia štetca v rozsahu 0..1
        self.brush_hardness: float = 1.0
        self.brush_opacity: float = 1.0
        self.brush_flow: float = 1.0
        self.brush_allow_overlap: bool = True

        #textúry a režim ich aplikovania
        self.textures: dict[str, Texture] = {}
        self.texture_style: str = "transparent"

        #ColorChecker korekcia náhľadu
        self.color_correction_matrix: np.ndarray | None = None
        self.color_correction_enabled: bool = False

    def mark_dirty(self) -> None:
        """Označí projekt ako zmenený"""
        self.is_dirty = True

    def mark_saved(self) -> None:
        """Označí projekt ako uložený"""
        self.is_dirty = False

    #---------správa vrstiev---------

    def add_layer(self, layer: Layer) -> None:
        """Pridá vrstvu do projektu"""
        self.layers.append(layer)

        if layer.meta.role == LayerRole.PAINT and self.damage_original_mask is not None:
            #ak už damage maska existuje, inicializujeme per-layer filled masku z alfa kanálu
            if getattr(layer, "damage_filled_mask", None) is None:
                alpha_filled = (layer.image[..., 3] > 0) & self.damage_original_mask
                layer.damage_filled_mask = alpha_filled.astype(bool)

    def remove_layer(self, layer_id: str) -> None:
        """Odstráni PAINT vrstvu z projektu"""
        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None:
            return

        if layer.meta.role != LayerRole.PAINT:
            raise ValueError("Only PAINT layers can be removed")

        self.layers = [l for l in self.layers if l.meta.id != layer_id]

        #prepočítame order vrstiev
        for idx, l in enumerate(self.layers):
            l.meta.order = idx

    def get_background_layer(self) -> Layer | None:
        """Vráti prvú BACKGROUND vrstvu alebo None"""
        for layer in self.layers:
            if layer.meta.role == LayerRole.BACKGROUND:
                return layer
        return None

    def get_paint_layers(self) -> list[Layer]:
        """Vráti zoznam všetkých PAINT vrstiev"""
        return [l for l in self.layers if l.meta.role == LayerRole.PAINT]

    def get_edge_layer(self) -> Layer | None:
        """Vráti EDGE vrstvu projektu alebo None"""
        for layer in self.layers:
            if layer.meta.role == LayerRole.EDGE:
                return layer
        return None

    def get_layer_damage_remaining_mask(self, layer_id: str) -> np.ndarray | None:
        """Vráti zostávajúcu damage masku pre konkrétnu PAINT vrstvu"""
        if self.damage_original_mask is None:
            return None

        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None or layer.meta.role != LayerRole.PAINT:
            return None

        if layer.damage_filled_mask is None or layer.damage_filled_mask.shape != self.damage_original_mask.shape:
            layer.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

        return self.damage_original_mask & ~layer.damage_filled_mask

    def mark_region_as_filled_on_layer(self, layer_id: str, region_mask: np.ndarray) -> None:
        """Označí danú oblasť ako vyplnenú iba na konkrétnej PAINT vrstve"""
        if self.damage_original_mask is None:
            return

        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None or layer.meta.role != LayerRole.PAINT:
            return

        if region_mask.shape != self.damage_original_mask.shape:
            raise ValueError("region_mask must have same shape as damage_original_mask")

        if layer.damage_filled_mask is None or layer.damage_filled_mask.shape != self.damage_original_mask.shape:
            layer.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

        layer.damage_filled_mask |= region_mask.astype(bool) & self.damage_original_mask

    #---------kompozícia obrazu---------

    def composited_image(self) -> np.ndarray:
        """
        Zloží výsledný RGB obraz z viditeľných vrstiev
        BACKGROUND tvorí podklad, PAINT vrstvy a EDGE vrstva sa skladajú pomocou alfa kanálu a krytia vrstvy
        """
        bg_layer = self.get_background_layer()
        if bg_layer is None:
            raise RuntimeError("Project has no BACKGROUND layer.")

        h, w, _ = bg_layer.image.shape

        #ak je background skrytý, podklad je čierny
        if not bg_layer.meta.visible:
            base = np.zeros((h, w, 3), dtype=np.float32)
        else:
            base = bg_layer.image[..., :3].astype(np.float32)

        #PAINT vrstvy skladáme zospodu hore podľa order
        paint_layers = sorted(self.get_paint_layers(), key=lambda l: l.meta.order)
        for layer in paint_layers:
            if not layer.meta.visible:
                continue
            if layer.image.shape[0] != h or layer.image.shape[1] != w:
                continue

            rgba = layer.image.astype(np.float32)
            rgb = rgba[..., :3]
            alpha = (rgba[..., 3:4] / 255.0) * float(layer.meta.opacity)
            alpha = np.clip(alpha, 0.0, 1.0)

            base = rgb * alpha + base * (1.0 - alpha)

        edge_layer = self.get_edge_layer()
        if edge_layer is not None and edge_layer.meta.visible:
            rgba = edge_layer.image.astype(np.float32)

            if rgba.shape[0] == h and rgba.shape[1] == w:
                rgb = rgba[..., :3]
                alpha = (rgba[..., 3:4] / 255.0) * float(edge_layer.meta.opacity)
                alpha = np.clip(alpha, 0.0, 1.0)

                base = rgb * alpha + base * (1.0 - alpha)

        out = np.clip(base, 0, 255).astype(np.uint8)

        #ColorChecker korekcia sa aplikuje iba na náhľad/export, nie na samotné vrstvy
        if self.color_correction_enabled and self.color_correction_matrix is not None:
            out = apply_color_correction(out, self.color_correction_matrix)

        return out
    
    def composited_region(self, bbox: tuple[int, int, int, int]) -> np.ndarray:
        """Zloží výsledný RGB obraz iba v oblasti bbox = (x, y, w, h)"""
        bg_layer = self.get_background_layer()
        if bg_layer is None:
            raise RuntimeError("Project has no BACKGROUND layer")

        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            #vrátime aspoň 1x1 obraz, aby volajúci kód nespadol na prázdnom výreze
            return np.zeros((1, 1, 3), dtype=np.uint8)

        H, W, _ = bg_layer.image.shape

        #orezanie bboxu do hraníc obrázka
        x0 = max(0, min(x, W))
        y0 = max(0, min(y, H))
        x1 = max(x0, min(x + w, W))
        y1 = max(y0, min(y + h, H))

        if x1 <= x0 or y1 <= y0:
            return np.zeros((1, 1, 3), dtype=np.uint8)

        #ak je background skrytý, podklad je čierny
        if not bg_layer.meta.visible:
            base = np.zeros((y1 - y0, x1 - x0, 3), dtype=np.float32)
        else:
            base = bg_layer.image[y0:y1, x0:x1, :3].astype(np.float32)

        #PAINT vrstvy
        paint_layers = sorted(self.get_paint_layers(), key=lambda l: l.meta.order)
        for layer in paint_layers:
            if not layer.meta.visible:
                continue
            if layer.image.shape[0] != H or layer.image.shape[1] != W:
                continue

            rgba = layer.image[y0:y1, x0:x1, :].astype(np.float32)
            if rgba.size == 0:
                continue

            rgb = rgba[..., :3]
            alpha = rgba[..., 3:4] / 255.0 * float(layer.meta.opacity)
            alpha = np.clip(alpha, 0.0, 1.0)

            base = rgb * alpha + base * (1.0 - alpha)

        #EDGE vrstva
        edge_layer = self.get_edge_layer()
        if edge_layer is not None and edge_layer.meta.visible:
            rgba = edge_layer.image

            if rgba.shape[0] == H and rgba.shape[1] == W:
                sub = rgba[y0:y1, x0:x1, :].astype(np.float32)

                if sub.size > 0:
                    rgb = sub[..., :3]
                    alpha = sub[..., 3:4] / 255.0 * float(edge_layer.meta.opacity)
                    alpha = np.clip(alpha, 0.0, 1.0)

                    base = rgb * alpha + base * (1.0 - alpha)

        out = np.clip(base, 0, 255).astype(np.uint8)

        if self.color_correction_enabled and self.color_correction_matrix is not None:
            out = apply_color_correction(out, self.color_correction_matrix)

        return out
    
    #---------undo/redo rozhranie---------

    def undo_global(self) -> UndoAction | None:
        """Vykoná globálne undo a vráti UndoAction alebo None"""
        return self.undo_manager.undo_global(self)

    def redo_global(self) -> UndoAction | None:
        """Vykoná globálne redo a vráti UndoAction alebo None"""
        return self.undo_manager.redo_global(self)

    def undo_on_layer(self, layer_id: str) -> UndoAction | None:
        """Vykoná undo na vrstve iba vtedy, ak posledná akcia patrí tejto vrstve"""
        return self.undo_manager.undo_on_layer(self, layer_id)

    def can_undo(self) -> bool:
        """Vráti True, ak je dostupné undo"""
        return self.undo_manager.can_undo()

    def can_redo(self) -> bool:
        """Vráti True, ak je dostupné redo"""
        return self.undo_manager.can_redo()

    #---------damage masky--------

    def set_damage_masks(self, original_mask: np.ndarray | None) -> None:
        """Nastaví pôvodnú damage masku, kde True znamená poškodený pixel"""
        if original_mask is None:
            raise ValueError("Damage mask could not be loaded (None)")
        
        original_mask = np.asarray(original_mask)

        if original_mask.ndim == 3:
            original_mask = original_mask[..., 0]

        if original_mask.ndim != 2:
            raise ValueError("Damage mask must be 2D (H, W)")

        bg_layer = self.get_background_layer()
        if bg_layer is not None and original_mask.shape != bg_layer.image.shape[:2]:
            raise ValueError("Damage mask must have the same size as the background layer")

        self.damage_original_mask = original_mask.astype(bool)
        self.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

        #ak už existujú PAINT vrstvy, doplníme ich per-layer filled masky podľa alfa kanálu
        for layer in self.get_paint_layers():
            self.sync_layer_filled_mask_from_alpha(layer.meta.id, mode="assign")

    def get_damage_remaining_mask(self) -> np.ndarray | None:
        """Vráti masku zostávajúcich nevyplnených poškodených pixelov"""
        if self.damage_original_mask is None:
            return None

        filled = self.compute_filled_mask_from_layers(visible_only=False)
        remaining = self.damage_original_mask & ~filled

        #globálnu filled masku držíme aktuálnu podľa všetkých PAINT vrstiev
        self.damage_filled_mask = filled.copy()
        return remaining
    
    def get_damage_remaining_mask_for_visible_layers(self) -> np.ndarray | None:
        """Vráti remaining damage masku iba podľa viditeľných PAINT vrstiev pre overlay"""
        if self.damage_original_mask is None:
            return None

        filled_visible = self.compute_filled_mask_from_layers(visible_only=True)
        return self.damage_original_mask & ~filled_visible

    def get_selection_from_click(self, x: int, y: int, layer_id: str | None = None, region_map: RegionMap | None = None) -> Selection | None:
        """Vráti výber poškodenej oblasti pod kliknutým bodom"""
        if self.damage_original_mask is None:
            return None

        mask: np.ndarray | None = None
        if layer_id is not None:
            layer = next((l for l in self.layers if l.meta.id == layer_id), None)

            if layer is not None and layer.meta.role == LayerRole.PAINT:
                mask = self.get_layer_damage_remaining_mask(layer_id)
            else:
                mask = self.damage_original_mask
        else:
            mask = self.damage_original_mask

        if mask is None:
            return None

        h, w = mask.shape

        if x < 0 or y < 0 or x >= w or y >= h:
            return None

        if not mask[y, x]:
            #klik mimo poškodenej oblasti
            return None

        if region_map is None:
            edge_layer = self.get_edge_layer()
            region_map = build_region_map(mask, edge_layer)

        label_image = region_map.label_image
        region_id = int(label_image[y, x])
        if region_id == 0:
            return None
        
        info = region_map.regions.get(region_id)
        if info is None:
            return None
        
        region_mask = region_map.get_region_mask(region_id)
        bbox = info.bbox

        return Selection(region_mask=region_mask, bbox=bbox, seed_point=(x, y), region_id=region_id)
    
    def get_selections_from_polygon(self, polygon_points: list[tuple[int, int]], layer_id: str | None = None, region_map: RegionMap | None = None) -> SelectionSet | None:
        """
        Nájde všetky damage oblasti, ktoré ležia vo vnútri polygonu lasa
        na PAINT vrstve používa remaining masku danej vrstvy
        """
        if self.damage_original_mask is None:
            return None

        if not polygon_points or len(polygon_points) < 3:
            return None

        mask: np.ndarray | None = None

        if layer_id is not None:
            layer = next((l for l in self.layers if l.meta.id == layer_id), None)
            if layer is not None and layer.meta.role == LayerRole.PAINT:
                mask = self.get_layer_damage_remaining_mask(layer_id)
            else:
                mask = self.damage_original_mask
        else:
            mask = self.damage_original_mask

        if mask is None:
            return None

        h, w = mask.shape

        if region_map is None:
            edge_layer = self.get_edge_layer()
            region_map = build_region_map(mask, edge_layer)

        #rasterizácia polygonu do bool masky
        poly_img = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(poly_img)
        draw.polygon(polygon_points, outline=1, fill=1)
        polygon_mask = np.array(poly_img, dtype=np.uint8) > 0

        #zaujímajú nás iba pixely v polygone, ktoré zároveň patria do relevantnej damage masky
        effective_mask = polygon_mask & mask
        if not effective_mask.any():
            return None

        #zistíme, ktoré region_id sa nachádzajú vo vnútri lasa
        label_sub = region_map.label_image[effective_mask]
        region_ids = np.unique(label_sub)
        region_ids = region_ids[region_ids > 0]

        if region_ids.size == 0:
            return None

        selections: list[Selection] = []

        for region_id in region_ids.tolist():
            info = region_map.regions.get(int(region_id))
            if info is None:
                continue

            region_mask = region_map.get_region_mask(int(region_id))
            bbox = info.bbox

            #seed point použijeme iba ako reprezentatívny bod oblasti
            x, y, bw, bh = bbox
            seed_point = (x + bw // 2, y + bh // 2)

            selections.append(Selection(region_mask=region_mask, bbox=bbox, seed_point=seed_point, region_id=int(region_id)))

        if not selections:
            return None

        return SelectionSet(selections=selections)

    def compute_filled_mask_from_layers(self, visible_only: bool = False) -> np.ndarray:
        """Vypočíta union vyplnených damage pixelov podľa alfa kanálu PAINT vrstiev"""
        if self.damage_original_mask is None:
            raise RuntimeError("Project has no damage mask")

        h, w = self.damage_original_mask.shape
        filled_union = np.zeros((h, w), dtype=bool)

        for layer in self.get_paint_layers():
            if visible_only and not layer.meta.visible:
                continue
            if layer.image.shape[0] != h or layer.image.shape[1] != w:
                continue

            alpha_filled = (layer.image[..., 3] > 0) & self.damage_original_mask
            filled_union |= alpha_filled

            if not visible_only:
                layer.damage_filled_mask = alpha_filled.astype(bool)
        
        filled_union &= self.damage_original_mask
        return filled_union
    
    def _compute_filled_mask_from_layers(self, visible_only: bool = False) -> np.ndarray | None:
        """Spätná kompatibilita pre staršie volania, používa verejnú metódu compute_filled_mask_from_layers"""
        if self.damage_original_mask is None:
            return None
        return self.compute_filled_mask_from_layers(visible_only=visible_only)

    def sync_layer_filled_mask_from_alpha(self, layer_id: str, bbox: tuple[int, int, int, int] | None = None, mode: str = "or") -> None:
        """
        Synchronizuje layer.damage_filled_mask podľa alfa kanálu vrstvy a damage masky
        mode="assign" prepíše hodnoty vo výreze, ostatné hodnoty mode pridávajú cez OR
        """
        if self.damage_original_mask is None:
            return

        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None or layer.meta.role != LayerRole.PAINT:
            return

        if layer.damage_filled_mask is None or layer.damage_filled_mask.shape != self.damage_original_mask.shape:
            layer.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

        h, w = self.damage_original_mask.shape
 
        if bbox is None:
            alpha_filled = (layer.image[..., 3] > 0) & self.damage_original_mask
            layer.damage_filled_mask[...] = alpha_filled
            return

        x, y, bw, bh = bbox
        if bw <= 0 or bh <= 0:
            return

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(w, x + bw)
        y1 = min(h, y + bh)
        if x1 <= x0 or y1 <= y0:
            return

        alpha_sub = layer.image[y0:y1, x0:x1, 3] > 0
        dmg_sub = self.damage_original_mask[y0:y1, x0:x1]
        filled_sub = alpha_sub & dmg_sub

        if mode == "assign":
            layer.damage_filled_mask[y0:y1, x0:x1] = filled_sub
        else:
            layer.damage_filled_mask[y0:y1, x0:x1] |= filled_sub

    #---------metódy pre externé algoritmy---------

    def get_original_image(self) -> np.ndarray | None:
        """Vráti pôvodný obraz alebo pracovnú kópiu, ak pôvodný súbor nie je dostupný"""
        if self.base_image_path is not None and self.base_image_scale == 1.0:
            #ak pracujeme v pôvodnom rozlíšení, môžeme skúsiť načítať obraz priamo zo súboru
            try:
                arr = load_image(self.base_image_path)
                return arr
            except Exception:
                #fallback na working image
                pass

        if self.base_image_working is not None:
            return self.base_image_working.copy()
        
        bg = self.get_background_layer()
        if bg is None:
            return None
        return bg.image.copy()

    def get_current_composited_image(self) -> np.ndarray:
        """Vráti aktuálny zložený obraz"""
        return self.composited_image()

    #---------farby, paleta---------

    def get_current_color_rgba(self) -> tuple[int, int, int, int]:
        """Vráti aktuálnu RGBA farbu"""
        return self.current_color_rgba

    def set_current_color_rgba(self, color: tuple[int, int, int, int]) -> None:
        """Nastaví aktuálnu RGBA farbu a oreže hodnoty do rozsahu 0..255"""
        r, g, b, a = [int(max(0, min(255, c))) for c in color]
        self.current_color_rgba = (r, g, b, a)

    def add_palette_color(self, color: tuple[int, int, int, int]) -> None:
        """Pridá farbu do palety, ak tam ešte nie je"""
        r, g, b, a = [int(max(0, min(255, c))) for c in color]
        rgba = (r, g, b, a)
        if rgba not in self.palette_colors:
            self.palette_colors.append(rgba)

    def get_palette_colors(self) -> list[tuple[int, int, int, int]]:
        """Vráti kópiu palety farieb"""
        return list(self.palette_colors)

    #---------ColorChecker korekcia---------

    def set_color_correction_matrix(self, matrix: np.ndarray | None) -> None:
        """Nastaví maticu farebnej korekcie alebo ju zruší"""
        if matrix is None:
            self.color_correction_matrix = None
            return

        m = np.asarray(matrix, dtype=np.float32)
        if m.shape not in [(3, 3), (3, 4)]:
            raise ValueError("Color correction matrix must be 3x3 or 3x4")
        self.color_correction_matrix = m

    def set_color_correction_enabled(self, enabled: bool) -> None:
        """Zapne alebo vypne ColorChecker korekciu náhľadu"""
        self.color_correction_enabled = bool(enabled)

    def has_color_correction(self) -> bool:
        """Vráti True, ak má projekt nastavenú ColorChecker korekciu"""
        return self.color_correction_matrix is not None

    #---------export--------

    def get_export_image(self) -> np.ndarray:
        """Vráti exportovateľný finálny obraz v pracovnom rozlíšení"""
        return self.composited_image()