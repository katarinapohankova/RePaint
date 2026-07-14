from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QSpinBox, QPushButton, QColorDialog 

class EdgeSettingsPanel(QWidget):
    """
    Panel pre nastavenie farby hrán a šírky zjemnenia po odstránení hrany
    - zjemnenie (px)
    - edge farba
    - použitie aktuálnej farby z panelu Barvy
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        #šírka zjemnenia hrany
        row_blend = QHBoxLayout()
        lbl_blend = QLabel("Šířka zjemnění (px):")
        self.spin_blend_width = QSpinBox()
        self.spin_blend_width.setRange(1, 100)
        self.spin_blend_width.setValue(5)
        self.spin_blend_width.setToolTip("Šířka pásu, ve kterém se zjemní přechod po odstranění hrany")
        row_blend.addWidget(lbl_blend)
        row_blend.addWidget(self.spin_blend_width)
        layout.addLayout(row_blend)

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

        self.btn_change_color.clicked.connect(self._on_change_color_clicked)
        self.btn_use_current.clicked.connect(self._on_use_current_clicked)
        self.btn_add_to_palette.clicked.connect(self._on_add_edge_color_to_palette_clicked)
        self.spin_blend_width.valueChanged.connect(self._on_blend_width_changed)
        self.spin_blend_width.editingFinished.connect(self._on_blend_width_editing_finished)

    #prepojenie s controllerom

    def set_controller(self, controller: object) -> None:
        """Nastaví controller a načíta z neho aktuálne hodnoty"""
        self._controller = controller
        self.refresh_from_controller(controller)

    def refresh_from_controller(self, controller: object) -> None:
        """
        Aktualizuje zobrazenie podľa hodnôt v controlleri
        """
        self._controller = controller

        if not hasattr(controller, "get_edge_color_rgba"):
            return

        if hasattr(controller, "get_edge_blend_buffer"):
            blend_width = controller.get_edge_blend_buffer()
            self.spin_blend_width.blockSignals(True)
            self.spin_blend_width.setValue(blend_width)
            self.spin_blend_width.blockSignals(False)

        color_arr = controller.get_edge_color_rgba()
        r, g, b, a = [int(x) for x in color_arr.tolist()]
        self._set_swatch_color(QColor(r, g, b, a))


    def _set_swatch_color(self, color: QColor) -> None:
        """Aktualizuje farebný náhľad edge farby"""
        self.color_swatch.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            "border: 1px solid #333;"
        )

    #---reakcie na UI---

    def _on_change_color_clicked(self) -> None:
        """Otvorí dialóg na výber edge farby"""
        if self._controller is None:
            return

        if not hasattr(self._controller, "get_edge_color_rgba"):
            return

        arr = self._controller.get_edge_color_rgba()
        r, g, b, a = [int(x) for x in arr.tolist()]
        initial = QColor(r, g, b, a)

        color = QColorDialog.getColor(initial, self, "Vyberte barvu hran")
        if not color.isValid():
            return

        self._set_swatch_color(color)

        if hasattr(self._controller, "set_edge_color_rgba"):
            self._controller.set_edge_color_rgba(
                (color.red(), color.green(), color.blue(), color.alpha())
            )

    def _on_use_current_clicked(self) -> None:
        """
        Použije aktuálnu farbu z panelu Barvy ako edge farbu
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
        """Pridá aktuálnu edge farbu do palety"""
        if self._controller is None:
            return
        if not hasattr(self._controller, "get_edge_color_rgba"):
            return

        arr = self._controller.get_edge_color_rgba()
        r, g, b, a = [int(x) for x in arr.tolist()]

        if hasattr(self._controller, "add_color_to_palette_rgba"):
            self._controller.add_color_to_palette_rgba((r, g, b, a), avoid_duplicates=True)

    def _on_blend_width_changed(self, value: int) -> None:
        """Nastaví šírku pásu pre edge blend nástroj"""
        if self._controller is None:
            return

        if hasattr(self._controller, "set_edge_blend_buffer"):
            self._controller.set_edge_blend_buffer(value)

    def _on_blend_width_editing_finished(self) -> None:
        """
        po potvrdení hodnoty Enterom alebo stratou focus vrátime focus na canvas, aby zase fungovali klávesové skratky
        """
        if self._controller is None:
            return

        canvas = getattr(self._controller, "canvas", None)
        if canvas is not None:
            canvas.setFocus(Qt.OtherFocusReason)