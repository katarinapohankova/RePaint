from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QRadioButton, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QDialogButtonBox


MAX_WIN = 1024


@dataclass
class RealisticFillDialogResult:
    bbox: tuple[int, int, int, int]  #(x, y, w, h)
    use_mock: bool


class RealisticFillDialog(QDialog):
    """
    Dialóg pre Realistic fill
    - používateľ si buď vezme bbox z aktuálneho selection, alebo si vyberie okno ručne cez canvas
    - okno musí byť max 1024x1024
    - ak okno neobsahuje žiadne poškodenie, nedovolíme spustiť
    """

    def __init__(self, controller: object, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Realistic fill – nastavení okna")

        self._controller = controller
        self._bbox: Optional[tuple[int, int, int, int]] = None
        self._use_mock: bool = True  #zatiaľ default (neskôr podľa dostupnosti algoritmu)

        layout = QVBoxLayout(self)

        self.info = QLabel(
            "Vyberte okno pro realistic fill\n"
            f"Maximální velikost okna je {MAX_WIN}×{MAX_WIN}"
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.lbl_bbox = QLabel("Okno: (nezvolené)")
        layout.addWidget(self.lbl_bbox)

        btn_row = QHBoxLayout()
        self.btn_use_selection = QRadioButton("Použít bbox zo selection")
        self.btn_pick_window = QRadioButton("Vybrat okno ručně…")
        btn_row.addWidget(self.btn_use_selection)
        btn_row.addWidget(self.btn_pick_window)
        layout.addLayout(btn_row)

        self.btn_use_selection.clicked.connect(self._on_use_selection_bbox)
        self.btn_pick_window.clicked.connect(self._on_pick_window)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        #dialog potrebuje dostávať zmeny pending bboxu
        if hasattr(self._controller, "set_pending_window_bbox_listener"):
            self._controller.set_pending_window_bbox_listener(self._on_external_bbox_changed)

        self._update_ok_enabled()

    def get_result(self) -> Optional[RealisticFillDialogResult]:
        if self._bbox is None:
            return None
        return RealisticFillDialogResult(bbox=self._bbox, use_mock=self._use_mock)

    def _update_ok_enabled(self) -> None:
        ok_btn = self.buttons.button(QDialogButtonBox.Ok)
        ok_btn.setEnabled(self._bbox is not None)

    def _set_bbox(self, bbox: tuple[int, int, int, int]) -> None:
        x, y, w, h = bbox
        self._bbox = bbox
        self.lbl_bbox.setText(f"Okno: x={x}, y={y}, w={w}, h={h}")
        self._update_ok_enabled()

    def _on_use_selection_bbox(self) -> None:
        if not hasattr(self._controller, "get_active_selection_bbox"):
            return
        bbox = self._controller.get_active_selection_bbox()
        if bbox is None:
            #controller už vypisuje user hlášku (tu to ignorujem)
            return

        x, y, w, h = bbox
        if w > MAX_WIN or h > MAX_WIN:
            #len UI info, reálne upozornenie spravíme cez controller hlášku
            if hasattr(self._controller, "show_tool_message"):
                self._controller.show_tool_message(
                    f"Vybraná oblast je příliš veliká ({w}×{h}). Maximum je {MAX_WIN}×{MAX_WIN}"
                )
            return

        self._set_bbox(bbox)

    def _on_pick_window(self) -> None:
        if not hasattr(self._controller, "request_manual_window_bbox"):
            return
        #ak už máme pending okno, tak ho nerušíme – len sa prepneme do manual režimu
        if hasattr(self._controller, "get_pending_window_bbox"):
            pending = self._controller.get_pending_window_bbox()
            if pending is not None:
                self._manual_mode = True
                self.btn_pick_window.setChecked(True)
                self.btn_use_selection.setChecked(False)
                self._set_bbox(pending)
                return
        self.hide()

        def _on_bbox_picked(bbox):
            self.show()
            self.raise_()
            self.activateWindow()

            if bbox is None:
                return

            x, y, w, h = bbox
            if w > MAX_WIN or h > MAX_WIN:
                if hasattr(self._controller, "show_tool_message"):
                    self._controller.show_tool_message(
                        f"Okno je příliš veliké ({w}×{h}). Maximum je {MAX_WIN}×{MAX_WIN}"
                    )
                return

            self._set_bbox(bbox)

        self._controller.request_manual_window_bbox(_on_bbox_picked, max_size=MAX_WIN)

    def _on_external_bbox_changed(self, bbox) -> None:
        if bbox is None:
            return
        
        #ak sa okno posúva -sme v manual režime
        self._manual_mode = True
        self._selection_mode = False
        self.btn_pick_window.setChecked(True) 
        self.btn_use_selection.setChecked(False)
        self._set_bbox(bbox)

    def _cleanup(self) -> None:
        if hasattr(self._controller, "clear_pending_window_bbox_listener"):
            self._controller.clear_pending_window_bbox_listener()

        #zrušenie červeného obdĺžnika (pending bbox)
        if hasattr(self._controller, "set_pending_window_bbox"):
            self._controller.set_pending_window_bbox(None)

        #ak je canvas ešte v režime výberu okna, zrušíme ho
        canvas = getattr(self._controller, "canvas", None)
        if canvas is not None and hasattr(canvas, "cancel_window_pick"):
            canvas.cancel_window_pick()

    def reject(self) -> None:
        self._cleanup()
        super().reject()

    def closeEvent(self, event) -> None:
        self._cleanup()
        super().closeEvent(event)