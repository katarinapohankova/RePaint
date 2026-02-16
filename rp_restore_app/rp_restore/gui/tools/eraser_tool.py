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
        self.brush_size: int = self.controller.get_brush_size()

        self._before_image: Optional[np.ndarray] = None
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None

        self._stroke_min_x: Optional[int] = None
        self._stroke_min_y: Optional[int] = None
        self._stroke_max_x: Optional[int] = None
        self._stroke_max_y: Optional[int] = None

    def _update_from_controller(self) -> None:
        self.brush_size = self.controller.get_brush_size()

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
        self._update_from_controller()
        if layer is None:
            self.controller.show_tool_message("Eraser sa dá použiť len na PAINT vrstvách")
            return

        self.is_erasing = True
        self._last_x = img_x
        self._last_y = img_y

        self._before_image = layer.image.copy()

        self._erase_dot(layer, img_x, img_y)

        self._stroke_min_x = img_x
        self._stroke_max_x = img_x
        self._stroke_min_y = img_y
        self._stroke_max_y = img_y

        r = self.brush_size
        x0 = img_x - r
        y0 = img_y - r
        w = 2 * r
        h = 2 * r
        if hasattr(self.controller, "refresh_canvas_region"):
            self.controller.refresh_canvas_region((x0, y0, w, h))
        else:
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

        prev_x = self._last_x
        prev_y = self._last_y
        self._erase_line(layer, prev_x, prev_y, img_x, img_y)

        self._last_x = img_x
        self._last_y = img_y

        #bbox celého ťahu
        self._stroke_min_x = min(self._stroke_min_x, prev_x, img_x)
        self._stroke_max_x = max(self._stroke_max_x, prev_x, img_x)
        self._stroke_min_y = min(self._stroke_min_y, prev_y, img_y)
        self._stroke_max_y = max(self._stroke_max_y, prev_y, img_y)

        self._refresh_segment_region(prev_x, prev_y, img_x, img_y, self.brush_size)

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_erasing:
            return

        self.is_erasing = False

        layer = self._get_active_paint_layer()
        if layer is None or self._before_image is None:
            return

        h, w, _ = layer.image.shape

        if (
            self._stroke_min_x is None
            or self._stroke_max_x is None
            or self._stroke_min_y is None
            or self._stroke_max_y is None
        ):
            x0, y0 = 0, 0
            x1, y1 = w, h
        else:
            margin = self.brush_size
            x0 = max(0, self._stroke_min_x - margin)
            y0 = max(0, self._stroke_min_y - margin)
            x1 = min(w, self._stroke_max_x + margin)
            y1 = min(h, self._stroke_max_y + margin)

        if x1 <= x0 or y1 <= y0:
            #nič sa nezmenilo
            self._before_image = None
            self._last_x = None
            self._last_y = None
            self._stroke_min_x = self._stroke_min_y = None
            self._stroke_max_x = self._stroke_max_y = None
            return

        bw = x1 - x0
        bh = y1 - y0

        before = self._before_image[y0:y1, x0:x1, :].copy()
        after = layer.image[y0:y1, x0:x1, :].copy()

        bbox = (x0, y0, bw, bh)

        action = UndoAction(description="Erase stroke", layer_id = layer.meta.id, layer_role = layer.meta.role, bbox = bbox, before = before, after = after)
        self.controller.project.undo_manager.push_action(action)

        self.controller.refresh_canvas_region(bbox)

        self._before_image = None
        self._last_x = None
        self._last_y = None
        self._stroke_min_x = None
        self._stroke_min_y = None
        self._stroke_max_x = None
        self._stroke_max_y = None

