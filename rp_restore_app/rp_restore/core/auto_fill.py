from __future__ import annotations

from typing import List

import numpy as np

from .history import UndoAction
from .layers import Layer, LayerRole
from .project_model import Project
from .regions import build_region_map


def auto_fill_small_regions(project: Project, target_layer: Layer, area_threshold: int = 200) -> int:
    """
    Automaticky vyplní malé poškodené oblasti na target_layer

    - používa damage_remaining_mask, rozdelí ju na oblasti pomocou build_region_map
    -pre tie s area < area_threshold:
      - spočíta priemernú farbu z okolia (z composited_image)
      - vyplní oblasť na target_layer, vytvorí UndoAction,
      - poznamená oblasť ako vyplnenú v damage maske

    vráti počet vyplnených oblastí
    """
    if project is None or target_layer.meta.role != LayerRole.PAINT:
        return 0

    damage_rem = project.get_damage_remaining_mask()
    if damage_rem is None:
        return 0

    edge_layers: List[Layer] = project.get_edge_layers()

    region_map = build_region_map(damage_rem, edge_layers)
    small_regions = region_map.get_regions_smaller_than(area_threshold)

    if not small_regions:
        return 0

    # composited obraz pred zmenami –zdroj farieb
    composited = project.composited_image()  # (H, W, 3), uint8

    h, w = damage_rem.shape

    #before -uložíme celú vrstvu
    before_all = target_layer.image.copy()

    filled_count = 0

    for region in small_regions:
        region_mask = region_map.get_region_mask(region.id)
        if not region_mask.any():
            continue

        x, y, rw, rh = region.bbox

        #kontrola hraníc
        if x < 0 or y < 0 or x + rw > w or y + rh > h:
            continue

        #lokálne masky a obrázky
        local_mask = region_mask[y : y + rh, x : x + rw]
        if not local_mask.any():
            continue

        sub_composited = composited[y : y + rh, x : x + rw, :]

        #farba okolia -pixely v bboxe, ktoré nie sú poškodené
        sub_damage = damage_rem[y : y + rh, x : x + rw]
        good_mask = ~sub_damage & True  # explicitne bool

        good_pixels = sub_composited[good_mask]
        if good_pixels.size == 0:
            #nemáme dobré okolité pixely – preskočíme oblasť
            continue

        mean_color = good_pixels.mean(axis=0).astype(np.uint8)  

        #vypĺňame na target_layer
        sub_target = target_layer.image[y : y + rh, x : x + rw, :]
        sub_target[local_mask, 0:3] = mean_color
        sub_target[local_mask, 3] = 255

        project.mark_region_as_filled(region_mask)

        filled_count += 1

    if filled_count == 0:
        return 0

    #after – celá vrstva po auto-fill
    after_all = target_layer.image.copy()

    # bbox = celá vrstva
    layer_h, layer_w, _ = target_layer.image.shape
    bbox = (0, 0, layer_w, layer_h)

    action = UndoAction(description=f"Auto-fill {filled_count} small regions", layer_id=target_layer.meta.id, layer_role=target_layer.meta.role, bbox=bbox, before=before_all, after=after_all)

    project.undo_manager.push_action(action)

    return filled_count
