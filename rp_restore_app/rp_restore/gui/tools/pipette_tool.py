from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt

from rp_restore.gui.tools.base_tool import BaseTool

class PipetteTool(BaseTool):
    """
    Pipeta
      - klikneme na obrázok
      - nástroj prečíta farbu z aktuálneho composited obrazu
      - nastaví ju ako aktuálnu farbu v Projecte (a teda aj pre Brush/Fill)
    """

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not (buttons & Qt.LeftButton):
            return

        project = self.controller.project
        if project is None:
            return

        composited = project.get_current_composited_image()  #(H, W, 3)
        h, w, _ = composited.shape

        if img_x < 0 or img_y < 0 or img_x >= w or img_y >= h:
            return

        rgb = composited[img_y, img_x, :]
        r, g, b = [int(c) for c in rgb.tolist()]
        a = 255

        self.controller.set_current_color_rgba((r, g, b, a))
        self.controller.show_tool_message(f"Vybraná barva pipetou: R={r}, G={g}, B={b}")
