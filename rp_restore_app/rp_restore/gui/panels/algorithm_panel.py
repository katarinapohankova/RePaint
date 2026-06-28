from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

from rp_restore.core.selection import SelectionSet
from rp_restore.core.algorithm_runner import AlgorithmType, TextureAlgorithmParams
from rp_restore.gui.realistic_fill_dialog import RealisticFillDialog
from rp_restore.gui.texture_fill_dialog import TextureFillDialog


class AlgorithmPanel(QWidget):
    """
    Panel s tlačidlami pre spustenie externých algoritmov:
      - Realistic fill
      - Texture fill

    tlačidlá sú enable len vtedy, keď existuje active_selection
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller: Optional[object] = None  #ProjectController

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
        self.btn_texture.setEnabled(False)

    def set_controller(self, controller: object) -> None:
        self._controller = controller

    def refresh_from_selection(self, selection_set: SelectionSet | None) -> None:
        """
        Zavolá controller, keď sa zmení active_selection
        """
        #Realistic je vždy dostupné
        self.btn_realistic.setEnabled(True)

        #Texture iba keď selection existuje
        if selection_set is None or selection_set.is_empty():
            self.info_label.setText("Není vybrána žádná oblast")
            self.btn_texture.setEnabled(False)
            return

        x, y, w, h = selection_set.combined_bbox()
        num_regions = len(selection_set.selections)

        if num_regions == 1:
            self.info_label.setText(f"Vybrána oblast: {w}×{h}")
        else:
            self.info_label.setText(f"Vybráno {num_regions} oblastí, společný ohraničující obdélník: {w}×{h}")
        self.btn_texture.setEnabled(True)

    def _on_realistic_clicked(self) -> None:
        if self._controller is None:
            return

        dlg = RealisticFillDialog(controller=self._controller, parent=self) 
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)

        def _on_accept() -> None:
            res = dlg.get_result()
            if res is None:
                return

            if hasattr(self._controller, "run_realistic_fill_window"):
                self._controller.run_realistic_fill_window(res.bbox, use_mock=res.use_mock, partial_noise=res.partial_noise, seed=res.seed, use_composited_input=res.use_composited_input)

        dlg.accepted.connect(_on_accept)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_texture_clicked(self) -> None:
        if self._controller is None:
            return
        
        dlg = TextureFillDialog(controller=self._controller, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        res = dlg.get_result()
        if res is None:
            return

        params = TextureAlgorithmParams(
            texture_name=res.texture_name,
            colors=res.colors,
            global_scale=res.global_scale,
            rotation=res.rotation,
            seed=res.seed,
        )

        if hasattr(self._controller, "run_algorithm_on_selection"):
            self._controller.run_algorithm_on_selection(AlgorithmType.TEXTURE, use_mock=False, texture_params=params)
