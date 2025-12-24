from __future__ import annotations

from typing import Iterable, TYPE_CHECKING

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from rp_restore.core.warnings import RegionReference


def draw_region_highlights(painter: QPainter, regions: Iterable["RegionReference"]) -> None:
    """
    Nakreslí polopriehľadné obdlžniky okolo bboxov z RegionReference
    """
    pen = QPen(QColor(255, 255, 0))
    pen.setWidth(2)
    pen.setStyle(Qt.DashLine)

    brush = QColor(255, 255, 0, 60)

    painter.setPen(pen)
    painter.setBrush(brush)

    for ref in regions:
        x, y, w, h = ref.bbox
        rect = QRect(x, y, w, h)
        painter.drawRect(rect)
