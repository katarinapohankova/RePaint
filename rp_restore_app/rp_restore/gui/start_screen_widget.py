from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem
from PySide6.QtGui import QPalette


class StartScreenWidget(QWidget):
    """
    Úvodná obrazovka
      - tlačítko Nový projekt
      - tlačítko Otvoriť projekt
      - zoznam Naposledy otvorené projekty
    """

    new_project_requested = Signal()
    open_project_requested = Signal()
    open_recent_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, Qt.black)
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)

        #nadpis
        title = QLabel("RP – Reštaurovanie obrazov")
        title.setAlignment(Qt.AlignCenter)
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        #tlačítka Nový / Otvoriť
        buttons_layout = QHBoxLayout()
        self.new_button = QPushButton("Nový projekt")
        self.open_button = QPushButton("Otvoriť projekt")

        buttons_layout.addWidget(self.new_button)
        buttons_layout.addWidget(self.open_button)
        main_layout.addLayout(buttons_layout)

        #naposledy otvorené
        recent_label = QLabel("Naposledy otvorené projekty:")
        main_layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        main_layout.addWidget(self.recent_list)

        #signály
        self.new_button.clicked.connect(self.new_project_requested)
        self.open_button.clicked.connect(self.open_project_requested)
        self.recent_list.itemActivated.connect(self._on_recent_item_activated)

    def set_recent_projects(self, paths: List[str]) -> None:
        """nastaví zoznam naposledy otvorených projektov"""
        self.recent_list.clear()
        for path in paths:
            item = QListWidgetItem(path)
            self.recent_list.addItem(item)

    def _on_recent_item_activated(self, item: QListWidgetItem) -> None:
        path = item.text()
        self.open_recent_requested.emit(path)
