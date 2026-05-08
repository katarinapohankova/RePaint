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
        self._stroke_committed_erase_u8: Optional[np.ndarray] = None
        self._pass_erase_u8: Optional[np.ndarray] = None
        self._last_dir: Optional[tuple[float, float]] = None
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
    
    def _opacity_limit_u8(self) -> int:
        """
        Krytí = maximálne množstvo vymazania v rámci jedného súvislého ťahu
        """
        opacity = 1.0
        if hasattr(self.controller, "get_brush_opacity"):
            opacity = float(self.controller.get_brush_opacity())
        opacity = max(0.0, min(1.0, opacity))
        return int(round(opacity * 255.0))

    def _commit_current_pass(self) -> None:
        """
        Uzavrie aktuálny pass do committed erase masky
        """
        if self._pass_erase_u8 is None:
            return

        if self._stroke_committed_erase_u8 is None:
            self._stroke_committed_erase_u8 = np.zeros_like(self._pass_erase_u8, dtype=np.uint8)

        limit = self._opacity_limit_u8()

        allow_overlap = True
        if hasattr(self.controller, "get_brush_allow_overlap"):
            allow_overlap = bool(self.controller.get_brush_allow_overlap())

        if allow_overlap:
            summed = self._stroke_committed_erase_u8.astype(np.uint16) + self._pass_erase_u8.astype(np.uint16)
            summed = np.minimum(summed, limit)
            self._stroke_committed_erase_u8[:] = summed.astype(np.uint8)
        else:
            np.maximum(self._stroke_committed_erase_u8, self._pass_erase_u8, out=self._stroke_committed_erase_u8)
            self._stroke_committed_erase_u8[:] = np.minimum(self._stroke_committed_erase_u8, limit).astype(np.uint8)

    def _maybe_start_new_pass(self, layer, dx: int, dy: int) -> None:
        """
        Pri výraznej zmene smeru začne nový pass
        -nový pass môže pridať ďalšie gumovanie, ale stále iba do hranice Krytí
        """
        length = float((dx * dx + dy * dy) ** 0.5)
        if length < 1.0:
            return

        new_dir = (dx / length, dy / length)

        if self._last_dir is None:
            self._last_dir = new_dir
            return

        old_dx, old_dy = self._last_dir
        dot = old_dx * new_dir[0] + old_dy * new_dir[1]

        if dot < -0.3:
            self._commit_current_pass()
            h, w, _ = layer.image.shape
            self._pass_erase_u8 = np.zeros((h, w), dtype=np.uint8)

        self._last_dir = new_dir

    def _make_soft_mask(self, sh: int, sw: int, cx: int, cy: int, radius: int) -> np.ndarray:
        hardness = 1.0
        if hasattr(self.controller, "get_brush_hardness"):
            hardness = float(self.controller.get_brush_hardness())

        yy, xx = np.ogrid[0:sh, 0:sw]
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

        if hardness >= 0.999:
            return (dist <= radius).astype(np.float32)

        inner = radius * hardness
        feather = max(1e-6, radius - inner)

        soft = (radius - dist) / feather
        mask = np.where(dist <= inner, 1.0, soft)
        mask = np.clip(mask, 0.0, 1.0)
        mask[dist > radius] = 0.0
        return mask.astype(np.float32)

    def _render_erase_from_stroke_mask(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        Renderuje aktuálny stav gumy z pôvodného before_image
        -aby sa nehromadilo množstvo gumy nad Krytí
        """
        if self._before_image is None or self._pass_erase_u8 is None:
            return

        if x1 <= x0 or y1 <= y0:
            return

        sub = layer.image[y0:y1, x0:x1, :]
        before = self._before_image[y0:y1, x0:x1, :]

        pass_erase = self._pass_erase_u8[y0:y1, x0:x1].astype(np.uint16)

        if self._stroke_committed_erase_u8 is not None:
            committed = self._stroke_committed_erase_u8[y0:y1, x0:x1].astype(np.uint16)
        else:
            committed = np.zeros_like(pass_erase, dtype=np.uint16)

        limit = self._opacity_limit_u8()

        allow_overlap = True
        if hasattr(self.controller, "get_brush_allow_overlap"):
            allow_overlap = bool(self.controller.get_brush_allow_overlap())

        if allow_overlap:
            erase_u16 = np.minimum(committed + pass_erase, limit)
        else:
            erase_u16 = np.maximum(committed, pass_erase)
            erase_u16 = np.minimum(erase_u16, limit)

        erase_amount = erase_u16.astype(np.float32) / 255.0

        sub[...] = before

        old_alpha = before[..., 3].astype(np.float32) / 255.0
        new_alpha = old_alpha * (1.0 - erase_amount)

        sub[..., 3] = np.clip(new_alpha * 255.0, 0, 255).astype(np.uint8)

        clear = sub[..., 3] <= 2
        sub[clear, 0:3] = 0
        sub[clear, 3] = 0

    def _erase_dot(self, layer, x: int, y: int) -> None:
        h, w, _ = layer.image.shape
        r = self.brush_size

        y_min = max(0, y - r)
        y_max = min(h, y + r + 1)
        x_min = max(0, x - r)
        x_max = min(w, x + r + 1)

        if x_max <= x_min or y_max <= y_min:
            return

        sh = y_max - y_min
        sw = x_max - x_min

        cx = x - x_min
        cy = y - y_min

        mask = self._make_soft_mask(sh, sw, cx, cy, r)

        flow = 1.0
        if hasattr(self.controller, "get_brush_flow"):
            flow = float(self.controller.get_brush_flow())
        flow = max(0.0, min(1.0, flow))

        erase_amount = np.clip(mask * flow, 0.0, 1.0)
        erase_u8 = np.clip(erase_amount * 255.0, 0, 255).astype(np.uint8)
        
        if self._pass_erase_u8 is None:
            self._pass_erase_u8 = np.zeros((h, w), dtype=np.uint8)

        if self._stroke_committed_erase_u8 is None:
            self._stroke_committed_erase_u8 = np.zeros((h, w), dtype=np.uint8)

        erase_sub = self._pass_erase_u8[y_min:y_max, x_min:x_max]
        np.maximum(erase_sub, erase_u8, out=erase_sub)

        self._render_erase_from_stroke_mask(layer, x_min, y_min, x_max, y_max)

    def _erase_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        dx = x1 - x0
        dy = y1 - y0
        self._maybe_start_new_pass(layer, dx, dy)
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

        h, w, _ = layer.image.shape
        self._stroke_committed_erase_u8 = np.zeros((h, w), dtype=np.uint8)
        self._pass_erase_u8 = np.zeros((h, w), dtype=np.uint8)
        self._last_dir = None

        self._erase_dot(layer, img_x, img_y)

        self._stroke_min_x = img_x
        self._stroke_max_x = img_x
        self._stroke_min_y = img_y
        self._stroke_max_y = img_y

        r = self.brush_size
        bbox = self._clamp_bbox_to_layer(layer, (img_x - r, img_y - r, 2 * r + 1, 2 * r + 1))
        if bbox is not None:
            self._sync_mask_and_refresh(layer, bbox)

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

        r = self.brush_size
        step_bbox = (
            min(prev_x, img_x) - r,
            min(prev_y, img_y) - r,
            abs(img_x - prev_x) + 2 * r + 1,
            abs(img_y - prev_y) + 2 * r + 1,
        )
        step_bbox = self._clamp_bbox_to_layer(layer, step_bbox)

        if step_bbox is not None:
            self._sync_mask_and_refresh(layer, step_bbox)

        self._last_x = img_x
        self._last_y = img_y

        #bbox celého ťahu
        self._stroke_min_x = min(self._stroke_min_x, prev_x, img_x)
        self._stroke_max_x = max(self._stroke_max_x, prev_x, img_x)
        self._stroke_min_y = min(self._stroke_min_y, prev_y, img_y)
        self._stroke_max_y = max(self._stroke_max_y, prev_y, img_y)

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_erasing:
            return

        self.is_erasing = False

        layer = self._get_active_paint_layer()
        if layer is None or self._before_image is None:
            self._cleanup()
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
            x1 = min(w, self._stroke_max_x + margin + 1)
            y1 = min(h, self._stroke_max_y + margin + 1)

        if x1 <= x0 or y1 <= y0:
            self._cleanup()
            return

        bw = x1 - x0
        bh = y1 - y0

        before = self._before_image[y0:y1, x0:x1, :].copy()
        after = layer.image[y0:y1, x0:x1, :].copy()

        bbox = (x0, y0, bw, bh)

        action = UndoAction(description="Erase stroke", layer_id = layer.meta.id, layer_role = layer.meta.role, bbox = bbox, before = before, after = after)
        self.controller.project.undo_manager.push_action(action)

        project = self.controller.project
        if project is not None:
            project.sync_layer_filled_mask_from_alpha(layer.meta.id, bbox, mode="assign")
            if hasattr(project, "mark_dirty"):
                project.mark_dirty()

        self.controller.invalidate_selection_region_map_cache()
        self.controller.refresh_canvas_region(bbox)

        self._cleanup()

    def _sync_mask_and_refresh(self, layer, bbox: tuple[int, int, int, int]) -> None:
        project = self.controller.project
        if project is not None:
            project.sync_layer_filled_mask_from_alpha(layer.meta.id, bbox)

        if hasattr(self.controller, "refresh_canvas_region"):
            self.controller.refresh_canvas_region(bbox)
        else:
            self.controller.refresh_canvas()

    def _clamp_bbox_to_layer(self, layer, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
        x, y, bw, bh = bbox
        if bw <= 0 or bh <= 0:
            return None

        H, W, _ = layer.image.shape

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(W, x + bw)
        y1 = min(H, y + bh)

        if x1 <= x0 or y1 <= y0:
            return None

        return (x0, y0, x1 - x0, y1 - y0)

    def _cleanup(self) -> None:
        self._before_image = None
        self._stroke_committed_erase_u8 = None
        self._pass_erase_u8 = None
        self._last_dir = None

        self._last_x = None
        self._last_y = None

        self._stroke_min_x = None
        self._stroke_min_y = None
        self._stroke_max_x = None
        self._stroke_max_y = None