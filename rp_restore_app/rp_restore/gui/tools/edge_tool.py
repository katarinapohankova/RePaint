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
        self.is_erasing: bool = False
        self.brush_size = 1
        self.edge_color: np.ndarray = controller.get_edge_color_rgba()
        #self._reset_stroke_state()

        self._before_image: Optional[np.ndarray] = None
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None
        self._stroke_min_x: Optional[int] = None
        self._stroke_min_y: Optional[int] = None
        self._stroke_max_x: Optional[int] = None
        self._stroke_max_y: Optional[int] = None

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

        project = self.controller.project
        damage_mask = None
        if project is not None:
            damage_mask = getattr(project, "damage_original_mask", None)

        y_min = max(0, y - r)
        y_max = min(h, y + r + 1)
        x_min = max(0, x - r)
        x_max = min(w, x + r + 1)

        feather = max(1.0, min(4.0, r * 0.35))

        for yy in range(y_min, y_max):
            for xx in range(x_min, x_max):
                dist = ((xx - x) ** 2 + (yy - y) ** 2) ** 0.5
                if dist > r:
                    continue

                #orezanie na damage masku
                if damage_mask is not None:
                    mh, mw = damage_mask.shape
                    if yy >= mh or xx >= mw:
                        continue
                    if not damage_mask[yy, xx]:
                        continue

                if self.is_erasing:
                    layer.image[yy, xx, 3] = 0
                    layer.image[yy, xx, 0:3] = 0
                    continue

                if dist <= r - feather:
                    alpha_factor = 1.0
                else:
                    alpha_factor = (r - dist) / feather

                alpha_factor = max(0.0, min(1.0, alpha_factor))

                src = self.edge_color.astype(np.float32).copy()
                src_alpha = int(src[3] * alpha_factor)

                #ak je alpha veľmi malá, preskočíme
                if src_alpha <= 0:
                    continue

                dst = layer.image[yy, xx, :].astype(np.float32)
                old_a = dst[3] / 255.0
                new_a = src_alpha / 255.0

                out_a = max(old_a, new_a)

                if out_a <= 0:
                    layer.image[yy, xx, :] = 0
                    continue

                #prekrytie farby podľa novej alpha
                layer.image[yy, xx, 0:3] = src[0:3].astype(np.uint8)
                layer.image[yy, xx, 3] = int(out_a * 255)

    def _draw_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)

        for i in range(steps + 1):
            t = i / steps
            xx = int(round(x0 + t * dx))
            yy = int(round(y0 + t * dy))
            self._draw_dot(layer, xx, yy)

    def _update_settings_from_controller(self) -> None:
        self.edge_color = self.controller.get_edge_color_rgba()

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not ((buttons & Qt.LeftButton) or (buttons & Qt.RightButton)):
            return
        
        self.is_erasing = bool(buttons & Qt.RightButton) or bool(modifiers & Qt.ShiftModifier)
        #pri začiatku ťahu natiahneme aktuálnu hrúbku a farbu
        self._update_settings_from_controller()

        layer = self._get_active_edge_layer()
        if layer is None:
            self.controller.show_tool_message("Edge tool sa dá použiť len na EDGE vrstve")
            return

        self.is_drawing = True
        self._last_x = img_x
        self._last_y = img_y

        self._before_image = layer.image.copy()

        self._draw_dot(layer, img_x, img_y)

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
        if not self.is_drawing:
            return

        layer = self._get_active_edge_layer()
        if layer is None:
            return

        if self._last_x is None or self._last_y is None:
            self._last_x = img_x
            self._last_y = img_y

        prev_x = self._last_x
        prev_y = self._last_y
        self._draw_line(layer, self._last_x, self._last_y, img_x, img_y)

        self._last_x = img_x
        self._last_y = img_y

        self._stroke_min_x = min(self._stroke_min_x, prev_x, img_x)
        self._stroke_max_x = max(self._stroke_max_x, prev_x, img_x)
        self._stroke_min_y = min(self._stroke_min_y, prev_y, img_y)
        self._stroke_max_y = max(self._stroke_max_y, prev_y, img_y)

        self._refresh_segment_region(prev_x, prev_y, img_x, img_y, self.brush_size)

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_drawing:
            return

        self.is_drawing = False

        layer = self._get_active_edge_layer()
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

        action = UndoAction(description="Edit edges", layer_id=layer.meta.id, layer_role=layer.meta.role, bbox=bbox, before=before, after=after)

        self.controller.project.undo_manager.push_action(action)

        #info Projecte o zmene hrán -region map diff + warningy
        self.controller.project.on_edge_layer_modified(layer.meta.id)  

        #refresh log panelu, aby sa warningy zobrazili
        self.controller.refresh_log_panel()

        self.controller.invalidate_selection_region_map_cache()

        #refresh canvasu len v bboxe
        self.controller.refresh_canvas_region(bbox)

        self._before_image = None
        self._last_x = None
        self._last_y = None
        self._stroke_min_x = None
        self._stroke_min_y = None
        self._stroke_max_x = None
        self._stroke_max_y = None


    def get_cursor(self):
        if self.controller is None:
            return Qt.CrossCursor
        return self.controller._make_edge_cursor()