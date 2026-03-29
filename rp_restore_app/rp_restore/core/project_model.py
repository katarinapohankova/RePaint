from __future__ import annotations

from typing import List, Optional

from pathlib import Path
import numpy as np

from .layers import Layer, LayerRole

from .history import UndoAction, GlobalUndoManager

from .warnings import UserWarning
from .warnings import LogManager, WarningType, RegionReference
from .selection import Selection
from .regions import RegionMap, build_region_map, compare_region_maps
from rp_restore.io.image_io import load_image
from rp_restore.core.texture_brush import Texture


class Project:
    """
    Reprezentuje jeden otvorený projekt
    Zatiaľ:
      - nemá warningy ani IO
      - vie držať vrstvy a urobiť jednoduchú kompozíciu
    """

    def __init__(self, project_name: str) -> None:
        self.project_name: str = project_name

        #info o pôvodnom obraze / working image
        self.base_image_path: Path | None = None
        self.is_dirty: bool = False
        self.base_image_scale: float = 1.0  #working_size / original_size
        self.base_image_working: np.ndarray | None = None  #to, čo sa reálne používa

        #všetky vrstvy v projekte (BACKGROUND, EDGE, PAINT)
        self.layers: List[Layer] = []

        #masky poškodenia – zatiaľ len pripravené, môžu byť None
        self.damage_original_mask: Optional[np.ndarray] = None
        self.damage_filled_mask: Optional[np.ndarray] = None

        #záznamy pre neskorší PDF report
        self.history_for_report: List[dict] = []

        #undo/redo manažér 
        self.undo_manager: GlobalUndoManager = GlobalUndoManager()

        #warningy a logy
        self.log_manager: LogManager = LogManager()

        #cace pre poslednú region mapu -pre porovnanie pri zmene hrán
        self._cached_region_map: RegionMap | None = None

        #paleta farieb a aktuálna farba (RGBA)
        self.palette_colors: list[tuple[int, int, int, int]] = []
        self.current_color_rgba: tuple[int, int, int, int] = (0, 0, 0, 255)  #default bude čierna

        self.textures: dict[str, "Texture"] = {}

    def mark_dirty(self) -> None:
        self.is_dirty = True

    def mark_saved(self) -> None:
        self.is_dirty = False
        
    #---------Správa vrstiev---------

    def add_layer(self, layer: Layer) -> None:
        """Pridá vrstvu do projektu"""
        self.layers.append(layer)

        if layer.meta.role == LayerRole.PAINT and self.damage_original_mask is not None:
            #ak už maska existuje, necháme ju -inak ju dopočítame z alfa kanálu
            if getattr(layer, "damage_filled_mask", None) is None:
                alpha_filled = (layer.image[..., 3] > 0) & self.damage_original_mask
                layer.damage_filled_mask = alpha_filled.astype(bool)
    
    def remove_layer(self, layer_id: str) -> None:
        """
        Odstráni vrstvu (iba paint)
        """
        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None:
            return

        if layer.meta.role != LayerRole.PAINT:
            raise ValueError("Only PAINT layers can be removed")

        self.layers = [l for l in self.layers if l.meta.id != layer_id]

        #prepočítame order vrstiev
        for idx, l in enumerate(self.layers):
            l.meta.order = idx

    def get_background_layer(self) -> Optional[Layer]:
        """Vráti prvú BACKGROUND vrstvu (alebo None, ak neexistuje)"""
        for layer in self.layers:
            if layer.meta.role == LayerRole.BACKGROUND:
                return layer
        return None

    def get_paint_layers(self) -> List[Layer]:
        """Vráti zoznam všetkých PAINT vrstiev"""
        return [l for l in self.layers if l.meta.role == LayerRole.PAINT]

    def get_edge_layers(self) -> List[Layer]:
        """Vráti zoznam všetkých EDGE vrstiev"""
        return [l for l in self.layers if l.meta.role == LayerRole.EDGE]

    def get_layer_damage_remaining_mask(self, layer_id: str) -> np.ndarray | None:
        """
        Remaining mask pre konkrétnu paint vrstvu
        """
        if self.damage_original_mask is None:
            return None

        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None or layer.meta.role != LayerRole.PAINT:
            return None

        if layer.damage_filled_mask is None:
            layer.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

        return self.damage_original_mask & ~layer.damage_filled_mask


    def mark_region_as_filled_on_layer(self, layer_id: str, region_mask: np.ndarray) -> None:
        """
        Označí daný region ako vyplnený iba na konkrétnej paint vrstve
        """
        if self.damage_original_mask is None:
            return

        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None or layer.meta.role != LayerRole.PAINT:
            return

        if region_mask.shape != self.damage_original_mask.shape:
            raise ValueError("region_mask must have same shape as damage_original_mask")

        if layer.damage_filled_mask is None:
            layer.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

        layer.damage_filled_mask |= region_mask.astype(bool)

    #---------Kompozícia obrazu---------

    def composited_image(self) -> np.ndarray:
        """
        Zloží výsledný RGB obraz z backgroundu a všetkých PAINT vrstiev
        Zatiaľ:
          - ignorujeme EDGE vrstvy
          - ignorujeme opacity v meta
          - PAINT vrstvy skladáme jednoduchým alpha blendingom
        """
        bg_layer = self.get_background_layer()
        if bg_layer is None:
            raise RuntimeError("Project has no BACKGROUND layer.")

        h, w, _ = bg_layer.image.shape

        #viditeľnosť backgroundu
        if not bg_layer.meta.visible:
            base = np.zeros((h, w, 3), dtype=np.float32)
        else:
            base = bg_layer.image[..., :3].astype(np.float32)

        #zoberieme všetky paint vrstvy zoradené
        paint_layers = sorted(self.get_paint_layers(), key=lambda l: l.meta.order)
        for layer in paint_layers:
            if not layer.meta.visible:
                continue
            rgba = layer.image.astype(np.float32)
            rgb = rgba[..., :3]
            alpha = (rgba[..., 3:4] / 255.0) * float(layer.meta.opacity)  #tvar (H, W, 1)
            alpha = np.clip(alpha, 0.0, 1.0)

            #alpha blending: out = rgb * a + base * (1 - a)
            base = rgb * alpha + base * (1.0 - alpha)

        edge_layers = sorted(self.get_edge_layers(), key=lambda l: l.meta.order)
        for layer in edge_layers:
            if not layer.meta.visible:
                continue
            rgba = layer.image.astype(np.float32)

            if rgba.shape[0] != h or rgba.shape[1] != w:
                continue
            rgb = rgba[..., :3]
            alpha = (rgba[..., 3:4] / 255.0) * float(layer.meta.opacity)
            alpha = np.clip(alpha, 0.0, 1.0)
            base = rgb * alpha + base * (1.0 - alpha)
        #výsledok pretypujeme na uint8
        return np.clip(base, 0, 255).astype(np.uint8)
    
    def composited_region(self, bbox: tuple[int, int, int, int]) -> np.ndarray:
        """
        Zloží výsledný RGB obraz iba v danej oblasti bbox = (x, y, w, h)
        -rovnaké ako composited_image(), ale len pre slice
        """
        bg_layer = self.get_background_layer()
        if bg_layer is None:
            raise RuntimeError("Project has no BACKGROUND layer")

        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            #vrátime aspoň nejaké 1x1, aby to nepadlo
            return np.zeros((1, 1, 3), dtype=np.uint8)

        H, W, _ = bg_layer.image.shape

        #orezanie bboxu do hraníc obrázka
        x0 = max(0, min(x, W))
        y0 = max(0, min(y, H))
        x1 = max(x0, min(x + w, W))
        y1 = max(y0, min(y + h, H))

        if x1 <= x0 or y1 <= y0:
            return np.zeros((1, 1, 3), dtype=np.uint8)

        #začneme s RGB z background v danom výseku
        base = bg_layer.image[y0:y1, x0:x1, :3].astype(np.float32)

        #PAINT vrstvy
        for layer in self.get_paint_layers():
            if not layer.meta.visible:
                continue
            rgba = layer.image[y0:y1, x0:x1, :].astype(np.float32)
            if rgba.size == 0:
                continue
            rgb = rgba[..., :3]
            alpha = rgba[..., 3:4] / 255.0 * float(layer.meta.opacity) #(h, w, 1)
            alpha = np.clip(alpha, 0.0, 1.0)
            base = rgb * alpha + base * (1.0 - alpha)

        #EDGE vrstvy
        for layer in self.get_edge_layers():
            if not layer.meta.visible:
                continue
            rgba = layer.image
            if rgba.shape[0] != H or rgba.shape[1] != W:
                continue
            sub = rgba[y0:y1, x0:x1, :].astype(np.float32)
            if sub.size == 0:
                continue
            rgb = sub[..., :3]
            alpha = sub[..., 3:4] / 255.0 * float(layer.meta.opacity)
            alpha = np.clip(alpha, 0.0, 1.0)
            base = rgb * alpha + base * (1.0 - alpha)

        return np.clip(base, 0, 255).astype(np.uint8)
    
    #---------Undo/redo rozhranie---------

    def undo_global(self) -> Optional[UndoAction]:
        """Vykoná globálne undo
        Vráti UndoAction alebo None"""
        return self.undo_manager.undo_global(self)

    def redo_global(self) -> Optional[UndoAction]:
        """Vykoná globálne redo
        Vráti UndoAction alebo None"""
        return self.undo_manager.redo_global(self)

    def undo_on_layer(self, layer_id: str) -> Optional[UndoAction]:
        """Vykoná undo na konkrétnej vrstve (zatiaľ jednoduchá verzia)"""
        return self.undo_manager.undo_on_layer(self, layer_id)
    
    def can_undo(self) -> bool:
        return self.undo_manager.can_undo()

    def can_redo(self) -> bool:
        return self.undo_manager.can_redo()

    #---------damage masky--------
    def set_damage_masks(self, original_mask: Optional[np.ndarray]) -> None:
        """
        Nastaví masku poškodenia
        original_mask -2D pole (H, W), kde true je poškodené miesto
        """
        if original_mask is None:
            raise ValueError("Damage mask could not be loaded (None)")
        
        original_mask = np.asarray(original_mask)

        if original_mask.ndim == 3:
            original_mask = original_mask[..., 0]
            
        if original_mask.ndim != 2:
            raise ValueError("Damage mask must be 2D (H, W)")

        self.damage_original_mask = original_mask.astype(bool)
        self.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

    def get_damage_remaining_mask(self) -> np.ndarray | None:
        """
        vráti masku zostávajúcich (nevyplnených) poškodených miest
        """
        if self.damage_original_mask is None or self.damage_filled_mask is None:
            return None

        filled = self._compute_filled_mask_from_layers()
        if filled is None:
            #žiadne paint vrstvy –všetko pôvodné poškodenie je remaining
            return self.damage_original_mask.copy()

        remaining = self.damage_original_mask & ~filled

        #synchronizácia damage_filled_mask (nech je aktuálna)
        self.damage_filled_mask = filled.copy()
        return remaining

    def mark_region_as_filled(self, region_mask: np.ndarray) -> None:
        """
        označí daný region v damage maske ako vyplnený
        """
        if self.damage_filled_mask is None:
            return

        if region_mask.shape != self.damage_filled_mask.shape:
            raise ValueError("region_mask must have same shape as damage mask")

        self.damage_filled_mask |= region_mask.astype(bool)

    def get_selection_from_click(self, x: int, y: int) -> Selection | None:
        """
        ak v bode (x, y) je pixel poškodený (true), spraví flood-fill a vráti Selection (region_mask + bbox)
        """
        if self.damage_original_mask is None:
            return None

        mask = self.damage_original_mask
        h, w = mask.shape

        if x < 0 or y < 0 or x >= w or y >= h:
            return None

        if not mask[y, x]:
            #klik mimo poškodenej oblasti
            return None

        edge_layers = self.get_edge_layers()
        region_map = build_region_map(mask, edge_layers)

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

    #---------zmeny hrán ---------
    def on_edge_layer_modified(self, edge_layer_id: str) -> None:
        """
        Zavolá sa po úprave EDGE vrstvy 
        -prepočíta RegionMap na damage_remaining_mask
        -porovná s predchádzajúcou verziou
        -podľa rozdielov vytvorí warningy
        """
        damage_rem = self.get_damage_remaining_mask()
        if damage_rem is None:
            return

        edge_layers = self.get_edge_layers()
        if not edge_layers:
            return

        new_map = build_region_map(damage_rem, edge_layers)

        #prvýkrát len nastavíme cache
        if self._cached_region_map is None:
            self._cached_region_map = new_map
            return

        old_map = self._cached_region_map
        changes = compare_region_maps(old_map, new_map)
        self._cached_region_map = new_map

        if not changes.changed_mask.any():
            return

        #zmena hrán zasahuje už vyplnené oblasti
        filled = self._compute_filled_mask_from_layers()
        if filled is not None:
            affected_mask = changes.changed_mask & filled
            if affected_mask.any():
                ys, xs = np.where(affected_mask)
                y_min = int(ys.min())
                y_max = int(ys.max())
                x_min = int(xs.min())
                x_max = int(xs.max())
                bbox = (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)

                region_refs: list[RegionReference] = []
                for layer in self.get_paint_layers():
                    region_refs.append(RegionReference(layer_id=layer.meta.id, bbox=bbox, region_id=None, seed_point=None))

                self.log_manager.add_warning(
                    warning_type=WarningType.EDGE_MODIFIED_TOUCHING_FILLS,
                    message="zmena hrán zasiahla už vyplnené oblasti",
                    details="Upravili ste hrany v blízkosti už vyplnených poškodených častí",
                    affected_regions=region_refs,
                )

        #zlúčené oblasti
        for old_ids, new_id, bbox in changes.merged_regions:
            region_refs: list[RegionReference] = []
            for layer in self.get_paint_layers():
                region_refs.append(RegionReference(layer_id=layer.meta.id, bbox=bbox, region_id=new_id, seed_point=None))

            self.log_manager.add_warning(
                warning_type=WarningType.EDGE_DELETED_REGIONS_MERGED,
                message="Úprava hrán zlúčila viac poškodených oblastí do jednej",
                details=f"Oblasti {sorted(old_ids)} boli zlúčené do oblasti {new_id}.",
                affected_regions=region_refs,
            )

    def _compute_filled_mask_from_layers(self) -> np.ndarray | None:
        """
        Vypočíta, ktoré pixely poškodenia sú aktuálne vyplnené
        podľa PAINT vrstiev (alfa > 0)
        """
        if self.damage_original_mask is None:
            return None

        h, w = self.damage_original_mask.shape
        filled_union = np.zeros((h, w), dtype=bool)

        for layer in self.get_paint_layers():
            if layer.image.shape[0] != h or layer.image.shape[1] != w:
                continue
            #preferujeme per-layer filled masku ak existuje
            layers_mask = getattr(layer, "damage_filled_mask", None)
            if layers_mask is not None:
                if layers_mask.shape != (h, w):
                    continue
                filled_union |= layers_mask.astype(bool)
                continue
            
            alpha_filled = (layer.image[..., 3] > 0) & self.damage_original_mask
            filled_union |= alpha_filled
        
        filled_union &= self.damage_original_mask
        return filled_union
    
    def sync_layer_filled_mask_from_alpha(self, layer_id: str, bbox: tuple[int,int,int,int] | None = None, mode: str = "or") -> None:
        """
        Synchronizuje layer.damage_filled_mask podľa alfa kanálu vrstvy (a len v damage_original_mask)
        -ak bbox je None, prepočíta celú masku
        """
        if self.damage_original_mask is None:
            return

        layer = next((l for l in self.layers if l.meta.id == layer_id), None)
        if layer is None or layer.meta.role != LayerRole.PAINT:
            return

        if layer.damage_filled_mask is None:
            layer.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

        h, w = self.damage_original_mask.shape
 
        if bbox is None:
            alpha_filled = (layer.image[..., 3] > 0) & self.damage_original_mask
            layer.damage_filled_mask[...] = alpha_filled
            return

        x, y, bw, bh = bbox
        if bw <= 0 or bh <= 0:
            return

        x0 = max(0, x); y0 = max(0, y)
        x1 = min(w, x + bw); y1 = min(h, y + bh)
        if x1 <= x0 or y1 <= y0:
            return

        alpha_sub = (layer.image[y0:y1, x0:x1, 3] > 0)
        dmg_sub = self.damage_original_mask[y0:y1, x0:x1]
        filled_sub = alpha_sub & dmg_sub

        if mode == "assign":
            layer.damage_filled_mask[y0:y1, x0:x1] = filled_sub
        else:
            layer.damage_filled_mask[y0:y1, x0:x1] |= filled_sub

    #---------metódy pre externé algoritmy---------
    def get_original_image(self) -> np.ndarray | None:
        """
        Vráti pôvodný obraz – zatiaľ berieme ako background vrstvu
        """
        if self.base_image_path is not None and self.base_image_scale == 1.0:
            #bezpečné načítanie full-res -pre report
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
        """
        Vráti aktuálny zložený obraz (background + paint vrstvy)
        """
        return self.composited_image()

    #---------farby, paleta---------

    def get_current_color_rgba(self) -> tuple[int, int, int, int]:
        return self.current_color_rgba

    def set_current_color_rgba(self, color: tuple[int, int, int, int]) -> None:
        r, g, b, a = [int(max(0, min(255, c))) for c in color]
        self.current_color_rgba = (r, g, b, a)

    def add_palette_color(self, color: tuple[int, int, int, int]) -> None:
        """
        Pridá farbu do palety (ak tam ešte nie je)
        """
        r, g, b, a = [int(max(0, min(255, c))) for c in color]
        rgba = (r, g, b, a)
        if rgba not in self.palette_colors:
            self.palette_colors.append(rgba)

    def get_palette_colors(self) -> list[tuple[int, int, int, int]]:
        return list(self.palette_colors)

    def clear_palette(self) -> None:
        self.palette_colors.clear()

    #--------export--------
    def get_export_image(self) -> np.ndarray:
        """
        vráti exportovateľný finálny náhľad (working resolution)
        """
        return self.composited_image()
