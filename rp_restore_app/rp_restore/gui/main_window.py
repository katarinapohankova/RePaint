from __future__ import annotations

import numpy as np
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMainWindow, QStatusBar, QMessageBox, QDockWidget, QToolBar, QFileDialog, QLabel

from rp_restore.config.settings import AppSettings
from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget
from rp_restore.gui.project_controller import ProjectController
from rp_restore.gui.start_screen_widget import StartScreenWidget
from rp_restore.gui.panels.layers_panel import LayersPanel
from rp_restore.gui.panels.log_panel import LogPanel
from rp_restore.gui.panels.algorithm_panel import AlgorithmPanel
from rp_restore.gui.panels.color_panel import ColorPanel
from rp_restore.gui.panels.edge_settings_panel import EdgeSettingsPanel
#from rp_restore.report.pdf_report import generate_report

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
        self.controller.set_message_callback(self._show_tool_message)
        self.setDockNestingEnabled(True)

        #layers panel
        self.layers_panel = LayersPanel(self)
        self.layers_dock = QDockWidget("Vrstvy", self)
        self.layers_dock.setObjectName("LayersDock")
        self.layers_dock.setWidget(self.layers_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock)

        #Log panel 
        self.log_panel = LogPanel(self)
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setWidget(self.log_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

        #algorithm panel 
        self.algorithm_panel = AlgorithmPanel(self)
        self.algorithm_dock = QDockWidget("Algoritmy", self)
        self.algorithm_dock.setObjectName("AlgorithmDock")
        self.algorithm_dock.setWidget(self.algorithm_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.algorithm_dock)
     
        #color panel
        self.color_panel = ColorPanel(self)
        self.color_dock = QDockWidget("Barvy", self)
        self.color_dock.setObjectName("ColorDock")
        self.color_dock.setWidget(self.color_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.color_dock)

        #edge nastavenia panel
        self.edge_settings_panel = EdgeSettingsPanel(self)
        self.edge_settings_dock = QDockWidget("Hrany", self)
        self.edge_settings_dock.setObjectName("EdgeSettingsDock")
        self.edge_settings_dock.setWidget(self.edge_settings_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.edge_settings_dock)

        #prepojenie controller - layers_panel, log_panel
        self.controller.set_layers_panel(self.layers_panel)
        self.controller.set_log_panel(self.log_panel)
        self.controller.set_algorithm_panel(self.algorithm_panel)
        self.controller.set_color_panel(self.color_panel)
        self.controller.set_edge_settings_panel(self.edge_settings_panel)

        #na začiatku (start screen) dock schováme
        self.layers_dock.hide()
        self.log_dock.hide()
        self.algorithm_dock.hide()
        self.color_dock.hide()
        self.edge_settings_dock.hide()

        self.layers_panel.visibility_changed.connect(self.controller.on_layer_visibility_changed)
        self.layers_panel.delete_layer_requested.connect(self._on_delete_layer_requested)

        #start screen
        self.start_screen = None
        # self.start_screen = StartScreenWidget(self)
        # self.start_screen.set_recent_projects(self.app_settings.get_recent_projects())
        # self.start_screen.new_project_requested.connect(self.on_new_project_from_image)
        # self.start_screen.open_project_requested.connect(self.on_open_project_requested)
        # self.start_screen.open_recent_requested.connect(self.on_open_recent_requested)

        self.current_tool_name: str | None = None
        #začíname na start screene
        self.show_start_screen()

        #menu, status bar
        self._create_menus()
        self._create_toolbars()
        self.setStatusBar(QStatusBar(self))

        #overlay na krátke hlášky v strede okna
        self._toast_label = QLabel(self)
        self._toast_label.setVisible(False)
        self._toast_label.setAlignment(Qt.AlignCenter)
        self._toast_label.setStyleSheet("""background-color: rgba(0, 0, 0, 180); color: white; padding: 8px 16px; border-radius: 8px; font-size: 12pt""")

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast_label.hide)


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

        # file_menu.addSeparator()

        # export_report_action = QAction("Exportovat report…", self)
        # export_report_action.triggered.connect(self.on_export_report)
        # file_menu.addAction(export_report_action)

        file_menu.addSeparator()

        #neskôr -Open/Save/Exit
        exit_action = QAction("Ukončiť", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        #undo/redo
        edit_menu = menu_bar.addMenu("&Edit")

        undo_action = QAction("Undo", self)
        undo_action.setShortcuts([QKeySequence.Undo])
        undo_action.triggered.connect(self.on_undo_triggered)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcuts([QKeySequence.Redo])
        redo_action.triggered.connect(self.on_redo_triggered)
        edit_menu.addAction(redo_action)

        view_menu = menu_bar.addMenu("&View")

        def _add_dock_toggle(view_menu, title: str, dock):
            action = QAction(title, self)
            action.setCheckable(True)
            action.setChecked(dock.isVisible())

            #menu -> dock
            action.toggled.connect(dock.setVisible)
            #dock -> menu (keď user zavrie krížikom)
            dock.visibilityChanged.connect(action.setChecked)

            view_menu.addAction(action)
            return action
        
        self.toggle_damage_overlay_action = QAction("Zobraziť poškodené oblasti", self)
        self.toggle_damage_overlay_action.setCheckable(True)
        self.toggle_damage_overlay_action.setChecked(True)
        self.toggle_damage_overlay_action.triggered.connect(self.on_toggle_damage_overlay)
        view_menu.addAction(self.toggle_damage_overlay_action)

        if hasattr(self, "layers_dock"):
            _add_dock_toggle(view_menu, "Vrstvy", self.layers_dock)

        if hasattr(self, "color_dock"):
            _add_dock_toggle(view_menu, "Barvy", self.color_dock)

        if hasattr(self, "log_dock"):
            _add_dock_toggle(view_menu, "Log", self.log_dock)

        if hasattr(self, "algorithm_dock"):
            _add_dock_toggle(view_menu, "Algoritmy", self.algorithm_dock)

        if hasattr(self, "edge_settings_dock"):
            _add_dock_toggle(view_menu, "Hrany", self.edge_settings_dock)

    def _create_toolbars(self) -> None:
        tools_toolbar = QToolBar("Nástroje", self)
        self.addToolBar(Qt.LeftToolBarArea, tools_toolbar)

        #skupina na exkluzívne checkovanie
        self.tool_action_group = QActionGroup(self)
        self.tool_action_group.setExclusive(True)
        self.tool_action_group.triggered.connect(self._on_tool_action_triggered)

        self.tool_actions: dict[QAction, str] = {}

        self.brush_action = QAction("Brush", self)
        self.brush_action.setShortcut("B")
        self.brush_action.setCheckable(True)
        tools_toolbar.addAction(self.brush_action)
        self.tool_action_group.addAction(self.brush_action)
        self.tool_actions[self.brush_action] = "brush"

        self.eraser_action = QAction("Eraser", self)
        self.eraser_action.setShortcut("E")
        self.eraser_action.setCheckable(True)
        tools_toolbar.addAction(self.eraser_action)
        self.tool_action_group.addAction(self.eraser_action)
        self.tool_actions[self.eraser_action] = "eraser"

        self.fill_action = QAction("Fill", self)
        self.fill_action.setShortcut("F")
        self.fill_action.setCheckable(True)
        tools_toolbar.addAction(self.fill_action)
        self.tool_action_group.addAction(self.fill_action)
        self.tool_actions[self.fill_action] = "fill"


        self.selection_action = QAction("Select", self)
        self.selection_action.setShortcut("S")
        self.selection_action.setCheckable(True)
        tools_toolbar.addAction(self.selection_action)
        self.tool_action_group.addAction(self.selection_action)
        self.tool_actions[self.selection_action] = "selection"

        self.edge_action = QAction("Edge", self)
        self.edge_action.setShortcut("G")  #G-graphics
        self.edge_action.setCheckable(True)
        tools_toolbar.addAction(self.edge_action)
        self.tool_action_group.addAction(self.edge_action)
        self.tool_actions[self.edge_action] = "edge"

        self.pipette_action = QAction("Pipette", self)
        self.pipette_action.setShortcut("I")    #eyedropper
        self.pipette_action.setCheckable(True)
        self.pipette_action.setToolTip("pipeta -vyber barvu z obrazu")
        tools_toolbar.addAction(self.pipette_action)
        self.tool_action_group.addAction(self.pipette_action)
        self.tool_actions[self.pipette_action] = "pipette"

        self.auto_fill_action = QAction("Auto-fill small", self)
        self.auto_fill_action.triggered.connect(self.on_auto_fill_small_regions)
        tools_toolbar.addAction(self.auto_fill_action)

    def _apply_right_dock_layout(self) -> None:
        """
        aby sa pravé docky neskladali cez seba, ale boli pod sebou (vertikálny split)
        """
        if not (hasattr(self, "algorithm_dock") and hasattr(self, "color_dock") and hasattr(self, "edge_settings_dock")):
            return

        self.setDockNestingEnabled(True)

        self.splitDockWidget(self.algorithm_dock, self.color_dock, Qt.Vertical)
        self.splitDockWidget(self.color_dock, self.edge_settings_dock, Qt.Vertical)

        self.resizeDocks(
            [self.algorithm_dock, self.color_dock, self.edge_settings_dock],
            [220, 320, 260],
            Qt.Vertical,
        )
        self.log_dock.show()
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomLeftCorner, Qt.BottomDockWidgetArea)
        

    def _show_tool_message(self, text: str) -> None:
        """
        Zobrazí krátke upozornenie v status bar
        """
        self.statusBar().showMessage(text, 4000)
        self._show_toast_message(text, 2500)

    def _show_toast_message(self, text: str, msec: int = 2500) -> None:
        """
        Zobrazí krátku hlášku uprostred pracovnej plochy a po chvíli zmizne
        """
        if not text:
            return

        self._toast_label.setText(text)
        self._toast_label.adjustSize()

        rect = self.rect()
        label_size = self._toast_label.sizeHint()

        x = (rect.width() - label_size.width()) // 2
        y = (rect.height() - label_size.height()) // 2

        self._toast_label.setGeometry(x, y, label_size.width(), label_size.height())

        self._toast_label.raise_()
        self._toast_label.show()

        self._toast_timer.stop()
        self._toast_timer.start(msec)


    def set_current_tool(self, tool_name: str) -> None:
        """
        Nastaví aktuálny nástroj v controllery a vizuálne ho zvýrazní v toolbar
        """
        self.controller.set_current_tool(tool_name)
        self.current_tool_name = tool_name

        #reset flagov
        for name, action in (
            ("brush", getattr(self, "action_brush", None)),
            ("eraser", getattr(self, "action_eraser", None)),
            ("fill", getattr(self, "action_fill", None)),
            ("selection", getattr(self, "action_selection", None)),
            ("edge", getattr(self, "action_edge", None)),
            ("pipette", getattr(self, "action_pipette", None)),
        ):
            if action is not None:
                action.setChecked(name == tool_name)

    #----------prepínanie obrazoviek-----------

    def show_start_screen(self) -> None:
        """zobrazí úvodnú obrazovku"""

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
        if hasattr(self, "log_dock"):
            self.log_dock.hide()
        if hasattr(self, "algorithm_dock"):
            self.algorithm_dock.hide()
        if hasattr(self, "color_dock"): 
            self.color_dock.hide()
        if hasattr(self, "edge_settings_dock"):
            self.edge_settings_dock.hide()

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
        if hasattr(self, "log_dock"):
            self.log_dock.show()
        if hasattr(self, "algorithm_dock"):
            self.algorithm_dock.show()
        if hasattr(self, "color_dock"):
            self.color_dock.show()
        if hasattr(self, "brush_action"): 
            self.brush_action.setChecked(True)  # spustí _on_tool_action_triggered
        if hasattr(self, "edge_settings_dock"):
            self.edge_settings_dock.show()
        QTimer.singleShot(0, self._apply_right_dock_layout)

    #----------akcie StartScreen-----------

    def _on_tool_action_triggered(self, action: QAction) -> None:
        """
        Reaguje na zmenu checknutého tool action v QActionGroup
        """
        tool_name = self.tool_actions.get(action)
        if not tool_name:
            return

        self.current_tool_name = tool_name
        self.controller.set_current_tool(tool_name)
        #QActionGroup sa postará o check/uncheck

    def _on_delete_layer_requested(self, layer_id: str) -> None:
        if self.controller.project is None:
            return

        reply = QMessageBox.question(
            self,
            "Smazat vrstvu",
            "Naozaj chceš smazat tuhle paint vrstvu?\nTahle akce nejde vrátit zpět",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        ok = self.controller.on_layer_delete_requested(layer_id)
        if not ok:
            QMessageBox.warning(self, "Smazat vrstvu", "Vrstvu sa nepodarilo smazat")

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

        #prekreslíme len daný bbox
        bbox = action.bbox
        self.controller.refresh_canvas_region(bbox)
        self.controller.refresh_layers_panel()

    def on_redo_triggered(self) -> None:
        project = self.controller.project
        if project is None:
            return

        action = project.redo_global()
        if action is None:
            return

        self.controller.set_active_layer(action.layer_id)
        bbox = action.bbox
        self.controller.refresh_canvas_region(bbox)
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

    # def on_export_report(self) -> None:
    #     """
    #     Exportuje PDF report o aktuálnom projekte
    #     """
    #     if self.controller.project is None:
    #         QMessageBox.information(self, "Žádný projekt", "Není otevřený žádný projekt")
    #         return

    #     pdf_path, _ = QFileDialog.getSaveFileName(
    #         self,
    #         "Uložit report jako",
    #         "",
    #         "PDF soubory (*.pdf);;Všechny soubory (*.*)",
    #     )
    #     if not pdf_path:
    #         return

    #     if not pdf_path.lower().endswith(".pdf"):
    #         pdf_path += ".pdf"

    #     try:
    #         generate_report(self.controller.project, pdf_path)
    #     except Exception as e:
    #         QMessageBox.critical(self, "Chyba při exportu reportu", str(e))
    #         return

    #     self.statusBar().showMessage("Report byl úspěšně exportován.", 5000)

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

    def on_auto_fill_small_regions(self) -> None:
        """
        Spustí automatické vyplnenie malých poškodených oblastí
        """
        if self.controller.project is None:
            QMessageBox.information(self, "Žiadny projekt", "Nie je otvorený žiadny projekt")
            return

        count = self.controller.run_auto_fill_small_regions()
        if count == 0:
            QMessageBox.information(
                self,
                "Auto-fill",
                "Nenašli sa žiadne malé oblasti na vyplnenie",
            )
        else:
            self.statusBar().showMessage(
                f"automaticky vyplnených oblastí: {count}",
                5000,
            )



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
        pridali sme 1 PAINT a 1 EDGE vrstvu
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

        edge_image = np.zeros((height, width, 4), dtype=np.uint8)
        edge_meta = LayerMeta(id="edge_1", name="Edges 1", role=LayerRole.EDGE)
        edge_layer = Layer(edge_meta, edge_image)

        project = Project("beta project")
        project.add_layer(bg_layer)
        project.add_layer(paint_layer)
        project.add_layer(edge_layer)

        #na skúšku je demage maska celý obraz
        damage_mask = np.ones((height, width), dtype=bool)
        project.set_damage_masks(damage_mask)

        return project

