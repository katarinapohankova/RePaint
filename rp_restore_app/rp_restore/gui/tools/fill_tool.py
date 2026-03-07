from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.core.history import UndoAction
from rp_restore.core.layers import LayerRole
from rp_restore.gui.tools.base_tool import BaseTool


class FillTool(BaseTool):
    """
    Bucket fill 
      - nájde oblasť poškodenia pod kurzorom
      -vyplní ju farbou na aktívnej PAINT vrstve
      - vytvorí UndoAction
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)

        self.fill_color_rgba = self.controller.get_current_color_rgba()     #np.array([0, 0, 255, 255], dtype=np.uint8)

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

    def _update_color_from_controller(self) -> None:
        self.fill_color_rgba = self.controller.get_current_color_rgba()

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not (buttons & Qt.LeftButton):
            return

        self._update_color_from_controller()
        project = self.controller.project
        if project is None:
            return

        layer = self._get_active_paint_layer()
        if layer is None:
            #aktívna vrstva nie je PAINT 
            self.controller.show_tool_message("Fill sa dá použiť len na PAINT vrstvách")
            return

        #z projektu si vypýtame selection (podľa damage_remaining_mask)
        selection_set = getattr(self.controller, "active_selection", None)
        if (selection_set is not None and hasattr(selection_set, "is_empty") and not selection_set.is_empty()):
            #multi-selection: combined mask + bbox
            region_mask = selection_set.combined_mask()
            x, y, w, h = selection_set.combined_bbox()
        else:
            selection = project.get_selection_from_click(img_x, img_y)
            if selection is None:
                return
            region_mask = selection.region_mask
            x, y, w, h = selection.bbox 

        #per-layer remaining mask
        remaining = project.get_layer_damage_remaining_mask(layer.meta.id)
        if remaining is None:
            self.controller.show_tool_message("Chybí damage maska alebo aktivní vrstva není PAINT")
            return
        
        #iba to čo na tejto vrstve ešte nie je vyplnené
        effective_mask = region_mask & remaining 
        if not effective_mask.any():
            self.controller.show_tool_message("Tahle oblast již bylo na této vrstvě vyplněná")
            return
        
        #before – uložíme subregion
        before = layer.clone_subregion(x, y, w, h)

        #lokálna maska pre subregion
        local_mask = effective_mask[y : y + h, x : x + w]

        #vyplnenie vo vrstve
        sub_img = layer.image[y : y + h, x : x + w, :]
        sub_img[local_mask] = self.fill_color_rgba

        #after – aktuálny stav subregionu
        after = layer.clone_subregion(x, y, w, h)

        action = UndoAction(description="Fill region", layer_id=layer.meta.id, layer_role=layer.meta.role, bbox=(x, y, w, h), before=before, after=after)

        project.undo_manager.push_action(action)
        project.mark_region_as_filled_on_layer(layer.meta.id, effective_mask)
        if hasattr(self.controller, "refresh_canvas_region"):
            self.controller.refresh_canvas_region((x, y, w, h))
        else:
            self.controller.refresh_canvas()