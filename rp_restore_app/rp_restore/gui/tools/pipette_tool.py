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
        
        x0 = max(0, img_x - 2)
        y0 = max(0, img_y - 2)
        x1 = img_x + 3
        y1 = img_y + 3

        w = max(0, x1 - x0)
        h = max(0, y1 - y0)
        if w <= 0 or h <= 0:
            return

        patch = project.composited_region((x0, y0, w, h))
        if patch.size == 0:
            return

        pixels = patch.reshape(-1, 3)
        color = np.median(pixels, axis=0)
        r, g, b = [int(round(c)) for c in color.tolist()]
        a = 255

        self.controller.set_current_color_rgba((r, g, b, 255))
        self.controller.show_tool_message(f"Vybraná barva pipetou: R={r}, G={g}, B={b}")

    def get_cursor(self):
        return Qt.CrossCursor