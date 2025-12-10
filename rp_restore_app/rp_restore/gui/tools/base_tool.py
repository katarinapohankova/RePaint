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
