from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from .layers import LayerRole


class UndoHighlightType(str, Enum):
    """Ako zvýrazniť zmenu pri undo -zatiaľ len BBOX"""

    BBOX = "bbox"
    #do budúcna môžeme bude asi niečo ako REGION_MASK = "region_mask"


@dataclass
class UndoAction:
    """
    Jedna undo/redo akcia – čo sa zmenilo na ktorej vrstve
    bbox: (x, y, w, h) – oblasť, kde sa pixely zmenili
    before / after: výrezy pixelov pred a po zmene
    """

    description: str
    layer_id: str
    layer_role: LayerRole

    bbox: Tuple[int, int, int, int]
    before: np.ndarray
    after: np.ndarray

    highlight_type: UndoHighlightType = UndoHighlightType.BBOX
    highlight_mask: Optional[np.ndarray] = None

    is_undone: bool = False  #použijeme neskôr pri "undo on this layer"

    extra_actions: Optional[List["UndoAction"]] = None

class GlobalUndoManager:
    """
    Jednoduchý undo/redo manažér 
    Implementujeme:
      - push_action() uloží akciu na vrch stacku a vyčistí redo_stack
      - undo_global() vráti poslednú akciu
      - redo_global() znovu aplikuje poslednú undo akciu
    """

    def __init__(self, max_actions: Optional[int] = None, on_change: Optional[callable] = None) -> None:
        self.stack: List[UndoAction] = []
        self.redo_stack: List[UndoAction] = []
        self.max_actions = max_actions
        self.on_change = on_change

    #--------interné pomocné metódy--------

    def _find_layer(self, project: "Project", layer_id: str):
        """Nájde vrstvu v projekte podľa ID"""
        #`Project` definujeme v project_model, voláme len cez typ "Project" (string)
        for layer in project.layers:
            if layer.meta.id == layer_id:
                return layer
        return None

    def _apply_before(self, project: "Project", action: UndoAction) -> None:
        """Aplikuje 'before' pixely akcie späť do vrstvy"""
        layer = self._find_layer(project, action.layer_id)
        if layer is None:
            return

        x, y, w, h = action.bbox
        layer.restore_subregion(x, y, action.before)

        self._sync_paint_layer_masks_after_apply(project, action)

        if action.extra_actions:
            for sub_action in action.extra_actions:
                sub_layer = self._find_layer(project, sub_action.layer_id)
                if sub_layer is None:
                    continue
                x, y, w, h = sub_action.bbox
                sub_layer.restore_subregion(x, y, sub_action.before)
                self._sync_paint_layer_masks_after_apply(project, sub_action)

    def _apply_after(self, project: "Project", action: UndoAction) -> None:
        """Aplikuje 'after' pixely akcie (používa sa pri redo)"""
        if action.extra_actions:
            for sub_action in action.extra_actions:
                sub_layer = self._find_layer(project, sub_action.layer_id)
                if sub_layer is None:
                    continue
                x, y, w, h = sub_action.bbox
                sub_layer.restore_subregion(x, y, sub_action.after)
                self._sync_paint_layer_masks_after_apply(project, sub_action)

        layer = self._find_layer(project, action.layer_id)
        if layer is None:
            return

        x, y, w, h = action.bbox
        layer.restore_subregion(x, y, action.after)

        self._sync_paint_layer_masks_after_apply(project, action)

    def _sync_paint_layer_masks_after_apply(self, project: "Project", action: UndoAction) -> None:
        """
        Po apply_before/apply_after zosynchronizuje per-layer damage mask pre PAINT vrstvy, aby overlay remaining sedel s reálnou alfa v layer.image
        """
        if action.layer_role != LayerRole.PAINT:
            return

        sync_fn = getattr(project, "sync_layer_filled_mask_from_alpha", None)
        if sync_fn is None:
            return

        try:
            sync_fn(action.layer_id, action.bbox, mode="assign")
        except TypeError:
            sync_fn(action.layer_id, action.bbox)

    #--------verejné metódy--------

    def push_action(self, action: UndoAction) -> None:
        """
        Pridá novú akciu do undo stacku
        Po pridaní novej akcie sa redo_stack vyprázdni – klasické správanie undo/redo.
        """
        self.stack.append(action)
        self.redo_stack.clear()

        #orezanie histórie, ak máme nastavený limit
        if self.max_actions is not None and len(self.stack) > self.max_actions:
            #zmažeme najstaršiu akciu
            self.stack.pop(0)
        
        if self.on_change is not None:
            self.on_change()

    def undo_global(self, project: "Project") -> Optional[UndoAction]:
        """
        Vráti poslednú akciu (globálne undo)
        Vráti UndoAction, aby GUI vedelo čo zvýrazniť
        """
        if not self.stack:
            return None

        action = self.stack.pop()
        self._apply_before(project, action)
        action.is_undone = True
        self.redo_stack.append(action)

        if self.on_change is not None:
            self.on_change()
        return action

    def redo_global(self, project: "Project") -> Optional[UndoAction]:
        """
        Znovu aplikuje poslednú undonutú akciu (globálne redo)
        """
        if not self.redo_stack:
            return None

        action = self.redo_stack.pop()
        self._apply_after(project, action)
        action.is_undone = False
        self.stack.append(action)
        if self.on_change is not None:
            self.on_change()
        return action

    def undo_on_layer(self, project: "Project", layer_id: str) -> Optional[UndoAction]:
        """
        Zatiaľ:
        - funguje len vtedy, ak posledná akcia na stacku patrí tejto vrstve
        Ak akcia nepatrí tejto vrstve, vráti None
        """
        if not self.stack:
            return None

        last_action = self.stack[-1]
        if last_action.layer_id != layer_id:
            return None

        action = self.stack.pop()
        self._apply_before(project, action)
        action.is_undone = True
        self.redo_stack.append(action)
        return action
    
    def can_undo(self) -> bool:
        return bool(self.stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)
