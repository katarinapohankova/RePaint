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

    damage_rem = project.get_layer_damage_remaining_mask(target_layer.meta.id)
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

    #o koľko rozšírime bbox pri hľadaní okolia
    margin = 3

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

        #definujeme širšie okolie pre výpočet farby
        sx0 = max(0, x - margin)
        sy0 = max(0, y - margin)
        sx1 = min(w, x + rw + margin)
        sy1 = min(h, y + rh + margin)

        sub_composited = composited[sy0:sy1, sx0:sx1, :]
        sub_damage = damage_rem[sy0:sy1, sx0:sx1]

        #pixely, ktoré nie sú poškodené
        good_mask = ~sub_damage
        good_pixels = sub_composited[good_mask]

        #ak ani v širšom okolí nie sú čisté pixely, použijeme všetky pixely v okolí
        if good_pixels.size == 0:
            good_pixels = sub_composited.reshape(-1, 3)

        if good_pixels.size == 0:
            #nemáme dobré okolité pixely – preskočíme oblasť
            continue

        mean_color = good_pixels.mean(axis=0).astype(np.uint8)  

        #vypĺňame na target_layer
        sub_target = target_layer.image[y : y + rh, x : x + rw, :]
        sub_target[local_mask, 0:3] = mean_color
        sub_target[local_mask, 3] = 255

        project.mark_region_as_filled_on_layer(target_layer.meta.id, region_mask)

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
