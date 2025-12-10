from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QStatusBar, QMessageBox, QDockWidget, QToolBar

from rp_restore.config.settings import AppSettings
from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget
from rp_restore.gui.project_controller import ProjectController
from rp_restore.gui.start_screen_widget import StartScreenWidget
from rp_restore.gui.panels.layers_panel import LayersPanel


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
        self.canvas.set_controller(self.controller)

        #layers panel
        self.layers_panel = LayersPanel(self)
        self.layers_dock = QDockWidget("Vrstvy", self)
        self.layers_dock.setObjectName("LayersDock")
        self.layers_dock.setWidget(self.layers_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.layers_dock)

        #prepojenie controller - layers_panel
        self.controller.set_layers_panel(self.layers_panel)

        #na začiatku (start screen) dock schováme
        self.layers_dock.hide()

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
        self._create_toolbars()
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

        #undo/redo
        edit_menu = menu_bar.addMenu("&Edit")

        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.on_undo_triggered)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.on_redo_triggered)
        edit_menu.addAction(redo_action)


    def _create_toolbars(self) -> None:
        tools_toolbar = QToolBar("Nástroje", self)
        self.addToolBar(Qt.LeftToolBarArea, tools_toolbar)

        brush_action = QAction("Brush", self)
        brush_action.setShortcut("B")
        brush_action.triggered.connect(lambda: self.controller.set_current_tool("brush"))
        tools_toolbar.addAction(brush_action)

        eraser_action = QAction("Eraser", self)
        eraser_action.setShortcut("E")
        eraser_action.triggered.connect(lambda: self.controller.set_current_tool("eraser"))
        tools_toolbar.addAction(eraser_action)

    #----------prepínanie obrazoviek-----------

    def show_start_screen(self) -> None:
        """zobrazí úvodnú obrazovku"""
        self.setCentralWidget(self.start_screen)

        #schováme dock panely (kým nie je otvorený projekt)
        if hasattr(self, "layers_dock"):
            self.layers_dock.hide()

    def show_workspace(self) -> None:
        """zobrazí pracovnú plochu (canvas, neskôr aj dock panely)"""
        self.setCentralWidget(self.canvas)
        if hasattr(self, "layers_dock"):
            self.layers_dock.show()

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

    def on_undo_triggered(self) -> None:
        project = self.controller.project
        if project is None:
            return

        action = project.undo_global()
        if action is None:
            return

        #nastavíme aktívnu vrstvu podľa akcie
        self.controller.set_active_layer(action.layer_id)
        #refresh canvas a panel vrstiev
        self.controller.refresh_canvas()
        self.controller.refresh_layers_panel()

    def on_redo_triggered(self) -> None:
        project = self.controller.project
        if project is None:
            return

        action = project.redo_global()
        if action is None:
            return

        self.controller.set_active_layer(action.layer_id)
        self.controller.refresh_canvas()
        self.controller.refresh_layers_panel()


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

        #paint vrstva -zatiaľ celá priehľadná
        paint_image = np.zeros((height, width, 4), dtype=np.uint8)
        paint_meta = LayerMeta(id="paint_1", name="Paint 1", role=LayerRole.PAINT)
        paint_layer = Layer(paint_meta, paint_image)

        project = Project("beta project")
        project.add_layer(bg_layer)
        project.add_layer(paint_layer)

        return project

