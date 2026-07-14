from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .layers import Layer


@dataclass
class RegionInfo:
    """Informácie o jednej spojitej oblasti damage masky"""
    id: int
    area: int
    bbox: tuple[int, int, int, int]

@dataclass
class RegionMap:
    """Rozdelenie damage masky na očíslované spojité oblasti"""

    label_image: np.ndarray
    regions: dict[int, RegionInfo]

    def get_region_mask(self, region_id: int) -> np.ndarray:
        """Vráti 2D bool masku pre danú oblasť"""
        return self.label_image == region_id

    def get_region_id_at(self, x: int, y: int) -> int:
        """
        Vráti ID oblasti na súradniciach (x, y) alebo 0 mimo regiónov
        """
        h, w = self.label_image.shape
        if x < 0 or y < 0 or x >= w or y >= h:
            return 0
        return int(self.label_image[y, x])

    def has_region(self, region_id: int) -> bool:
        """
        Vráti, či región s daným ID existuje
        """
        return region_id in self.regions

    def get_region_bbox(self, region_id: int) -> tuple[int, int, int, int] | None:
        """
        Vráti bbox regiónu alebo None, ak región neexistuje
        """
        info = self.regions.get(region_id)
        if info is None:
            return None
        return info.bbox

    def get_region_ids_smaller_than(self, threshold: int) -> list[int]:
        """
        Vráti len ID regiónov menších ako zadaný prah
        """
        return [r.id for r in self.regions.values() if r.area < threshold]

def build_region_map(damage_mask: np.ndarray, edge_layer: Layer | None = None) -> RegionMap:
    """Rozdelí damage masku na spojité oblasti oddelené EDGE bariérami"""
    if damage_mask.ndim != 2:
        raise ValueError("damage_mask must be 2D bool array")

    h, w = damage_mask.shape

    #pixely s alfou v EDGE vrstve berieme ako bariéru
    barrier = np.zeros_like(damage_mask, dtype=bool)
    if edge_layer is not None:
        if edge_layer.image.shape[:2] != (h, w):
            raise ValueError("edge_layer must have the same size as damage_mask")

        barrier = edge_layer.image[..., 3] > 0

    #segmentujeme iba poškodené pixely, ktoré nie sú bariérou
    valid = damage_mask & ~barrier

    #OpenCV očakáva binárny obraz typu uint8
    valid_u8 = valid.astype(np.uint8)

    num_labels, label_image, stats, _ = cv2.connectedComponentsWithStats(valid_u8, connectivity=4)

    label_image = label_image.astype(np.int32, copy=False)
    regions: dict[int, RegionInfo] = {}

    #label 0 je pozadie, reálne regióny začínajú od 1
    for region_id in range(1, num_labels):
        x = int(stats[region_id, cv2.CC_STAT_LEFT])
        y = int(stats[region_id, cv2.CC_STAT_TOP])
        width = int(stats[region_id, cv2.CC_STAT_WIDTH])
        height = int(stats[region_id, cv2.CC_STAT_HEIGHT])
        area = int(stats[region_id, cv2.CC_STAT_AREA])

        regions[region_id] = RegionInfo(id=region_id, area=area, bbox=(x, y, width, height))

    return RegionMap(label_image=label_image, regions=regions)