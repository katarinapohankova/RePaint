from __future__ import annotations

from typing import Iterable, TYPE_CHECKING

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtCore import Qt
import numpy as np

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

def draw_selection_highlight(painter: QPainter, selection_mask: np.ndarray) -> None:
    """
    Nakreslí polopriehľadný overlay podľa 2D bool selection_mask
    """
    if selection_mask is None:
        return
    if selection_mask.ndim != 2:
        return

    mask = selection_mask.astype(bool)
    h, w = mask.shape
    if h == 0 or w == 0:
        return

    #vytvoríme ARGB QImage s tyrkysovým overlayom
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)

    ptr = img.bits()
    #ptr.setsize(h * w * 4)
    buf = np.frombuffer(ptr, np.uint8).reshape((h, w, 4))

    #RGBA: (0, 255, 255, alpha) pre pixely v maske, inak alpha = 0
    buf[..., 0] = 0 #B
    buf[..., 1] = 255   #G
    buf[..., 2] = 255   #R
    buf[..., 3] = np.where(selection_mask, 80, 0).astype(np.uint8)  #A

    painter.drawImage(0, 0, img)