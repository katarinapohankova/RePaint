from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QPushButton

from rp_restore.core.selection import SelectionSet
from rp_restore.core.algorithm_runner import AlgorithmType, TextureAlgorithmParams
from rp_restore.gui.realistic_fill_dialog import RealisticFillDialog
from rp_restore.gui.texture_fill_dialog import TextureFillDialog


class AlgorithmPanel(QWidget):
    """
    Panel s tlačidlami pre spustenie externých algoritmov

    -Realistické doplnenie je dostupné aj bez aktívneho výberu, pretože používateľ môže zvoliť okno ručne
    -Texturové doplnenie je dostupné iba vtedy, keď existuje aktívny výber
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: object | None = None  #ProjectController
        self._realistic_dialog: RealisticFillDialog | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.info_label = QLabel("Není vybrána žádná oblast.")
        layout.addWidget(self.info_label)

        self.btn_realistic = QPushButton("Realistické doplnění")
        self.btn_texture = QPushButton("Texturové doplnění")

        layout.addWidget(self.btn_realistic)
        layout.addWidget(self.btn_texture)
        layout.addStretch(1)

        self.btn_realistic.clicked.connect(self._on_realistic_clicked)
        self.btn_texture.clicked.connect(self._on_texture_clicked)

        self.btn_realistic.setEnabled(True)
        self.btn_texture.setEnabled(True)

    def set_controller(self, controller: object) -> None:
        """Nastaví controller používaný na spúšťanie algoritmov"""
        self._controller = controller

    def refresh_from_selection(self, selection_set: SelectionSet | None) -> None:
        """
        Aktualizuje panel podľa aktuálneho výberu
        """
        self.btn_realistic.setEnabled(True)
        self.btn_texture.setEnabled(True)

        if selection_set is None or selection_set.is_empty():
            self.info_label.setText("Není vybrána žádná oblast.")
            return

        _x, _y, width, height = selection_set.combined_bbox()
        num_regions = len(selection_set.selections)

        if num_regions == 1:
            self.info_label.setText(f"Vybrána oblast: {width}×{height}")
        else:
            self.info_label.setText(
                f"Vybráno {num_regions} oblastí, "
                "společný ohraničující obdélník: "
                f"{width}×{height}"
            )

    def _on_realistic_clicked(self) -> None:
        """Otvorí dialóg pre realistické doplnenie"""
        if self._controller is None:
            return

        if self._realistic_dialog is not None:
            self._realistic_dialog.show()
            self._realistic_dialog.raise_()
            self._realistic_dialog.activateWindow()
            return

        dlg = RealisticFillDialog(controller=self._controller, parent=self) 
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        self._realistic_dialog = dlg

        def _on_accept() -> None:
            res = dlg.get_result()
            if res is None:
                return

            if hasattr(self._controller, "run_realistic_fill_window"):
                self._controller.run_realistic_fill_window(res.bbox, use_mock=res.use_mock, partial_noise=res.partial_noise, seed=res.seed, realistic_mode=res.realistic_mode, input_source=res.input_source, use_composited_layers=res.use_composited_layers)

        dlg.accepted.connect(_on_accept)
        dlg.destroyed.connect(lambda _obj=None: setattr(self, "_realistic_dialog", None))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_texture_clicked(self) -> None:
        """Otvorí dialóg pre texturové doplnenie a spustí algoritmus nad aktívnym výberom"""
        if self._controller is None:
            return

        dialog = TextureFillDialog(controller=self._controller, parent=self)

        if dialog.exec() != QDialog.Accepted:
            return

        result = dialog.get_result()

        if result is None:
            if hasattr(self._controller, "show_tool_message"):
                self._controller.show_tool_message("Parametry texturového algoritmu nejsou platné")
            return

        texture_params = TextureAlgorithmParams(
            texture_name=result.texture_name,
            colors=result.colors,
            color_strengths=result.color_strengths,
            scale_x=result.scale_x,
            scale_y=result.scale_y,
            density_x=result.density_x,
            density_y=result.density_y,
            rotation=result.rotation,
            global_scale=result.global_scale,
            white_background=result.white_background,
            background_brightness=result.background_brightness,
            generate_square=result.generate_square,
            width=result.width,
            height=result.height,
            seed=result.seed,
        )

        if result.generate_square:
            if hasattr(self._controller, "generate_texture_and_add_to_project"):
                self._controller.generate_texture_and_add_to_project(texture_params)
            else:
                self._controller.show_tool_message("Generování samostatné textury zatím není dostupné")

            return

        selection_set = getattr(self._controller, "active_selection", None)
        if selection_set is None or selection_set.is_empty():
            if hasattr(self._controller, "show_tool_message"):
                self._controller.show_tool_message("Nejprve vyberte oblast pro texturové doplnění")
            return

        if hasattr(self._controller, "run_algorithm_on_selection"):
            self._controller.run_algorithm_on_selection(AlgorithmType.TEXTURE, use_mock=False, texture_params=texture_params)