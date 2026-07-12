from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QDialog, QRadioButton, QVBoxLayout, QLabel, QHBoxLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox, QCheckBox, QButtonGroup

from rp_restore.core.algorithm_runner import RealisticFillMode

MAX_WIN = 1440


@dataclass
class RealisticFillDialogResult:
    """Výsledok nastavení pre realistické doplnenie"""
    bbox: tuple[int, int, int, int]  #(x, y, w, h)
    use_mock: bool
    partial_noise: float
    seed: Optional[int]
    realistic_mode: RealisticFillMode


class RealisticFillDialog(QDialog):
    """
    Dialóg pre nastavenie realistického doplnenia
    používateľ použije bbox aktuálneho výberu alebo ručne vyberie okno cez canvas
    okno môže mať maximálne 1440x1440 pixelov
    """

    def __init__(self, controller: object, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Realistické doplnění – nastavení okna")

        self._controller = controller
        self._bbox: Optional[tuple[int, int, int, int]] = None
        self._use_mock: bool = False 

        layout = QVBoxLayout(self)

        self.info = QLabel(
            "Vyberte okno pro realistické doplnění\n"
            f"Maximální velikost okna je {MAX_WIN}×{MAX_WIN}"
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.model_info = QLabel("*Model je primárně určený pro restaurování děl Albrechta Dürera.")
        self.model_info.setWordWrap(True)
        layout.addWidget(self.model_info)

        self.lbl_bbox = QLabel("Okno: (nezvolené)")
        layout.addWidget(self.lbl_bbox)

        btn_row = QHBoxLayout()
        self.btn_use_selection = QRadioButton("Použít ohraničení výběru")
        self.btn_pick_window = QRadioButton("Vybrat okno ručně…")
        btn_row.addWidget(self.btn_use_selection)
        btn_row.addWidget(self.btn_pick_window)
        layout.addLayout(btn_row)

        self.window_button_group = QButtonGroup(self)
        self.window_button_group.setExclusive(True)
        self.window_button_group.addButton(self.btn_use_selection)
        self.window_button_group.addButton(self.btn_pick_window)

        self.btn_use_selection.clicked.connect(self._on_use_selection_bbox)
        self.btn_pick_window.clicked.connect(self._on_pick_window)

        mode_info = QLabel("Režim doplnění:")
        layout.addWidget(mode_info)

        mode_row = QHBoxLayout()

        self.basic_mode_radio = QRadioButton("Základní")
        self.guided_mode_radio = QRadioButton("Vedené podle náčrtu")

        self.basic_mode_radio.setChecked(True)

        mode_row.addWidget(self.basic_mode_radio)
        mode_row.addWidget(self.guided_mode_radio)
        layout.addLayout(mode_row)

        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        self.mode_button_group.addButton(self.basic_mode_radio)
        self.mode_button_group.addButton(self.guided_mode_radio)

        guided_help = (
            "Vedené doplnění je výrazně pomalejší a je určené hlavně pro případy, "
            "kdy restaurátor do maskované oblasti načrtl požadovanou strukturu. "
            "Vodicí čáry by měly být tmavé a tenké, ideálně přibližně 1 px. "
            "Pro tento režim se jako vstup použije aktuální složený obraz."
        )

        self.guided_mode_radio.setToolTip(guided_help)

        self.guided_info = QLabel(
            "Vedené doplnění je pomalejší a používá aktuální složený obraz s případným náčrtem."
        )
        self.guided_info.setWordWrap(True)
        self.guided_info.setVisible(False)
        layout.addWidget(self.guided_info)

        self.basic_mode_radio.toggled.connect(self._on_mode_changed)
        self.guided_mode_radio.toggled.connect(self._on_mode_changed)

        partial_noise_help = (
            "Parametr míra dogenerování určuje, jak výrazně může algoritmus přepracovat maskovanou oblast.\n"
            "Nižší hodnota více zachovává původní strukturu pod maskou.\n"
            "Hodnota 1.0 znamená úplné dogenerování.\n"
            "Pokud pod maskou nejsou použitelné původní pixely, použijte hodnotu 1.0."
        )

        noise_row = QHBoxLayout()
        partial_noise_label = QLabel("Míra dogenerování:")
        partial_noise_label.setToolTip(partial_noise_help)
        noise_row.addWidget(partial_noise_label)

        self.partial_noise_spin = QDoubleSpinBox()
        self.partial_noise_spin.setRange(0.0, 1.0)
        self.partial_noise_spin.setSingleStep(0.05)
        self.partial_noise_spin.setDecimals(2)
        self.partial_noise_spin.setValue(0.70)
        noise_row.addWidget(self.partial_noise_spin)
        self.partial_noise_spin.setToolTip(partial_noise_help)

        layout.addLayout(noise_row)

        seed_row = QHBoxLayout()

        self.seed_checkbox = QCheckBox("Použít seed")
        seed_row.addWidget(self.seed_checkbox)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setValue(111)
        self.seed_spin.setEnabled(False)
        seed_row.addWidget(self.seed_spin)

        layout.addLayout(seed_row)

        self.seed_checkbox.toggled.connect(self.seed_spin.setEnabled)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        #dialóg potrebuje dostávať zmeny pending bboxu pri ručnom posúvaní okna
        if hasattr(self._controller, "set_pending_window_bbox_listener"):
            self._controller.set_pending_window_bbox_listener(self._on_external_bbox_changed)

        self._update_ok_enabled()

    def get_result(self) -> Optional[RealisticFillDialogResult]:
        """Vráti nastavenia dialógu alebo None, ak nie je zvolené okno"""
        if self._bbox is None:
            return None
        
        seed: Optional[int]
        if self.seed_checkbox.isChecked():
            seed = int(self.seed_spin.value())
        else:
            seed = None

        realistic_mode = RealisticFillMode.GUIDED if self.guided_mode_radio.isChecked() else RealisticFillMode.BASIC

        return RealisticFillDialogResult(bbox=self._bbox, use_mock=self._use_mock, partial_noise=float(self.partial_noise_spin.value()), seed=seed, realistic_mode=realistic_mode)

    def _update_ok_enabled(self) -> None:
        """Povolí OK až po zvolení okna"""
        ok_btn = self.buttons.button(QDialogButtonBox.Ok)
        ok_btn.setEnabled(self._bbox is not None)

    def _on_mode_changed(self) -> None:
        """Aktualizuje dialóg podľa zvoleného režimu realistického doplnenia"""
        guided = self.guided_mode_radio.isChecked()

        #partial_noise patrí iba k základnému režimu restore_file()
        self.partial_noise_spin.setEnabled(not guided)
        self.guided_info.setVisible(guided)

    def _set_bbox(self, bbox: tuple[int, int, int, int]) -> None:
        """Nastaví aktuálne vybrané okno a aktualizuje text v dialógu"""
        x, y, w, h = bbox
        self._bbox = bbox
        self.lbl_bbox.setText(f"Okno: x={x}, y={y}, w={w}, h={h}")
        self._update_ok_enabled()

    def _clear_bbox(self) -> None:
        """Zruší aktuálne zvolené okno a aktualizuje text v dialógu"""
        self._bbox = None
        self.lbl_bbox.setText("Okno: (nezvolené)")
        self._update_ok_enabled()

    def _clear_manual_window_preview(self) -> None:
        """Zruší rozpracované ručné okno na canvase, ak existuje"""
        if hasattr(self._controller, "set_pending_window_bbox"):
            self._controller.set_pending_window_bbox(None)

        canvas = getattr(self._controller, "canvas", None)
        if canvas is not None and hasattr(canvas, "cancel_window_pick"):
            canvas.cancel_window_pick()

    def _on_use_selection_bbox(self) -> None:
        """Použije ohraničenie aktuálneho výberu ako okno pre algoritmus"""
        self._clear_manual_window_preview()

        if not hasattr(self._controller, "get_active_selection_bbox"):
            self._clear_bbox()
            return

        bbox = self._controller.get_active_selection_bbox()
        if bbox is None:
            #controller už vypisuje user hlášku
            self._clear_bbox()
            return

        x, y, w, h = bbox
        if w > MAX_WIN or h > MAX_WIN:
            if hasattr(self._controller, "show_tool_message"):
                self._controller.show_tool_message(
                    f"Vybraná oblast je příliš veliká ({w}×{h}). Maximum je {MAX_WIN}×{MAX_WIN}"
                )
            self._clear_bbox()
            return

        self._set_bbox(bbox)

    def _on_pick_window(self) -> None:
        """Spustí ručný výber okna na canvase"""
        if not hasattr(self._controller, "request_manual_window_bbox"):
            return
        #ak už máme pending okno, tak ho nerušíme, iba ho znovu použijeme
        if hasattr(self._controller, "get_pending_window_bbox"):
            pending = self._controller.get_pending_window_bbox()
            if pending is not None:
                self.btn_pick_window.setChecked(True)
                self._set_bbox(pending)
                return

        self._clear_bbox()
        self.hide()

        def _on_bbox_picked(bbox):
            self.show()
            self.raise_()
            self.activateWindow()

            if bbox is None:
                self._clear_bbox()
                return

            x, y, w, h = bbox
            if w > MAX_WIN or h > MAX_WIN:
                if hasattr(self._controller, "show_tool_message"):
                    self._controller.show_tool_message(
                        f"Okno je příliš veliké ({w}×{h}). Maximum je {MAX_WIN}×{MAX_WIN}"
                    )
                self._clear_bbox()
                return

            self._set_bbox(bbox)

        self._controller.request_manual_window_bbox(_on_bbox_picked, max_size=MAX_WIN)

    def _on_external_bbox_changed(self, bbox) -> None:
        """Aktualizuje dialóg, keď sa pending okno zmení mimo dialógu"""
        if bbox is None:
            if self.btn_pick_window.isChecked():
                self._clear_bbox()
            return
        
        self.btn_pick_window.setChecked(True) 
        self._set_bbox(bbox)

    def _cleanup(self) -> None:
        """Odpojí listener a zruší rozpracovaný ručný výber okna"""
        if hasattr(self._controller, "clear_pending_window_bbox_listener"):
            self._controller.clear_pending_window_bbox_listener()

        #zrušenie červeného obdĺžnika pending bboxu
        if hasattr(self._controller, "set_pending_window_bbox"):
            self._controller.set_pending_window_bbox(None)

        #ak je canvas ešte v režime výberu okna, zrušíme ho
        canvas = getattr(self._controller, "canvas", None)
        if canvas is not None and hasattr(canvas, "cancel_window_pick"):
            canvas.cancel_window_pick()

    def accept(self) -> None:
        """Potvrdí dialóg a vyčistí dočasný stav výberu okna"""
        self._cleanup()
        super().accept()

    def reject(self) -> None:
        """Zruší dialóg a vyčistí dočasný stav výberu okna"""
        self._cleanup()
        super().reject()

    def closeEvent(self, event) -> None:
        """Pri zatvorení dialógu vyčistí dočasný stav výberu okna"""
        self._cleanup()
        super().closeEvent(event)