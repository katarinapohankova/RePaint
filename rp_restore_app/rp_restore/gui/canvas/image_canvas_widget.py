from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


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

        self.setMinimumSize(400, 300)
        self.setAutoFillBackground(True)

    def set_image(self, image: QImage) -> None:
        """Nastaví nový obraz a prekreslí widget."""
        self.current_image = image
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
