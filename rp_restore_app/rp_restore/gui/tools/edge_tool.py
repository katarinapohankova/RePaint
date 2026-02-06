from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.gui.tools.base_tool import BaseTool


class EdgeTool(BaseTool):
    """
    Nástroj na kreslenie hrán -EDGE vrstvy
    - kreslí čierne čiary (RGBA = 0,0,0,255) na aktívnej EDGE vrstve, vytvára UndoAction
    - pri release zavolá project.on_edge_layer_modified(...)
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)

        self.is_drawing: bool = False
        self.brush_size: int = 2
        self.edge_color = np.array([0, 0, 0, 255], dtype=np.uint8)

        self._before_image: Optional[np.ndarray] = None
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None

    def _get_active_edge_layer(self):
        project = self.controller.project
        if project is None or self.controller.active_layer_id is None:
            return None

        for layer in project.layers:
            if layer.meta.id == self.controller.active_layer_id:
                if layer.meta.role == LayerRole.EDGE:
                    return layer
                else:
                    return None
        return None

    def _draw_dot(self, layer, x: int, y: int) -> None:
        h, w, _ = layer.image.shape
        r = self.brush_size

        y_min = max(0, y - r)
        y_max = min(h, y + r)
        x_min = max(0, x - r)
        x_max = min(w, x + r)

        for yy in range(y_min, y_max):
            for xx in range(x_min, x_max):
                if (xx - x) ** 2 + (yy - y) ** 2 <= r * r:
                    layer.image[yy, xx, :] = self.edge_color

    def _draw_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)

        for i in range(steps + 1):
            t = i / steps
            xx = int(round(x0 + t * dx))
            yy = int(round(y0 + t * dy))
            self._draw_dot(layer, xx, yy)

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not (buttons & Qt.LeftButton):
            return

        layer = self._get_active_edge_layer()
        if layer is None:
            self.controller.show_tool_message("Edge tool sa dá použiť len na EDGE vrstve")
            return

        self.is_drawing = True
        self._last_x = img_x
        self._last_y = img_y

        self._before_image = layer.image.copy()

        self._draw_dot(layer, img_x, img_y)
        self.controller.refresh_canvas()

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_drawing:
            return

        layer = self._get_active_edge_layer()
        if layer is None:
            return

        if self._last_x is None or self._last_y is None:
            self._last_x = img_x
            self._last_y = img_y

        self._draw_line(layer, self._last_x, self._last_y, img_x, img_y)

        self._last_x = img_x
        self._last_y = img_y

        self.controller.refresh_canvas()

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_drawing:
            return

        self.is_drawing = False

        layer = self._get_active_edge_layer()
        if layer is None or self._before_image is None:
            return

        after_image = layer.image.copy()
        h, w, _ = layer.image.shape
        bbox = (0, 0, w, h)

        action = UndoAction(description="Edit edges", layer_id=layer.meta.id, layer_role=layer.meta.role, bbox=bbox, before=self._before_image, after=after_image)

        self.controller.project.undo_manager.push_action(action) 

        #info Projecte o zmene hrán -region map diff + warningy
        self.controller.project.on_edge_layer_modified(layer.meta.id)  

        #refresh log panelu, aby sa warningy zobrazili
        self.controller.refresh_log_panel()

        self._before_image = None
        self._last_x = None
        self._last_y = None

        self.controller.refresh_canvas()
