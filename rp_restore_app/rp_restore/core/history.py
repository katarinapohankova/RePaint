from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .layers import LayerRole

@dataclass
class UndoAction:
    """Popis jednej undo/redo akcie nad výrezom vrstvy"""
    description: str
    layer_id: str
    layer_role: LayerRole
    bbox: tuple[int, int, int, int]
    before: np.ndarray
    after: np.ndarray

    #ďalšie zmeny, ktoré sa majú undo/redo spolu s hlavnou akciou
    extra_actions: list[UndoAction] | None = None

class GlobalUndoManager:
    """Spravuje globálny undo/redo stack projektu"""

    def __init__(self, max_actions: int | None = None, on_change: Callable[[], None] | None = None) -> None:
        self.stack: list[UndoAction] = []
        self.redo_stack: list[UndoAction] = []
        self.max_actions = max_actions
        self.on_change = on_change
    
    def push_action(self, action: UndoAction) -> None:
        """Pridá novú akciu do undo stacku a vyčistí redo stack"""
        self.stack.append(action)
        self.redo_stack.clear()

        #ak je nastavený limit, odstránime najstaršiu akciu
        if self.max_actions is not None and len(self.stack) > self.max_actions:
            self.stack.pop(0)
        
        if self.on_change is not None:
            self.on_change()
    
    def undo_global(self, project: Project) -> UndoAction | None:
        """Vráti poslednú globálnu akciu späť a presunie ju do redo stacku"""
        if not self.stack:
            return None

        action = self.stack.pop()
        self._apply_before(project, action)
        self.redo_stack.append(action)

        if self.on_change is not None:
            self.on_change()
        return action

    def redo_global(self, project: Project) -> UndoAction | None:
        """Znovu aplikuje poslednú vrátenú akciu"""
        if not self.redo_stack:
            return None

        action = self.redo_stack.pop()
        self._apply_after(project, action)
        self.stack.append(action)
        if self.on_change is not None:
            self.on_change()
        return action

    def undo_on_layer(self, project: Project, layer_id: str) -> UndoAction | None:
        """Vráti poslednú akciu späť iba vtedy, ak patrí zadanej vrstve"""
        if not self.stack:
            return None

        last_action = self.stack[-1]
        #nevyhľadávame staršie akcie, povoľujeme iba vrch globálneho stacku
        if last_action.layer_id != layer_id:
            return None

        action = self.stack.pop()
        self._apply_before(project, action)
        self.redo_stack.append(action)

        if self.on_change is not None:
            self.on_change()
        return action
    
    def can_undo(self) -> bool:
        return bool(self.stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def _apply_before(self, project: Project, action: UndoAction) -> None:
        """Aplikuje stav pred akciou späť do všetkých dotknutých vrstiev"""
        self._apply_action_pixels(project, action, action.before)

        if action.extra_actions:
            for sub_action in action.extra_actions:
                self._apply_action_pixels(project, sub_action, sub_action.before)

    def _apply_after(self, project: Project, action: UndoAction) -> None:
        """Aplikuje stav po akcii do všetkých dotknutých vrstiev"""
        if action.extra_actions:
            for sub_action in action.extra_actions:
                self._apply_action_pixels(project, sub_action, sub_action.after)

        self._apply_action_pixels(project, action, action.after)

    def _apply_action_pixels(self, project: Project, action: UndoAction, pixels: np.ndarray) -> None:
        """Obnoví pixely jednej akcie a synchronizuje masky podľa potreby"""
        layer = self._find_layer(project, action.layer_id)
        if layer is None:
            return

        x, y, _, _ = action.bbox
        layer.restore_subregion(x, y, pixels)

        self._sync_paint_layer_masks_after_apply(project, action)

    def _find_layer(self, project: Project, layer_id: str):
        """Nájde vrstvu v projekte podľa ID"""
        for layer in project.layers:
            if layer.meta.id == layer_id:
                return layer
        return None

    def _sync_paint_layer_masks_after_apply(self, project: Project, action: UndoAction) -> None:
        """Zosynchronizuje filled masku PAINT vrstvy po obnovení pixelov"""
        if action.layer_role != LayerRole.PAINT:
            return

        project.sync_layer_filled_mask_from_alpha(action.layer_id, action.bbox, mode="assign")
