from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.gui.tools.base_tool import BaseTool


class EdgeTool(BaseTool):
    """
    Nástroj na kreslenie a mazanie hrán na aktívnej EDGE vrstve
    kreslené hrany slúžia ako bariéry pri výbere a výplni poškodených oblastí
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)

        self.is_drawing: bool = False
        self.is_erasing: bool = False
        self.brush_size = 1
        self.edge_color: np.ndarray = controller.get_edge_color_rgba()

        self._before_image: np.ndarray | None = None
        self._last_x: int | None = None
        self._last_y: int | None = None
        self._stroke_min_x: int | None = None
        self._stroke_min_y: int | None = None
        self._stroke_max_x: int | None = None
        self._stroke_max_y: int | None = None

    def _get_active_edge_layer(self):
        """Nájde aktívnu EDGE vrstvu podľa active_layer_id v controlleri"""
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
        """Nakreslí alebo vymaže jeden bod hrany"""
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

                #hrany kreslíme iba v damage maske
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

                #pixely s nulovou alfou netreba zapisovať
                if src_alpha <= 0:
                    continue

                dst = layer.image[yy, xx, :].astype(np.float32)
                old_a = dst[3] / 255.0
                new_a = src_alpha / 255.0

                out_a = max(old_a, new_a)

                if out_a <= 0:
                    layer.image[yy, xx, :] = 0
                    continue

                #farbu hrany berieme z aktuálneho edge nastavenia
                layer.image[yy, xx, 0:3] = src[0:3].astype(np.uint8)
                layer.image[yy, xx, 3] = int(out_a * 255)

    def _draw_line(self, layer, x0: int, y0: int, x1: int, y1: int) -> None:
        """Kreslí medzi dvoma bodmi tak, aby ťah nebol prerušovaný"""
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)

        for i in range(steps + 1):
            t = i / steps
            xx = int(round(x0 + t * dx))
            yy = int(round(y0 + t * dy))
            self._draw_dot(layer, xx, yy)

    def _update_settings_from_controller(self) -> None:
        """Načíta aktuálnu edge farbu z controlleru"""
        self.edge_color = self.controller.get_edge_color_rgba()

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """Začne nový ťah na EDGE vrstve"""
        if not ((buttons & Qt.LeftButton) or (buttons & Qt.RightButton)):
            return
        
        self.is_erasing = bool(buttons & Qt.RightButton) or bool(modifiers & Qt.ShiftModifier)

        #pri začiatku ťahu načítame aktuálnu farbu hrany
        self._update_settings_from_controller()

        layer = self._get_active_edge_layer()
        if layer is None:
            self.controller.show_tool_message("Hrany lze kreslit pouze na vrstvě hran")
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
        w = 2 * r + 1
        h = 2 * r + 1
        if hasattr(self.controller, "refresh_canvas_region"):
            self.controller.refresh_canvas_region((x0, y0, w, h))
        else:
            self.controller.refresh_canvas()

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """Pokračuje v kreslení alebo mazaní hrany počas ťahu"""
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
        """Ukončí ťah na EDGE vrstve a uloží undo akciu"""
        if not self.is_drawing:
            return

        self.is_drawing = False

        layer = self._get_active_edge_layer()
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
            #nič sa reálne nezmenilo
            self._cleanup()
            return

        bw = x1 - x0
        bh = y1 - y0

        before = self._before_image[y0:y1, x0:x1, :].copy()
        after = layer.image[y0:y1, x0:x1, :].copy()

        if np.array_equal(before, after):
            self._cleanup()
            return

        bbox = (x0, y0, bw, bh)

        description = "Mazání hran" if self.is_erasing else "Kreslení hran"
        action = UndoAction(description=description, layer_id=layer.meta.id, layer_role=layer.meta.role, bbox=bbox, before=before, after=after)

        self.controller.project.undo_manager.push_action(action)

        project = self.controller.project
        if project is not None and hasattr(project, "mark_dirty"):
            project.mark_dirty()

        self.controller.invalidate_selection_region_map_cache()

        #prekreslíme iba dotknutú oblasť canvasu
        self.controller.refresh_canvas_region(bbox)

        self._cleanup()

    def _cleanup(self) -> None:
        """Vyčistí dočasný stav po ťahu"""
        self.is_drawing = False
        self.is_erasing = False
        self._before_image = None
        self._last_x = None
        self._last_y = None
        self._stroke_min_x = None
        self._stroke_min_y = None
        self._stroke_max_x = None
        self._stroke_max_y = None


    def get_cursor(self):
        """Vráti kurzor nástroja na kreslenie hrán"""
        if self.controller is None:
            return Qt.CrossCursor
        return self.controller._make_edge_cursor()