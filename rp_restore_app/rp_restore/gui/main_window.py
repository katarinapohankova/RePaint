from __future__ import annotations

import numpy as np
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QStatusBar, QMessageBox, QDockWidget, QToolBar, QFileDialog

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
        # self.canvas = ImageCanvasWidget(self)
        # self.controller.set_canvas(self.canvas)
        # self.canvas.set_controller(self.controller)
        self.canvas = None

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
        self.start_screen = None
        # self.start_screen = StartScreenWidget(self)
        # self.start_screen.set_recent_projects(self.app_settings.get_recent_projects())
        # self.start_screen.new_project_requested.connect(self.on_new_project_from_image)
        # self.start_screen.open_project_requested.connect(self.on_open_project_requested)
        # self.start_screen.open_recent_requested.connect(self.on_open_recent_requested)

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

        new_beta_action = QAction("Nový projekt (beta)", self)
        new_beta_action.setShortcut("Ctrl+Shift+N")
        new_beta_action.triggered.connect(self.on_new_project_beta)
        file_menu.addAction(new_beta_action)

        new_from_image_action = QAction("Nový projekt z obrázku...", self)
        new_from_image_action.setShortcut("Ctrl+N")
        new_from_image_action.triggered.connect(self.on_new_project_from_image)
        file_menu.addAction(new_from_image_action)

        open_action = QAction("Otvoriť projekt...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.on_open_project_requested)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Uložiť projekt", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.on_save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Uložiť projekt ako...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.on_save_project_as)
        file_menu.addAction(save_as_action)

        close_project_action = QAction("Zavrieť projekt", self)
        close_project_action.setShortcut("Ctrl+W")
        close_project_action.triggered.connect(self.on_close_project)
        file_menu.addAction(close_project_action)

        file_menu.addSeparator()

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

        view_menu = menu_bar.addMenu("&View")

        self.toggle_damage_overlay_action = QAction("Zobraziť poškodené oblasti", self)
        self.toggle_damage_overlay_action.setCheckable(True)
        self.toggle_damage_overlay_action.setChecked(True)
        self.toggle_damage_overlay_action.triggered.connect(self.on_toggle_damage_overlay)
        view_menu.addAction(self.toggle_damage_overlay_action)

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

        fill_action = QAction("Fill", self)
        fill_action.setShortcut("F")
        fill_action.triggered.connect(lambda: self.controller.set_current_tool("fill"))
        tools_toolbar.addAction(fill_action)

        selection_action = QAction("Select", self)
        selection_action.setShortcut("S")
        selection_action.triggered.connect(lambda: self.controller.set_current_tool("selection"))
        tools_toolbar.addAction(selection_action)

    #----------prepínanie obrazoviek-----------

    def show_start_screen(self) -> None:
        """zobrazí úvodnú obrazovku"""
        # if self.start_screen is not None:
        #     self.start_screen.deleteLater()
        #     self.start_screen = None
        # self.setCentralWidget(self.start_screen)

        start_screen = StartScreenWidget(self)
        start_screen.set_recent_projects(self.app_settings.get_recent_projects())
        start_screen.new_project_requested.connect(self.on_new_project_from_image)
        start_screen.open_project_requested.connect(self.on_open_project_requested)
        start_screen.open_recent_requested.connect(self.on_open_recent_requested)

        self.start_screen = start_screen
        self.setCentralWidget(self.start_screen)

        #schováme dock panely (kým nie je otvorený projekt)
        if hasattr(self, "layers_dock"):
            self.layers_dock.hide()

    def show_workspace(self) -> None:
        """zobrazí pracovnú plochu (canvas, neskôr aj dock panely)"""
        #vytvoríme nový canvas vždy, keď ideme do workspace
        canvas = ImageCanvasWidget(self)
        self.canvas = canvas

        self.controller.set_canvas(canvas)
        canvas.set_controller(self.controller)

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
        zip_path, _ = QFileDialog.getOpenFileName(
            self,
            "Otvoriť projekt",
            "",
            "RP projekty (*.zip);;Všetky súbory (*.*)",
        )
        if not zip_path:
            return
        self.show_workspace()

        try:
            self.controller.open_project(zip_path)
        except Exception as e:
            QMessageBox.critical(self, "Chyba pri otváraní projektu", str(e))
            self.show_start_screen()
            return

        # aktualizujeme zoznam recent projektov na start screene
        #self.start_screen.set_recent_projects(self.app_settings.get_recent_projects())

    def on_open_recent_requested(self, path: str) -> None:
        """
        bude otvárať projekt zo zoznamu naposledy otvorené
        zatiaľ len info
        """
        self.show_workspace()

        try:
            self.controller.open_project(path)
        except Exception as e:
            QMessageBox.critical(self, "Chyba pri otváraní projektu", str(e))
            self.show_start_screen()
            return


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

    def on_new_project_from_image(self) -> None:
        """
        Vytvorí nový projekt z obrázka (a voliteľne masky)
        """
        img_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyber základný obrázok",
            "",
            "Obrázky (*.png *.jpg *.jpeg *.tif *.tiff);;Všetky súbory (*.*)",
        )
        if not img_path:
            return

        mask_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyber masku poškodenia (voliteľné)",
            "",
            "Obrázky (*.png *.jpg *.jpeg *.tif *.tiff);;Všetky súbory (*.*)",
        )
        if not mask_path:
            mask_path = None

        self.show_workspace()

        try:
            self.controller.create_project_from_files(img_path, mask_path)
        except Exception as e:
            QMessageBox.critical(self, "Chyba pri vytváraní projektu", str(e))
            self.controller.close_project()
            self.show_start_screen()
            return


    def on_save_project(self) -> None:
        """
        Uloží projekt na existujúcu cestu, alebo spustí Uložiť ako...
        """
        if self.controller.project is None:
            QMessageBox.information(self, "Žiadny projekt", "Nie je otvorený žiadny projekt")
            return

        if not self.controller.save_project():
            # nemáme current_project_path → Save As
            self.on_save_project_as()
            return

        #self.start_screen.set_recent_projects(self.app_settings.get_recent_projects())
        self.statusBar().showMessage("Projekt uložený", 3000)

    def on_save_project_as(self) -> None:
        """
        Uloží projekt do nového .zip súboru
        """
        if self.controller.project is None:
            QMessageBox.information(self, "Žiadny projekt", "Nie je otvorený žiadny projekt")
            return

        zip_path, _ = QFileDialog.getSaveFileName(
            self,
            "Uložiť projekt ako",
            "",
            "RP projekty (*.zip);;Všetky súbory (*.*)",
        )
        if not zip_path:
            return

        if not zip_path.lower().endswith(".zip"):
            zip_path += ".zip"

        try:
            self.controller.save_project_as(zip_path)
        except Exception as e:
            QMessageBox.critical(self, "Chyba pri ukladaní projektu", str(e))
            return

        #self.start_screen.set_recent_projects(self.app_settings.get_recent_projects())
        self.statusBar().showMessage("Projekt uložený", 3000)

    def on_toggle_damage_overlay(self, checked: bool) -> None:
        """
        zapne/vypne vizualizáciu damage masky na canvase
        """
        self.controller.set_show_damage_overlay(checked)

    def on_close_project(self) -> None:
        """
        Zavrie aktuálny projekt a vráti sa na úvodnú obrazovku
        """
        if self.controller.project is None:
            # nič nie je otvorené, tak len ukážeme start screen 
            self.show_start_screen()
            return

        # neskôr sa spýtame na uloženie (Save)
        self.show_start_screen()


    #----------helper metódy-----------

    def on_new_project_beta(self) -> None:
        """Vytvorí jednoduchý beta projekt (na testovanie)"""
        self.show_workspace()
        project = self._create_beta_project()
        self.controller.set_project(project)
        self.controller.current_project_path = None

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

        #na skúšku je demage maska celý obraz
        damage_mask = np.ones((height, width), dtype=bool)
        project.set_damage_masks(damage_mask)

        return project

