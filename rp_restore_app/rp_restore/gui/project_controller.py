from __future__ import annotations

from typing import Optional
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

from PySide6.QtCore import Qt

from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.config.settings import AppSettings
from rp_restore.core.selection import Selection
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget
from rp_restore.gui.panels.layers_panel import LayersPanel
from rp_restore.gui.tools.base_tool import BaseTool
from rp_restore.gui.tools.brush_tool import BrushTool
from rp_restore.gui.tools.eraser_tool import EraserTool
from rp_restore.gui.tools.fill_tool import FillTool
from rp_restore.gui.tools.selection_tool import SelectionTool
from rp_restore.io import image_io
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
        #neskôr pribudnú ďalšie ako layers_panel, log_panel, tools_panel...
        self.active_layer_id: Optional[str] = None
        self.layers_panel: Optional[LayersPanel] = None
        self.current_tool: Optional[BaseTool] = None
        self.active_selection: Optional[Selection] = None

        self.current_project_path: Optional[str] = None


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
        #neskôr refreshne všetko (refresh_layers_panel(), refresh_log_panel()...)

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
        else:
            self.current_tool = None

    def set_active_selection(self, selection: Selection | None) -> None:
        """
        nastaví aktuálnu selection
        zatiaľ len uložíme do atribútu, neskôr pridáme highlight na canvase a info AlgorithmPanelu
        """
        self.active_selection = selection


    #refresh metódy

    def refresh_canvas(self) -> None:
        if self.project is None or self.canvas is None:
            return

        #numpy (H, W, 3, uint8)
        image_rgb = self.project.composited_image()
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

    def refresh_layers_panel(self) -> None:
        if self.project is None or self.layers_panel is None:
            return

        self.layers_panel.refresh_from_project(self.project, self.active_layer_id)


    def refresh_log_panel(self) -> None:
        #treba dorobiť
        pass

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

        project_name = Path(image_path).stem
        project = Project(project_name)
        project.add_layer(bg_layer)
        project.add_layer(paint_layer)

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

