from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QGridLayout, QColorDialog, QToolButton, QFrame, QScrollArea, QRadioButton, QButtonGroup, QGroupBox
from shiboken6 import isValid

from rp_restore.core.project_model import Project


class PalettePanel(QWidget):
    """
    Panel palety farieb pod vrstvami
    -aktuálna farba (swatch + dialog)
    -paleta (scroll, x na odstránenie, flash/scroll pri duplikáte)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None
        self._project: Optional[Project] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # title = QLabel("Paleta")
        # layout.addWidget(title)

        #---aktuálna farba---
        self.current_color: QColor = QColor(0, 0, 0, 255)

        swatch_row = QHBoxLayout()
        self.swatch_label = QLabel()
        self.swatch_label.setFixedSize(36, 36)
        self.swatch_label.setStyleSheet("background-color: black; border: 1px solid #333;")
        swatch_row.addWidget(self.swatch_label)

        self.btn_change_color = QPushButton("Změnit barvu…")
        self.btn_add_to_palette = QPushButton("Přidat do palety")
        swatch_row.addWidget(self.btn_change_color)
        layout.addLayout(swatch_row)
        layout.addWidget(self.btn_add_to_palette)

        #---paleta scroll---
        self.palette_label = QLabel("Paleta:")
        layout.addWidget(self.palette_label)

        self.palette_container = QWidget()
        self.palette_layout = QGridLayout(self.palette_container)
        self.palette_layout.setSpacing(3)
        self.palette_layout.setContentsMargins(0, 0, 0, 0)

        self.palette_scroll = QScrollArea()
        self.palette_scroll.setWidgetResizable(True)
        self.palette_scroll.setWidget(self.palette_container)
        self.palette_scroll.setMinimumHeight(140)
        self.palette_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        layout.addWidget(self.palette_scroll)

        self._palette_swatch_widgets: list[QWidget] = []

        layout.addStretch(1)

        #signals
        self.btn_change_color.clicked.connect(self._on_change_color_clicked)
        self.btn_add_to_palette.clicked.connect(self._on_add_to_palette_clicked)

    def set_controller(self, controller: object) -> None:
        self._controller = controller

    def refresh_from_project(self, project: Project) -> None:
        self._project = project

        #current color z projektu
        r, g, b, a = project.get_current_color_rgba()
        self.set_current_color(QColor(r, g, b, a))

        #rebuild palety
        while self.palette_layout.count():
            item = self.palette_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        palette = project.get_palette_colors()
        self._palette_swatch_widgets = []

        if not palette:
            self.palette_label.setText("Paleta: (prázdná)")
            return

        self.palette_label.setText("Paleta:")
        cols = 6

        for idx, rgba in enumerate(palette):
            r, g, b, a = rgba
            row = idx // cols
            col = idx % cols

            container = QFrame()
            container.setFixedSize(22, 22)
            container.setStyleSheet("border: 0px;")

            swatch = QPushButton(container)
            swatch.setGeometry(0, 0, 20, 20)
            swatch.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid #555;")
            swatch.setToolTip(f"R={r}, G={g}, B={b}")
            swatch.clicked.connect(lambda checked=False, rgba=rgba: self._on_palette_color_clicked(rgba))

            self._palette_swatch_widgets.append(swatch)

            xbtn = QToolButton(container)
            xbtn.setText("×")
            xbtn.setToolTip("Odstranit barvu")
            xbtn.setGeometry(12, -2, 12, 12)
            xbtn.setStyleSheet(
                "QToolButton { background: rgba(0,0,0,120); color: white; border: none; font-weight: bold; }"
                "QToolButton:hover { background: rgba(200,0,0,180); }"
            )
            xbtn.clicked.connect(lambda checked=False, i=idx: self._remove_color_from_palette(i))

            self.palette_layout.addWidget(container, row, col)

    #---------UI----------

    def set_current_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.current_color = color
        self.swatch_label.setStyleSheet(
            f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            "border: 1px solid #333;"
        )

    def _scroll_palette_to_index(self, index: int) -> None:
        if index < 0 or index >= len(self._palette_swatch_widgets):
            return
        w = self._palette_swatch_widgets[index]
        self.palette_scroll.ensureWidgetVisible(w, xmargin=10, ymargin=10)

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

    def _on_change_color_clicked(self) -> None:
        if self._project is None:
            return

        initial = self.current_color
        if initial.red() == 0 and initial.green() == 0 and initial.blue() == 0:
            initial = QColor(255, 255, 255, 255)

        color = QColorDialog.getColor(initial, self, "Vyber barvu", options=QColorDialog.DontUseNativeDialog)
        if not color.isValid():
            return

        self.set_current_color(color)
        rgba = (color.red(), color.green(), color.blue(), color.alpha())
        if self._controller is not None and hasattr(self._controller, "set_current_color_rgba"):
            self._controller.set_current_color_rgba(rgba)

    def _on_add_to_palette_clicked(self) -> None:
        if self._controller is None or self._project is None:
            return

        rgba = (self.current_color.red(), self.current_color.green(), self.current_color.blue(), self.current_color.alpha())
        palette = self._project.get_palette_colors()

        for i, p in enumerate(palette):
            if tuple(p) == rgba:
                self._scroll_palette_to_index(i)
                self._flash_palette_index(i)
                return

        if hasattr(self._controller, "add_color_to_palette_rgba"):
            self._controller.add_color_to_palette_rgba(rgba, avoid_duplicates=True)

    def _on_palette_color_clicked(self, rgba: tuple[int, int, int, int]) -> None:
        r, g, b, a = rgba
        self.set_current_color(QColor(r, g, b, a))
        if self._controller is not None and hasattr(self._controller, "set_current_color_rgba"):
            self._controller.set_current_color_rgba(rgba)

    def _remove_color_from_palette(self, index: int) -> None:
        if self._controller is None:
            return
        if hasattr(self._controller, "remove_color_from_palette"):
            self._controller.remove_color_from_palette(index)