from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt


class BaseTool:
    """
    Základná trieda pre nástroj
    každý nástroj má prístup k ProjectControlleru a ku canvasu a reaguje na udalosti myši v obrazových súradniciach
    """

    def __init__(self, controller: "ProjectController", canvas: "ImageCanvasWidget") -> None:
        self.controller = controller
        self.canvas = canvas

    def _refresh_segment_region(self, x0: int, y0: int, x1: int, y1: int, radius: int,) -> None:
        """
        z dvoch bodov a polomeru štetca spraví bbox a zavolá refresh_canvas_region
        """
        if self.controller is None:
            return

        margin = max(1, int(radius))
        x_min = min(x0, x1) - margin
        y_min = min(y0, y1) - margin
        x_max = max(x0, x1) + margin
        y_max = max(y0, y1) + margin

        w = x_max - x_min
        h = y_max - y_min
        if w <= 0 or h <= 0:
            return

        if hasattr(self.controller, "refresh_canvas_region"):
            self.controller.refresh_canvas_region((x_min, y_min, w, h))
        else:
            self.controller.refresh_canvas()

    #myš v image súradniciach:
    # img_x, img_y: int
    # buttons: Qt.MouseButtons
    # modifiers: Qt.KeyboardModifiers

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """reakcia na stlačenie myši"""
        return

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """reakcia na pohyb myši s tlačidlami"""
        return

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        """reakcia na uvoľnenie tlačidla myši"""
        return
