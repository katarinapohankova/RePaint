from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from rp_restore.core.selection import Selection, SelectionSet
from rp_restore.core.algorithm_runner import AlgorithmType


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

        # title = QLabel("Externé algoritmy")
        # layout.addWidget(title)

        self.info_label = QLabel("Žiadna vybraná oblasť.")
        layout.addWidget(self.info_label)

        self.btn_realistic = QPushButton("Realistic fill")
        self.btn_texture = QPushButton("Texture fill")

        layout.addWidget(self.btn_realistic)
        layout.addWidget(self.btn_texture)
        layout.addStretch(1)

        self.btn_realistic.clicked.connect(self._on_realistic_clicked)
        self.btn_texture.clicked.connect(self._on_texture_clicked)

        self._set_buttons_enabled(False)

    def set_controller(self, controller: object) -> None:
        self._controller = controller

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.btn_realistic.setEnabled(enabled)
        self.btn_texture.setEnabled(enabled)

    def refresh_from_selection(self, selection_set: SelectionSet | None) -> None:
        """
        Zavolá controller, keď sa zmení active_selection
        """
        if selection_set is None or selection_set.is_empty():
            self.info_label.setText("Žiadna vybraná oblasť")
            self._set_buttons_enabled(False)
            return

        x, y, w, h = selection_set.combined_bbox()
        num_regions = len(selection_set.selections)

        if num_regions == 1:
            self.info_label.setText(f"Vybrán region: {w}×{h}")
        else:
            self.info_label.setText(f"Vybráno {num_regions} oblastí, společný bbox: {w}×{h}")
        self._set_buttons_enabled(True)
        self.current_selection_bbox = (x, y, w, h)

    def _on_realistic_clicked(self) -> None:
        if self._controller is None:
            return
        if hasattr(self._controller, "run_algorithm_on_selection"):
            #zatiaľ v mock režime
            self._controller.run_algorithm_on_selection(AlgorithmType.REALISTIC, use_mock=True)

    def _on_texture_clicked(self) -> None:
        if self._controller is None:
            return
        if hasattr(self._controller, "run_algorithm_on_selection"):
            self._controller.run_algorithm_on_selection(AlgorithmType.TEXTURE, use_mock=False)
