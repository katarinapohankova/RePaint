from __future__ import annotations

from PySide6.QtCore import Qt

from rp_restore.gui.tools.base_tool import BaseTool


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

        selection = project.get_selection_from_click(img_x, img_y)
        self.controller.set_active_selection(selection)
        #neskôr -canvas highlight, algorithm panel enable/disable
