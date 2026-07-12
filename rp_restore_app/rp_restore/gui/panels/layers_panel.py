from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QInputDialog, QToolButton, QFrame, QSlider

from rp_restore.core.project_model import Project

class ClickablePreviewLabel(QLabel):
    """
    QLabel, ktorý vyšle signál po kliknutí na malý náhľad vrstvy
    """
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return

        super().mousePressEvent(event)

class LayersPanel(QWidget):
    """
    Panel so zoznamom vrstiev
    - zobrazuje vrstvy z Projectu
    - pri kliknutí na vrstvu povie controlleru, že ju má nastaviť ako aktívnu
    """
    visibility_changed = Signal(str, bool)   #(layer_id, visible)
    delete_layer_requested = Signal(str)    #(layer_id)
    opacity_changed = Signal(str, float)    #(layer_id, opacity_0_1)
    preview_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None  #ProjectController

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        buttons_row = QHBoxLayout()
        self.btn_add_paint = QPushButton("Nová vrstva malby")
        self.btn_rename = QPushButton("Přejmenovat vrstvu")
        buttons_row.addWidget(self.btn_add_paint)
        buttons_row.addWidget(self.btn_rename)
        layout.addLayout(buttons_row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.list_widget)

        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.btn_add_paint.clicked.connect(self._on_add_paint_clicked)
        self.btn_rename.clicked.connect(self._on_rename_clicked)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        layout.addWidget(separator)

        self.preview_label = QLabel("Náhled vrstvy")
        layout.addWidget(self.preview_label)

        self.preview_image = ClickablePreviewLabel()
        self.preview_image.clicked.connect(self.preview_clicked.emit)
        self.preview_image.setCursor(Qt.PointingHandCursor)
        self.preview_image.setToolTip("Kliknutím zobrazíte / skryjete zvětšený náhled vrstvy")
        self.preview_image.setFixedSize(180, 120)
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setStyleSheet("border: 1px solid #555; background: #222;")
        layout.addWidget(self.preview_image)

        self.opacity_label = QLabel("Průhlednost vrstvy:")
        layout.addWidget(self.opacity_label)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setToolTip("Průhlednost aktivní vrstvy (0–100 %)")
        layout.addWidget(self.opacity_slider)

        self.opacity_slider.valueChanged.connect(self._on_opacity_slider_changed)

        self._active_layer_id_for_opacity: str | None = None

    def set_controller(self, controller: object) -> None:
        """
        uloží referenciu na controller
        """
        self._controller = controller

    def set_preview(self, qimage) -> None:
        """Nastaví malý náhľad aktívnej vrstvy"""
        if qimage is None:
            self.preview_image.clear()
            return
        pix = QPixmap.fromImage(qimage)
        pix = pix.scaled(self.preview_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_image.setPixmap(pix)

    #----------aktualizácia podľa projectu----------

    def refresh_from_project(self, project: Project, active_layer_id: Optional[str]) -> None:
        """
        naplní zoznam podľa vrstiev v projekte
        active_layer_id: id vrstvy, ktorá má byť označená ako aktívna
        """
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        role_names = {
            "background": "původní",
            "edge": "hrany",
            "paint": "malba",
        }

        for layer in project.layers:
            meta = layer.meta

            #item slúži ako kontajner pre vlastný widget riadku
            item = QListWidgetItem()
            item.setData(Qt.UserRole, meta.id)
            item.setData(Qt.UserRole + 1, meta.name)
            self.list_widget.addItem(item)

            #widget riadku
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.setSpacing(6)

            #tlačidlo viditeľnosti
            eye = QToolButton()
            eye.setCheckable(True)
            eye.setChecked(meta.visible)
            eye.setToolTip("Zobrazit / skrýt vrstvu")
            eye.setText("◉" if meta.visible else "⦸")

            def _on_eye_toggled(checked, layer_id=meta.id, btn=eye):
                btn.setText("◉" if checked else "⦸")
                self.visibility_changed.emit(layer_id, checked)

            eye.toggled.connect(_on_eye_toggled)
            row_layout.addWidget(eye)

            #názov vrstvy
            name_label = QLabel(meta.name)
            row_layout.addWidget(name_label, 1)

            #typ vrstvy
            role_label = QLabel(role_names.get(meta.role.value, meta.role.value))
            role_label.setStyleSheet("color: #aaa; font-size: 10px;")
            row_layout.addWidget(role_label)

            #delete button len pre PAINT
            if meta.role.value == "paint":
                delete_btn = QToolButton()
                delete_btn.setText("🗑")
                delete_btn.setToolTip("Smazat vrstvu malby")
                delete_btn.clicked.connect(lambda _=False, layer_id=meta.id: self.delete_layer_requested.emit(layer_id))
                row_layout.addWidget(delete_btn)

            item.setSizeHint(row.sizeHint())
            self.list_widget.setItemWidget(item, row)

            if active_layer_id is not None and meta.id == active_layer_id:
                item.setSelected(True)


        self.list_widget.blockSignals(False)
        self._active_layer_id_for_opacity = active_layer_id

        active_layer = None
        if active_layer_id is not None:
            for layer in project.layers:
                if layer.meta.id == active_layer_id:
                    active_layer = layer
                    break

        if active_layer is None:
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(100)
            self.opacity_slider.blockSignals(False)
        else:
            val = int(round(float(active_layer.meta.opacity) * 100))
            val = max(0, min(100, val))
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(val)
            self.opacity_slider.blockSignals(False)

    #----------callback pri kliknutí----------

    def _on_selection_changed(self) -> None:
        """Nastaví kliknutú vrstvu ako aktívnu"""
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
        """Požiada controller o pridanie novej PAINT vrstvy"""
        if self._controller is None:
            return
        if hasattr(self._controller, "add_paint_layer"):
            self._controller.add_paint_layer()

    def _on_rename_clicked(self) -> None:
        """Premenuje aktuálne vybranú vrstvu"""
        if self._controller is None:
            return

        items = self.list_widget.selectedItems()
        if not items:
            return

        item = items[0]
        layer_id = item.data(Qt.UserRole)

        # old_name = item.text()
        old_name = item.data(Qt.UserRole + 1) or ""

        new_name, ok = QInputDialog.getText(
            self,
            "Přejmenovat vrstvu",
            "Nový název vrstvy:",
            text=old_name,
        )
        if not ok or not new_name.strip():
            return

        if hasattr(self._controller, "rename_layer"):
            self._controller.rename_layer(layer_id, new_name.strip())

    def _on_opacity_slider_changed(self, value: int) -> None:
        """Odošle zmenu krytia aktívnej vrstvy"""
        if self._active_layer_id_for_opacity is None:
            return
        opacity = float(value) / 100.0
        self.opacity_changed.emit(self._active_layer_id_for_opacity, opacity)
