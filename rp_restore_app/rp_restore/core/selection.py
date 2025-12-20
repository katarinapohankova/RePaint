from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class Selection:
    """
    Reprezentuje vybranú poškodenú oblasť
    region_mask -2D bool pole tvaru (H, W)
    bbox (x, y, w, h) – minimálny obal oblasti
    seed_point -bod, kde užívateľ klikol
    region_id -necháme None, neskôr môžeme pridať ID z RegionMap
    """

    region_mask: np.ndarray
    bbox: Tuple[int, int, int, int]
    seed_point: Tuple[int, int]
    region_id: Optional[int] = None
