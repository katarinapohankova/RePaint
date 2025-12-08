from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtGui import QImage

from rp_restore.core.project_model import Project
from rp_restore.config.settings import AppSettings
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget


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


    def set_canvas(self, canvas: ImageCanvasWidget) -> None:
        self.canvas = canvas

    def set_project(self, project: Project) -> None:
        """nastaví aktuálny Project a refreshne GUI"""
        self.project = project
        self.refresh_canvas()
        #neskôr refreshne všetko (refresh_layers_panel(), refresh_log_panel()...)

    #refresh metódy

    def refresh_canvas(self) -> None:
        if self.project is None or self.canvas is None:
            return

        #numpy (H, W, 3, uint8)
        image_rgb = self.project.composited_image()
        qimage = self._numpy_rgb_to_qimage(image_rgb)
        self.canvas.set_image(qimage)

    def refresh_layers_panel(self) -> None:
        #treba dorobiť
        pass

    def refresh_log_panel(self) -> None:
        #treba dorobiť
        pass


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
