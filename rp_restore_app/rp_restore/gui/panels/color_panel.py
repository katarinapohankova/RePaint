from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton,QHBoxLayout, QGridLayout, QColorDialog, QSpinBox

from rp_restore.core.project_model import Project


class ColorPanel(QWidget):
    """
    Panel s aktuálnou farbou a paletou farieb
    -zobrazuje aktuálnu farbu
    -umožňuje ju zmeniť cez QColorDialog
    -umožňuje pridať farbu do palety
    -zobrazuje paletu ako malé farebné štvorce
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None
        self._project: Optional[Project] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        title = QLabel("Barvy")
        layout.addWidget(title)

        #aktuálna farba
        swatch_row = QHBoxLayout()
        self.swatch_label = QLabel()
        self.swatch_label.setFixedSize(40, 40)
        
        self.swatch_label.setStyleSheet("background-color: black; border: 1px solid #333;")

        self.btn_change_color = QPushButton("Změnit barvu…")
        self.btn_add_to_palette = QPushButton("Přidat do palety")

        self.btn_change_color.setToolTip("Otevře dialog pro výběr barvy štětce/výplně")
        self.btn_add_to_palette.setToolTip("Přidá aktuální barvu do palety tohoto projektu")

        swatch_row.addWidget(self.swatch_label)
        swatch_row.addWidget(self.btn_change_color)
        layout.addLayout(swatch_row)
        layout.addWidget(self.btn_add_to_palette)

        #paleta
        self.palette_label = QLabel("Paleta:")
        layout.addWidget(self.palette_label)

        self.palette_layout = QGridLayout()
        self.palette_layout.setSpacing(4)
        layout.addLayout(self.palette_layout)

        #veľkosť Brush/Eraser
        brush_row = QHBoxLayout()
        brush_label = QLabel("Velikost štětce:")
        self.brush_spin = QSpinBox()
        self.brush_spin.setRange(1, 200)
        self.brush_spin.setToolTip("Velikost štětce pro nástroje Brush a Eraser")
        brush_row.addWidget(brush_label)
        brush_row.addWidget(self.brush_spin)
        layout.addLayout(brush_row)

        layout.addStretch(1)

        self.btn_change_color.clicked.connect(self._on_change_color_clicked)
        self.btn_add_to_palette.clicked.connect(self._on_add_to_palette_clicked)
        self.brush_spin.valueChanged.connect(self._on_brush_size_changed)

    def set_controller(self, controller: object) -> None:
        self._controller = controller
        if hasattr(controller, "get_brush_size") and hasattr(self, "brush_spin"):
            self.set_brush_size_value(controller.get_brush_size())

    def refresh_from_project(self, project: Project) -> None:
        """
        Zavolá controller, keď sa zmení projekt alebo farba/paleta
        """
        self._project = project

        #aktuálna farba
        r, g, b, a = project.get_current_color_rgba()
        color = QColor(r, g, b, a)
        self._set_swatch_color(color)

        #paleta
        while self.palette_layout.count():
            item = self.palette_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        palette = project.get_palette_colors()
        if not palette:
            self.palette_label.setText("Paleta: (prázdna)")
            return

        self.palette_label.setText("Paleta:")
        cols = 6
        for idx, rgba in enumerate(palette):
            r, g, b, a = rgba
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setToolTip(f"R={r}, G={g}, B={b}")
            btn.setStyleSheet(
                f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid #555;"
            )
            btn.clicked.connect(lambda checked=False, rgba=rgba: self._on_palette_color_clicked(rgba))

            row = idx // cols
            col = idx % cols
            self.palette_layout.addWidget(btn, row, col)

    def _set_swatch_color(self, color: QColor) -> None:
        self.swatch_label.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});""border: 1px solid #333;"
        )

    def _on_change_color_clicked(self) -> None:
        if self._controller is None or self._project is None:
            return

        r, g, b, a = self._project.get_current_color_rgba()
        initial = QColor(r, g, b, a)

        color = QColorDialog.getColor(initial, self, "Vyber barvu")
        if not color.isValid():
            return

        self._set_swatch_color(color)

        if hasattr(self._controller, "set_current_color_rgba"):
            self._controller.set_current_color_rgba(
                (color.red(), color.green(), color.blue(), color.alpha())
            )

    def _on_add_to_palette_clicked(self) -> None:
        if self._controller is None:
            return
        if hasattr(self._controller, "add_current_color_to_palette"):
            self._controller.add_current_color_to_palette()

    def _on_palette_color_clicked(self, rgba: tuple[int, int, int, int]) -> None:
        if self._controller is None:
            return
        r, g, b, a = rgba
        color = QColor(r, g, b, a)
        self._set_swatch_color(color)
        if hasattr(self._controller, "set_current_color_rgba"):
            self._controller.set_current_color_rgba(rgba)

    def _on_brush_size_changed(self, value: int) -> None:
        """
        Užívateľ zmenil veľkosť štetca v spinboxe
        """
        if self._controller is None:
            return
        if hasattr(self._controller, "set_brush_size"):
            self._controller.set_brush_size(value)

    def set_brush_size_value(self, value: int) -> None:
        """
        Nastaví hodnotu spinboxu z controlleru
        """
        if not hasattr(self, "brush_spin"):
            return
        self.brush_spin.blockSignals(True)
        self.brush_spin.setValue(int(value))
        self.brush_spin.blockSignals(False)
