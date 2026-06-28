from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Set

import numpy as np

from .layers import Layer


@dataclass
class RegionInfo:
    id: int
    area: int
    bbox: Tuple[int, int, int, int]  #x, y, w, h


class RegionMap:
    """
    Rozdelenie damage masky na oblasti

    label_image: 2D pole int32, 0 = nič, >0 = ID oblasti
    regions: dict id -> RegionInfo
    """

    def __init__(self, label_image: np.ndarray, regions: Dict[int, RegionInfo]) -> None:
        self.label_image = label_image
        self.regions = regions

    def get_region_mask(self, region_id: int) -> np.ndarray:
        """Vráti 2D bool masku pre danú oblasť"""
        return self.label_image == region_id

    def get_regions_smaller_than(self, threshold: int) -> List[RegionInfo]:
        """Vráti zoznam oblastí, ktorých area < threshold (v počte pixelov)"""
        return [r for r in self.regions.values() if r.area < threshold]
    
    def get_region_id_at(self, x: int, y: int) -> int:
        """
        Vráti ID oblasti na súradniciach (x, y)
        -ak je mimo rozsah alebo tam nie je žiadna oblasť, vráti 0
        """
        h, w = self.label_image.shape
        if x < 0 or y < 0 or x >= w or y >= h:
            return 0
        return int(self.label_image[y, x])

    def has_region(self, region_id: int) -> bool:
        """
        True, ak taká oblasť existuje v region_map
        """
        return region_id in self.regions

    def get_region_bbox(self, region_id: int) -> Tuple[int, int, int, int] | None:
        """
        Vráti bbox oblasti podľa ID alebo None
        """
        info = self.regions.get(region_id)
        if info is None:
            return None
        return info.bbox

    def get_region_ids_smaller_than(self, threshold: int) -> List[int]:
        """
        Vráti len ID oblastí, ktorých area < threshold
        """
        return [r.id for r in self.regions.values() if r.area < threshold]

def build_region_map(damage_mask: np.ndarray, edge_layer: Layer | None = None) -> RegionMap:
    """
    Rozdelí damage_mask na spojité oblasti, pričom hrany (EDGE vrstvy)
    fungujú ako bariéry

    damage_mask -2D bool pole (True = poškodené miesto, ktoré chceme segmentovať)
    edge_layers -hraničné vrstvy – pixely s alfou > 0 tvoria bariéru
    """
    if damage_mask.ndim != 2:
        raise ValueError("damage_mask must be 2D bool array")

    h, w = damage_mask.shape

    #bariéry z EDGE vrstiev
    barrier = np.zeros_like(damage_mask, dtype=bool)
    if edge_layer is not None and edge_layer.image.shape[:2] == (h, w):
        barrier = edge_layer.image[..., 3] > 0

    #len tie pixely, ktoré sú poškodené a nie sú bariéra
    valid = damage_mask & ~barrier

    label_image = np.zeros((h, w), dtype=np.int32)
    regions: Dict[int, RegionInfo] = {}

    current_id = 1

    for y in range(h):
        for x in range(w):
            if not valid[y, x]:
                continue
            if label_image[y, x] != 0:
                continue

            #flood-fill pre novú oblasť
            stack = [(x, y)]
            label_image[y, x] = current_id

            area = 0
            x_min = x_max = x
            y_min = y_max = y

            while stack:
                cx, cy = stack.pop()
                area += 1

                if cx < x_min:
                    x_min = cx
                if cx > x_max:
                    x_max = cx
                if cy < y_min:
                    y_min = cy
                if cy > y_max:
                    y_max = cy

                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        if valid[ny, nx] and label_image[ny, nx] == 0:
                            label_image[ny, nx] = current_id
                            stack.append((nx, ny))

            bbox = (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)
            regions[current_id] = RegionInfo(id=current_id, area=area, bbox=bbox)
            current_id += 1

    return RegionMap(label_image, regions)
