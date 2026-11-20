from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class LayerRole(str, Enum):
    """Typ vrstvy v projekte"""

    BACKGROUND = "background"
    REFERENCE = "reference"
    EDGE = "edge"
    PAINT = "paint"

@dataclass
class LayerMeta:
    """Metadata o vrstve - bez samotných pixelov"""

    id: str     #interné ID vrstvy
    name: str   #názov, ktorý vidí užívateľ
    role: LayerRole #typ vrstvy
    visible: bool = True
    opacity: float = 1.0    #krytie vrstvy v rozsahu 0.0–1.0
    order: int = 0      #poradie vrstvy (zospodu hore)

class Layer:
    """Jedna vrstva projektu s metadátami a RGBA obrazom"""

    def __init__(self, meta: LayerMeta, image: np.ndarray) -> None:
        if image.ndim != 3 or image.shape[2] != 4:
            raise ValueError("Layer image must have shape (H, W, 4) – RGBA.")

        if image.dtype != np.uint8:
            raise ValueError("Layer image must have dtype uint8.")

        self.meta = meta
        self.image = image
        #maska vyplnených poškodených pixelov pre konkrétnu PAINT vrstvu
        self.damage_filled_mask: np.ndarray | None = None

    @property
    def size(self) -> tuple[int, int]:
        """Veľkosť vrstvy ako (width, height)"""
        h, w, _ = self.image.shape
        return w, h

    @property
    def width(self) -> int:
        """Šírka vrstvy v pixeloch"""
        return self.size[0]

    @property
    def height(self) -> int:
        """Výška vrstvy v pixeloch"""
        return self.size[1]

    def clone_subregion(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """Vráti kópiu pixelov z výrezu vrstvy"""
        if w <= 0 or h <= 0:
            #prázdny výrez má vždy RGBA tvar 
            return np.zeros((0, 0, 4), dtype=self.image.dtype)

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)

        if x1 <= x0 or y1 <= y0:
            return np.zeros((0, 0, 4), dtype=self.image.dtype)

        #vraciame kópiu, aby úpravy výrezu nemenili pôvodnú vrstvu
        return self.image[y0:y1, x0:x1, :].copy()

    def restore_subregion(self, x: int, y: int, data: np.ndarray) -> None:
        """Vloží RGBA výrez späť do vrstvy na pozíciu (x, y)"""
        if data.size == 0:
            return

        if data.ndim != 3 or data.shape[2] != 4:
            raise ValueError("Subregion data must have shape (h, w, 4).")

        if data.dtype != self.image.dtype:
            raise ValueError("Subregion data must have same dtype as layer image.")

        h, w, _ = data.shape

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)

        if x1 <= x0 or y1 <= y0:
            return

        #vyberieme iba tú časť data, ktorá sa vojde do vrstvy
        dx0 = x0 - x
        dy0 = y0 - y
        dx1 = dx0 + (x1 - x0)
        dy1 = dy0 + (y1 - y0)

        self.image[y0:y1, x0:x1, :] = data[dy0:dy1, dx0:dx1, :]
