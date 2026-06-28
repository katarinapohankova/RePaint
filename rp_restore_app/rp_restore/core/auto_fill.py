from __future__ import annotations

from typing import List, Tuple
from dataclasses import dataclass

import numpy as np

from .history import UndoAction
from .layers import Layer, LayerRole
from .project_model import Project
from .regions import RegionMap


@dataclass
class AutoFillRegion:
    """
    Jedna oblasť určená na auto-fill
    region_id: id toho regiónu
    bbox: (x, y, w, h)
    """
    region_id: int
    bbox: Tuple[int, int, int, int]


def _compute_region_mean_color(composited_rgb: np.ndarray, damage_remaining_mask: np.ndarray, bbox: Tuple[int, int, int, int], padding: int = 8) -> np.ndarray | None:
    """
    Spočíta priemernú farbu okolia v bboxe oblasti
    -berie len tie pixely v bboxe, ktoré nie sú poškodené
    vráti RGB uint8 alebo None, ak sa nenašli žiadne vhodné pixely
    """
    x, y, w, h = bbox
    img_h, img_w = damage_remaining_mask.shape

    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(img_w, x + w + padding)
    y1 = min(img_h, y + h + padding)

    sub_rgb = composited_rgb[y0:y1, x0:x1, :]
    sub_damage = damage_remaining_mask[y0:y1, x0:x1]

    #vhodné pixely 
    good_mask = ~sub_damage
    good_pixels = sub_rgb[good_mask]

    if good_pixels.size == 0:
        return None

    mean_color = good_pixels.mean(axis=0).astype(np.uint8)
    return mean_color


def _fill_single_region(project: Project, target_layer: Layer, region_map: RegionMap, region_id: int, bbox: Tuple[int, int, int, int], composited_rgb: np.ndarray) -> bool:
    """
    Vyplní jednu oblasť na target_layer
    -vráti True, ak sa oblasť podarilo vyplniť
    """
    if project is None or target_layer.meta.role != LayerRole.PAINT:
        return False

    damage_rem = project.get_layer_damage_remaining_mask(target_layer.meta.id)
    if damage_rem is None:
        return False

    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return False
    
    img_h, img_w = damage_rem.shape
    if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
        return False

    #lokálna maska iba v bboxe
    label_sub = region_map.label_image[y:y + h, x:x + w]
    local_mask = (label_sub == region_id)

    if not local_mask.any():
        return False

    mean_color = _compute_region_mean_color(composited_rgb=composited_rgb, damage_remaining_mask=damage_rem, bbox=bbox, padding=8)
    if mean_color is None:
        return False

    sub_target = target_layer.image[y:y + h, x:x + w, :]
    sub_target[local_mask, 0:3] = mean_color
    sub_target[local_mask, 3] = 255

    project.sync_layer_filled_mask_from_alpha(target_layer.meta.id, bbox=bbox,mode="assign")

    return True


def auto_fill_regions(project: Project, target_layer: Layer, region_map: RegionMap, regions_to_fill: List[AutoFillRegion]) -> int:
    """
    Vyplní zoznam konkrétnych oblastí po jednej (ale undo je len jeden krok pre všetky)
    """
    if project is None or target_layer.meta.role != LayerRole.PAINT:
        return 0

    if not regions_to_fill:
        return 0

    composited_before = project.composited_image()
    #celá vrstva pre jedno undo
    before_all = target_layer.image.copy()
    filled_count = 0

    for region in regions_to_fill:
        ok = _fill_single_region(project=project, target_layer=target_layer, region_map=region_map, region_id=region.region_id, bbox=region.bbox, composited_rgb=composited_before)
        if ok:
            filled_count += 1

    if filled_count == 0:
        return 0

    #celá vrstva po auto-fille
    after_all = target_layer.image.copy()
    layer_h, layer_w, _ = target_layer.image.shape
    bbox_all = (0, 0, layer_w, layer_h)
    action = UndoAction(description=f"Auto-fill {filled_count} regions", layer_id=target_layer.meta.id, layer_role=target_layer.meta.role, bbox=bbox_all, before=before_all, after=after_all)
    project.undo_manager.push_action(action)

    return filled_count