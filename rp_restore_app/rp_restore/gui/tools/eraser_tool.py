from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.gui.tools.base_tool import BaseTool


class EraserTool(BaseTool):
    """
    guma -maže na aktívnej PAINT vrstve, nastaví alfa kanál na 0 (priehľadné) a undo funguje rovnako ako pri štetci
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)

        self.is_erasing: bool = False
        self.brush_size: int = 10

        self._before_image: Optional[np.ndarray] = None
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None

    def _get_active_paint_layer(self):
        project = self.controller.project
        if project is None or self.controller.active_layer_id is None:
            return None

        for layer in project.layers:
            if layer.meta.id == self.controller.active_layer_id:
                if layer.meta.role == LayerRole.PAINT:
                    return layer
                else:
                    return None
        return None

    def _erase_dot(self, layer, x: int, y: int) -> None:
        h, w, _ = layer.image.shape
        r = self.brush_size

        y_min = max(0, y - r)
        y_max = min(h, y + r)
        x_min = max(0, x - r)
        x_max = min(w, x + r)

        for yy in range(y_min, y_max):
            for xx in range(x_min, x_max):
                if (xx - x) ** 2 + (yy - y) ** 2 <= r * r:
                    #nastavíme alfa na 0 
                    layer.image[yy, xx, 3] = 0
                    #vynulujeme aj RGB kanály
                    layer.image[yy, xx, 0:3] = 0

    def _erase_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)

        for i in range(steps + 1):
            t = i / steps
            xx = int(round(x0 + t * dx))
            yy = int(round(y0 + t * dy))
            self._erase_dot(layer, xx, yy)

    #--------udalosti myši--------
    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not (buttons & Qt.LeftButton):
            return

        layer = self._get_active_paint_layer()
        if layer is None:
            self.controller.show_tool_message("Eraser sa dá použiť len na PAINT vrstvách")
            return

        self.is_erasing = True
        self._last_x = img_x
        self._last_y = img_y

        self._before_image = layer.image.copy()

        self._erase_dot(layer, img_x, img_y)
        self.controller.refresh_canvas()

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_erasing:
            return

        layer = self._get_active_paint_layer()
        if layer is None:
            return

        if self._last_x is None or self._last_y is None:
            self._last_x = img_x
            self._last_y = img_y

        self._erase_line(layer, self._last_x, self._last_y, img_x, img_y)

        self._last_x = img_x
        self._last_y = img_y

        self.controller.refresh_canvas()

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_erasing:
            return

        self.is_erasing = False

        layer = self._get_active_paint_layer()
        if layer is None or self._before_image is None:
            return

        after_image = layer.image.copy()
        h, w, _ = layer.image.shape
        bbox = (0, 0, w, h)

        action = UndoAction(description="Erase stroke", layer_id = layer.meta.id, layer_role = layer.meta.role, bbox = bbox, before = self._before_image, after = after_image)

        self.controller.project.undo_manager.push_action(action)  

        self._before_image = None
        self._last_x = None
        self._last_y = None

        self.controller.refresh_canvas()
