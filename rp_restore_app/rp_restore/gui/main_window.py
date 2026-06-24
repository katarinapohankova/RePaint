from __future__ import annotations

import numpy as np
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QCloseEvent, QCursor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMainWindow, QSizePolicy, QSlider, QSpinBox, QStatusBar, QMessageBox, QDockWidget, QToolBar, QFileDialog, QLabel, QAbstractButton, QScrollArea, QWidget, QWidgetAction

from rp_restore.config.settings import AppSettings
from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget
from rp_restore.gui.project_controller import ProjectController
from rp_restore.gui.start_screen_widget import StartScreenWidget
from rp_restore.gui.panels.layers_panel import LayersPanel
from rp_restore.gui.panels.log_panel import LogPanel
from rp_restore.gui.panels.algorithm_panel import AlgorithmPanel
from rp_restore.gui.panels.edge_settings_panel import EdgeSettingsPanel
from rp_restore.gui.panels.materials_panel import MaterialsPanel
from rp_restore.gui.panels.palette_panel import PalettePanel
from rp_restore.gui.colorchecker_dialog import ColorCheckerDialog
from rp_restore.report.pdf_report import generate_report
from rp_restore.report.report_dialog import ReportDialog

class MainWindow(QMainWindow):
    """
    hlavné okno aplikácie
    - pri štarte zobrazuje StartScreenWidget
    - po vytvorení/otvorení projektu zobrazuje canvas
    """

    def __init__(self, app_settings: AppSettings, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("RePaint")

        self.resize(1200, 800)

        self.app_settings = app_settings

        #controller
        self.controller = ProjectController(app_settings=self.app_settings)
        self.controller.set_undo_redo_changed_callback(self.update_undo_redo_actions)

        #workspace canvas
        # self.canvas = ImageCanvasWidget(self)
        # self.controller.set_canvas(self.canvas)
        # self.canvas.set_controller(self.controller)
        self.canvas = None
        self.controller.set_message_callback(self._show_tool_message)
        self.controller.set_brush_size_preview_callback(self._show_brush_size_preview)
        self.setDockNestingEnabled(True)

        #autofill
        self.auto_fill_slider: QSlider | None = None
        self.auto_fill_spinbox: QSpinBox | None = None

        #layers panel
        self.layers_panel = LayersPanel(self)
        self.layers_dock = QDockWidget("Vrstvy", self)
        self.layers_dock.setObjectName("LayersDock")
        self.layers_dock.setWidget(self.layers_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock)

        self.palette_panel = PalettePanel(self)
        self.palette_dock = QDockWidget("Paleta", self)
        self.palette_dock.setObjectName("PaletteDock")
        self.palette_dock.setWidget(self.palette_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)

        self.splitDockWidget(self.layers_dock, self.palette_dock, Qt.Vertical)
        

        #Log panel 
        self.log_panel = LogPanel(self)
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setWidget(self.log_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

        #algorithm panel 
        self.algorithm_panel = AlgorithmPanel(self)
        self.algorithm_dock = QDockWidget("Externé algoritmy", self)
        self.algorithm_dock.setObjectName("AlgorithmDock")
        self.algorithm_dock.setWidget(self.algorithm_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.algorithm_dock)

        #edge nastavenia panel
        self.edge_settings_panel = EdgeSettingsPanel(self)
        self.edge_settings_dock = QDockWidget("Hrany", self)
        self.edge_settings_dock.setObjectName("EdgeSettingsDock")
        self.edge_settings_dock.setWidget(self.edge_settings_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.edge_settings_dock)

        self.materials_panel = MaterialsPanel(self)
        self.materials_scroll = QScrollArea(self)
        self.materials_scroll. setWidgetResizable(True)
        self.materials_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.materials_scroll.setWidget(self.materials_panel)
        self.materials_dock = QDockWidget("Materiály", self)
        self.materials_dock.setObjectName("MaterialsDock")
        self.materials_dock.setWidget(self.materials_scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.materials_dock)

        #prepojenie controller - layers_panel, log_panel
        self.controller.set_layers_panel(self.layers_panel)
        self.controller.set_log_panel(self.log_panel)
        self.controller.set_algorithm_panel(self.algorithm_panel)
        self.controller.set_edge_settings_panel(self.edge_settings_panel)
        self.controller.set_materials_panel(self.materials_panel)
        self.controller.set_palette_panel(self.palette_panel)

        #na začiatku (start screen) dock schováme
        self.layers_dock.hide()
        self.log_dock.hide()
        self.algorithm_dock.hide()
        self.edge_settings_dock.hide()
        self.palette_dock.hide()

        self.layers_panel.visibility_changed.connect(self.controller.on_layer_visibility_changed)
        self.layers_panel.delete_layer_requested.connect(self._on_delete_layer_requested)
        self.layers_panel.opacity_changed.connect(self.controller.on_layer_opacity_changed)

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

        #overlay kruh pre náhľad veľkosti štetca
        self._brush_preview_label = QLabel(self)
        self._brush_preview_label.setVisible(False)
        self._brush_preview_label.setAlignment(Qt.AlignCenter)

        self._brush_preview_timer = QTimer(self)
        self._brush_preview_timer.setSingleShot(True)
        self._brush_preview_timer.timeout.connect(self._brush_preview_label.hide)

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

        open_action = QAction("Otevřít projekt...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.on_open_project_requested)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Uložit projekt", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.on_save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Uložit projekt ako...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.on_save_project_as)
        file_menu.addAction(save_as_action)

        close_project_action = QAction("Zavřít projekt", self)
        close_project_action.setShortcut("Ctrl+W")
        close_project_action.triggered.connect(self.on_close_project)
        file_menu.addAction(close_project_action)

        export_img_action = QAction("Exportovat obraz…", self)
        export_img_action.triggered.connect(self.on_export_image)
        file_menu.addAction(export_img_action)

        file_menu.addSeparator()

        export_report_action = QAction("Exportovat report…", self)
        export_report_action.triggered.connect(self.on_export_report)
        file_menu.addAction(export_report_action)

        file_menu.addSeparator()

        #neskôr -Open/Save/Exit
        exit_action = QAction("Ukončit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        #undo/redo
        edit_menu = menu_bar.addMenu("&Edit")

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcuts([QKeySequence.Undo])
        self.undo_action.triggered.connect(self.on_undo_triggered)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcuts([QKeySequence.Redo])
        self.redo_action.triggered.connect(self.on_redo_triggered)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()
        self.colorchecker_action = QAction("ColorChecker...", self)
        self.colorchecker_action.triggered.connect(self.on_colorchecker_dialog)
        edit_menu.addAction(self.colorchecker_action)

        edit_menu.addSeparator()

        increase_brush_action = QAction("Zvětšit štětec", self)
        increase_brush_action.setShortcuts([QKeySequence("+"), QKeySequence("=")])
        increase_brush_action.triggered.connect(lambda: self.controller.adjust_brush_size(1))
        edit_menu.addAction(increase_brush_action)

        decrease_brush_action = QAction("Zmenšit štětec", self)
        decrease_brush_action.setShortcut(QKeySequence("-"))
        decrease_brush_action.triggered.connect(lambda: self.controller.adjust_brush_size(-1))
        edit_menu.addAction(decrease_brush_action)

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
        
        self.toggle_damage_overlay_action = QAction("Zobrazit poškoděné oblasti", self)
        self.toggle_damage_overlay_action.setCheckable(True)
        self.toggle_damage_overlay_action.setChecked(True)
        self.toggle_damage_overlay_action.triggered.connect(self.on_toggle_damage_overlay)
        view_menu.addAction(self.toggle_damage_overlay_action)

        opacity_action = QWidgetAction(self)
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(0, 100)

        #default 35%
        opacity_slider.setValue(35)

        opacity_slider.setToolTip("Priehľadnosť poškodených oblastí")

        opacity_slider.valueChanged.connect(lambda v: self.controller.set_damage_overlay_opacity(v / 100.0))
        opacity_action.setDefaultWidget(opacity_slider)
        view_menu.addAction(opacity_action)

        #slider aktívny len keď je overlay zapnutý
        opacity_slider.setEnabled(self.toggle_damage_overlay_action.isChecked())
        self.toggle_damage_overlay_action.toggled.connect(opacity_slider.setEnabled)

        view_menu.addSeparator()

        self.toggle_colorchecker_action = QAction("Použít ColorChecker korekci", self)
        self.toggle_colorchecker_action.setCheckable(True)
        self.toggle_colorchecker_action.setChecked(False)
        self.toggle_colorchecker_action.setEnabled(False)
        self.toggle_colorchecker_action.toggled.connect(self.on_toggle_colorchecker)
        view_menu.addAction(self.toggle_colorchecker_action)

        if hasattr(self, "layers_dock"):
            _add_dock_toggle(view_menu, "Vrstvy", self.layers_dock)

        if hasattr(self, "materials_dock"):
            _add_dock_toggle(view_menu, "Materiály", self.materials_dock)

        if hasattr(self, "palette_dock"):
            _add_dock_toggle(view_menu, "Paleta", self.palette_dock)

        if hasattr(self, "log_dock"):
            _add_dock_toggle(view_menu, "Log", self.log_dock)

        if hasattr(self, "algorithm_dock"):
            _add_dock_toggle(view_menu, "Algoritmy", self.algorithm_dock)

        if hasattr(self, "edge_settings_dock"):
            _add_dock_toggle(view_menu, "Hrany", self.edge_settings_dock)

    def _create_toolbars(self) -> None:
        self.tools_toolbar = QToolBar("Nástroje", self)
        self.addToolBar(Qt.LeftToolBarArea, self.tools_toolbar)

        #skupina na exkluzívne checkovanie
        self.tool_action_group = QActionGroup(self)
        self.tool_action_group.setExclusive(True)
        self.tool_action_group.triggered.connect(self._on_tool_action_triggered)

        self.tool_actions: dict[QAction, str] = {}

        self.brush_action = QAction("Štětec", self)
        self.brush_action.setShortcut("B")
        self.brush_action.setCheckable(True)
        self.tools_toolbar.addAction(self.brush_action)
        self.tool_action_group.addAction(self.brush_action)
        self.tool_actions[self.brush_action] = "brush"

        self.eraser_action = QAction("Guma", self)
        self.eraser_action.setShortcut("E")
        self.eraser_action.setCheckable(True)
        self.tools_toolbar.addAction(self.eraser_action)
        self.tool_action_group.addAction(self.eraser_action)
        self.tool_actions[self.eraser_action] = "eraser"

        self.blend_action = QAction("Blend", self)
        self.blend_action.setShortcut("D")
        self.blend_action.setCheckable(True)
        self.blend_action.setToolTip("Rozmazává na aktivní paint vrstvě, nebo i na background vrstvě")
        self.tools_toolbar.addAction(self.blend_action)
        self.tool_action_group.addAction(self.blend_action)
        self.tool_actions[self.blend_action] = "blend"

        self.fill_action = QAction("Výplň", self)
        self.fill_action.setShortcut("F")
        self.fill_action.setCheckable(True)
        self.tools_toolbar.addAction(self.fill_action)
        self.tool_action_group.addAction(self.fill_action)
        self.tool_actions[self.fill_action] = "fill"


        self.selection_action = QAction("Vybrat", self)
        self.selection_action.setShortcut("S")
        self.selection_action.setCheckable(True)
        self.tools_toolbar.addAction(self.selection_action)
        self.tool_action_group.addAction(self.selection_action)
        self.tool_actions[self.selection_action] = "selection"

        self.lasso_action = QAction("Laso", self)
        self.lasso_action.setShortcut("L")
        self.lasso_action.setCheckable(True)
        self.tools_toolbar.addAction(self.lasso_action)
        self.tool_action_group.addAction(self.lasso_action)
        self.tool_actions[self.lasso_action] = "lasso"

        self.edge_action = QAction("Hrana", self)
        self.edge_action.setShortcut("G")  #G-graphics
        self.edge_action.setCheckable(True)
        self.tools_toolbar.addAction(self.edge_action)
        self.tool_action_group.addAction(self.edge_action)
        self.tool_actions[self.edge_action] = "edge"

        self.edge_blend_action = QAction("Zjemnit hranu", self)
        self.edge_blend_action.setShortcut("M")
        self.edge_blend_action.setCheckable(True)
        self.edge_blend_action.setToolTip("Zjemní přechod přes existující hranu a odstraní ji")
        self.tools_toolbar.addAction(self.edge_blend_action)
        self.tool_action_group.addAction(self.edge_blend_action)
        self.tool_actions[self.edge_blend_action] = "edge_blend"

        self.pipette_action = QAction("Pipeta", self)
        self.pipette_action.setShortcut("I")    #eyedropper
        self.pipette_action.setCheckable(True)
        self.pipette_action.setToolTip("pipeta -vyber barvu z obrazu")
        self.tools_toolbar.addAction(self.pipette_action)
        self.tool_action_group.addAction(self.pipette_action)
        self.tool_actions[self.pipette_action] = "pipette"

        self.auto_fill_action = QAction("Auto-výplň mini \n (px)", self)
        self.auto_fill_action.triggered.connect(self.on_auto_fill_small_regions)
        self.tools_toolbar.addAction(self.auto_fill_action)

        auto_fill_widget = QWidget(self)
        auto_fill_layout = QHBoxLayout(auto_fill_widget)
        auto_fill_layout.setContentsMargins(0, 0, 0, 0)
        auto_fill_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.auto_fill_slider = QSlider(Qt.Vertical, auto_fill_widget)
        self.auto_fill_slider.setMinimum(1)
        self.auto_fill_slider.setMaximum(5000)
        self.auto_fill_slider.setValue(self.controller.auto_fill_threshold)
        self.auto_fill_slider.setFixedHeight(120)

        self.auto_fill_spinbox = QSpinBox(auto_fill_widget)
        self.auto_fill_spinbox.setMinimum(1)
        self.auto_fill_spinbox.setMaximum(5000)
        self.auto_fill_spinbox.setValue(self.controller.auto_fill_threshold)

        auto_fill_layout.addWidget(self.auto_fill_slider)
        auto_fill_layout.addWidget(self.auto_fill_spinbox)

        self.tools_toolbar.addWidget(auto_fill_widget)

        self.auto_fill_slider.valueChanged.connect(self._sync_auto_fill_slider_to_spinbox_only)
        self.auto_fill_slider.sliderReleased.connect(self._commit_auto_fill_slider_value)

        self.auto_fill_spinbox.valueChanged.connect(self._sync_auto_fill_spinbox_to_slider_only)
        self.auto_fill_spinbox.editingFinished.connect(self._commit_auto_fill_spinbox_value)

        self.tools_toolbar.hide()

    def _apply_right_dock_layout(self) -> None:
        """
        aby sa pravé docky neskladali cez seba, ale boli pod sebou (vertikálny split)
        """
        if not (hasattr(self, "algorithm_dock") and hasattr(self, "edge_settings_dock") and hasattr(self, "materials_dock")):
            return

        self.setDockNestingEnabled(True)

        self.splitDockWidget(self.algorithm_dock, self.edge_settings_dock, Qt.Vertical)
        self.splitDockWidget(self.edge_settings_dock, self.materials_dock, Qt.Vertical)

        self.resizeDocks(
            [self.algorithm_dock, self.edge_settings_dock, self.materials_dock],
            [200, 220, 380],
            Qt.Vertical,
        )
        # self.log_dock.show()
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

    def _show_brush_size_preview(self, brush_size: int) -> None:
        """
        Zobrazí dočasný kruh zodpovedajúci aktuálnej veľkosti štetca
        -veľkosť sa prepočítava podľa zoomu canvasu
        """
        if self.canvas is None:
            return

        zoom = float(getattr(self.canvas, "zoom_factor", 1.0))
        diameter = int(max(8, round(brush_size * 2 * zoom)))

        #aby pri veľkom zoome nebol overlay cez celé okno
        diameter = min(diameter, 500)

        self._brush_preview_label.setText(f"{brush_size}px")
        self._brush_preview_label.setFixedSize(QSize(diameter, diameter))
        self._brush_preview_label.setStyleSheet(
            f"""
            QLabel {{
                color: white;
                background-color: rgba(0, 0, 0, 35);
                border: 2px solid rgba(255, 255, 255, 210);
                border-radius: {diameter // 2}px;
                font-size: 11px;
            }}
            """
        )

        canvas_center = self.canvas.rect().center()
        center_in_window = self.canvas.mapTo(self, canvas_center)

        x = center_in_window.x() - diameter // 2
        y = center_in_window.y() - diameter // 2

        self._brush_preview_label.setGeometry(x, y, diameter, diameter)
        self._brush_preview_label.raise_()
        self._brush_preview_label.show()

        self._brush_preview_timer.stop()
        self._brush_preview_timer.start(2000)

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
        self._update_colorchecker_actions()

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
        if hasattr(self, "materials_dock"):
            self.materials_dock.hide()
        if hasattr(self, "palette_dock"):
            self.palette_dock.hide()
        if hasattr(self, "tools_toolbar"):
            self.tools_toolbar.hide()

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
        # if hasattr(self, "log_dock"):
        #     self.log_dock.show()
        if hasattr(self, "algorithm_dock"):
            self.algorithm_dock.show()
        if hasattr(self, "brush_action"): 
            self.brush_action.setChecked(True)  # spustí _on_tool_action_triggered
        if hasattr(self, "edge_settings_dock"):
            self.edge_settings_dock.show()
        if hasattr(self, "materials_dock"):
            self.materials_dock.show()
        if hasattr(self, "palette_dock"):
            self.palette_dock.show()
        if hasattr(self, "tools_toolbar"):
            self.tools_toolbar.show()
        QTimer.singleShot(0, self._apply_right_dock_layout)
        self.update_undo_redo_actions()
        self._update_colorchecker_actions()

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
        self._update_colorchecker_actions()

    def on_open_project_requested(self) -> None:
        """
        Bude otvárať existujúci projekt (zo .zip)
        Zatiaľ nič
        """
        zip_path, _ = QFileDialog.getOpenFileName(
            self,
            "Otevřít projekt",
            "",
            "RP projekty (*.zip);;Všetky súbory (*.*)",
        )
        if not zip_path:
            return
        self.show_workspace()

        try:
            self.controller.open_project(zip_path)
            if hasattr(self, "texture_panel"):
                self.texture_panel.refresh_from_controller()
            self.update_undo_redo_actions()
            self._update_colorchecker_actions()
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
            if hasattr(self, "texture_panel"):
                self.texture_panel.refresh_from_controller()
            self._update_colorchecker_actions()
        except Exception as e:
            QMessageBox.critical(self, "Chyba pri otváraní projektu", str(e))
            self.show_start_screen()
            return

    def on_export_image(self) -> None:
        if self.controller.project is None:
            QMessageBox.information(self, "Žándý projekt", "Není otevřený žádný projekt")
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportovat obraz",
            "",
            "TIFF (*.tif *.tiff);;PNG (*.png);;JPEG (*.jpg *.jpeg)",
        )
        if not path:
            return

        p = Path(path)
        if p.suffix == "":
            if "TIFF" in selected_filter:
                path += ".tif"
            elif "PNG" in selected_filter:
                path += ".png"
            else:
                path += ".jpg"

        try:
            self.controller.export_image(path)
        except Exception as e:
            QMessageBox.critical(self, "Chyba exportu", str(e))
            return

        self.statusBar().showMessage("Obraz byl exportován", 4000)

    def on_undo_triggered(self) -> None:
        project = self.controller.project
        if project is None:
            return

        action = project.undo_global()
        if action is None:
            return
        
        self.controller.invalidate_selection_region_map_cache()

        #nastavíme aktívnu vrstvu podľa akcie
        self.controller.set_active_layer(action.layer_id)
        #refresh canvas a panel vrstiev

        #prekreslíme len daný bbox
        bbox = action.bbox
        self.controller.refresh_canvas_region(bbox)
        self.controller.refresh_layers_panel()

        self._show_toast_message("Undo", 1500)
        self.update_undo_redo_actions()

    def on_redo_triggered(self) -> None:
        project = self.controller.project
        if project is None:
            return

        action = project.redo_global()
        if action is None:
            return
        
        self.controller.invalidate_selection_region_map_cache()

        self.controller.set_active_layer(action.layer_id)
        bbox = action.bbox
        self.controller.refresh_canvas_region(bbox)
        self.controller.refresh_layers_panel()

        self._show_toast_message("Redo", 1500)
        self.update_undo_redo_actions()

    def update_undo_redo_actions(self) -> None:
        if not hasattr(self, "undo_action") or not hasattr(self, "redo_action"):
            return
        self.undo_action.setEnabled(self.controller.can_undo())
        self.redo_action.setEnabled(self.controller.can_redo())

    def _update_colorchecker_actions(self) -> None:
        """
        Zapne/vypne možnosti v menu podľa toho, či projekt má color correction
        """
        proj = self.controller.project
        if proj is None:
            if hasattr(self, "toggle_colorchecker_action"):
                self.toggle_colorchecker_action.setEnabled(False)
                self.toggle_colorchecker_action.setChecked(False)
            return

        has_cc = proj.has_color_correction()
        if hasattr(self, "toggle_colorchecker_action"):
            self.toggle_colorchecker_action.setEnabled(has_cc)
            self.toggle_colorchecker_action.blockSignals(True)
            self.toggle_colorchecker_action.setChecked(bool(proj.color_correction_enabled) if has_cc else False)
            self.toggle_colorchecker_action.blockSignals(False)

    def on_colorchecker_dialog(self) -> None:
        if self.controller.project is None:
            QMessageBox.information(self, "Žiadny projekt", "Nie je otvorený žiadny projekt.")
            return

        dlg = ColorCheckerDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        result = dlg.get_result()
        if result is None:
            QMessageBox.warning(self, "ColorChecker", "Nebola spočítaná korekcia.")
            return

        #uložíme do projektu
        self.controller.set_color_correction_matrix(result.matrix)

        #zapneme toggle vo view
        self._update_colorchecker_actions()
        self._show_toast_message(f"ColorChecker korekce spočtena (RMS {result.rms_error:.2f})", 2500)

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
            if hasattr(self, "texture_panel"):
                self.texture_panel.refresh_from_controller()
            self.update_undo_redo_actions()
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
            "Uložit projekt ako",
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

    def ask_to_save_before_close(self) -> str:
        """
        Vráti: "save" | "discard" | "cancel"
        """
        msg: QMessageBox = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Neuložené změny")
        msg.setText("Projekt není uložen. Chcete uložit změny před zavřením?")
        btn_save: QAbstractButton = msg.addButton("Uložit", QMessageBox.AcceptRole)
        btn_discard = msg.addButton("Neukládat", QMessageBox.DestructiveRole)
        btn_cancel = msg.addButton("Zrušit", QMessageBox.RejectRole)
        msg.setDefaultButton(btn_save)

        msg.exec()
        clicked: QAbstractButton | None = msg.clickedButton()

        if clicked == btn_save:
            return "save"
        if clicked == btn_discard:
            return "discard"
        return "cancel"

    def on_export_report(self) -> None:
        """
        Exportuje PDF report o projekte
        """
        if self.controller.project is None:
            QMessageBox.information(self, "Žádný projekt", "Není otevřený žádný projekt")
            return

        dialog = ReportDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        pdf_path, _ = QFileDialog.getSaveFileName(
            self,
            "Uložit report jako",
            "",
            "PDF soubory (*.pdf);;Všechny soubory (*.*)",
        )
        if not pdf_path:
            return

        if not pdf_path.lower().endswith(".pdf"):
            pdf_path += ".pdf"

        try:
            generate_report(self.controller.project, pdf_path, metadata=dialog.metadata())
        except Exception as e:
            QMessageBox.critical(self, "Chyba při exportu reportu", str(e))
            return

        self.statusBar().showMessage("Report byl úspěšně exportován.", 5000)

    def on_toggle_damage_overlay(self, checked: bool) -> None:
        """
        zapne/vypne vizualizáciu damage masky na canvase
        """
        self.controller.set_show_damage_overlay(checked)

    def on_toggle_colorchecker(self, checked: bool) -> None:
        if self.controller.project is None:
            return
        self.controller.set_color_correction_enabled(checked)
        self._update_colorchecker_actions()

    def on_close_project(self) -> None:
        """
        Zavrie aktuálny projekt a vráti sa na úvodnú obrazovku
        """
        if self.controller.project is None:
            # nič nie je otvorené, tak len ukážeme start screen 
            self.show_start_screen()
            return
        
        #ak dirty -opýtať sa
        if self.controller.is_project_dirty():
            result = self.ask_to_save_before_close()
            if result == "cancel":
                return
            if result == "save":
                if not self.controller.save_project_with_dialog_if_needed():
                    return
            #discard -pokračujeme

        self._update_colorchecker_actions()
        # neskôr sa spýtame na uloženie (Save)
        self.controller.close_project()
        self.show_start_screen()

    def closeEvent(self, event: QCloseEvent) -> None:
        #ak nie je otvorený projekt alebo nie je dirty, môžeme zavrieť
        if not self.controller.has_open_project() or not self.controller.is_project_dirty():
            event.accept()
            return

        result = self.ask_to_save_before_close()
        if result == "cancel":
            event.ignore()
            return

        if result == "save":
            if not self.controller.save_project_with_dialog_if_needed():
                event.ignore()
                return

        #discard alebo úspešný save
        event.accept()

    def on_auto_fill_small_regions(self) -> None:
        """
        Spustí automatické vyplnenie malých poškodených oblastí
        """
        if self.controller.project is None:
            QMessageBox.information(self, "Žiadny projekt", "Nie je otvorený žiadny projekt")
            return

        threshold = self.controller.auto_fill_threshold
        if self.auto_fill_spinbox is not None:
            threshold = int(self.auto_fill_spinbox.value())
        count = self.controller.run_auto_fill_small_regions(area_threshold=threshold)
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

    def _on_auto_fill_slider_changed(self, value: int) -> None:
        """
        Keď sa zmení slider, prepíšeme spinbox a controller threshold
        """
        if self.auto_fill_spinbox is not None and self.auto_fill_spinbox.value() != value:
            self.auto_fill_spinbox.blockSignals(True)
            self.auto_fill_spinbox.setValue(value)
            self.auto_fill_spinbox.blockSignals(False)

        self.controller.set_auto_fill_threshold(value)

    def _on_auto_fill_spinbox_changed(self, value: int) -> None:
        """
        Keď sa zmení spinbox, prepíšeme slider a controller threshold
        """
        if self.auto_fill_slider is not None and self.auto_fill_slider.value() != value:
            self.auto_fill_slider.blockSignals(True)
            self.auto_fill_slider.setValue(value)
            self.auto_fill_slider.blockSignals(False)

        self.controller.set_auto_fill_threshold(value)

    def _sync_auto_fill_slider_to_spinbox_only(self, value: int) -> None:
        if self.auto_fill_spinbox is not None and self.auto_fill_spinbox.value() != value:
            self.auto_fill_spinbox.blockSignals(True)
            self.auto_fill_spinbox.setValue(value)
            self.auto_fill_spinbox.blockSignals(False)

    def _sync_auto_fill_spinbox_to_slider_only(self, value: int) -> None:
        if self.auto_fill_slider is not None and self.auto_fill_slider.value() != value:
            self.auto_fill_slider.blockSignals(True)
            self.auto_fill_slider.setValue(value)
            self.auto_fill_slider.blockSignals(False)

    def _commit_auto_fill_slider_value(self) -> None:
        if self.auto_fill_slider is None:
            return
        self.controller.set_auto_fill_threshold(self.auto_fill_slider.value())

    def _commit_auto_fill_spinbox_value(self) -> None:
        if self.auto_fill_spinbox is None:
            return
        self.controller.set_auto_fill_threshold(self.auto_fill_spinbox.value())
            
    def _on_material_tab_changed(self, idx: int):
        #0 = Barvy, 1 = Textury
        self.controller.texture_mode_enabled = (idx == 1)

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

