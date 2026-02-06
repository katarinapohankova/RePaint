from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QInputDialog

from rp_restore.core.project_model import Project


class LayersPanel(QWidget):
    """
    Panel so zoznamom vrstiev
    - zobrazuje vrstvy z Projectu
    - pri kliknutí na vrstvu povie controlleru, že ju má nastaviť ako aktívnu
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None  #ProjectController

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        label = QLabel("Vrstvy")
        layout.addWidget(label)

        #self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        buttons_row = QHBoxLayout()
        self.btn_add_paint = QPushButton("Nová paint vrstva")
        self.btn_rename = QPushButton("Premenovať vrstvu")
        buttons_row.addWidget(self.btn_add_paint)
        buttons_row.addWidget(self.btn_rename)
        layout.addLayout(buttons_row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.list_widget)

        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.btn_add_paint.clicked.connect(self._on_add_paint_clicked)
        self.btn_rename.clicked.connect(self._on_rename_clicked)

        #keď sa zmení výber, zavoláme callback
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

    def set_controller(self, controller: object) -> None:
        """
        uloží referenciu na controller
        """
        self._controller = controller

    #----------aktualizácia podľa projectu----------

    def refresh_from_project(self, project: Project, active_layer_id: Optional[str]) -> None:
        """
        naplní zoznam podľa vrstiev v projekte
        active_layer_id: id vrstvy, ktorá má byť označená ako aktívna
        """
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for layer in project.layers:
            meta = layer.meta
            text = f"{meta.name} ({meta.role.value})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, meta.id)
            self.list_widget.addItem(item)

            if active_layer_id is not None and meta.id == active_layer_id:
                item.setSelected(True)

        self.list_widget.blockSignals(False)

    #----------callback pri kliknutí----------

    def _on_selection_changed(self) -> None:
        if self._controller is None:
            return

        items = self.list_widget.selectedItems()
        if not items:
            return

        item = items[0]
        layer_id = item.data(Qt.UserRole)

        if hasattr(self._controller, "set_active_layer"):
            self._controller.set_active_layer(layer_id)

    def _on_add_paint_clicked(self) -> None:
        if self._controller is None:
            return
        if hasattr(self._controller, "add_paint_layer"):
            self._controller.add_paint_layer()

    def _on_rename_clicked(self) -> None:
        if self._controller is None:
            return

        items = self.list_widget.selectedItems()
        if not items:
            return

        item = items[0]
        layer_id = item.data(Qt.UserRole)

        # starý názov – vezmeme text pred " ("
        full_text = item.text()
        if " (" in full_text:
            old_name = full_text.split(" (", 1)[0]
        else:
            old_name = full_text

        new_name, ok = QInputDialog.getText(
            self,
            "Premenovať vrstvu",
            "Nový názov vrstvy:",
            text=old_name,
        )
        if not ok or not new_name.strip():
            return

        if hasattr(self._controller, "rename_layer"):
            self._controller.rename_layer(layer_id, new_name.strip())


