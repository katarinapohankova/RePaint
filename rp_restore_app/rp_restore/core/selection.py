from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Selection:
    """Reprezentuje jednu vybranú poškodenú oblasť"""
    region_mask: np.ndarray
    bbox: tuple[int, int, int, int]
    seed_point: tuple[int, int]
    region_id: int | None = None

    def __post_init__(self) -> None:
        """Skontroluje základný tvar výberu po vytvorení"""
        if self.region_mask.ndim != 2:
            raise ValueError("region_mask must be a 2D array")

        x, y, w, h = self.bbox
        if w < 0 or h < 0:
            raise ValueError("bbox width and height must be non-negative")

        if len(self.seed_point) != 2:
            raise ValueError("seed_point must contain x and y coordinates")

        self.region_mask = self.region_mask.astype(bool, copy=False)
        self.bbox = (int(x), int(y), int(w), int(h))
        self.seed_point = (int(self.seed_point[0]), int(self.seed_point[1]))



@dataclass
class SelectionSet:
    """Skupina jednej alebo viacerých vybraných poškodených oblastí"""
    selections: list[Selection]

    def is_empty(self) -> bool:
        """Vráti, či výber neobsahuje žiadnu oblasť"""
        return len(self.selections) == 0

    def combined_mask(self) -> np.ndarray:
        """
        Spojí masky všetkých vybraných oblastí do jednej bool masky
        """
        if self.is_empty():
            raise ValueError("SelectionSet is empty – no mask to combine")

        mask = self.selections[0].region_mask.astype(bool).copy()
        #všetky selection masky musia patriť k rovnakému obrazu
        for sel in self.selections[1:]:
            if sel.region_mask.shape != mask.shape:
                raise ValueError("All selection masks must have the same shape")
            mask |= sel.region_mask.astype(bool)
        return mask

    def combined_bbox(self) -> tuple[int, int, int, int]:
        """
        vráti najmenší bbox, ktorý pokrýva všetky vybrané oblasti
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
        """Vráti, či už výber obsahuje región s daným ID"""
        return any(sel.region_id == region_id for sel in self.selections)

    def add_selection(self, sel: Selection) -> None:
        """Pridá oblasť do výberu, ak tam ešte nie je podľa region_id"""
        #region_id=None nevieme porovnať, a preto taký výber vždy pridáme
        if sel.region_id is not None and self.contains_region_id(sel.region_id):
            return
        self.selections.append(sel)

    def remove_by_region_id(self, region_id: int) -> None:
        """Odstráni z výberu oblast so zadaným region_id"""
        self.selections = [sel for sel in self.selections if sel.region_id != region_id]
