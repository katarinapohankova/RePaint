from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

import numpy as np


class LayerRole(str, Enum):
    """Typ vrstvy v projekte"""

    BACKGROUND = "background"
    EDGE = "edge"
    PAINT = "paint"


@dataclass
class LayerMeta:
    """Metadata o vrstve – bez samotných pixelov"""

    id: str     #interné ID, napr. "layer_1"
    name: str   #názov, ktorý vidí užívateľ
    role: LayerRole #BACKGROUND / EDGE / PAINT
    visible: bool = True
    opacity: float = 1.0    #0.0–1.0
    order: int = 0      #poradie vrstvy (zospodu hore)
    path: str | None = None # cesta v ZIPe (zatiaľ None)


class Layer:
    """
    Jedna vrstva v projekte – metadata + RGBA obraz
    image: numpy pole tvaru (height, width, 4), dtype=uint8
    """

    def __init__(self, meta: LayerMeta, image: np.ndarray) -> None:
        if image.ndim != 3 or image.shape[2] != 4:
            raise ValueError("Layer image must have shape (H, W, 4) – RGBA.")

        if image.dtype != np.uint8:
            raise ValueError("Layer image must have dtype uint8.")

        self.meta = meta
        self.image = image
        self.damage_filled_mask: np.ndarray | None = None

    @property
    def size(self) -> Tuple[int, int]:
        """(width, height) obrázka vo vrstve"""
        h, w, _ = self.image.shape
        return w, h

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    def clone_subregion(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """
        Vráti kópiu pixelov z obdĺžnika (x, y, w, h)
        Ak obdĺžnik presahuje okraj, oreže ho podľa hraníc vrstvy
        """
        if w <= 0 or h <= 0:
            #prázdne pole 0x0x4
            return np.zeros((0, 0, 4), dtype=self.image.dtype)

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)

        if x1 <= x0 or y1 <= y0:
            return np.zeros((0, 0, 4), dtype=self.image.dtype)

        #copy() – aby sa zmeny mimo tejto kópie nedotýkali vrstvy
        return self.image[y0:y1, x0:x1, :].copy()

    def restore_subregion(self, x: int, y: int, data: np.ndarray) -> None:
        """
        Vloží dané pixely späť do vrstvy na pozíciu (x, y)
        Ak data presahujú okraj vrstvy, oreže sa podľa hraníc 
        """
        if data.size == 0:
            return

        if data.ndim != 3 or data.shape[2] != 4:
            raise ValueError("Subregion data must have shape (h, w, 4).")

        h, w, _ = data.shape

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)

        if x1 <= x0 or y1 <= y0:
            return

        #vypočítame, ktorá časť 'data' sa skutočne vojde do vrstvy
        dx0 = x0 - x
        dy0 = y0 - y
        dx1 = dx0 + (x1 - x0)
        dy1 = dy0 + (y1 - y0)

        self.image[y0:y1, x0:x1, :] = data[dy0:dy1, dx0:dx1, :]
