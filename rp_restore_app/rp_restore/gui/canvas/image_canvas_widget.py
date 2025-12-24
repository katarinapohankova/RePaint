from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from typing import List, Optional, TYPE_CHECKING

from .overlay_highlight import draw_region_highlights

if TYPE_CHECKING:
    from rp_restore.core.warnings import RegionReference


class ImageCanvasWidget(QWidget):
    """
    reprezentuje hlavnú kresliacu plochu
    zatiaľ:
      - drží aktuálny QImage
      - vykreslí ho v paintEvent
      - bez myšovej interakcie, zoomu a posúvania
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.current_image: QImage | None = None

        #zatiaľ len tak
        self.zoom_factor: float = 1.0
        self.pan_offset_x: int = 0
        self.pan_offset_y: int = 0

        self.controller = None

        self._highlight_regions: List["RegionReference"] = []

        self.setMinimumSize(400, 300)
        self.setAutoFillBackground(True)

    def set_image(self, image: QImage) -> None:
        """Nastaví nový obraz a prekreslí widget."""
        self.current_image = image
        self.update()

    def set_controller(self, controller) -> None:
        """nastaví controller, ktorému budeme posielať udalosti myši"""
        self.controller = controller

    def set_highlight_for_regions(self, regions: Optional[List["RegionReference"]]) -> None:
        """
        Nastaví zoznam regionov na zvýraznenie -podľa warningu...
        """
        self._highlight_regions = regions or []
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None: 
        painter = QPainter(self)

        #vyplníme pozadie -čiernou
        painter.fillRect(self.rect(), Qt.black)

        if self.current_image is None or self.current_image.isNull():
            return

        #zatiaľ bez zoomu 
        #nakreslíme obraz do ľavého horného rohu
        painter.drawImage(0, 0, self.current_image)
        
        #overlay highlight (warningy / selection)
        if self._highlight_regions:
            draw_region_highlights(painter, self._highlight_regions)

    #--------myš--------
    def _map_widget_to_image(self, x: int, y: int) -> tuple[int, int] | None:
        """
        prepočet súradníc z widgetu na obrázok
        zatiaľ:
          - žiadny zoom
          - obraz je v ľavom hornom rohu
          - ak klikne mimo obrázok, vráti None
        """
        if self.current_image is None:
            return None

        img_w = self.current_image.width()
        img_h = self.current_image.height()

        if x < 0 or y < 0 or x >= img_w or y >= img_h:
            return None

        return int(x), int(y)

    def mousePressEvent(self, event):  
        if self.controller is None or self.current_image is None:
            return

        pos = event.position()
        mapped = self._map_widget_to_image(int(pos.x()), int(pos.y()))
        if mapped is None:
            return

        img_x, img_y = mapped
        self.controller.on_canvas_mouse_press(img_x, img_y, event.buttons(), event.modifiers())

    def mouseMoveEvent(self, event): 
        if self.controller is None or self.current_image is None:
            return

        pos = event.position()
        mapped = self._map_widget_to_image(int(pos.x()), int(pos.y()))
        if mapped is None:
            return

        img_x, img_y = mapped
        self.controller.on_canvas_mouse_move(
            img_x,
            img_y,
            event.buttons(),
            event.modifiers(),
        )

    def mouseReleaseEvent(self, event):  
        if self.controller is None or self.current_image is None:
            return

        pos = event.position()
        mapped = self._map_widget_to_image(int(pos.x()), int(pos.y()))
        if mapped is None:
            return

        img_x, img_y = mapped
        self.controller.on_canvas_mouse_release(
            img_x,
            img_y,
            event.buttons(),
            event.modifiers(),
        )

