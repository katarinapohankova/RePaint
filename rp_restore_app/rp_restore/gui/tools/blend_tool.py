from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.gui.tools.base_tool import BaseTool


class BlendTool(BaseTool):
    """
    Nástroj na rozmazanie pixelov v rámci aktívnej PAINT vrstvy
    funguje iba v damage maske a zdroj môže brať z aktívnej vrstvy alebo z kombinácie pozadia a aktívnej vrstvy
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)

        self.is_blending: bool = False
        self.brush_size: int = self.controller.get_brush_size()

        self._before_image: Optional[np.ndarray] = None

        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None

        self._stroke_min_x: Optional[int] = None
        self._stroke_min_y: Optional[int] = None
        self._stroke_max_x: Optional[int] = None
        self._stroke_max_y: Optional[int] = None

    def _get_active_paint_layer(self):
        """Vráti aktívnu PAINT vrstvu alebo None"""
        project = self.controller.project
        if project is None or self.controller.active_layer_id is None:
            return None

        for layer in project.layers:
            if layer.meta.id == self.controller.active_layer_id:
                if layer.meta.role == LayerRole.PAINT:
                    return layer
                return None

        return None

    def _make_soft_mask(self, sh: int, sw: int, cx: int, cy: int, radius: int) -> np.ndarray:
        """Vytvorí kruhovú masku štetca so zohľadnením tvrdosti"""
        hardness = 1.0
        if hasattr(self.controller, "get_brush_hardness"):
            hardness = float(self.controller.get_brush_hardness())

        yy, xx = np.ogrid[0:sh, 0:sw]
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

        if hardness >= 0.999:
            mask = (dist <= radius).astype(np.float32)
            return mask

        inner = radius * hardness
        feather = max(1e-6, radius - inner)

        soft = (radius - dist) / feather
        mask = np.where(dist <= inner, 1.0, soft)
        mask = np.clip(mask, 0.0, 1.0)
        mask[dist > radius] = 0.0
        return mask.astype(np.float32)

    def _blend_dot(self, layer, src_x: int, src_y: int, dst_x: int, dst_y: int) -> None:
        """
        Prenesie patch z predchádzajúcej pozície na aktuálnu pozíciu a zmieša ho s cieľovými pixelmi
        """
        h, w, _ = layer.image.shape
        r = int(self.brush_size)

        dst_x0 = max(0, dst_x - r)
        dst_y0 = max(0, dst_y - r)
        dst_x1 = min(w, dst_x + r + 1)
        dst_y1 = min(h, dst_y + r + 1)

        if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
            return

        sw = dst_x1 - dst_x0
        sh = dst_y1 - dst_y0

        src_x0 = src_x - (dst_x - dst_x0)
        src_y0 = src_y - (dst_y - dst_y0)
        src_x1 = src_x0 + sw
        src_y1 = src_y0 + sh

        #ak by zdroj vyšiel mimo obrázka, upravíme rovnako zdroj aj cieľ
        shift_left = max(0, -src_x0)
        shift_top = max(0, -src_y0)
        shift_right = max(0, src_x1 - w)
        shift_bottom = max(0, src_y1 - h)

        src_x0 += shift_left
        dst_x0 += shift_left
        src_y0 += shift_top
        dst_y0 += shift_top

        src_x1 -= shift_right
        dst_x1 -= shift_right
        src_y1 -= shift_bottom
        dst_y1 -= shift_bottom

        if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
            return

        sw = dst_x1 - dst_x0
        sh = dst_y1 - dst_y0

        cx = dst_x - dst_x0
        cy = dst_y - dst_y0

        mask = self._make_soft_mask(sh, sw, cx, cy, r)

        strength = 0.5
        if hasattr(self.controller, "get_blend_strength"):
            strength = float(self.controller.get_blend_strength())

        alpha = np.clip(mask * strength, 0.0, 1.0)

        project = self.controller.project
        if project is not None and project.damage_original_mask is not None:
            dm = project.damage_original_mask[dst_y0:dst_y1, dst_x0:dst_x1].astype(np.float32)
            alpha *= dm

        if not np.any(alpha > 0):
            return

        project = self.controller.project
        if project is None:
            return

        source_mode = "active_paint"
        if hasattr(self.controller, "get_blend_source_mode"):
            source_mode = self.controller.get_blend_source_mode()

        if source_mode == "background_and_active_paint":
            background = project.get_background_layer()
            if background is None:
                return

            bg_rgb = background.image[src_y0:src_y1, src_x0:src_x1, :3].astype(np.float32)

            paint_rgb = layer.image[src_y0:src_y1, src_x0:src_x1, :3].astype(np.float32)
            paint_alpha = layer.image[src_y0:src_y1, src_x0:src_x1, 3:4].astype(np.float32) / 255.0

            src_rgb = bg_rgb * (1.0 - paint_alpha) + paint_rgb * paint_alpha

            src_patch = np.zeros((sh, sw, 4), dtype=np.float32)
            src_patch[..., :3] = src_rgb
            src_patch[..., 3] = 255.0
        else:
            src_patch = layer.image[src_y0:src_y1, src_x0:src_x1, :].astype(np.float32)

        dst_patch = layer.image[dst_y0:dst_y1, dst_x0:dst_x1, :].astype(np.float32)

        a = alpha[..., None]

        out = dst_patch * (1.0 - a) + src_patch * a
        layer.image[dst_y0:dst_y1, dst_x0:dst_x1, :] = np.clip(out, 0, 255).astype(np.uint8)

    def _blend_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        """Rozmaže úsek medzi dvoma bodmi postupnými odtlačkami štetca"""
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)

        prev_x = x0
        prev_y = y0

        for i in range(1, steps + 1):
            t = i / steps
            xx = int(round(x0 + t * dx))
            yy = int(round(y0 + t * dy))

            self._blend_dot(layer, prev_x, prev_y, xx, yy)

            prev_x = xx
            prev_y = yy

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """Začne ťah rozmazávacieho nástroja"""
        if not (buttons & Qt.LeftButton):
            return

        layer = self._get_active_paint_layer()
        if layer is None:
            self.controller.show_tool_message("Rozmazání lze použít pouze na vrstvě malby")
            return

        self.brush_size = self.controller.get_brush_size()
        self.is_blending = True

        self._before_image = layer.image.copy()

        self._last_x = img_x
        self._last_y = img_y

        self._stroke_min_x = img_x
        self._stroke_max_x = img_x
        self._stroke_min_y = img_y
        self._stroke_max_y = img_y

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """Pokračuje v rozmazávaní počas ťahu myšou"""
        if not self.is_blending:
            return

        layer = self._get_active_paint_layer()
        if layer is None:
            return

        if self._last_x is None or self._last_y is None:
            self._last_x = img_x
            self._last_y = img_y
            return

        prev_x = self._last_x
        prev_y = self._last_y

        self._blend_line(layer, prev_x, prev_y, img_x, img_y)

        self._last_x = img_x
        self._last_y = img_y

        self._stroke_min_x = min(self._stroke_min_x, prev_x, img_x)
        self._stroke_max_x = max(self._stroke_max_x, prev_x, img_x)
        self._stroke_min_y = min(self._stroke_min_y, prev_y, img_y)
        self._stroke_max_y = max(self._stroke_max_y, prev_y, img_y)

        self._refresh_segment_region(prev_x, prev_y, img_x, img_y, self.brush_size)

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """Ukončí ťah rozmazania a uloží undo akciu"""
        if not self.is_blending:
            return

        self.is_blending = False

        layer = self._get_active_paint_layer()
        if layer is None or self._before_image is None:
            self._cleanup()
            return

        h, w, _ = layer.image.shape

        if (
            self._stroke_min_x is None
            or self._stroke_min_y is None
            or self._stroke_max_x is None
            or self._stroke_max_y is None
        ):
            self._cleanup()
            return

        margin = self.brush_size + 2
        x0 = max(0, self._stroke_min_x - margin)
        y0 = max(0, self._stroke_min_y - margin)
        x1 = min(w, self._stroke_max_x + margin + 1)
        y1 = min(h, self._stroke_max_y + margin + 1)

        if x1 <= x0 or y1 <= y0:
            self._cleanup()
            return

        bbox = (x0, y0, x1 - x0, y1 - y0)

        before = self._before_image[y0:y1, x0:x1, :].copy()
        after = layer.image[y0:y1, x0:x1, :].copy()

        if not np.array_equal(before, after):
            action = UndoAction(description="Rozmazání", layer_id=layer.meta.id, layer_role=layer.meta.role, bbox=bbox, before=before, after=after)
            self.controller.project.undo_manager.push_action(action)

            project = self.controller.project
            if project is not None:
                project.sync_layer_filled_mask_from_alpha(layer.meta.id, bbox, mode="assign")
                project.mark_dirty()

            if hasattr(self.controller, "invalidate_selection_region_map_cache"):
                self.controller.invalidate_selection_region_map_cache()

        self.controller.refresh_canvas_region(bbox)
        self._cleanup()

    def _cleanup(self) -> None:
        """Vyčistí dočasný stav po ťahu"""
        self.is_blending = False
        self._before_image = None

        self._last_x = None
        self._last_y = None

        self._stroke_min_x = None
        self._stroke_min_y = None
        self._stroke_max_x = None
        self._stroke_max_y = None

    def get_cursor(self):
        """Vráti kurzor rozmazávacieho nástroja"""
        radius = int(self.controller.get_brush_size())
        return self.controller._make_blend_cursor(radius)