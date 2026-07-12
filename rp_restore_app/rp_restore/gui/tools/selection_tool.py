from __future__ import annotations

from PySide6.QtCore import Qt

from rp_restore.gui.tools.base_tool import BaseTool
from rp_restore.core.selection import SelectionSet


class SelectionTool(BaseTool):
    """
    Nástroj na výber poškodených oblastí kliknutím
    pri podržaní Ctrl pridáva alebo odoberá oblasti z aktuálneho výberu
    """

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """Vyberie oblasť pod kurzorom alebo upraví aktuálny výber pri Ctrl kliknutí"""
        if not (buttons & Qt.LeftButton):
            return

        project = self.controller.project
        if project is None:
            return

        region_map = self.controller.get_selection_region_map_for_active_layer()
        selection = project.get_selection_from_click(img_x, img_y, layer_id=self.controller.active_layer_id, region_map=region_map)
        ctrl_down = bool(modifiers & Qt.ControlModifier)

        #na kliknutom mieste nie je žiadna vyberateľná oblasť
        if selection is None:
            if not ctrl_down:
                #bez Ctrl zrušíme aktuálny výber
                self.controller.clear_selection()
            return

        current_set = self.controller.active_selection

        if not ctrl_down or current_set is None or current_set.is_empty():
            #bez Ctrl alebo bez existujúceho výberu vytvoríme nový SelectionSet
            new_set = SelectionSet(selections=[selection])
            self.controller.set_selection(new_set)
            return

        #pri Ctrl kliknutí existujúcu oblasť odoberieme, inak pridáme novú
        if selection.region_id is not None and current_set.contains_region_id(selection.region_id):
            current_set.remove_by_region_id(selection.region_id)
            if current_set.is_empty():
                self.controller.clear_selection()
            else:
                self.controller.set_selection(current_set)
        else:
            current_set.add_selection(selection)
            self.controller.set_selection(current_set)
