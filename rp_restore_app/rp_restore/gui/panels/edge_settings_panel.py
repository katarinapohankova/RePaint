from __future__ import annotations

from typing import Optional

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QSpinBox, QPushButton, QColorDialog 

class EdgeSettingsPanel(QWidget):
    """
    Panel pre nastavenie hrúbky a farby EdgeToolu
    - hrúbka (px)
    - edge farba
    - Použiť aktuální barvu
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # title = QLabel("Hrany")
        # layout.addWidget(title)

        #hrúbka
        row_width = QHBoxLayout()
        lbl_width = QLabel("hrúbka (px):")
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 50)
        self.spin_width.setValue(2)
        self.spin_width.setToolTip("Nastaví hrúbku hrany (štětce pro Edge nástroj)")
        row_width.addWidget(lbl_width)
        row_width.addWidget(self.spin_width)
        layout.addLayout(row_width)

        #farba hrany
        row_color = QHBoxLayout()
        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(24, 24)
        self.color_swatch.setStyleSheet("background-color: black; border: 1px solid #333;")
        row_color.addWidget(QLabel("Barva:"))
        row_color.addWidget(self.color_swatch)
        layout.addLayout(row_color)

        #tlačidlá
        self.btn_change_color = QPushButton("Změnit barvu…")
        self.btn_use_current = QPushButton("Použít aktuální barvu")
        self.btn_add_to_palette = QPushButton("Přidat barvu do palety")

        self.btn_change_color.setToolTip("Otevře dialog pro výběr barvy hran")
        self.btn_use_current.setToolTip("Použije aktuální barvu z panelu Barvy jako barvu hran")
        self.btn_add_to_palette.setToolTip("Přidá aktuální barvu hran do palety v panelu Barvy")

        layout.addWidget(self.btn_change_color)
        layout.addWidget(self.btn_use_current)
        layout.addWidget(self.btn_add_to_palette)
        layout.addStretch(1)

        self.spin_width.valueChanged.connect(self._on_width_changed)
        self.btn_change_color.clicked.connect(self._on_change_color_clicked)
        self.btn_use_current.clicked.connect(self._on_use_current_clicked)
        self.btn_add_to_palette.clicked.connect(self._on_add_edge_color_to_palette_clicked)

    #prepojenie s controllerom

    def set_controller(self, controller: object) -> None:
        self._controller = controller
        self.refresh_from_controller(controller)

    def refresh_from_controller(self, controller: object) -> None:
        """
        Aktualizuje zobrazenie podľa hodnôt v controlleri
        """
        self._controller = controller

        if not hasattr(controller, "get_edge_brush_size") or not hasattr(controller, "get_edge_color_rgba"):
            return

        width = controller.get_edge_brush_size()
        self.spin_width.blockSignals(True)
        self.spin_width.setValue(width)
        self.spin_width.blockSignals(False)

        color_arr = controller.get_edge_color_rgba()
        r, g, b, a = [int(x) for x in color_arr.tolist()]
        self._set_swatch_color(QColor(r, g, b, a))


    def _set_swatch_color(self, color: QColor) -> None:
        self.color_swatch.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            "border: 1px solid #333;"
        )

    #---reakcie na UI---

    def _on_width_changed(self, value: int) -> None:
        if self._controller is None:
            return
        if hasattr(self._controller, "set_edge_brush_size"):
            self._controller.set_edge_brush_size(value)

    def _on_change_color_clicked(self) -> None:
        if self._controller is None:
            return

        if not hasattr(self._controller, "get_edge_color_rgba"):
            return

        arr = self._controller.get_edge_color_rgba()
        r, g, b, a = [int(x) for x in arr.tolist()]
        initial = QColor(r, g, b, a)

        color = QColorDialog.getColor(initial, self, "Vyber barvu hran")
        if not color.isValid():
            return

        self._set_swatch_color(color)

        if hasattr(self._controller, "set_edge_color_rgba"):
            self._controller.set_edge_color_rgba(
                (color.red(), color.green(), color.blue(), color.alpha())
            )

    def _on_use_current_clicked(self) -> None:
        """
        Použije aktuálnu barvu z Barvy panelu ako edge barvu
        """
        if self._controller is None:
            return

        if not hasattr(self._controller, "get_current_color_rgba"):
            return

        arr = self._controller.get_current_color_rgba()
        r, g, b, a = [int(x) for x in arr.tolist()]

        if hasattr(self._controller, "set_edge_color_rgba"):
            self._controller.set_edge_color_rgba((r, g, b, a))

        self._set_swatch_color(QColor(r, g, b, a))
    
    def _on_add_edge_color_to_palette_clicked(self) -> None:
        if self._controller is None:
            return
        if not hasattr(self._controller, "get_edge_color_rgba"):
            return

        arr = self._controller.get_edge_color_rgba()
        r, g, b, a = [int(x) for x in arr.tolist()]

        if hasattr(self._controller, "add_color_to_palette_rgba"):
            self._controller.add_color_to_palette_rgba((r, g, b, a), avoid_duplicates=True)
