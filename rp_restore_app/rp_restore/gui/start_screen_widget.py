from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem


class StartScreenWidget(QWidget):
    """
    Úvodná obrazovka aplikácie
    obsahuje tlačidlá na vytvorenie alebo otvorenie projektu a zoznam naposledy otvorených projektov
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

        #nadpis aplikácie
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)
        title_layout.setAlignment(Qt.AlignCenter)

        icon_path = Path(__file__).resolve().parents[1] / "resources" / "RePaint_icon.png"
        icon_pixmap = QPixmap(str(icon_path))

        if not icon_pixmap.isNull():
            icon_label = QLabel()
            icon_label.setFixedSize(48, 48)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setPixmap(icon_pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            title_layout.addWidget(icon_label)

        title = QLabel("RePaint")
        title.setAlignment(Qt.AlignVCenter)
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        title_layout.addWidget(title)

        main_layout.addLayout(title_layout)

        #tlačidlá pre vytvorenie alebo otvorenie projektu
        buttons_layout = QHBoxLayout()
        self.new_button = QPushButton("Nový projekt")
        self.open_button = QPushButton("Otevřít projekt")

        buttons_layout.addWidget(self.new_button)
        buttons_layout.addWidget(self.open_button)
        main_layout.addLayout(buttons_layout)

        #zoznam naposledy otvorených projektov
        recent_label = QLabel("Naposledy otevřené projekty:")
        main_layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        main_layout.addWidget(self.recent_list)

        #signály
        self.new_button.clicked.connect(self.new_project_requested)
        self.open_button.clicked.connect(self.open_project_requested)
        self.recent_list.itemActivated.connect(self._on_recent_item_activated)

    def set_recent_projects(self, paths: list[str]) -> None:
        """Nastaví zoznam naposledy otvorených projektov"""
        self.recent_list.clear()
        for path in paths:
            display_path = path.replace("\\", "/")
            item = QListWidgetItem(display_path)
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.recent_list.addItem(item)

    def _on_recent_item_activated(self, item: QListWidgetItem) -> None:
        """Odošle signál na otvorenie vybraného naposledy otvoreného projektu"""
        path = item.data(Qt.UserRole)
        if not path:
            path = item.text()
        self.open_recent_requested.emit(path)
