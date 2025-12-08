from __future__ import annotations

from typing import List, Optional

import numpy as np

from .layers import Layer, LayerRole

from .history import UndoAction, GlobalUndoManager

from .warnings import UserWarning
from .warnings import LogManager


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

        #zoberieme všetky paint vrstvy v poradí, v akom sú v zozname
        for layer in self.get_paint_layers():
            rgba = layer.image.astype(np.float32)
            rgb = rgba[..., :3]
            alpha = rgba[..., 3:4] / 255.0  #tvar (H, W, 1)

            #alpha blending: out = rgb * a + base * (1 - a)
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

