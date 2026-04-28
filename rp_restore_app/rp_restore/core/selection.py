from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

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


@dataclass
class SelectionSet:
    """
    Pre výber viacerých poškodených oblastí naraz (pomocou ctrl)
    """
    selections: List[Selection]

    def is_empty(self) -> bool:
        return len(self.selections) == 0

    def combined_mask(self) -> np.ndarray:
        """
        OR všetkých region_mask
        """
        if self.is_empty():
            raise ValueError("SelectionSet is empty – no mask to combine")

        mask = self.selections[0].region_mask.astype(bool).copy()
        for sel in self.selections[1:]:
            if sel.region_mask.shape != mask.shape:
                raise ValueError("All selection masks must have the same shape")
            mask |= sel.region_mask.astype(bool)
        return mask

    def combined_bbox(self) -> Tuple[int, int, int, int]:
        """
        Najmenší bbox, ktorý pokrýva všetky selection bboxy
        """
        if self.is_empty():
            return 0, 0, 0, 0

        xs_min = []
        ys_min = []
        xs_max = []
        ys_max = []
        for sel in self.selections:
            x, y, w, h = sel.bbox
            xs_min.append(x)
            ys_min.append(y)
            xs_max.append(x + w)
            ys_max.append(y + h)

        x_min = min(xs_min)
        y_min = min(ys_min)
        x_max = max(xs_max)
        y_max = max(ys_max)
        return x_min, y_min, x_max - x_min, y_max - y_min

    def contains_region_id(self, region_id: int) -> bool:
        return any(sel.region_id == region_id for sel in self.selections)

    def add_selection(self, sel: Selection) -> None:
        """
        Pridá nový selection, ak ešte nie je v zozname (podľa region_id)
        -ak region_id je None, tak to pridáme vždy
        """
        if sel.region_id is not None and self.contains_region_id(sel.region_id):
            return
        self.selections.append(sel)

    def remove_by_region_id(self, region_id: int) -> None:
        self.selections = [sel for sel in self.selections if sel.region_id != region_id]

    def extend_unique(self, other: "SelectionSet") -> None:
        """
        Pridá selections z iného set bez duplicít podľa region_id
        """
        for sel in other.selections:
            self.add_selection(sel)