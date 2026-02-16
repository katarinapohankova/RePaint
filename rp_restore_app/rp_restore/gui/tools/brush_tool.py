from __future__ import annotations
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.gui.tools.base_tool import BaseTool


class BrushTool(BaseTool):
    """
    štetec -kreslí na aktívnu PAINT vrstvu a ukladá undo ako celú vrstvu
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)
        self.is_drawing: bool = False
        self._active_layer_index: Optional[int] = None

        #nastavenia štetca
        self.brush_size: int = self.controller.get_brush_size()
        self.color_rgba = self.controller.get_current_color_rgba()  #np.array([255, 0, 0, 255], dtype=np.uint8)

        #undo
        self._before_image: Optional[np.ndarray] = None

        #posledná pozícia
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None

        self._stroke_min_x: Optional[int] = None
        self._stroke_min_y: Optional[int] = None
        self._stroke_max_x: Optional[int] = None
        self._stroke_max_y: Optional[int] = None

    def _update_from_controller(self) -> None:
        self.brush_size = self.controller.get_brush_size()
        self.color_rgba = self.controller.get_current_color_rgba()

    def _get_active_paint_layer(self):
        """nájde aktívnu PAINT vrstvu podľa active_layer_id v controlleri"""
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
    
    def _draw_dot(self, layer, x: int, y: int) -> None:
        """nakreslí plný kruh štetcom na vrstve okolo (x, y)"""
        h, w, _ = layer.image.shape
        r = self.brush_size

        #damage mask z projektu
        project = self.controller.project
        damage_mask = None
        if project is not None:
            damage_mask = project.damage_original_mask  #alebo get_damage_remaining_mask()

        y_min = max(0, y - r)
        y_max = min(h, y + r)
        x_min = max(0, x - r)
        x_max = min(w, x + r)

        for yy in range(y_min, y_max):
            for xx in range(x_min, x_max):
                #kruhová maska
                if (xx - x) ** 2 + (yy - y) ** 2 <= r * r:
                    #ak máme damage masku, nekreslíme mimo nej
                    if damage_mask is not None:
                        mh, mw = damage_mask.shape
                        if yy >= mh or xx >= mw:
                            continue
                        if not damage_mask[yy, xx]:
                            continue

                    layer.image[yy, xx, :] = self.color_rgba

    def _draw_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        jednoduché kreslenie medzi dvoma bodmi (aby ťah nebol dierkovaný)
        prejde po úsečke medzi (x0, y0) a (x1, y1) a kreslíme draw_dot
        """
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)

        for i in range(steps + 1):
            t = i / steps
            xx = int(round(x0 + t * dx))
            yy = int(round(y0 + t * dy))
            self._draw_dot(layer, xx, yy)

    def _update_color_from_controller(self) -> None:
        self.color_rgba = self.controller.get_current_color_rgba()

    #--------udalosti myši--------
    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if not (buttons & Qt.LeftButton):
            return
        layer = self._get_active_paint_layer()
        self._update_from_controller()

        if layer is None:
            self.controller.show_tool_message("Brush sa dá použiť len na PAINT vrstvách")
            return
        #vždy pri začiatku ťahu si vezmeme aktuálnu farbu z panelu
        self._update_color_from_controller()
        self.is_drawing = True
        self._last_x = img_x
        self._last_y = img_y

        #pre undo si uložíme celú vrstvu
        self._before_image = layer.image.copy()

        #prvý bod
        self._draw_dot(layer, img_x, img_y)
        #rýchly refresh len okolo prvého bodu
        self._stroke_min_x = img_x
        self._stroke_max_x = img_x
        self._stroke_min_y = img_y
        self._stroke_max_y = img_y

        r = self.brush_size
        x0 = img_x - r
        y0 = img_y - r
        w = 2 * r
        h = 2 * r

        self.controller.refresh_canvas_region((x0, y0, w, h))

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if not self.is_drawing:
            return
        layer = self._get_active_paint_layer()
        if layer is None:
            return
        
        if self._last_x is None or self._last_y is None:
            self._last_x = img_x
            self._last_y = img_y

        #kreslíme čiaru medzi poslednou pozíciou a aktuálnou pozíciou
        prev_x = self._last_x
        prev_y = self._last_y
        self._draw_line(layer, prev_x, prev_y, img_x, img_y)

        self._last_x = img_x
        self._last_y = img_y
        #bbox celého ťahu
        self._stroke_min_x = min(self._stroke_min_x, prev_x, img_x)
        self._stroke_max_x = max(self._stroke_max_x, prev_x, img_x)
        self._stroke_min_y = min(self._stroke_min_y, prev_y, img_y)
        self._stroke_max_y = max(self._stroke_max_y, prev_y, img_y)

        #rýchly refresh len v okolí tejto úsečky
        self._refresh_segment_region(prev_x, prev_y, img_x, img_y, self.brush_size)

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if not self.is_drawing:
            return
        
        self.is_drawing = False

        layer = self._get_active_paint_layer()
        if layer is None or self._before_image is None:
            return
        h, w, _ = layer.image.shape

        #ak sa bbox nenastavil, fallback na celú vrstvu
        if (
            self._stroke_min_x is None
            or self._stroke_min_y is None
            or self._stroke_max_x is None
            or self._stroke_max_y is None
        ):
            x0, y0 = 0, 0
            x1, y1 = w, h
        else:
            margin = self.brush_size  #pridáme rezervu podľa hrúbky štetca
            x0 = max(0, self._stroke_min_x - margin)
            y0 = max(0, self._stroke_min_y - margin)
            x1 = min(w, self._stroke_max_x + margin)
            y1 = min(h, self._stroke_max_y + margin)

        if x1 <= x0 or y1 <= y0:
            #nič sa reálne nekreslilo
            self._before_image = None
            self._last_x = None
            self._last_y = None
            self._stroke_min_x = self._stroke_min_y = None
            self._stroke_max_x = self._stroke_max_y = None
            return

        bw = x1 - x0
        bh = y1 - y0

        #before –výrez z FULL snapshotu
        before = self._before_image[y0:y1, x0:x1, :].copy()
        #after –výrez z aktuálnej vrstvy
        after = layer.image[y0:y1, x0:x1, :].copy()

        bbox = (x0, y0, bw, bh)

        action = UndoAction(description="Brush stroke", layer_id=layer.meta.id, layer_role=layer.meta.role, bbox=bbox, before=before, after=after)

        self.controller.project.undo_manager.push_action(action)

        #cleanup
        self._before_image = None
        self._last_x = None
        self._last_y = None
        self._stroke_min_x = None
        self._stroke_min_y = None
        self._stroke_max_x = None
        self._stroke_max_y = None

        self.controller.refresh_canvas_region(bbox)