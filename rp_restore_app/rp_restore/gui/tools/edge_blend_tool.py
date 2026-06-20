from __future__ import annotations

from typing import List, Optional

import numpy as np
from PySide6.QtCore import Qt

try:
    import cv2
except Exception:
    cv2 = None

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import Layer, LayerRole
from rp_restore.core.edge_blend import blend_across_edge
from rp_restore.gui.tools.base_tool import BaseTool


class EdgeBlendTool(BaseTool):
    """
    Nástroj na zjemnenie už existujúcej hrany

    keď hrana rozdelila poškodenú oblasť a obe strany sú vyplnené, tak zjemní prechod medzi vyplnenými časťami
      -zistí, kadiaľ používateľ prešiel po existujúcej EDGE čiare
      -odstráni túto EDGE čiaru
      -na aktívnej PAINT vrstve vytvorí zjemnený prechod
      -doplní miesto po hrane, aby nezostala prázdna medzera
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)

        self.is_drawing: bool = False
        self.stroke_radius = 2

        #2D maska, kade užívateľ prešiel
        self._stroke_mask: Optional[np.ndarray] = None

        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None

        self._bx0: Optional[int] = None
        self._by0: Optional[int] = None
        self._bx1: Optional[int] = None
        self._by1: Optional[int] = None

    def _project(self):
        return self.controller.project
    
    def _active_paint_layer(self):
        """
        Vráti aktívnu vrstvu iba vtedy, ak je to PAINT vrstva
        """
        project = self._project()
        if project is None or self.controller.active_layer_id is None:
            return None

        for layer in project.layers:
            if layer.meta.id == self.controller.active_layer_id:
                if layer.meta.role == LayerRole.PAINT:
                    return layer
                return None

        return None

    def _stamp(self, x: int, y: int) -> None:
        """
        Pridá kruh do stroke masky
        """
        if self._stroke_mask is None:
            return

        r = self.stroke_radius

        if cv2 is not None:
            cv2.circle(self._stroke_mask, (int(x), int(y)), int(r), 1, thickness=-1)
        else:
            h, w = self._stroke_mask.shape
            y0 = max(0, y - r)
            y1 = min(h, y + r + 1)
            x0 = max(0, x - r)
            x1 = min(w, x + r + 1)

            yy, xx = np.ogrid[y0:y1, x0:x1]
            circle = (xx - x) ** 2 + (yy - y) ** 2 <= r * r
            sub = self._stroke_mask[y0:y1, x0:x1]
            sub[circle] = 1

        self._bx0 = x - r if self._bx0 is None else min(self._bx0, x - r)
        self._by0 = y - r if self._by0 is None else min(self._by0, y - r)
        self._bx1 = x + r if self._bx1 is None else max(self._bx1, x + r)
        self._by1 = y + r if self._by1 is None else max(self._by1, y + r)

    def _stamp_line(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        Spojí dva body súvislou stopou
        """
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)

        for i in range(steps + 1):
            t = i / steps
            xx = int(round(x0 + t * dx))
            yy = int(round(y0 + t * dy))
            self._stamp(xx, yy)

    def _edge_union_alpha(self, edge_layers: List[Layer]) -> Optional[np.ndarray]:
        """
        Spojí alfa kanály všetkých EDGE vrstiev do jednej bool masky
        """
        if not edge_layers:
            return None

        union = None
        for layer in edge_layers:
            alpha = layer.image[..., 3] > 0
            union = alpha if union is None else (union | alpha)

        return union

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not (buttons & Qt.LeftButton):
            return

        project = self._project()
        if project is None or project.damage_original_mask is None:
            self.controller.show_tool_message("Projekt nemá damage masku")
            return

        if self._active_paint_layer is None:
            self.controller.show_tool_message("Zjemnění hrany lze použít pouze na PAINT vrstvě")
            return

        if not project.get_edge_layers():
            self.controller.show_tool_message("V projektu není žádná EDGE vrstva s hranou")
            return

        h, w = project.damage_original_mask.shape
        self._stroke_mask = np.zeros((h, w), dtype=np.uint8)

        self._bx0 = None
        self._by0 = None
        self._bx1 = None
        self._by1 = None

        self.is_drawing = True
        self._last_x = img_x
        self._last_y = img_y

        self._stamp(img_x, img_y)

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_drawing or self._stroke_mask is None:
            return

        if self._last_x is None or self._last_y is None:
            self._last_x = img_x
            self._last_y = img_y

        self._stamp_line(self._last_x, self._last_y, img_x, img_y)

        self._last_x = img_x
        self._last_y = img_y

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_drawing:
            return

        self.is_drawing = False

        project = self._project()
        if project is None or self._stroke_mask is None or project.damage_original_mask is None:
            self._reset()
            return

        active = self._active_paint_layer()
        if active is None:
            self.controller.show_tool_message("Zjemnění hrany lze použít pouze na PAINT vrstvě")
            self._reset()
            return

        damage = project.damage_original_mask.astype(bool)
        edge_layers = project.get_edge_layers()
        edge_union = self._edge_union_alpha(edge_layers)

        if edge_union is None:
            self._reset()
            return

        stroke = self._stroke_mask > 0
        edge_hit = stroke & edge_union & damage

        if not edge_hit.any():
            self.controller.show_tool_message("Zjemnění funguje jen tam, kde je nakreslená hrana")
            self._reset()
            return

        buffer = int(self.controller.get_edge_blend_buffer())

        ys, xs = np.where(edge_hit)
        pad = buffer + self.stroke_radius + 2

        H, W = damage.shape
        x0 = max(0, int(xs.min()) - pad)
        y0 = max(0, int(ys.min()) - pad)
        x1 = min(W, int(xs.max()) + pad + 1)
        y1 = min(H, int(ys.max()) + pad + 1)

        bw = x1 - x0
        bh = y1 - y0

        if bw <= 0 or bh <= 0:
            self._reset()
            return

        filled = project._compute_filled_mask_from_layers()
        if filled is None:
            self.controller.show_tool_message("Chybí maska vyplněných oblastí")
            self._reset()
            return

        damage_c = damage[y0:y1, x0:x1]
        filled_c = filled[y0:y1, x0:x1]
        edge_hit_c = edge_hit[y0:y1, x0:x1]

        #dočasne odstránime hranu z composited náhľadu, aby sa EDGE čiara nedostala do výpočtu zjemnenia
        prev_cc = getattr(project, "color_correction_enabled", False)
        saved_edge_subimages = []

        try:
            for edge_layer in edge_layers:
                edge_sub = edge_layer.image[y0:y1, x0:x1, :]
                saved_edge_subimages.append((edge_layer, edge_sub.copy()))
                edge_sub[edge_hit_c] = 0

            project.color_correction_enabled = False
            comp = project.composited_region((x0, y0, bw, bh))

        finally:
            project.color_correction_enabled = prev_cc

            for edge_layer, saved_sub in saved_edge_subimages:
                edge_layer.image[y0:y1, x0:x1, :] = saved_sub

        band_c, blended_c = blend_across_edge(composited_rgb=comp, damage_mask=damage_c, edge_remove_mask=edge_hit_c, filled_mask=filled_c, buffer=buffer)

        if band_c is None or blended_c is None:
            self.controller.show_tool_message("Není co zjemnit – nejprve vyplňte oblasti po obou stranách hrany")
            self._reset()
            return

        #pripravíme zmeny EDGE vrstvy
        extra_edge_actions: list[UndoAction] = []

        for edge_layer in edge_layers:
            sub_hit = edge_hit[y0:y1, x0:x1]
            if not sub_hit.any():
                continue

            before_edge = edge_layer.image[y0:y1, x0:x1, :].copy()

            edge_sub = edge_layer.image[y0:y1, x0:x1, :]
            edge_sub[sub_hit] = 0

            after_edge = edge_layer.image[y0:y1, x0:x1, :].copy()

            if np.array_equal(before_edge, after_edge):
                continue

            extra_edge_actions.append(UndoAction(description="Zjemnění hrany – odstranění hrany", layer_id=edge_layer.meta.id, layer_role=edge_layer.meta.role, bbox=(x0, y0, bw, bh), before=before_edge, after=after_edge))

            project.on_edge_layer_modified(edge_layer.meta.id)

        #zjemnenie zapíšeme do aktívnej PAINT vrstvy
        before_paint = active.image[y0:y1, x0:x1, :].copy()

        paint_sub = active.image[y0:y1, x0:x1, :]
        rgb_sub = paint_sub[..., :3]
        alpha_sub = paint_sub[..., 3]

        rgb_sub[band_c] = blended_c[band_c]
        alpha_sub[band_c] = 255

        after_paint = active.image[y0:y1, x0:x1, :].copy()

        #jedna spoločná undo akcia (hlavná je PAINT, EDGE zmeny sú extra_actions)
        if not np.array_equal(before_paint, after_paint) or extra_edge_actions:
            project.undo_manager.push_action(UndoAction(description="Zjemnění hrany", layer_id=active.meta.id, layer_role=active.meta.role, bbox=(x0, y0, bw, bh), before=before_paint, after=after_paint, extra_actions=extra_edge_actions))

        band_full = np.zeros_like(damage, dtype=bool)
        band_full[y0:y1, x0:x1] = band_c
        project.mark_region_as_filled_on_layer(active.meta.id, band_full)

        project.mark_dirty()

        if hasattr(self.controller, "invalidate_selection_region_map_cache"):
            self.controller.invalidate_selection_region_map_cache()

        self.controller.refresh_log_panel()
        self.controller.refresh_canvas_region((x0, y0, bw, bh))

        self._reset()

    def _reset(self) -> None:
        self._stroke_mask = None
        self._last_x = None
        self._last_y = None
        self._bx0 = None
        self._by0 = None
        self._bx1 = None
        self._by1 = None

    def get_cursor(self):
        if hasattr(self.controller, "_make_edge_blend_cursor"):
            return self.controller._make_edge_blend_cursor()
        return super().get_cursor()
    