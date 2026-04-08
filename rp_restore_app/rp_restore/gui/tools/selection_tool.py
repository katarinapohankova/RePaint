from __future__ import annotations

from PySide6.QtCore import Qt

from rp_restore.gui.tools.base_tool import BaseTool
from rp_restore.core.selection import SelectionSet


class SelectionTool(BaseTool):
    """
    Nástroj na výber jednej poškodenej oblasti

    zatiaľ:
      - len uloží Selection do controller.active_selection
      - nevyužíva undo a nič nemení
    """

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not (buttons & Qt.LeftButton):
            return

        project = self.controller.project
        if project is None:
            return

        region_map = self.controller.get_selection_region_map_for_active_layer()
        selection = project.get_selection_from_click(img_x, img_y, layer_id=self.controller.active_layer_id, region_map=region_map)
        ctrl_down = bool(modifiers & Qt.ControlModifier)

        #žiadna oblasť na danom mieste
        if selection is None:
            if not ctrl_down:
                #bez ctrl –zrušíme výber
                self.controller.clear_selection()
            return

        #validná Selection
        current_set = self.controller.active_selection

        if not ctrl_down or current_set is None or current_set.is_empty():
            #bez ctrl alebo zatiaľ nič vybrané ->nový set len s týmto výberom
            new_set = SelectionSet(selections=[selection])
            self.controller.set_selection(new_set)
            return

        #ctrl + klik + existujúci výber
        if selection.region_id is not None and current_set.contains_region_id(selection.region_id):
            #odstránime túto oblasť
            current_set.remove_by_region_id(selection.region_id)
            if current_set.is_empty():
                self.controller.clear_selection()
            else:
                self.controller.set_selection(current_set)
        else:
            #pridáme novú oblasť
            current_set.add_selection(selection)
            self.controller.set_selection(current_set)
