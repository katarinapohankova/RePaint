from __future__ import annotations

from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt
import numpy as np

def draw_selection_highlight(painter: QPainter, selection_mask: np.ndarray) -> None:
    """
    Nakreslí polopriehľadné zvýraznenie podľa 2D bool selection_mask
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
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    ptr = img.bits()
    buf = np.frombuffer(ptr, np.uint8).reshape((h, w, 4))

    #v pamäti je poradie kanálov BGRA
    buf[..., 0] = 0 #B
    buf[..., 1] = 255   #G
    buf[..., 2] = 255   #R
    buf[..., 3] = np.where(mask, 80, 0).astype(np.uint8)  #A

    painter.drawImage(0, 0, img)