from __future__ import annotations

from typing import List, Optional

import numpy as np

from .layers import Layer, LayerRole

from .history import UndoAction, GlobalUndoManager

from .warnings import UserWarning
from .warnings import LogManager, WarningType, RegionReference
from .selection import Selection
from .regions import RegionMap, build_region_map, compare_region_maps


class Project:
    """
    Reprezentuje jeden otvorený projekt
    Zatiaľ:
      - nemá warningy ani IO
      - vie držať vrstvy a urobiť jednoduchú kompozíciu
    """

    def __init__(self, project_name: str) -> None:
        self.project_name: str = project_name

        #všetky vrstvy v projekte (BACKGROUND, EDGE, PAINT)
        self.layers: List[Layer] = []

        #masky poškodenia – zatiaľ len pripravené, môžu byť None
        self.damage_original_mask: Optional[np.ndarray] = None
        self.damage_filled_mask: Optional[np.ndarray] = None

        #záznamy pre neskorší PDF report
        self.history_for_report: List[dict] = []

        #undo/redo manažér 
        self.undo_manager: GlobalUndoManager = GlobalUndoManager()

        #warningy a logy
        self.log_manager: LogManager = LogManager()

        #cace pre poslednú region mapu -pre porovnanie pri zmene hrán
        self._cached_region_map: RegionMap | None = None


    #---------Správa vrstiev---------

    def add_layer(self, layer: Layer) -> None:
        """Pridá vrstvu do projektu"""
        self.layers.append(layer)

    def get_background_layer(self) -> Optional[Layer]:
        """Vráti prvú BACKGROUND vrstvu (alebo None, ak neexistuje)"""
        for layer in self.layers:
            if layer.meta.role == LayerRole.BACKGROUND:
                return layer
        return None

    def get_paint_layers(self) -> List[Layer]:
        """Vráti zoznam všetkých PAINT vrstiev"""
        return [l for l in self.layers if l.meta.role == LayerRole.PAINT]

    def get_edge_layers(self) -> List[Layer]:
        """Vráti zoznam všetkých EDGE vrstiev"""
        return [l for l in self.layers if l.meta.role == LayerRole.EDGE]

    #---------Kompozícia obrazu---------

    def composited_image(self) -> np.ndarray:
        """
        Zloží výsledný RGB obraz z backgroundu a všetkých PAINT vrstiev
        Zatiaľ:
          - ignorujeme EDGE vrstvy
          - ignorujeme opacity v meta
          - PAINT vrstvy skladáme jednoduchým alpha blendingom
        """
        bg_layer = self.get_background_layer()
        if bg_layer is None:
            raise RuntimeError("Project has no BACKGROUND layer.")

        #začneme s RGB z backgroundu
        base = bg_layer.image[..., :3].astype(np.float32)
        h, w, _ = base.shape

        #zoberieme všetky paint vrstvy v poradí, v akom sú v zozname
        for layer in self.get_paint_layers():
            rgba = layer.image.astype(np.float32)
            rgb = rgba[..., :3]
            alpha = rgba[..., 3:4] / 255.0  #tvar (H, W, 1)

            #alpha blending: out = rgb * a + base * (1 - a)
            base = rgb * alpha + base * (1.0 - alpha)

        for layer in self.get_edge_layers():
            rgba = layer.image.astype(np.float32)

            if rgba.shape[0] != h or rgba.shape[1] != w:
                continue
            rgb = rgba[..., :3]
            alpha = rgba[..., 3:4] / 255.0
            base = rgb * alpha + base * (1.0 - alpha)
        #výsledok pretypujeme na uint8
        return np.clip(base, 0, 255).astype(np.uint8)
    
    #---------Undo/redo rozhranie---------

    def undo_global(self) -> Optional[UndoAction]:
        """Vykoná globálne undo
        Vráti UndoAction alebo None"""
        return self.undo_manager.undo_global(self)

    def redo_global(self) -> Optional[UndoAction]:
        """Vykoná globálne redo
        Vráti UndoAction alebo None"""
        return self.undo_manager.redo_global(self)

    def undo_on_layer(self, layer_id: str) -> Optional[UndoAction]:
        """Vykoná undo na konkrétnej vrstve (zatiaľ jednoduchá verzia)"""
        return self.undo_manager.undo_on_layer(self, layer_id)
    

    #---------damage masky--------
    def set_damage_masks(self, original_mask: np.ndarray) -> None:
        """
        Nastaví masku poškodenia
        original_mask -2D pole (H, W), kde true je poškodené miesto
        """
        if original_mask.ndim != 2:
            raise ValueError("Damage mask must be 2D (H, W)")

        self.damage_original_mask = original_mask.astype(bool)
        self.damage_filled_mask = np.zeros_like(self.damage_original_mask, dtype=bool)

    def get_damage_remaining_mask(self) -> np.ndarray | None:
        """
        vráti masku zostávajúcich (nevyplnených) poškodených miest
        """
        if self.damage_original_mask is None or self.damage_filled_mask is None:
            return None

        filled = self._compute_filled_mask_from_layers()
        if filled is None:
            #žiadne paint vrstvy –všetko pôvodné poškodenie je remaining
            return self.damage_original_mask.copy()

        remaining = self.damage_original_mask & ~filled

        #synchronizácia damage_filled_mask (nech je aktuálna)
        self.damage_filled_mask = filled.copy()
        return remaining

    def mark_region_as_filled(self, region_mask: np.ndarray) -> None:
        """
        označí daný region v damage maske ako vyplnený
        """
        if self.damage_filled_mask is None:
            return

        if region_mask.shape != self.damage_filled_mask.shape:
            raise ValueError("region_mask must have same shape as damage mask")

        self.damage_filled_mask |= region_mask.astype(bool)

    def get_selection_from_click(self, x: int, y: int) -> Selection | None:
        """
        ak v bode (x, y) je pixel poškodený (true), spraví flood-fill a vráti Selection (region_mask + bbox)
        """
        remaining = self.get_damage_remaining_mask()
        if remaining is None:
            return None

        h, w = remaining.shape
        if x < 0 or y < 0 or x >= w or y >= h:
            return None

        if not remaining[y, x]:
            #klik mimo poškodenej oblasti
            return None

        edge_layers = self.get_edge_layers()
        region_map = build_region_map(remaining, edge_layers)

        label_image = region_map.label_image
        region_id = int(label_image[y, x])
        if region_id == 0:
            return None
        
        info = region_map.regions.get(region_id)
        if info is None:
            return None
        
        region_mask = region_map.get_region_mask(region_id)
        bbox = info.bbox

        return Selection(region_mask=region_mask, bbox=bbox, seed_point=(x, y), region_id=region_id)

    #---------zmeny hrán ---------
    def on_edge_layer_modified(self, edge_layer_id: str) -> None:
        """
        Zavolá sa po úprave EDGE vrstvy 
        -prepočíta RegionMap na damage_remaining_mask
        -porovná s predchádzajúcou verziou
        -podľa rozdielov vytvorí warningy
        """
        damage_rem = self.get_damage_remaining_mask()
        if damage_rem is None:
            return

        edge_layers = self.get_edge_layers()
        if not edge_layers:
            return

        new_map = build_region_map(damage_rem, edge_layers)

        #prvýkrát len nastavíme cache
        if self._cached_region_map is None:
            self._cached_region_map = new_map
            return

        old_map = self._cached_region_map
        changes = compare_region_maps(old_map, new_map)
        self._cached_region_map = new_map

        if not changes.changed_mask.any():
            return

        #zmena hrán zasahuje už vyplnené oblasti
        filled = self._compute_filled_mask_from_layers()
        if filled is not None:
            affected_mask = changes.changed_mask & filled
            if affected_mask.any():
                ys, xs = np.where(affected_mask)
                y_min = int(ys.min())
                y_max = int(ys.max())
                x_min = int(xs.min())
                x_max = int(xs.max())
                bbox = (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)

                region_refs: list[RegionReference] = []
                for layer in self.get_paint_layers():
                    region_refs.append(RegionReference(layer_id=layer.meta.id, bbox=bbox, region_id=None, seed_point=None))

                self.log_manager.add_warning(
                    warning_type=WarningType.EDGE_MODIFIED_TOUCHING_FILLS,
                    message="zmena hrán zasiahla už vyplnené oblasti",
                    details="Upravili ste hrany v blízkosti už vyplnených poškodených častí",
                    affected_regions=region_refs,
                )

        #zlúčené oblasti
        for old_ids, new_id, bbox in changes.merged_regions:
            region_refs: list[RegionReference] = []
            for layer in self.get_paint_layers():
                region_refs.append(RegionReference(layer_id=layer.meta.id, bbox=bbox, region_id=new_id, seed_point=None))

            self.log_manager.add_warning(
                warning_type=WarningType.EDGE_DELETED_REGIONS_MERGED,
                message="Úprava hrán zlúčila viac poškodených oblastí do jednej",
                details=f"Oblasti {sorted(old_ids)} boli zlúčené do oblasti {new_id}.",
                affected_regions=region_refs,
            )

    def _compute_filled_mask_from_layers(self) -> np.ndarray | None:
        """
        Vypočíta, ktoré pixely poškodenia sú aktuálne vyplnené
        podľa PAINT vrstiev (alfa > 0)
        """
        if self.damage_original_mask is None:
            return None

        h, w = self.damage_original_mask.shape
        filled = np.zeros((h, w), dtype=bool)

        for layer in self.get_paint_layers():
            if layer.image.shape[0] != h or layer.image.shape[1] != w:
                continue
            alpha = layer.image[..., 3] > 0
            filled |= alpha

        return filled


