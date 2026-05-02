from __future__ import annotations

from typing import Optional, Callable
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog
from PySide6.QtCore import Qt, QTimer

from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.config.settings import AppSettings
from rp_restore.core.selection import Selection, SelectionSet
from rp_restore.core.warnings import UserWarning
from rp_restore.core.algorithm_runner import AlgorithmType, AlgorithmRequest, AlgorithmRunner
from rp_restore.core.history import UndoAction
from rp_restore.core.texture_brush import TextureSettings, Texture
from rp_restore.core import mask_alignment
from rp_restore.core.auto_fill import auto_fill_regions, AutoFillRegion
from rp_restore.core.regions import RegionMap, build_region_map
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget
from rp_restore.gui.panels.layers_panel import LayersPanel
from rp_restore.gui.panels.log_panel import LogPanel
from rp_restore.gui.tools.base_tool import BaseTool
from rp_restore.gui.tools.brush_tool import BrushTool
from rp_restore.gui.tools.eraser_tool import EraserTool
from rp_restore.gui.tools.fill_tool import FillTool
from rp_restore.gui.tools.selection_tool import SelectionTool
from rp_restore.gui.tools.edge_tool import EdgeTool
from rp_restore.gui.tools.pipette_tool import PipetteTool
from rp_restore.gui.tools.lasso_tool import LassoTool
from rp_restore.gui.mask_alignment_dialog import MaskAlignmentDialog
from rp_restore.io import image_io
from rp_restore.io.image_io import load_working_image
from rp_restore.io.project_storage import ProjectLoader, ProjectSerializer

class ProjectController:
    """
    riadi Project a GUI (canvas, panely)
    zatiaľ:
      - drží aktuálny Project
      - a vie obnoviť canvas podľa projektu
    """

    def __init__(self, app_settings: AppSettings) -> None:
        self.app_settings = app_settings
        self.project: Optional[Project] = None

        self.canvas: Optional[ImageCanvasWidget] = None
        self._brush_size: int = 10

        self.selection_region_map_cache: RegionMap | None = None
        self.selection_region_map_cache_layer_id: str | None = None

        self.materials_panel = None
        self.palette_panel = None
        
        self.edge_settings_panel: Optional[object] = None
        self._edge_brush_size: int = 2
        self._edge_color_rgba: np.ndarray = np.array([0, 0, 0, 255], dtype=np.uint8)
        #neskôr pribudnú ďalšie ako layers_panel, log_panel, tools_panel...
        self.active_layer_id: Optional[str] = None
        self.layers_panel: Optional[LayersPanel] = None
        self.log_panel: Optional[LogPanel] = None
        self.current_tool: Optional[BaseTool] = None
        self.active_selection: SelectionSet | None = None
        self.auto_fill_preview_active: bool = False
        self.auto_fill_threshold: int = 200
        self.auto_fill_region_map: RegionMap | None = None
        self.auto_fill_candidate_region_ids: set[int] = set()
        self.auto_fill_excluded_region_ids: set[int] = set()
        self.auto_fill_preview_layer_id: str | None = None
        #vizualizácia damage masky v canvase
        self.show_damage_overlay: bool = True
        self.algorithm_panel = None
        self.palette_panel = None

        self.current_project_path: Optional[str] = None

        self._undo_redo_changed_callback: Optional[Callable[[], None]] = None

        self._message_callback: Optional[Callable[[str], None]] = None
        
        self._brush_size_preview_callback: Optional[Callable[[int], None]] = None

        #debounce pre opacity refresh (aby compositing nebežal pri každom ticku slidera)
        self._opacity_debounce_timer: QTimer = QTimer()
        self._opacity_debounce_timer.setSingleShot(True)
        self._opacity_debounce_timer.timeout.connect(self._apply_opacity_debounced_refresh)

        self.texture_settings = TextureSettings(texture=None, scale=1.0, color=(255, 255, 255), strength=1.0, texture_style="transparent")
        self.texture_mode_enabled: bool = False

        self.paint_mode: str = "brush"

    def set_canvas(self, canvas: ImageCanvasWidget) -> None:
        self.canvas = canvas

    def set_project(self, project: Project) -> None:
        """nastaví aktuálny Project a refreshne GUI"""
        self.project = project
        self.project.undo_manager.on_change = self._on_undo_manager_changed
        self.invalidate_selection_region_map_cache()
        self.clear_auto_fill_preview()

        self.texture_settings.texture_style = getattr(project, "texture_style", "transparent")

        self.reset_tools_to_default()
        
        #default aktívna vrstva bude preferovaná BACKGROUND, inak prvú vrstvu v zozname
        self.active_layer_id = None
        if self.project.layers:
            bg = self.project.get_background_layer()
            if bg is not None:
                self.active_layer_id = bg.meta.id
            else:
                self.active_layer_id = self.project.layers[0].meta.id
        self.refresh_canvas()

        if self.canvas is not None:
            self.canvas.fit_to_window()

        self.refresh_layers_panel()
        self.refresh_log_panel()
        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(project)
        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(project)
        if self.edge_settings_panel is not None and hasattr(self.edge_settings_panel, "refresh_from_controller"):
            self.edge_settings_panel.refresh_from_controller(self)
        #neskôr refreshne všetko (refresh_layers_panel(), refresh_log_panel()...)
    
    def set_texture(self, texture_name: str | None) -> None:
        if self.project is None:
            self.texture_settings.texture = None
            return
        if texture_name is None:
            self.texture_settings.texture = None
            return
        tex = self.project.textures.get(texture_name)
        self.texture_settings.texture = tex

    def set_texture_scale(self, scale: float) -> None:
        self.texture_settings.scale = float(scale)

    def set_texture_color(self, rgb: tuple[int,int,int]) -> None:
        self.texture_settings.color = rgb

    def set_texture_strength(self, strength: float) -> None:
        self.texture_settings.strength = float(strength)

    def set_texture_style(self, style: str) -> None:
        """
        Nastaví spôsob generovania textúry:
            - transparent - pôvodná priesvitná textúra
            - color - farebná textúra s odtieňmi
        """
        if style not in ("transparent", "color"):
            style = "transparent"

        self.texture_settings.texture_style = style

        if self.project is not None:
            self.project.texture_style = style
            self.project.mark_dirty()

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    def _load_default_textures_into_project(self, project: Project, max_tex_size: int = 512) -> None:
        """
        Načíta default textúry z rp_restore/resources/textures do project.textures
        """
        rp_restore_dir = Path(__file__).resolve().parents[1]
        tex_dir = rp_restore_dir / "resources" / "textures"
        if not tex_dir.is_dir():
            return

        project.textures = {}

        exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        for p in sorted(tex_dir.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue

            try:
                #načítame ako working (zmenšenie na max_tex_size)
                arr, _ = load_working_image(str(p), max_size=max_tex_size)
                #chceme RGBA alebo aspoň RGB
                if arr.ndim == 3 and arr.shape[2] == 3:
                    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
                    rgba[..., :3] = arr
                    rgba[..., 3] = 255
                    arr = rgba
                elif arr.ndim == 2:
                    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
                    rgba[..., 0] = arr
                    rgba[..., 1] = arr
                    rgba[..., 2] = arr
                    rgba[..., 3] = 255
                    arr = rgba

                name = p.stem
                project.textures[name] = Texture(name=name, image=arr)
            except Exception:
                #textúra sa nepodarila načítať, preskočíme
                continue
    
    def add_texture_from_file_via_dialog(self, parent=None) -> None:
        """
        Otvorí dialóg a pridá vybraný obrázok ako textúru iba do aktuálneho projektu
        """
        if self.project is None:
            return

        path, _ = QFileDialog.getOpenFileName(
            parent,
            "Přidat texturu",
            "",
            "Obrázky (*.png *.jpg *.jpeg *.tif *.tiff);;Všechny soubory (*.*)",
        )
        if not path:
            return

        try:
            self.add_texture_from_file(path)
        except Exception as e:
            self.show_tool_message(f"Texturu se nepodařilo přidat: {e}")

    def add_texture_from_file(self, path: str, max_tex_size: int = 512) -> None:
        """
        Pridá textúru do aktuálneho projektu
        (nekopíruje ju do default resources, iba do project.textures)
        """
        if self.project is None:
            return

        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(str(p))

        arr, _ = load_working_image(str(p), max_size=max_tex_size)

        # normalizácia na RGBA
        if arr.ndim == 2:
            rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
            rgba[..., 0] = arr
            rgba[..., 1] = arr
            rgba[..., 2] = arr
            rgba[..., 3] = 255
            arr = rgba
        elif arr.ndim == 3 and arr.shape[2] == 3:
            rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
            rgba[..., :3] = arr
            rgba[..., 3] = 255
            arr = rgba
        elif arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr.astype(np.uint8)
        else:
            raise ValueError("Unsupported texture image format")

        base_name = p.stem or "texture"
        name = self._make_unique_texture_name(base_name)

        tex = Texture(name=name, image=arr)
        self.project.textures[name] = tex

        #hneď ju vyberieme ako aktuálnu textúru
        self.texture_settings.texture = tex

        self.project.mark_dirty()

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    def _make_unique_texture_name(self, base_name: str) -> str:
        """
        Vytvorí jedinečný názov textúry v aktuálnom projekte
        """
        if self.project is None:
            return base_name

        existing = set(getattr(self.project, "textures", {}).keys())

        safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in base_name).strip("_")
        if not safe:
            safe = "texture"

        if safe not in existing:
            return safe

        i = 2
        while f"{safe}_{i}" in existing:
            i += 1
        return f"{safe}_{i}"
    
    def set_materials_panel(self, panel: object) -> None:
        self.materials_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)
    
    def set_edge_settings_panel(self, panel: object) -> None:
        """
        Prepojí controller s EdgeSettingsPanelom
        """
        self.edge_settings_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)

    def set_palette_panel(self, panel: object) -> None:
        self.palette_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)

    def get_current_color_rgba(self) -> np.ndarray:
        """
        vráti aktuálnu farbu ako numpy RGBA 
        """
        if self.project is None:
            return np.array([0, 0, 0, 255], dtype=np.uint8)
        r, g, b, a = self.project.get_current_color_rgba()
        return np.array([r, g, b, a], dtype=np.uint8)

    def set_current_color_rgba(self, color: tuple[int, int, int, int]) -> None:
        if self.project is None:
            return
        self.project.set_current_color_rgba(color)
        if hasattr(self, "texture_settings"):
            r, g, b, a = self.project.get_current_color_rgba()
            self.texture_settings.color = (r, g, b)

        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(self.project)
        #refresh panel
        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    def add_current_color_to_palette(self) -> None:
        if self.project is None:
            return
        self.project.add_palette_color(self.project.get_current_color_rgba())
        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(self.project)

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)
   
    def add_color_to_palette_rgba(self, color: tuple[int, int, int, int], avoid_duplicates: bool = True) -> None:
        """
        Pridá ľubovoľnú farbu do palety
        """
        if self.project is None:
            return

        if avoid_duplicates:
            if color in self.project.get_palette_colors():
                return

        self.project.add_palette_color(color)

        #refresh ColorPanel
        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(self.project)

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    def remove_color_from_palette(self, index: int) -> None:
        """
        Odstráni farbu z palety podľa indexu
        """
        if self.project is None:
            return

        palette = self.project.get_palette_colors()
        if index < 0 or index >= len(palette):
            return

        #priamo upravíme zoznam
        self.project.palette_colors.pop(index)

        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(self.project)

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    #-Edge -hrúbka a farba
    def get_edge_brush_size(self) -> int:
        return int(self._edge_brush_size)

    def set_edge_brush_size(self, size: int) -> None:
        self._edge_brush_size = max(1, int(size))
        if self.edge_settings_panel is not None and hasattr(self.edge_settings_panel, "refresh_from_controller"):
            self.edge_settings_panel.refresh_from_controller(self)

    def get_edge_color_rgba(self) -> np.ndarray:
        return self._edge_color_rgba.copy()

    def set_edge_color_rgba(self, color: tuple[int, int, int, int]) -> None:
        arr = np.array(color, dtype=np.int32)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        self._edge_color_rgba = arr
        if self.edge_settings_panel is not None and hasattr(self.edge_settings_panel, "refresh_from_controller"):
            self.edge_settings_panel.refresh_from_controller(self)

    def get_brush_size(self) -> int:
        return int(self._brush_size)

    def set_brush_size(self, size: int) -> None:
        self._brush_size = max(1, int(size))
    
        if self.materials_panel is not None and hasattr(self.materials_panel, "set_brush_size_value"):
            self.materials_panel.set_brush_size_value(self._brush_size)

        if self._brush_size_preview_callback is not None:
            self._brush_size_preview_callback(self._brush_size)

    def adjust_brush_size(self, delta: int) -> None:
        """
        zväčší/zmenší brush size o delta
        """
        self.set_brush_size(self._brush_size + int(delta))

    def set_layers_panel(self, panel: LayersPanel) -> None:
        """prepojí controller s panelom vrstiev"""
        self.layers_panel = panel
        panel.set_controller(self)

    def set_current_tool(self, tool_type: str) -> None:
        """
        nastaví aktuálny nástroj podľa typu (brush, eraser, ...)
        """
        if self.canvas is None:
            return
        self.clear_auto_fill_preview()
        self._auto_switch_active_layer_for_tool(tool_type)
        if tool_type == "brush":
            self.current_tool = BrushTool(self, self.canvas)
        elif tool_type == "eraser":
            self.current_tool = EraserTool(self, self.canvas)
        elif tool_type == "fill":
            self.current_tool = FillTool(self, self.canvas)
        elif tool_type == "selection":
            self.current_tool = SelectionTool(self, self.canvas)
        elif tool_type == "edge":
            self.current_tool = EdgeTool(self, self.canvas)
        elif tool_type == "pipette":
            self.current_tool = PipetteTool(self, self.canvas)
        elif tool_type == "lasso":
            self.current_tool = LassoTool(self, self.canvas)
        else:
            self.current_tool = None

    def reset_tools_to_default(self) -> None:
        """
        Reset nástrojov pri otvorení/zmene projektu:
        - zruší selection
        - nastaví default tool = brush
        """
        self.active_selection = None
        self.set_current_tool("brush")

    def set_active_selection(self, selection) -> None:
        """
        nastaví aktuálnu selection
        zatiaľ len uložíme do atribútu, neskôr pridáme highlight na canvase a info AlgorithmPanelu
        """
        self.active_selection = selection
        if self.active_selection is not None and not self.active_selection.is_empty():
            self.clear_auto_fill_preview()

    def has_active_selection(self) -> bool:
        """
        True ak existuje neprázdny výber oblastí
        """
        return self.active_selection is not None and not self.active_selection.is_empty()

    def clear_active_selection(self) -> None:
        """
        Zruší aktuálny výber oblastí
        """
        self.active_selection = None

    def set_selection(self, selection_set: SelectionSet | None) -> None:
        """
        Nastaví aktuálny multi-selection (SelectionSet) a refreshne canvas + AlgorithmPanel
        """
        self.active_selection = selection_set

        #informujeme AlgorithmPanel
        if self.algorithm_panel is not None and hasattr(self.algorithm_panel, "refresh_from_selection"):
            self.algorithm_panel.refresh_from_selection(selection_set)

        #refresh canvas
        self.refresh_canvas()

    def clear_selection(self) -> None:
        self.set_selection(None)

    def set_show_damage_overlay(self, show: bool) -> None:
        """
        Zapne / vypne vizualizáciu damage_remaining_mask na canvase
        """
        self.show_damage_overlay = show
        self.refresh_canvas()

    def set_log_panel(self, panel: LogPanel) -> None:
        self.log_panel = panel
        panel.set_controller(self)
    
    def set_algorithm_panel(self, panel: object) -> None:
        """
        Prepojí controller s AlgorithmPanelom
        """
        self.algorithm_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)

    def set_undo_redo_changed_callback(self, callback: Callable[[], None]) -> None:
        self._undo_redo_changed_callback = callback

    def set_message_callback(self, callback: Callable[[str], None]) -> None:
        """
        nastaví callback na zobrazovanie krátkych hlášok pre užívateľa
        (tool warnings a pod.)
        """
        self._message_callback = callback

    def set_brush_size_preview_callback(self, callback: Callable[[int], None]) -> None:
        """
        nastaví callback pre zobrazenie náhľadu veľkosti brush
        """
        self._brush_size_preview_callback = callback

    def show_tool_message(self, text: str) -> None:
        """
        zobrazí krátku hlášku o používaní nástrojov
        """
        if self._message_callback is not None:
            self._message_callback(text)
        else:
            print(text)

    #refresh metódy

    def _get_damage_overlay_mask_for_view(self) -> np.ndarray | None:
        """
        Vráti masku, ktorú chceme zobrazovať ako overlay
        - globálne remaining
        """
        if self.project is None:
            return None
        return self.project.get_damage_remaining_mask()
    
    def _auto_switch_active_layer_for_tool(self, tool_type: str) -> None:
        """
        Automaticky prepne aktívnu vrstvu podľa nástroja 
        - edge ->EDGE vrstva
        - brush ->prvá PAINT vrstva
        """
        if self.project is None:
            return

        def find_first(role: LayerRole) -> str | None:
            for layer in self.project.layers:
                if layer.meta.role == role:
                    return layer.meta.id
            return None

        #edge tool -> EDGE vrstva
        if tool_type == "edge":
            edge_id = find_first(LayerRole.EDGE)
            if edge_id is not None:
                self.set_active_layer(edge_id)

        #brush tool -> PAINT vrstva 
        if tool_type == "brush":
            if self.active_layer_id is not None:
                active = self.get_layer_by_id(self.active_layer_id)
                if active is not None and active.meta.role == LayerRole.PAINT:
                    return
            paint_id = find_first(LayerRole.PAINT)
            if paint_id is not None:
                self.set_active_layer(paint_id)

    def refresh_canvas(self) -> None:
        if self.project is None or self.canvas is None:
            return

        #numpy (H, W, 3, uint8)
        image_rgb = self.project.composited_image()

        #overlay poškodených oblastí (damage_remaining_mask)
        if self.show_damage_overlay:
            remaining = self._get_damage_overlay_mask_for_view()
            if remaining is not None:
                h_img, w_img, _ = image_rgb.shape
                h_mask, w_mask = remaining.shape

                #len ak sedí veľkosť – aby to nespadlo, keby maska bola zlá
                if h_mask == h_img and w_mask == w_img:
                    #vybielený náhľad poškodených oblastí
                    overlay_color = np.array([255, 255, 255], dtype=np.float32)
                    alpha = 0.6  # 0 = nič, 1 = úplne biele

                    region = remaining
                    orig = image_rgb[region].astype(np.float32)
                    blended = orig * (1.0 - alpha) + overlay_color * alpha
                    image_rgb[region] = blended.clip(0, 255).astype(np.uint8)
                #inak overlay ignorujeme -maska nesedí
        qimage = self._numpy_rgb_to_qimage(image_rgb)
        self.canvas.set_image(qimage)
        #selection overlay
        if self.active_selection is not None and not self.active_selection.is_empty():
            try:
                sel_mask = self.active_selection.combined_mask()
            except ValueError:
                sel_mask = None
        else:
            sel_mask = None
        self.canvas.set_selection_mask(sel_mask)

    def refresh_canvas_region(self, bbox: tuple[int, int, int, int]) -> None:
        """
        rýchla verzia refreshu -len v oblasti bbox = (x, y, w, h), a ten patchuje do existujúceho QImage v canvase
        """
        if self.project is None or self.canvas is None:
            return

        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return

        #composited patch z core
        region_rgb = self.project.composited_region(bbox)
        #damage overlay len pre túto oblasť
        if self.show_damage_overlay:
            remaining = self._get_damage_overlay_mask_for_view()
            if remaining is not None:
                y0, x0 = y, x
                y1, x1 = y + h, x + w

                Hmask, Wmask = remaining.shape
                #orezať do hraníc masky
                y0c = max(0, min(y0, Hmask))
                y1c = max(0, min(y1, Hmask))
                x0c = max(0, min(x0, Wmask))
                x1c = max(0, min(x1, Wmask))

                if y1c > y0c and x1c > x0c:
                    sub_mask = remaining[y0c:y1c, x0c:x1c]
                    h_sub, w_sub = sub_mask.shape
                    h_img, w_img, _ = region_rgb.shape

                    if h_sub == h_img and w_sub == w_img:
                        overlay_color = np.array([255, 255, 255], dtype=np.float32)
                        alpha = 0.6

                        region = sub_mask
                        orig = region_rgb[region].astype(np.float32)
                        blended = orig * (1.0 - alpha) + overlay_color * alpha
                        region_rgb[region] = blended.clip(0, 255).astype(np.uint8)

        #konverzia patchu na QImage
        patch_qimage = self._numpy_rgb_to_qimage(region_rgb)
        #patch do canvasu
        self.canvas.patch_region(patch_qimage, x, y)

    def set_active_layer(self, layer_id: str) -> None:
        """
        nastaví aktívnu vrstvu podľa jej id
        zatiaľ len uloží ID a refreshne LayersPanel
        -neskôr o tom budú vedieť aj nástroje (brush, fill, ...)
        """
        if self.project is None:
            return

        if self.active_layer_id == layer_id:
            return

        #overíme, či vrstva s takým ID existuje
        if not any(layer.meta.id == layer_id for layer in self.project.layers):
            return

        self.active_layer_id = layer_id
        self.refresh_layers_panel()
        self.clear_auto_fill_preview()
        self.update_layer_preview()
        self.invalidate_selection_region_map_cache()
        #neskôr informujeme nástroje

    def add_paint_layer(self) -> None:
        """
        Vytvorí novú prázdnu PAINT vrstvu nad existujúcimi vrstvami
        a nastaví ju ako aktívnu
        """
        if self.project is None:
            return

        bg = self.project.get_background_layer()
        if bg is None:
            return

        h, w, c = bg.image.shape
        new_image = np.zeros((h, w, c), dtype=np.uint8)

        #index novej paint vrstvy
        paint_count = sum(1 for layer in self.project.layers if layer.meta.role == LayerRole.PAINT)
        index = paint_count + 1

        layer_id = f"paint_{index}"
        meta = LayerMeta(id=layer_id, name=f"Paint {index}", role=LayerRole.PAINT)
        new_layer = Layer(meta, new_image)

        self.project.add_layer(new_layer)
        self.active_layer_id = layer_id

        self.refresh_layers_panel()
        self.refresh_canvas()
    
    def get_layer_by_id(self, layer_id: str) -> Layer | None:
        if self.project is None:
            return None
        for layer in self.project.layers:
            if layer.meta.id == layer_id:
                return layer
        return None
    
    def on_layer_visibility_changed(self, layer_id: str, visible: bool) -> None:
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return

        layer.meta.visible = bool(visible)
        self.refresh_canvas()
        self.refresh_layers_panel()
        self.project.mark_dirty()

    def on_layer_delete_requested(self, layer_id: str) -> bool:
        """
        Zmaže paint vrstvu
        -vráti True, ak sa podarilo
        """
        if self.project is None:
            return False

        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return False

        if layer.meta.role != LayerRole.PAINT:
            self.show_tool_message("This layer can't be deleted")
            return False

        try:
            self.project.remove_layer(layer_id)
            self.project.mark_dirty()
        except Exception as e:
            self.show_tool_message(str(e))
            return False

        #ak sme zmazali aktívnu vrstvu, nastavíme inú aktívnu
        if self.active_layer_id == layer_id:
            #preferujme prvú PAINT, inak background
            paint_layers = self.project.get_paint_layers()
            if paint_layers:
                self.active_layer_id = paint_layers[-1].meta.id
            else:
                bg = self.project.get_background_layer()
                self.active_layer_id = bg.meta.id if bg else None

        self.refresh_layers_panel()
        self.refresh_canvas()
        return True

    def on_layer_opacity_changed(self, layer_id: str, opacity: float) -> None:
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return

        layer.meta.opacity = float(max(0.0, min(1.0, opacity)))
        self._opacity_debounce_timer.start(80)
        self.project.mark_dirty()

    def _apply_opacity_debounced_refresh(self) -> None:
        """
        Zavolá sa po debounce timeout
        """
        self.refresh_canvas()

    def rename_layer(self, layer_id: str, new_name: str) -> None:
        """
        Premenuje vrstvu s daným id
        """
        if self.project is None:
            return

        for layer in self.project.layers:
            if layer.meta.id == layer_id:
                layer.meta.name = new_name
                break

        self.refresh_layers_panel()


    def refresh_layers_panel(self) -> None:
        if self.project is None or self.layers_panel is None:
            return

        self.layers_panel.refresh_from_project(self.project, self.active_layer_id)
        self.update_layer_preview()

    def update_layer_preview(self) -> None:
        if self.project is None or self.layers_panel is None:
            return

        if self.active_layer_id is None:
            if hasattr(self.layers_panel, "set_preview"):
                self.layers_panel.set_preview(None)
            return

        layer = self.get_layer_by_id(self.active_layer_id)
        if layer is None:
            if hasattr(self.layers_panel, "set_preview"):
                self.layers_panel.set_preview(None)
            return

        #RGBA -> RGB cez alfa blending na tmavé pozadie
        rgba = layer.image.astype(np.float32)
        rgb = rgba[..., :3]
        alpha = rgba[..., 3:4] / 255.0
        bg = np.zeros_like(rgb) + 30.0  #tmavé pozadie
        out = rgb * alpha + bg * (1.0 - alpha)
        out = np.clip(out, 0, 255).astype(np.uint8)

        qimg = self._numpy_rgb_to_qimage(out)

        if hasattr(self.layers_panel, "set_preview"):
            #zmenší sa už v LayersPanel.set_preview, takže tu netreba
            self.layers_panel.set_preview(qimg)

    def refresh_log_panel(self) -> None:
        if self.project is None or self.log_panel is None:
            return
        self.log_panel.refresh_from_project(self.project)

    def on_canvas_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifier) -> None:
        if buttons & Qt.LeftButton:
            handled = self.toggle_auto_fill_candidate_at(img_x, img_y)
            if handled:
                return
        if self.current_tool is None:
            return
        self.current_tool.on_mouse_press(img_x, img_y, buttons, modifiers)

    def on_canvas_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if self.current_tool is None:
            return
        self.current_tool.on_mouse_move(img_x, img_y, buttons, modifiers)

    def on_canvas_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if self.current_tool is None:
            return
        self.current_tool.on_mouse_release(img_x, img_y, buttons, modifiers)

    def _numpy_rgb_to_qimage(self, arr: np.ndarray) -> QImage:
        """
        konverzia numpy RGB (H, W, 3, uint8) na QImage RGB
        .copy(), aby QImage mal vlastnú kópiu dát 
        """
        if arr.dtype != np.uint8 or arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError("Expected RGB image of shape (H, W, 3) with dtype=uint8")

        h, w, ch = arr.shape
        bytes_per_line = ch * w
        qimage = QImage(arr.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return qimage.copy()
    
    #load /save projektu
    def create_project_from_files(self, image_path: str, mask_path: Optional[str] = None) -> Project:
        """
        Vytvorí nový Project zo zadaného obrázka (a voliteľne damage masky)
        """
        
        working_arr, scale = load_working_image(image_path, max_size=4000)

        bg_meta = LayerMeta(id="background", name="Background", role=LayerRole.BACKGROUND)
        bg_layer = Layer(bg_meta, working_arr.copy())

        paint_img = np.zeros_like(working_arr, dtype=np.uint8)
        paint_meta = LayerMeta(id="paint_1", name="Paint 1", role=LayerRole.PAINT)
        paint_layer = Layer(paint_meta, paint_img)

        edge_img = np.zeros_like(working_arr, dtype=np.uint8)
        edge_meta = LayerMeta(id="edge_1", name="Edges 1", role=LayerRole.EDGE)
        edge_layer = Layer(edge_meta, edge_img)

        project_name = Path(image_path).stem
        project = Project(project_name)

        self._load_default_textures_into_project(project)

        project.base_image_path = Path(image_path)
        project.base_image_scale = scale
        project.base_image_working = working_arr    

        project.add_layer(bg_layer)
        project.add_layer(paint_layer)
        project.add_layer(edge_layer)

        h_img, w_img, _ = working_arr.shape
        if mask_path:
            mask_preview_arr, _ = load_working_image(mask_path, max_size=4000)

            #otvoríme dialóg na zarovnanie
            parent = QApplication.activeWindow()
            dlg = MaskAlignmentDialog(working_arr, mask_preview_arr, parent=parent)
            result = dlg.exec()

            if result != QDialog.Accepted:
                raise RuntimeError("Mask alignment was cancelled by the user")
            
            image_points, mask_points = dlg.get_points()
            H = mask_alignment.compute_homography(src_points=mask_points, dst_points=image_points)
            wrapped_mask_rgb = mask_alignment.warp_mask_to_image(mask_rgb=mask_preview_arr, H=H, target_size=(w_img, h_img))

            damage_mask = mask_alignment.rgb_to_damage_mask(wrapped_mask_rgb)
            project.set_damage_masks(damage_mask)

        self.set_project(project)
        self.current_project_path = None
        return project

    def open_project(self, zip_path: str) -> Project:
        """
        Načíta projekt zo .zip súboru a nastaví ho ako aktuálny
        """
        project = ProjectLoader.load_from_zip(zip_path)
        self.set_project(project)
        self.current_project_path = zip_path
        self.app_settings.add_recent_project(zip_path)
        return project

    def save_project_as(self, zip_path: str) -> None:
        """
        Uloží projekt do nového .zip súboru a aktualizuje current_project_path
        """
        if self.project is None:
            return

        ProjectSerializer.save_to_zip(self.project, zip_path)
        self.current_project_path = zip_path
        self.app_settings.add_recent_project(zip_path)
        self.project.mark_saved()

    def save_project(self) -> bool:
        """
        Uloží projekt na aktuálnu cestu

        vráti True, ak sa uložil, False ak nemá nastavenú cestu
        """
        if self.project is None:
            return False

        if not self.current_project_path:
            return False

        ProjectSerializer.save_to_zip(self.project, self.current_project_path)
        self.app_settings.add_recent_project(self.current_project_path)
        self.project.mark_saved()
        return True
    
    def has_open_project(self) -> bool:
        return self.project is not None

    def is_project_dirty(self) -> bool:
        return self.project is not None and bool(getattr(self.project, "is_dirty", False))

    def save_project_with_dialog_if_needed(self) -> bool:
        """
        Ak projekt nemá path -> vyžiada Save As dialóg (cez QFileDialog)
        -inak spraví Save
        -vráti True ak úspech, False ak zrušené alebo chyba
        """
        if self.project is None:
            return False

        #ak nemáme path, tak Save As dialog
        if not self.current_project_path:
            parent = QApplication.activeWindow()
            zip_path, _ = QFileDialog.getSaveFileName(
                parent,
                "Uložiť projekt ako",
                "",
                "RP projekty (*.zip);;Všetky súbory (*.*)",
            )
            if not zip_path:
                return False

            if not zip_path.lower().endswith(".zip"):
                zip_path += ".zip"

            try:
                self.save_project_as(zip_path)
            except Exception as e:
                self.show_tool_message(f"Chyba pri ukladaní: {e}")
                return False

            #po úspechu mark_saved
            self.project.mark_saved()
            return True

        #inak obyčajný save
        ok = self.save_project()
        if ok:
            self.project.mark_saved()
        return ok

    def close_project(self) -> None:
        """
        Zavrie aktuálny projekt v controlleri

        - zabudne referenciu na Project
        - zruší aktívnu vrstvu, selection, nástroj
        -vyčistí canvas (obraz)
        """
        self.project = None
        self.active_layer_id = None
        self.active_selection = None
        self.current_tool = None
        self.current_project_path = None

        if self._undo_redo_changed_callback is not None:
            self._undo_redo_changed_callback()

    def run_auto_fill_small_regions(self, area_threshold: int = 200) -> int:
        """
        spustí auto-fill malých oblastí na aktívnej PAINT vrstve
        (alebo na prvej paint vrstve, ak aktívna nie je paint)

        vráti počet vyplnených oblastí
        """
        if self.project is None:
            return 0

        #cieľová vrstva – preferujeme aktívnu, ak je PAINT
        target_layer = self.get_active_paint_layer_for_autofill()
        if target_layer is None:
            return 0
        
        mode = self.get_auto_fill_mode()

        regions_to_fill: list[AutoFillRegion] = []
        region_map = None

        if mode == "selection":
            damage_rem = self.project.get_layer_damage_remaining_mask(target_layer.meta.id)
            if damage_rem is None:
                return 0
            edge_layers = self.project.get_edge_layers()
            region_map = build_region_map(damage_rem, edge_layers)
            regions_to_fill = self._build_autofill_regions_from_selection()
        elif mode == "preview":
            if self.auto_fill_region_map is None:
                return 0
            region_map = self.auto_fill_region_map
            regions_to_fill = self._build_autofill_regions_from_preview()
        else: 
            return 0

        if not regions_to_fill or region_map is None:
            return 0
        count = auto_fill_regions(self.project, target_layer, region_map, regions_to_fill)

        if count > 0:
            self.invalidate_selection_region_map_cache()
            if mode == "selection":
                self.clear_active_selection()
            else:
                self.clear_auto_fill_preview()
            self.refresh_canvas()

        return count
    
    def run_algorithm_on_selection(self, algorithm_type: AlgorithmType, use_mock: bool = False) -> None:
        """
        Spustí externý algoritmus na aktuálnej selection
        - pripraví AlgorithmRequest, zavolá AlgorithmRunner.run
        - výsledný patch vloží do aktívnej (alebo prvej) PAINT vrstvy
        - pridá UndoAction a označí oblasť v damage maske ako vyplnenú
        """
        project = self.project
        if project is None or self.active_selection is None:
            return

        selection_set = self.active_selection

        original = project.get_original_image()
        current = project.get_current_composited_image()
        damage_rem = project.get_damage_remaining_mask()

        if original is None or damage_rem is None:
            return

        #zabezpečíme tvar masiek
        selected_mask = selection_set.combined_mask()
        remaining_mask = damage_rem.astype(bool)

        #device – zatiaľ natvrdo cpu, neskôr z konfigurácie
        device = "cpu"

        request = AlgorithmRequest(original_image=original, current_image=current, selected_mask=selected_mask, remaining_mask=remaining_mask, algorithm_type=algorithm_type, device=device, mock=use_mock)

        try:
            result = AlgorithmRunner.run(request)
        except Exception as e:
            #zatia+ to aspoň vypíšeme do konzoly
            print("Algorithm error:", e)
            self.show_tool_message(f"Algorithm error: {e}")
            return

        #nájdeme cieľovú PAINT vrstvu
        target_layer: Layer | None = None

        if self.active_layer_id is not None:
            for layer in project.layers:
                if layer.meta.id == self.active_layer_id and layer.meta.role == LayerRole.PAINT:
                    target_layer = layer
                    break

        if target_layer is None:
            for layer in project.layers:
                if layer.meta.role == LayerRole.PAINT:
                    target_layer = layer
                    break

        if target_layer is None:
            return

        x, y, w, h = result.bbox
        local_sel = selected_mask[y:y+h, x:x+w]
        patch = result.output_patch

        #zarovnanie patch na RGBA
        if patch.ndim != 3:
            return
        if patch.shape[2] == 3:
            patch_rgba = np.zeros((h, w, 4), dtype=np.uint8)
            patch_rgba[..., :3] = patch
            patch_rgba[..., 3] = 255
        else:
            patch_rgba = patch

        #before
        before = target_layer.clone_subregion(x, y, w, h)

        #vložíme patch do vrstvy
        sub_img = target_layer.image[y : y + h, x : x + w, :]
        sub_img[local_sel] = patch_rgba[local_sel]

        #after
        after = target_layer.clone_subregion(x, y, w, h)

        action = UndoAction(description=f"Algorithm {algorithm_type.value} fill", layer_id=target_layer.meta.id, layer_role=target_layer.meta.role, bbox=(x, y, w, h), before=before, after=after)

        project.undo_manager.push_action(action)

        #označíme selection ako vyplnenú v damage maske
        project.mark_region_as_filled_on_layer(target_layer.meta.id, selected_mask)

        #pridáme info do history_for_report
        project.history_for_report.append(
            {
                "type": "algorithm_fill",
                "algorithm": algorithm_type.value,
                "bbox": (x, y, w, h),
                "log": result.log_messages,
            }
        )

        self.refresh_canvas()


    def focus_warning(self, warning_id: int) -> None:
        """
        Reaguje na klik na warning v LogPaneli
        - nastaví aktívnu vrstvu podľa prvého RegionReference a nastaví highlight v canvase
        """
        if self.project is None or self.canvas is None:
            return

        w = self.project.log_manager.find_by_id(warning_id)
        if w is None:
            return

        regions = w.affected_regions

        if regions:
            #nastavíme aktívnu vrstvu podľa prvého odkazu
            first = regions[0]
            self.set_active_layer(first.layer_id)

        #highlight v canvase
        self.canvas.set_highlight_for_regions(regions)

    def can_undo(self) -> bool:
        return self.project is not None and self.project.can_undo()

    def can_redo(self) -> bool:
        return self.project is not None and self.project.can_redo()
    
    def _on_undo_manager_changed(self) -> None:
        """
        Volá sa pri push_action /undo /redo
        -nastaví dirty
        -MainWindow aktualizuje enabled stav Undo/Redo
        """
        if self.project is not None:
            self.project.mark_dirty()
        
        if self._undo_redo_changed_callback is not None:
            self._undo_redo_changed_callback()

    #-------export--------
    def export_image(self, path: str, resolution: str = "working") -> None:
        if self.project is None:
            return
        img = self.project.get_export_image()
        image_io.save_image(path, img)

    #ColorChecker
    def set_color_correction_matrix(self, matrix: np.ndarray | None) -> None:
        if self.project is None:
            return
        self.project.set_color_correction_matrix(matrix)
        #ak nastavíme matrix, default zapneme
        if matrix is not None:
            self.project.set_color_correction_enabled(True)
        else:
            self.project.set_color_correction_enabled(False)

        self.project.mark_dirty()
        self.refresh_canvas()

    def set_color_correction_enabled(self, enabled: bool) -> None:
        if self.project is None:
            return
        if enabled and not self.project.has_color_correction():
            return
        self.project.set_color_correction_enabled(enabled)
        self.project.mark_dirty()
        self.refresh_canvas()

    def has_color_correction(self) -> bool:
        return self.project is not None and self.project.has_color_correction()
    
    #--autofill-------
    def get_active_paint_layer_for_autofill(self) -> Layer | None:
        """
        Vráti paint vrstvu, na ktorej sa má robiť auto-fill preview/fill
        -najprv berieme:
            -aktívnu vrstvu, ak je PAINT
            -prvú PAINT vrstvu v projekte
        """
        if self.project is None:
            return None

        if self.active_layer_id is not None:
            for layer in self.project.layers:
                if layer.meta.id == self.active_layer_id and layer.meta.role == LayerRole.PAINT:
                    return layer

        for layer in self.project.layers:
            if layer.meta.role == LayerRole.PAINT:
                return layer

        return None

    def clear_auto_fill_preview(self) -> None:
        """
        Zruší auto-fill preview stav
        """
        self.auto_fill_preview_active = False
        self.auto_fill_region_map = None
        self.auto_fill_candidate_region_ids.clear()
        self.auto_fill_excluded_region_ids.clear()
        self.auto_fill_preview_layer_id = None

        if self.canvas is not None:
            self.canvas.clear_auto_fill_preview_regions()

    def set_auto_fill_threshold(self, threshold: int) -> None:
        """
        Nastaví nový threshold pre auto-fill preview
        + reset ručne vyradených oblastí
        + prepočítanie kandidátov
        """
        threshold = max(1, int(threshold))
        self.auto_fill_threshold = threshold
        self.auto_fill_excluded_region_ids.clear()
        self.update_auto_fill_preview()
    
    def update_auto_fill_preview(self) -> None:
        """
        Prepočíta kandidátov pre auto-fill small podľa current threshold
        -postaví RegionMap nad damage_remaining maskou cieľovej PAINT vrstvy
        - uloží region_id kandidátov do controlleru
        - zapne preview režim
        """
        self.clear_auto_fill_preview()

        if self.project is None:
            return
        target_layer = self.get_active_paint_layer_for_autofill()
        if target_layer is None:
            return
        damage_rem = self.project.get_layer_damage_remaining_mask(target_layer.meta.id)
        if damage_rem is None:
            return

        edge_layers = self.project.get_edge_layers()
        region_map = build_region_map(damage_rem, edge_layers)

        candidate_ids = set(region_map.get_region_ids_smaller_than(self.auto_fill_threshold))
        self.auto_fill_region_map = region_map
        self.auto_fill_candidate_region_ids = candidate_ids
        self.auto_fill_preview_layer_id = target_layer.meta.id
        self.auto_fill_preview_active = True

        self._refresh_auto_fill_preview_overlay()

    def get_effective_auto_fill_region_ids(self) -> list[int]:
        """
        Vráti region_id, ktoré sa majú reálne vyplniť cez auto-fill preview režim (bez vyradených oblastí)
        """
        ids = self.auto_fill_candidate_region_ids - self.auto_fill_excluded_region_ids
        return sorted(ids)
    
    def toggle_auto_fill_candidate_at(self, x: int, y: int) -> bool:
        """
        Keď je aktívny auto-fill preview režim, kliknutie na kandidáta ju:
        -vyradí z auto-fill, ak bola aktívna
        -alebo ju znovu zaradí, ak už bola vyradená
        vráti True, ak sa niečo zmenilo
        """
        if not self.auto_fill_preview_active:
            return False

        if self.auto_fill_region_map is None:
            return False

        region_id = self.auto_fill_region_map.get_region_id_at(x, y)
        if region_id == 0:
            return False

        if region_id not in self.auto_fill_candidate_region_ids:
            return False

        if region_id in self.auto_fill_excluded_region_ids:
            self.auto_fill_excluded_region_ids.remove(region_id)
        else:
            self.auto_fill_excluded_region_ids.add(region_id)

        self._refresh_auto_fill_preview_overlay()
        return True
    
    def _refresh_auto_fill_preview_overlay(self) -> None:
        """
        Pošle canvas aktuálny stav auto-fill preview -všetkých kandidátov regióny a aj tie, ktoré sú ručne vyradené
        """
        if self.canvas is None:
            return

        self.canvas.set_auto_fill_preview_regions(self.auto_fill_region_map, self.auto_fill_candidate_region_ids, self.auto_fill_excluded_region_ids)

    def _build_autofill_regions_from_preview(self) -> list[AutoFillRegion]:
        """
        Vytvorí zoznam AutoFillRegion z aktuálneho threshold preview režimu
        """
        result: list[AutoFillRegion] = []

        if self.auto_fill_region_map is None:
            return result

        effective_ids = self.get_effective_auto_fill_region_ids()
        for region_id in effective_ids:
            if not self.auto_fill_region_map.has_region(region_id):
                continue

            bbox = self.auto_fill_region_map.get_region_bbox(region_id)
            if bbox is None:
                continue

            result.append(AutoFillRegion(region_id=region_id, bbox=bbox))

        return result
    
    def _build_autofill_regions_from_selection(self) -> list[AutoFillRegion]:
        """
        Vytvorí zoznam AutoFillRegion z aktívneho SelectionSetu
        """
        result: list[AutoFillRegion] = []

        if self.active_selection is None or self.active_selection.is_empty():
            return result

        for sel in self.active_selection.selections:
            result.append(AutoFillRegion(region_id=sel.region_id, bbox=sel.bbox))

        return result
    
    def has_auto_fill_preview_candidates(self) -> bool:
        """
        True, ak existuje auto-fill preview a sú v ňom aspoň nejaký kandidáti
        """
        return self.auto_fill_preview_active and self.auto_fill_region_map is not None and len(self.get_effective_auto_fill_region_ids()) > 0
    

    def get_auto_fill_mode(self) -> str | None:
        """
        Vráti aktuálny režim auto-fill:
        -"selection" -ak existuje active_selection
        -"preview" -ak neexistuje selection, ale existuje preview kandidátov
        -None
        """
        if self.has_active_selection():
            return "selection"
        if self.has_auto_fill_preview_candidates():
            return "preview"

        return None

    def invalidate_selection_region_map_cache(self) -> None:
        """
        Zruší cached RegionMap pre selection
        """
        self.selection_region_map_cache = None
        self.selection_region_map_cache_layer_id = None

    def get_selection_region_map_for_active_layer(self) -> RegionMap | None:
        """
        Vráti RegionMap pre selection na aktuálnej vrstve
        -na PAINT vrstve používa layer_damage_remaining_mask
        -na BACKGROUND (alebo iné) používa damage_original_mask
        """
        if self.project is None:
            return None

        layer_id = self.active_layer_id
        if layer_id is None:
            return None

        if self.selection_region_map_cache is not None and self.selection_region_map_cache_layer_id == layer_id:
            return self.selection_region_map_cache

        #zoberieme aktívnu vrstvu
        layer = next((l for l in self.project.layers if l.meta.id == layer_id), None)
        if layer is None:
            return None

        if layer.meta.role == LayerRole.PAINT:
            mask = self.project.get_layer_damage_remaining_mask(layer_id)
        else:
            #ostatné
            mask = self.project.damage_original_mask

        if mask is None:
            return None

        edge_layers = self.project.get_edge_layers()
        region_map = build_region_map(mask, edge_layers)

        self.selection_region_map_cache = region_map
        self.selection_region_map_cache_layer_id = layer_id

        return region_map