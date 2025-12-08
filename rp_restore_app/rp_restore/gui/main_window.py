from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QStatusBar, QMessageBox

from rp_restore.config.settings import AppSettings
from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget
from rp_restore.gui.project_controller import ProjectController
from rp_restore.gui.start_screen_widget import StartScreenWidget


class MainWindow(QMainWindow):
    """
    hlavné okno aplikácie
    - pri štarte zobrazuje StartScreenWidget
    - po vytvorení/otvorení projektu zobrazuje canvas
    """

    def __init__(self, app_settings: AppSettings, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("RP – Reštaurovanie obrazov")

        self.resize(1200, 800)

        self.app_settings = app_settings

        #controller
        self.controller = ProjectController(app_settings=self.app_settings)

        #workspace canvas
        self.canvas = ImageCanvasWidget(self)
        self.controller.set_canvas(self.canvas)

        #start screen
        self.start_screen = StartScreenWidget(self)
        self.start_screen.set_recent_projects(self.app_settings.get_recent_projects())
        self.start_screen.new_project_requested.connect(self.on_new_project_requested)
        self.start_screen.open_project_requested.connect(self.on_open_project_requested)
        self.start_screen.open_recent_requested.connect(self.on_open_recent_requested)

        #začíname na start screene
        self.show_start_screen()

        #menu, status bar
        self._create_menus()
        self.setStatusBar(QStatusBar(self))

    #----------GUI setup-----------

    def _create_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("Nový projekt", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.on_new_project_requested)
        file_menu.addAction(new_action)

        #neskôr -Open/Save/Exit
        exit_action = QAction("Ukončiť", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    #----------prepínanie obrazoviek-----------

    def show_start_screen(self) -> None:
        """zobrazí úvodnú obrazovku"""
        self.setCentralWidget(self.start_screen)

    def show_workspace(self) -> None:
        """zobrazí pracovnú plochu (canvas, neskôr aj dock panely)"""
        self.setCentralWidget(self.canvas)

    #----------akcie StartScreen-----------

    def on_new_project_requested(self) -> None:
        """vytvorí jednoduchý projekt a prepne do workspace"""
        project = self._create_beta_project()
        self.controller.set_project(project)
        self.show_workspace()

    def on_open_project_requested(self) -> None:
        """
        Bude otvárať existujúci projekt (zo .zip)
        Zatiaľ nič
        """
        QMessageBox.information(
            self,
            "ešte nie je",
            "otváranie existujúceho projektu zatiaľ nie je implementované\n"
            "použi Nový projekt",
        )

    def on_open_recent_requested(self, path: str) -> None:
        """
        bude otvárať projekt zo zoznamu naposledy otvorené
        zatiaľ len info
        """
        QMessageBox.information(
            self,
            "ešte nie je",
            f"otváranie recent projektu zatiaľ nie je implementované.\nPath: {path}",
        )

    #----------helper metódy-----------

    def _create_beta_project(self) -> Project:
        """
        vytvorí testovací Project s jednou background vrstvou –sivý obrázok 800x600
        """
        width, height = 800, 600

        image = np.zeros((height, width, 4), dtype=np.uint8)
        image[..., :3] = 200  #svetlo sivá
        image[..., 3] = 255   #alfa = 255

        meta = LayerMeta(
            id="background",
            name="Background",
            role=LayerRole.BACKGROUND,
        )
        bg_layer = Layer(meta, image)

        project = Project("beta project")
        project.add_layer(bg_layer)
        return project

