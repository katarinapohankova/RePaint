from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.core.texture_brush import generate_fill_pattern
from rp_restore.gui.tools.base_tool import BaseTool


class FillTool(BaseTool):
    """
    Nástroj na vyplnenie vybranej poškodenej oblasti na aktívnej PAINT vrstve
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)

        self.fill_color_rgba = self.controller.get_current_color_rgba()

    def _get_active_paint_layer(self):
        """Nájde aktívnu PAINT vrstvu podľa active_layer_id v controlleri"""
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
    
    def _blend_pattern_into(self, dst: np.ndarray, pattern: np.ndarray, mask: np.ndarray) -> None:
        """Vloží textúrový pattern do RGBA výrezu iba v pixeloch masky"""
        if dst.shape != pattern.shape:
            return
        if mask.shape != dst.shape[:2]:
            return

        src_rgb = pattern[..., :3].astype(np.float32) / 255.0
        src_a = pattern[..., 3:4].astype(np.float32) / 255.0
        dst_rgb = dst[..., :3].astype(np.float32) / 255.0
        dst_a = dst[..., 3:4].astype(np.float32) / 255.0

        m = mask.astype(np.float32)[..., None]
        src_a = src_a * m

        out_a = src_a + dst_a * (1.0 - src_a)

        out_rgb = np.zeros_like(dst_rgb)
        valid = out_a[..., 0] > 1e-6
        out_rgb[valid] = (src_rgb[valid] * src_a[valid] + dst_rgb[valid] * dst_a[valid] * (1.0 - src_a[valid])) / out_a[valid]

        dst[..., :3] = np.clip(out_rgb * 255.0, 0, 255).astype(np.uint8)
        dst[..., 3] = np.clip(out_a[..., 0] * 255.0, 0, 255).astype(np.uint8)

    def _update_color_from_controller(self) -> None:
        """Načíta aktuálnu farbu z controlleru"""
        self.fill_color_rgba = self.controller.get_current_color_rgba()

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """Vyplní kliknutú alebo aktuálne vybranú poškodenú oblasť"""
        if not (buttons & Qt.LeftButton):
            return

        self._update_color_from_controller()
        project = self.controller.project
        if project is None:
            return

        layer = self._get_active_paint_layer()
        if layer is None:
            self.controller.show_tool_message("Výplň lze použít pouze na vrstvě malby")
            return

        #ak existuje aktívny výber, vyplníme celý výber, inak oblasť pod kliknutím
        selection_set = getattr(self.controller, "active_selection", None)
        used_selection_set = (selection_set is not None and hasattr(selection_set, "is_empty") and not selection_set.is_empty())
        if used_selection_set:
            region_mask = selection_set.combined_mask()
            x, y, w, h = selection_set.combined_bbox()
        else:
            region_map = self.controller.get_selection_region_map_for_active_layer()
            selection = project.get_selection_from_click(img_x, img_y, layer_id=self.controller.active_layer_id, region_map=region_map)
            if selection is None:
                return
            region_mask = selection.region_mask
            x, y, w, h = selection.bbox

        #remaining maska je samostatná pre každú PAINT vrstvu
        remaining = project.get_layer_damage_remaining_mask(layer.meta.id)
        if remaining is None:
            self.controller.show_tool_message("Chybí maska poškození nebo aktivní vrstva není vrstva malby")
            return
        
        #vypĺňame iba pixely, ktoré na tejto vrstve ešte nie sú vyplnené
        effective_mask = region_mask & remaining 
        if not effective_mask.any():
            self.controller.show_tool_message("Tato oblast již byla na této vrstvě vyplněna")
            return
        
        #before uloží stav výrezu pred výplňou
        before = layer.clone_subregion(x, y, w, h)

        #lokálna maska pre vybraný výrez
        local_mask = effective_mask[y : y + h, x : x + w]

        sub_img = layer.image[y : y + h, x : x + w, :]
        paint_mode = getattr(self.controller, "paint_mode", "brush")
        ts = getattr(self.controller, "texture_settings", None)
        if paint_mode == "texture":
            if ts is None or ts.texture is None:
                self.controller.show_tool_message("Není vybrána žádná textura")
                return
            pattern = generate_fill_pattern(ts, w=w, h=h, offset_x=x, offset_y=y)
            self._blend_pattern_into(sub_img, pattern, local_mask)
        else:
            sub_img[local_mask] = self.fill_color_rgba

        #after uloží stav výrezu po výplni
        after = layer.clone_subregion(x, y, w, h)

        if np.array_equal(before, after):
            return

        action = UndoAction(description="Výplň oblasti", layer_id=layer.meta.id, layer_role=layer.meta.role, bbox=(x, y, w, h), before=before, after=after)

        project.undo_manager.push_action(action)
        project.mark_region_as_filled_on_layer(layer.meta.id, effective_mask)
        project.mark_dirty()
        self.controller.invalidate_selection_region_map_cache()

        if used_selection_set:
            self.controller.clear_selection()
        if hasattr(self.controller, "refresh_canvas_region"):
            self.controller.refresh_canvas_region((x, y, w, h))
        else:
            self.controller.refresh_canvas()