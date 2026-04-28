from __future__ import annotations

from PySide6.QtCore import Qt

from rp_restore.gui.tools.base_tool import BaseTool
from rp_restore.core.selection import SelectionSet
from rp_restore.core.layers import LayerRole


class LassoTool(BaseTool):
    """
    Laso nástroj:
    -užívateľ myšou nakreslí uzatvorenú čiaru
    -po pustení myši sa nájdu všetky damage oblasti vo vnútri polygonu a z nich sa vytvorí SelectionSet
    """

    def __init__(self, controller, canvas) -> None:
        super().__init__(controller, canvas)
        self.is_drawing: bool = False
        self.points: list[tuple[int, int]] = []

    def on_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not (buttons & Qt.LeftButton):
            return
        
        layer = self._get_active_paint_layer()
        if layer is None:
            self.controller.show_tool_message("Laso se dá použít jenom na PAINT vrstvě")
            return

        self.is_drawing = True
        self.points = [(img_x, img_y)]
        
        if hasattr(self.canvas, "set_lasso_preview_points"):
            self.canvas.set_lasso_preview_points(self.points)

    def on_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_drawing:
            return
        #pridáme bod len ak sa reálne posunul
        if not self.points or self.points[-1] != (img_x, img_y):
            self.points.append((img_x, img_y))

            if hasattr(self.canvas, "set_lasso_preview_points"):
                self.canvas.set_lasso_preview_points(self.points)

    def on_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifiers) -> None:
        if not self.is_drawing:
            return

        self.is_drawing = False

        if hasattr(self.canvas, "clear_lasso_preview"):
            self.canvas.clear_lasso_preview()

        if not self.points or self.points[-1] != (img_x, img_y):
            self.points.append((img_x, img_y))

        #na polygon potrebujeme aspoň 3 body
        if len(self.points) < 3:
            self.points = []
            return

        project = self.controller.project
        if project is None:
            self.points = []
            return

        region_map = self.controller.get_selection_region_map_for_active_layer()

        selection_set = project.get_selections_from_polygon(polygon_points=self.points, layer_id=self.controller.active_layer_id, region_map=region_map)

        ctrl_down = bool(modifiers & Qt.ControlModifier)

        if selection_set is None or selection_set.is_empty():
            if not ctrl_down:
                self.controller.clear_selection()
            self.points = []
            return

        current_set = self.controller.active_selection

        if not ctrl_down or current_set is None or current_set.is_empty():
            self.controller.set_selection(selection_set)
            self.points = []
            return

        #Ctrl (pridanie k existujúcemu výberu)
        for sel in selection_set.selections:
            current_set.add_selection(sel)

        self.controller.set_selection(current_set)
        self.points = []

    def _get_active_paint_layer(self):
        project = self.controller.project
        if project is None or self.controller.active_layer_id is None:
            return None

        for layer in project.layers:
            if layer.meta.id == self.controller.active_layer_id:
                if layer.meta.role == LayerRole.PAINT:
                    return layer
                return None
        return None