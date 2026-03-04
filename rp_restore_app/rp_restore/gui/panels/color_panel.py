from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from shiboken6 import isValid
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton,QHBoxLayout, QGridLayout, QColorDialog, QSpinBox, QToolButton, QFrame, QScrollArea

from rp_restore.core.project_model import Project


class ColorPanel(QWidget):
    """
    Panel s aktuálnou farbou a paletou farieb
    -zobrazuje aktuálnu farbu
    -umožňuje ju zmeniť cez QColorDialog
    -umožňuje pridať farbu do palety
    -zobrazuje paletu ako malé farebné štvorce
    """

    color_selected = Signal(QColor)

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
        self.current_color: QColor = QColor(0, 0, 0, 255)
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

        self.palette_container = QWidget()
        self.palette_layout = QGridLayout(self.palette_container)
        self.palette_layout.setSpacing(3)
        self.palette_layout.setContentsMargins(0, 0, 0, 0)

        self.palette_scroll = QScrollArea()
        self.palette_scroll.setWidgetResizable(True)
        self.palette_scroll.setWidget(self.palette_container)
        self.palette_scroll.setMinimumHeight(120)
        self.palette_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        layout.addWidget(self.palette_scroll)

        self.palette: list[QColor] = []
        self._palette_swatch_widgets: list[QWidget] = []

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
        self.set_current_color(color)

        #paleta
        while self.palette_layout.count():
            item = self.palette_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        palette = project.get_palette_colors()
        if not palette:
            self.palette_label.setText("Paleta: (prázdna)")
            self._palette_swatch_widgets = []
            return
        self.palette = [QColor(r, g, b, a) for (r, g, b, a) in palette]
        self.palette_label.setText("Paleta:")
        cols = 6
        self._palette_swatch_widgets = []
        for idx, rgba in enumerate(palette):
            r, g, b, a = rgba
            row = idx // cols
            col = idx % cols

            container = QFrame()
            container.setFixedSize(22, 22)
            container.setStyleSheet("border: 0px;")

            #swatch button (celý štvorček)
            swatch = QPushButton(container)
            swatch.setGeometry(0, 0, 20, 20)
            swatch.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid #555;")
            swatch.setToolTip(f"R={r}, G={g}, B={b}")
            swatch.clicked.connect(lambda checked=False, rgba=rgba: self._on_palette_color_clicked(rgba))

            self._palette_swatch_widgets.append(swatch)

            #delete "x" button (vpravo hore)
            xbtn = QToolButton(container)
            xbtn.setText("×")
            xbtn.setToolTip("Odstranit barvu")
            xbtn.setGeometry(12, -2, 12, 12)
            xbtn.setStyleSheet(
                "QToolButton { background: rgba(0,0,0,120); color: white; border: none; font-weight: bold; }"
                "QToolButton:hover { background: rgba(200,0,0,180); }"
            )
            xbtn.clicked.connect(lambda checked=False, i=idx: self.remove_color_from_palette(i))

            self.palette_layout.addWidget(container, row, col)

    def _flash_palette_index(self, index: int) -> None:
        if index < 0 or index >= len(self._palette_swatch_widgets):
            return
        w = self._palette_swatch_widgets[index]
        if not isValid(w):
            return

        old_style = w.styleSheet()
        w.setStyleSheet(old_style + "border: 2px solid red;")

        def _restore():
            if isValid(w):
                w.setStyleSheet(old_style)
        QTimer.singleShot(700, _restore)

    def _set_swatch_color(self, color: QColor) -> None:
        self.swatch_label.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});""border: 1px solid #333;"
        )

    def _scroll_palette_to_index(self, index: int) -> None:
        if index < 0 or index >= len(self._palette_swatch_widgets):
            return
        w = self._palette_swatch_widgets[index]
        self.palette_scroll.ensureWidgetVisible(w, xmargin=10, ymargin=10)

    def _on_change_color_clicked(self) -> None:
        if self._controller is None or self._project is None:
            return

        r, g, b, a = self._project.get_current_color_rgba()
        initial = QColor(r, g, b, a)

        if initial.red() == 0 and initial.green() == 0 and initial.blue() == 0:
            initial = QColor(255, 255, 255, 255)

        color = QColorDialog.getColor(initial, self, "Vyber barvu", options=QColorDialog.DontUseNativeDialog)
        if not color.isValid():
            return

        self._set_swatch_color(color)

        if hasattr(self._controller, "set_current_color_rgba"):
            self._controller.set_current_color_rgba(
                (color.red(), color.green(), color.blue(), color.alpha())
            )

    def _on_add_to_palette_clicked(self) -> None:
        self.add_color_to_palette(self.current_color, avoid_duplicates=True)

    def _on_palette_color_clicked(self, rgba: tuple[int, int, int, int]) -> None:
        if self._controller is None:
            return
        r, g, b, a = rgba
        color = QColor(r, g, b, a)
        self._set_swatch_color(color)
        if hasattr(self._controller, "set_current_color_rgba"):
            self._controller.set_current_color_rgba(rgba)
        self.color_selected.emit(color)

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

    def set_current_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.current_color = color
        self._set_swatch_color(color)

    def add_color_to_palette(self, color: QColor, avoid_duplicates: bool = True) -> None:
        if self._controller is None or self._project is None:
            return
        if not color.isValid():
            return
        rgba = (color.red(), color.green(), color.blue(), color.alpha())

        if avoid_duplicates:
            for i, c in enumerate(self.palette):
                if (c.red(), c.green(), c.blue(), c.alpha()) == rgba:
                    self._scroll_palette_to_index(i)
                    self._flash_palette_index(i)
                    return
            
        if hasattr(self._controller, "add_color_to_palette_rgba"):
            self._controller.add_color_to_palette_rgba(rgba, avoid_duplicates=avoid_duplicates)

    def remove_color_from_palette(self, index: int) -> None:
        if self._controller is None or self._project is None:
            return
        if hasattr(self._controller, "remove_color_from_palette"):
            self._controller.remove_color_from_palette(index)
