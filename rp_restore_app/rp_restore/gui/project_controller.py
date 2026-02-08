from __future__ import annotations

from typing import Optional, Callable
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

from PySide6.QtCore import Qt

from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.config.settings import AppSettings
from rp_restore.core.selection import Selection
from rp_restore.core.warnings import UserWarning
from rp_restore.core.algorithm_runner import AlgorithmType, AlgorithmRequest, AlgorithmRunner
from rp_restore.core.history import UndoAction
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
from rp_restore.io import image_io
from rp_restore.io.project_storage import ProjectLoader, ProjectSerializer
from rp_restore.core.auto_fill import auto_fill_small_regions

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
        self.color_panel = None
        self._brush_size: int = 10
        
        self.edge_settings_panel: Optional[object] = None
        self._edge_brush_size: int = 2
        self._edge_color_rgba: np.ndarray = np.array([0, 0, 0, 255], dtype=np.uint8)
        #neskôr pribudnú ďalšie ako layers_panel, log_panel, tools_panel...
        self.active_layer_id: Optional[str] = None
        self.layers_panel: Optional[LayersPanel] = None
        self.log_panel: Optional[LogPanel] = None
        self.current_tool: Optional[BaseTool] = None
        self.active_selection: Optional[Selection] = None
        #vizualizácia damage masky v canvase
        self.show_damage_overlay: bool = True
        self.algorithm_panel = None

        self.current_project_path: Optional[str] = None

        self._message_callback: Optional[Callable[[str], None]] = None

    def set_canvas(self, canvas: ImageCanvasWidget) -> None:
        self.canvas = canvas

    def set_project(self, project: Project) -> None:
        """nastaví aktuálny Project a refreshne GUI"""
        self.project = project

        #default aktívna vrstva bude preferovaná BACKGROUND, inak prvú vrstvu v zozname
        self.active_layer_id = None
        if self.project.layers:
            bg = self.project.get_background_layer()
            if bg is not None:
                self.active_layer_id = bg.meta.id
            else:
                self.active_layer_id = self.project.layers[0].meta.id
        self.refresh_canvas()
        self.refresh_layers_panel()
        self.refresh_log_panel()
        if self.color_panel is not None and hasattr(self.color_panel, "refresh_from_project"):
            self.color_panel.refresh_from_project(project)
        if self.edge_settings_panel is not None and hasattr(self.edge_settings_panel, "refresh_from_controller"):
            self.edge_settings_panel.refresh_from_controller(self)
        #neskôr refreshne všetko (refresh_layers_panel(), refresh_log_panel()...)

    def set_color_panel(self, panel: object) -> None:
        """
        prepojí controller s ColorPanelom
        """
        self.color_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)
    
    def set_edge_settings_panel(self, panel: object) -> None:
        """
        Prepojí controller s EdgeSettingsPanelom
        """
        self.edge_settings_panel = panel
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
        #refresh panel
        if self.color_panel is not None and hasattr(self.color_panel, "refresh_from_project"):
            self.color_panel.refresh_from_project(self.project)

    def add_current_color_to_palette(self) -> None:
        if self.project is None:
            return
        self.project.add_palette_color(self.project.get_current_color_rgba())
        if self.color_panel is not None and hasattr(self.color_panel, "refresh_from_project"):
            self.color_panel.refresh_from_project(self.project)
   
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
        if self.color_panel is not None and hasattr(self.color_panel, "set_brush_size_value"):
            self.color_panel.set_brush_size_value(self._brush_size)

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
        else:
            self.current_tool = None

    def set_active_selection(self, selection: Selection | None) -> None:
        """
        nastaví aktuálnu selection
        zatiaľ len uložíme do atribútu, neskôr pridáme highlight na canvase a info AlgorithmPanelu
        """
        self.active_selection = selection
        if self.algorithm_panel is not None and hasattr(self.algorithm_panel, "refresh_from_selection"):
            self.algorithm_panel.refresh_from_selection(selection)
        #neskôr aj highlight selection v canvase

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

    def set_message_callback(self, callback: Callable[[str], None]) -> None:
        """
        nastaví callback na zobrazovanie krátkych hlášok pre užívateľa
        (tool warnings a pod.)
        """
        self._message_callback = callback

    def show_tool_message(self, text: str) -> None:
        """
        zobrazí krátku hlášku o používaní nástrojov
        """
        if self._message_callback is not None:
            self._message_callback(text)
        else:
            print(text)

    #refresh metódy

    def refresh_canvas(self) -> None:
        if self.project is None or self.canvas is None:
            return

        #numpy (H, W, 3, uint8)
        image_rgb = self.project.composited_image()

        #overlay poškodených oblastí (damage_remaining_mask)
        if self.show_damage_overlay:
            remaining = self.project.get_damage_remaining_mask()
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


    def refresh_log_panel(self) -> None:
        if self.project is None or self.log_panel is None:
            return
        self.log_panel.refresh_from_project(self.project)

    def on_canvas_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifier) -> None:
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
        img_rgba = image_io.load_image(image_path)
        h, w, _ = img_rgba.shape

        bg_meta = LayerMeta(id="background", name="Background", role=LayerRole.BACKGROUND)
        bg_layer = Layer(bg_meta, img_rgba)

        paint_img = np.zeros_like(img_rgba, dtype=np.uint8)
        paint_meta = LayerMeta(id="paint_1", name="Paint 1", role=LayerRole.PAINT)
        paint_layer = Layer(paint_meta, paint_img)

        edge_img = np.zeros_like(img_rgba, dtype=np.uint8)
        edge_meta = LayerMeta(id="edge_1", name="Edges 1", role=LayerRole.EDGE)
        edge_layer = Layer(edge_meta, edge_img)

        project_name = Path(image_path).stem
        project = Project(project_name)
        project.add_layer(bg_layer)
        project.add_layer(paint_layer)
        project.add_layer(edge_layer)

        if mask_path:
            mask = image_io.load_mask(mask_path)
            project.set_damage_masks(mask)

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
        return True

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

    def run_auto_fill_small_regions(self, area_threshold: int = 200) -> int:
        """
        spustí auto-fill malých oblastí na aktívnej PAINT vrstve
        (alebo na prvej paint vrstve, ak aktívna nie je paint)

        vráti počet vyplnených oblastí
        """
        if self.project is None:
            return 0

        #cieľová vrstva – preferujeme aktívnu, ak je PAINT
        target_layer: Layer | None = None

        if self.active_layer_id is not None:
            for layer in self.project.layers:
                if layer.meta.id == self.active_layer_id and layer.meta.role == LayerRole.PAINT:
                    target_layer = layer
                    break

        if target_layer is None:
            #fallback na prvú PAINT vrstvu
            for layer in self.project.layers:
                if layer.meta.role == LayerRole.PAINT:
                    target_layer = layer
                    break

        if target_layer is None:
            return 0

        count = auto_fill_small_regions(self.project, target_layer, area_threshold)

        if count > 0:
            self.refresh_canvas()

        return count
    
    def run_algorithm_on_selection(self, algorithm_type: AlgorithmType, use_mock: bool = True) -> None:
        """
        Spustí externý algoritmus na aktuálnej selection
        - pripraví AlgorithmRequest, zavolá AlgorithmRunner.run
        - výsledný patch vloží do aktívnej (alebo prvej) PAINT vrstvy
        - pridá UndoAction a označí oblasť v damage maske ako vyplnenú
        """
        project = self.project
        if project is None or self.active_selection is None:
            return

        selection = self.active_selection

        original = project.get_original_image()
        current = project.get_current_composited_image()
        damage_rem = project.get_damage_remaining_mask()

        if original is None or damage_rem is None:
            return

        #zabezpečíme tvar masiek
        selected_mask = selection.region_mask.astype(bool)
        remaining_mask = damage_rem.astype(bool)

        #device – zatiaľ natvrdo cpu, neskôr z konfigurácie
        device = "cpu"

        request = AlgorithmRequest(original_image=original, current_image=current, selected_mask=selected_mask, remaining_mask=remaining_mask, algorithm_type=algorithm_type, device=device, mock=use_mock)

        try:
            result = AlgorithmRunner.run(request)
        except Exception as e:
            #zatia+ to aspoň vypíšeme do konzoly
            print("Algorithm error:", e)
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
        sub_img[...] = patch_rgba

        #after
        after = target_layer.clone_subregion(x, y, w, h)

        action = UndoAction(description=f"Algorithm {algorithm_type.value} fill", layer_id=target_layer.meta.id, layer_role=target_layer.meta.role, bbox=(x, y, w, h), before=before, after=after)

        project.undo_manager.push_action(action)

        #označíme selection ako vyplnenú v damage maske
        project.mark_region_as_filled(selection.region_mask)

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
