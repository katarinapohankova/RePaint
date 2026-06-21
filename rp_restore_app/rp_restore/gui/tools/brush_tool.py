from __future__ import annotations
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.core.texture_brush import generate_fill_pattern
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
        self._stroke_seed: int = 0

        #undo
        self._before_image: Optional[np.ndarray] = None
        self._stroke_committed_alpha_u8: Optional[np.ndarray] = None
        self._pass_alpha_u8: Optional[np.ndarray] = None
        self._last_dir: Optional[tuple[float, float]] = None

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
    
    def _opacity_limit_u8(self) -> int:
        opacity = 1.0
        if hasattr(self.controller, "get_brush_opacity"):
            opacity = float(self.controller.get_brush_opacity())
        opacity = max(0.0, min(1.0, opacity))
        return int(round(opacity * 255.0))

    def _commit_current_pass(self) -> None:
        """
        Uzavrie aktuálny čiastočný pass do committed masky
        """
        if self._pass_alpha_u8 is None:
            return

        if self._stroke_committed_alpha_u8 is None:
            self._stroke_committed_alpha_u8 = np.zeros_like(self._pass_alpha_u8, dtype=np.uint8)

        limit = self._opacity_limit_u8()
        allow_overlap = True
        if hasattr(self.controller, "get_brush_allow_overlap"):
            allow_overlap = bool(self.controller.get_brush_allow_overlap())

        if allow_overlap:
            summed = self._stroke_committed_alpha_u8.astype(np.uint16) + self._pass_alpha_u8.astype(np.uint16)
            summed = np.minimum(summed, limit)
            self._stroke_committed_alpha_u8[:] = summed.astype(np.uint8)
        else:
            np.maximum(self._stroke_committed_alpha_u8, self._pass_alpha_u8, out=self._stroke_committed_alpha_u8)

    def _maybe_start_new_pass(self, layer, dx: int, dy: int) -> None:
        """
        Ak sa smer ťahu výrazne otočí, začneme nový pass
        -vrstvenie farby pri návrate späť cez už prejdenú časť (nefunguje do kruhu a podobne)
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

        #dot < -0.3 približne znamená výrazné otočenie smeru
        #pri úplnom návrate späť je dot blízko -1
        if dot < -0.3:
            self._commit_current_pass()
            h, w, _ = layer.image.shape
            self._pass_alpha_u8 = np.zeros((h, w), dtype=np.uint8)
        self._last_dir = new_dir
        
    def _make_soft_mask(self, sh: int, sw: int, cx: int, cy: int, radius: int) -> np.ndarray:
        """
        Vytvorí masku štetca 0..1 podľa tvrdosti
        1 = plná sila, 0 = mimo štetca
        """
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

        mask = np.ones((sh, sw), dtype=np.float32)
        soft = (radius - dist) / feather
        mask = np.where(dist <= inner, 1.0, soft)
        mask = np.clip(mask, 0.0, 1.0)
        mask[dist > radius] = 0.0
        return mask.astype(np.float32)

    def _alpha_blend_rgba(self, dst: np.ndarray, src_rgb: np.ndarray, src_alpha: np.ndarray) -> None:
        """
        Alpha blending do RGBA vrstvy
        dst: subregion layer.image
        src_rgb: (H,W,3) alebo (3,)
        src_alpha: (H,W) 0..1
        """
        if src_alpha.size == 0:
            return

        src_a = np.clip(src_alpha, 0.0, 1.0)[..., None]
        if not np.any(src_a > 0):
            return

        dst_rgb = dst[..., :3].astype(np.float32) / 255.0
        dst_a = dst[..., 3:4].astype(np.float32) / 255.0

        if src_rgb.ndim == 1:
            src_rgb_f = src_rgb.astype(np.float32)[None, None, :] / 255.0
            src_rgb_f = np.broadcast_to(src_rgb_f, dst_rgb.shape)
        else:
            src_rgb_f = src_rgb.astype(np.float32) / 255.0

        out_a = src_a + dst_a * (1.0 - src_a)

        out_rgb = np.zeros_like(dst_rgb)
        valid = out_a[..., 0] > 1e-6
        out_rgb[valid] = (src_rgb_f[valid] * src_a[valid] + dst_rgb[valid] * dst_a[valid] * (1.0 - src_a[valid])) / out_a[valid]

        dst[..., :3] = np.clip(out_rgb * 255.0, 0, 255).astype(np.uint8)
        dst[..., 3] = np.clip(out_a[..., 0] * 255.0, 0, 255).astype(np.uint8)

    def _render_from_stroke_alpha(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        Renderuje aktuálny stav celého ťahu z pôvodného before_image
        -ťah sa môže vrstviť, ale nikdy neprekročí nastavené Krytí
        """
        if self._before_image is None or self._pass_alpha_u8 is None:
            return

        if x1 <= x0 or y1 <= y0:
            return

        sub = layer.image[y0:y1, x0:x1, :]
        before = self._before_image[y0:y1, x0:x1, :]

        pass_alpha = self._pass_alpha_u8[y0:y1, x0:x1].astype(np.uint16)

        if self._stroke_committed_alpha_u8 is not None:
            committed = self._stroke_committed_alpha_u8[y0:y1, x0:x1].astype(np.uint16)
        else:
            committed = np.zeros_like(pass_alpha, dtype=np.uint16)

        limit = self._opacity_limit_u8()
        allow_overlap = True
        if hasattr(self.controller, "get_brush_allow_overlap"):
            allow_overlap = bool(self.controller.get_brush_allow_overlap())

        if allow_overlap:
            alpha_u16 = np.minimum(committed + pass_alpha, limit)
        else:
            alpha_u16 = np.maximum(committed, pass_alpha)
            alpha_u16 = np.minimum(alpha_u16, limit)

        alpha = alpha_u16.astype(np.float32) / 255.0

        if not np.any(alpha > 0):
            return

        ts = getattr(self.controller, "texture_settings", None)
        texture_enabled = bool(getattr(self.controller, "paint_mode", "brush") == "texture")

        r_col, g_col, b_col, a_col = self.controller.project.get_current_color_rgba()
        if ts is not None:
            ts.color = (int(r_col), int(g_col), int(b_col))

        if texture_enabled and ts is not None and ts.texture is not None:
            h_sub = y1 - y0
            w_sub = x1 - x0
            pattern = generate_fill_pattern(ts, w_sub, h_sub, offset_x=x0, offset_y=y0)
            src_rgb = pattern[..., :3]
        else:
            src_rgb = np.array([r_col, g_col, b_col], dtype=np.uint8)

        sub[...] = before
        self._alpha_blend_rgba(sub, src_rgb, alpha)

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
        y_max = min(h, y + r + 1)
        x_min = max(0, x - r)
        x_max = min(w, x + r + 1)

        if x_max <= x_min or y_max <= y_min:
            return

        sh = y_max - y_min
        sw = x_max - x_min

        #kruhová maska v tomto subregion-e
        cx = x - x_min
        cy = y - y_min

        brush_mask = self._make_soft_mask(sh, sw, cx, cy, r)
        #damage mask obmedzenie
        if damage_mask is not None:
            dm_sub = damage_mask[y_min:y_max, x_min:x_max].astype(np.float32)
            brush_mask *= dm_sub

        if not np.any(brush_mask > 0):
            return

        flow = float(self.controller.get_brush_flow()) if hasattr(self.controller, "get_brush_flow") else 1.0

        ts = getattr(self.controller, "texture_settings", None)
        texture_enabled = bool(getattr(self.controller, "paint_mode", "brush") == "texture")
        if texture_enabled and ts is not None and ts.texture is not None:
            #pattern je pre tento subregion ukotvený offsetom (x_min,y_min) -nadväzuje na seba
            pattern = generate_fill_pattern(ts, sw, sh, offset_x=x_min, offset_y=y_min)
            local_alpha = (pattern[..., 3].astype(np.float32) / 255.0) * brush_mask * flow
        else:
            r_col, g_col, b_col, a_col = self.controller.project.get_current_color_rgba()
            local_alpha = brush_mask * (a_col / 255.0) * flow

        local_u8 = np.clip(local_alpha * 255.0, 0, 255).astype(np.uint8)

        if self._pass_alpha_u8 is None:
            h, w, _ = layer.image.shape
            self._pass_alpha_u8 = np.zeros((h, w), dtype=np.uint8)

        if self._stroke_committed_alpha_u8 is None:
            h, w, _ = layer.image.shape
            self._stroke_committed_alpha_u8 = np.zeros((h, w), dtype=np.uint8)

        alpha_sub = self._pass_alpha_u8[y_min:y_max, x_min:x_max]

        #počas jedného ťahu pixel nezosilňujeme opakovane
        #iba si pamätáme najsilnejšie pokrytie, ktoré daný ťah v tomto pixeli dosiahol
        np.maximum(alpha_sub, local_u8, out=alpha_sub)

        self._render_from_stroke_alpha(layer, x_min, y_min, x_max, y_max)

    def _draw_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        jednoduché kreslenie medzi dvoma bodmi (aby ťah nebol dierkovaný)
        prejde po úsečke medzi (x0, y0) a (x1, y1) a kreslíme draw_dot
        """
        self._maybe_start_new_pass(layer, x1 - x0, y1 - y0)
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
        self._stroke_seed = int(np.random.randint(0, 2**31 - 1))

        #pre undo si uložíme celú vrstvu
        self._before_image = layer.image.copy()

        h, w, _ = layer.image.shape
        self._stroke_committed_alpha_u8 = np.zeros((h, w), dtype=np.uint8)
        self._pass_alpha_u8 = np.zeros((h, w), dtype=np.uint8)
        self._last_dir = None
        #prvý bod
        self._draw_dot(layer, img_x, img_y)

        # po prvom bode – sync filled mask pre malú oblasť
        project = self.controller.project
        r = int(self.brush_size)
        fallback_bbox = (img_x - r, img_y - r, 2 * r + 1, 2 * r + 1)
        first_bbox = self._clamp_bbox_to_layer(layer, fallback_bbox)
        if project is not None and first_bbox is not None:
            project.sync_layer_filled_mask_from_alpha(layer.meta.id, first_bbox, mode="assign")

        #a refresh
        self.controller.refresh_canvas_region(first_bbox if first_bbox is not None else fallback_bbox)

        self._stroke_min_x = img_x
        self._stroke_max_x = img_x
        self._stroke_min_y = img_y
        self._stroke_max_y = img_y

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

        r = self.brush_size
        step_bbox = (
            min(self._last_x, img_x) - r,
            min(self._last_y, img_y) - r,
            abs(img_x - self._last_x) + 2 * r + 1,
            abs(img_y - self._last_y) + 2 * r + 1,
        )
       
        step_bbox = self._clamp_bbox_to_layer(layer, step_bbox)
        if step_bbox is None:
            self._last_x = img_x
            self._last_y = img_y
            return
        
        project = self.controller.project
        if project is not None:
            project.sync_layer_filled_mask_from_alpha(layer.meta.id, step_bbox)

        #refresh tej oblasti
        self.controller.refresh_canvas_region(step_bbox)

        self._last_x = img_x
        self._last_y = img_y
        #bbox celého ťahu
        self._stroke_min_x = min(self._stroke_min_x, prev_x, img_x)
        self._stroke_max_x = max(self._stroke_max_x, prev_x, img_x)
        self._stroke_min_y = min(self._stroke_min_y, prev_y, img_y)
        self._stroke_max_y = max(self._stroke_max_y, prev_y, img_y)

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if not self.is_drawing:
            return
        
        self.is_drawing = False

        layer = self._get_active_paint_layer()
        if layer is None or self._before_image is None:
            return
        h, w, _ = layer.image.shape

        #ak sa bbox nenastavil, tak celú vrstvu
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
            x1 = min(w, self._stroke_max_x + margin + 1)
            y1 = min(h, self._stroke_max_y + margin + 1)

        if x1 <= x0 or y1 <= y0:
            #nič sa reálne nekreslilo
            self._cleanup()
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

        project = self.controller.project
        if project is not None:
            project.sync_layer_filled_mask_from_alpha(layer.meta.id, bbox)
        self.controller.invalidate_selection_region_map_cache()

        #cleanup
        self._cleanup()

        self.controller.refresh_canvas_region(bbox)

    def _cleanup(self) -> None:
        self._before_image = None
        self._stroke_committed_alpha_u8 = None
        self._pass_alpha_u8 = None
        self._last_dir = None

        self._last_x = None
        self._last_y = None

        self._stroke_min_x = None
        self._stroke_min_y = None
        self._stroke_max_x = None
        self._stroke_max_y = None

    def _clamp_bbox_to_layer(self, layer, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return None

        H, W, _ = layer.image.shape

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(W, x + w)
        y1 = min(H, y + h)

        if x1 <= x0 or y1 <= y0:
            return None

        return (x0, y0, x1 - x0, y1 - y0)
    
    def get_cursor(self):
        if self.controller is None:
            return Qt.ArrowCursor

        #size -radius v image px
        radius = int(self.controller.get_brush_size())

        #ak je texture mode, cursor = textura
        if getattr(self.controller, "paint_mode", "brush") == "texture":
            return self.controller._make_texture_cursor(radius)

        #inak brush cursor s farbou current_color
        rgba = self.controller.project.get_current_color_rgba() if self.controller.project is not None else (0, 0, 0, 255)
        rgba_t = tuple(int(x) for x in rgba)
        return self.controller._make_brush_cursor(radius, rgba_t)