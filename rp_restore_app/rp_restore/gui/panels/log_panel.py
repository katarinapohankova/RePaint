from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem

from rp_restore.core.project_model import Project
from rp_restore.core.warnings import UserWarning


class LogPanel(QWidget):
    """
    Panel s warningami / logmi pre užívateľa
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None  #ProjectController

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        label = QLabel("Log / Warningy")
        layout.addWidget(label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.list_widget.itemActivated.connect(self._on_item_activated)

    def set_controller(self, controller: object) -> None:
        self._controller = controller

    def refresh_from_project(self, project: Project) -> None:
        """
        Naplní panel warningami z project.log_manager
        """
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        warnings = project.log_manager.get_all_warnings()

        for w in warnings:
            text = f"[{w.warning_type.value}] {w.message}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, w.id)
            #odlíšenie neaktívnych
            if w.dismissed:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.list_widget.addItem(item)

        self.list_widget.blockSignals(False)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        if self._controller is None:
            return

        warning_id = item.data(Qt.UserRole)
        if hasattr(self._controller, "focus_warning"):
            self._controller.focus_warning(warning_id)
