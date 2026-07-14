from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QRadioButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from rp_restore.core.algorithm_runner import AlgorithmRunner, TextureAlgorithmParams


MAX_COLORS = 3

TEXTURE_PREVIEW_MAX_SIZE = 256
TEXTURE_PREVIEW_MIN_SIZE = 64

DENSITY_APPLICABLE_TEXTURES = {
    "texture_D",
    "texture_G",
    "texture_I",
    "texture_J",
}

@dataclass
class TextureFillDialogResult:
    """Výsledok nastavení textúrového algoritmu"""

    texture_name: str

    scale_x: float
    scale_y: float
    density_x: float
    density_y: float
    rotation: float
    global_scale: float

    colors: list[tuple[int, int, int]]
    color_strengths: list[float]

    white_background: bool
    background_brightness: float

    generate_square: bool
    width: int
    height: int

    seed: int


class _TextureColorRow(QWidget):
    """
    Jeden riadok pre výber jednej farby textúry
    """
    changed = Signal()

    def __init__(self, index: int, color: tuple[int, int, int], remove_callback: Callable[["_TextureColorRow"], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._index = index
        self._color = QColor(color[0], color[1], color[2])
        self._remove_callback = remove_callback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.lbl_name = QLabel()
        self.lbl_name.setMinimumWidth(65)
        layout.addWidget(self.lbl_name)

        self.swatch = QLabel()
        self.swatch.setFixedSize(24, 24)
        layout.addWidget(self.swatch)

        self.lbl_rgb = QLabel()
        self.lbl_rgb.setMinimumWidth(110)
        layout.addWidget(self.lbl_rgb)

        self.btn_change = QPushButton("Změnit…")
        layout.addWidget(self.btn_change)

        layout.addWidget(QLabel("Síla:"))

        self.strength_spin = QDoubleSpinBox()
        self.strength_spin.setRange(0.0, 1.0)
        self.strength_spin.setSingleStep(0.05)
        self.strength_spin.setDecimals(2)
        self.strength_spin.setValue(1.0)
        self.strength_spin.setToolTip("Síla této barevné vrstvy v rozsahu 0 až 1")
        self.strength_spin.valueChanged.connect(lambda _value: self.changed.emit())
        layout.addWidget(self.strength_spin)

        self.btn_remove = QPushButton("Odstranit")
        layout.addWidget(self.btn_remove)
        layout.addStretch(1)

        self.btn_change.clicked.connect(self._on_change_clicked)
        self.btn_remove.clicked.connect(self._on_remove_clicked)

        self.set_index(index)
        self._refresh_color_display()

    def set_index(self, index: int) -> None:
        """Nastaví poradové číslo farby"""
        self._index = index
        self.lbl_name.setText(f"Barva {index}:")

    def set_remove_enabled(self, enabled: bool) -> None:
        """Povolí alebo zakáže odstránenie farby"""
        self.btn_remove.setEnabled(enabled)

    def get_rgb(self) -> tuple[int, int, int]:
        """Vráti aktuálnu farbu ako RGB trojicu"""
        return (self._color.red(), self._color.green(), self._color.blue())

    def get_strength(self) -> float:
        """Vráti silu aktuálnej farebnej vrstvy"""
        return float(self.strength_spin.value())

    def _refresh_color_display(self) -> None:
        """Aktualizuje náhľad farby a text RGB hodnôt"""
        r, g, b = self.get_rgb()
        self.swatch.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b});"
            "border: 1px solid #333;"
        )
        self.lbl_rgb.setText(f"({r}, {g}, {b})")

    def _on_change_clicked(self) -> None:
        """Otvorí dialóg na zmenu farby"""
        color = QColorDialog.getColor(self._color, self, f"Vyberte barvu {self._index}", options=QColorDialog.DontUseNativeDialog)
        if not color.isValid():
            return

        self._color = color
        self._refresh_color_display()
        self.changed.emit()

    def _on_remove_clicked(self) -> None:
        """Požiada rodičovský dialóg o odstránenie tohto riadku"""
        self._remove_callback(self)


class TextureFillDialog(QDialog):
    """
    Dialóg pre nastavenie parametrov textúrového algoritmu
    používateľ vyberá typ textúry, jednu až tri farby, mierku, rotáciu a voliteľný seed
    """

    def __init__(self, controller: object, parent=None, initial_params: TextureAlgorithmParams | None = None, force_generate_texture_mode: bool = False, color_edit_only: bool = False) -> None:
        super().__init__(parent)

        self.setWindowTitle("Texturové doplnění – parametry")

        self.setMinimumSize(700, 520)

        screen = self.screen()

        if screen is not None:
            available_geometry = screen.availableGeometry()

            dialog_width = min(820, available_geometry.width() - 80)
            dialog_height = min(760, available_geometry.height() - 80)

            self.resize(dialog_width, dialog_height)
        else:
            self.resize(820, 760)

        self._controller = controller
        self._color_rows: list[_TextureColorRow] = []
        self._selection_bbox = self._get_selection_bbox()
        self._initial_params = initial_params
        self._force_generate_texture_mode = force_generate_texture_mode
        self._color_edit_only = color_edit_only
        self._preview_is_current = False

        #vonkajšie rozloženie obsahuje posúvateľný obsah a tlačidlá dialógu, ktoré zostávajú stále viditeľné
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(8)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content_widget = QWidget()

        #všetky skupiny s parametrami algoritmu
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        #režim výstupu
        output_group = QGroupBox("Výstup algoritmu")
        output_layout = QVBoxLayout(output_group)

        self.fill_selection_radio = QRadioButton("Doplnit vybranou oblast obrazu")
        self.generate_texture_radio = QRadioButton("Vygenerovat samostatnou texturu a přidat ji do materiálů")

        has_selection = self._selection_bbox is not None

        self.fill_selection_radio.setEnabled(has_selection)
        self.fill_selection_radio.setChecked(has_selection)
        self.generate_texture_radio.setChecked(not has_selection)

        if self._force_generate_texture_mode:
            self.fill_selection_radio.setChecked(False)
            self.generate_texture_radio.setChecked(True)
            self.fill_selection_radio.setEnabled(False)

            if self._color_edit_only:
                self.generate_texture_radio.setEnabled(False)

        self.fill_selection_radio.toggled.connect(lambda _checked: self._update_output_mode())
        self.generate_texture_radio.toggled.connect(lambda _checked: self._update_output_mode())

        output_layout.addWidget(self.fill_selection_radio)
        output_layout.addWidget(self.generate_texture_radio)
        layout.addWidget(output_group)

        #model textúry a náhľad
        model_group = QGroupBox("Model textury")
        model_layout = QHBoxLayout(model_group)

        model_left_layout = QVBoxLayout()

        texture_row = QHBoxLayout()
        texture_row.addWidget(QLabel("Typ textury:"))

        self.texture_combo = QComboBox()

        try:
            available_names = AlgorithmRunner.get_available_texture_names()
        except RuntimeError as exc:
            available_names = []
            self.texture_combo.addItem("Modely nelze načíst", None)
            self.texture_combo.setEnabled(False)
            model_error = str(exc)
        else:
            model_error = ""

        if available_names:
            for texture_name in available_names:
                self.texture_combo.addItem(texture_name, texture_name)
        elif not model_error:
            self.texture_combo.addItem("Nebyl nalezen žádný model", None)
            self.texture_combo.setEnabled(False)

        self.texture_combo.currentIndexChanged.connect(lambda _index: self._update_texture_model())

        texture_row.addWidget(self.texture_combo, 1)
        model_left_layout.addLayout(texture_row)

        self.model_info_label = QLabel(model_error)
        self.model_info_label.setWordWrap(True)
        model_left_layout.addWidget(self.model_info_label)
        model_left_layout.addStretch(1)

        self.texture_preview = QLabel("Náhled není k dispozici")
        self.texture_preview.setFixedSize(190, 130)
        self.texture_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texture_preview.setStyleSheet("border: 1px solid #777;")

        model_layout.addLayout(model_left_layout, 1)
        model_layout.addWidget(self.texture_preview)

        layout.addWidget(model_group)

        #farby textúry
        colors_group = QGroupBox("Barevné vrstvy")
        colors_group_layout = QVBoxLayout(colors_group)

        self.colors_container = QWidget()
        self.colors_layout = QVBoxLayout(self.colors_container)
        self.colors_layout.setContentsMargins(0, 0, 0, 0)
        self.colors_layout.setSpacing(6)

        colors_group_layout.addWidget(self.colors_container)

        self.btn_add_color = QPushButton("Přidat barvu")
        self.btn_add_color.clicked.connect(self._on_add_color_clicked)
        colors_group_layout.addWidget(self.btn_add_color)

        layout.addWidget(colors_group)

        #tvar a hustota
        transform_group = QGroupBox("Tvar a hustota textury")
        transform_form = QFormLayout(transform_group)

        self.scale_x_spin = self._make_double_spin(minimum=0.10, maximum=10.0, value=1.0, step=0.10)
        self.scale_y_spin = self._make_double_spin(minimum=0.10, maximum=10.0, value=1.0, step=0.10)
        self.density_x_spin = self._make_double_spin(minimum=-0.90, maximum=1.0, value=0.0, step=0.05)
        self.density_y_spin = self._make_double_spin(minimum=-0.90, maximum=1.0, value=0.0, step=0.05)
        self.rotation_spin = self._make_double_spin(minimum=-180.0, maximum=180.0, value=0.0, step=1.0, decimals=1)
        self.global_scale_spin = self._make_double_spin(minimum=0.10, maximum=10.0, value=1.0, step=0.10)

        transform_form.addRow("Měřítko X:", self.scale_x_spin)
        transform_form.addRow("Měřítko Y:", self.scale_y_spin)
        transform_form.addRow("Hustota X:", self.density_x_spin)
        transform_form.addRow("Hustota Y:", self.density_y_spin)
        transform_form.addRow("Rotace (°):", self.rotation_spin)
        transform_form.addRow("Celkové měřítko:", self.global_scale_spin)

        self.density_note = QLabel()
        self.density_note.setWordWrap(True)
        transform_form.addRow(self.density_note)

        layout.addWidget(transform_group)

        #pozadie
        background_group = QGroupBox("Pozadí výsledku")
        background_form = QFormLayout(background_group)

        self.white_background_checkbox = QCheckBox("Použít neprůhledné pozadí")
        self.white_background_checkbox.setChecked(True)
        self.white_background_checkbox.toggled.connect(lambda _checked: self._update_background_controls())

        background_form.addRow(self.white_background_checkbox)

        self.background_brightness_spin = self._make_double_spin(minimum=0.0, maximum=1.0, value=1.0, step=0.05)
        self.background_brightness_spin.setToolTip(
            "0 znamená černé pozadí "
            "1 znamená bílé pozadí"
        )

        background_form.addRow("Jas pozadí:", self.background_brightness_spin)

        background_note = QLabel(
            "Při vypnutém neprůhledném pozadí vrátí algoritmus texturu s průhledností. "
            "Při zapnutém pozadí určuje jas hodnotu od černé 0 po bílou 1."
        )
        background_note.setWordWrap(True)
        background_form.addRow(background_note)

        layout.addWidget(background_group)

        #rozmery samostatnej textúry
        self.square_group = QGroupBox("Rozměry samostatné textury")
        square_form = QFormLayout(self.square_group)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(64, 4096)
        self.width_spin.setSingleStep(64)
        self.width_spin.setValue(1024)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(64, 4096)
        self.height_spin.setSingleStep(64)
        self.height_spin.setValue(1024)

        square_form.addRow("Šířka (px):", self.width_spin)
        square_form.addRow("Výška (px):", self.height_spin)

        layout.addWidget(self.square_group)

        #seed
        seed_row = QHBoxLayout()
        seed_row.addWidget(QLabel("Seed:"))

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setValue(42)

        seed_row.addWidget(self.seed_spin)
        seed_row.addStretch(1)

        layout.addLayout(seed_row)

        #náhľad výslednej textúry
        preview_group = QGroupBox("Náhled výsledné textury")
        preview_layout = QVBoxLayout(preview_group)

        preview_note = QLabel("Náhled se vytvoří z aktuálních parametrů v menším rozlišení")
        preview_note.setWordWrap(True)
        preview_layout.addWidget(preview_note)

        self.result_preview_label = QLabel("Náhled zatím nebyl vygenerován")
        self.result_preview_label.setFixedSize(TEXTURE_PREVIEW_MAX_SIZE, TEXTURE_PREVIEW_MAX_SIZE)
        self.result_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_preview_label.setStyleSheet(
            "border: 1px solid #777;"
            "background-color: #2b2b2b;"
        )
        preview_layout.addWidget(self.result_preview_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.preview_status_label = QLabel("Nastavte parametry a klikněte na „Vygenerovat náhled“.")
        self.preview_status_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_status_label)

        self.btn_generate_texture_preview = QPushButton("Vygenerovat náhled")
        self.btn_generate_texture_preview.clicked.connect(self._on_generate_texture_preview_clicked)
        preview_layout.addWidget(self.btn_generate_texture_preview)

        layout.addWidget(preview_group)
        layout.addStretch(1)

        self.scroll_area.setWidget(content_widget)
        outer_layout.addWidget(self.scroll_area, 1)

        #tlačidlá nie sú súčasťou scrollovateľného obsahu, preto zostávajú stále viditeľné naspodku dialógu
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        outer_layout.addWidget(self.buttons)

        if self._initial_params is not None:
            self._apply_initial_texture_params(self._initial_params)
        else:
            self._add_color_row(self._get_initial_color())

        self._update_background_controls()
        self._update_output_mode()
        self._update_texture_model()

        if self._color_edit_only:
            self._apply_color_edit_only_mode()

        self._update_color_rows()
        self._connect_texture_preview_signals()

    @staticmethod
    def _make_double_spin(minimum: float, maximum: float, value: float, step: float, decimals: int = 2) -> QDoubleSpinBox:
        """Vytvorí desatinné vstupné pole s jednotným nastavením"""
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setValue(value)
        return spin

    def get_result(self) -> TextureFillDialogResult | None:
        """Vráti zvolené parametre textúrového algoritmu"""
        texture_name = self.texture_combo.currentData()

        if texture_name is None or not self._color_rows:
            return None

        return TextureFillDialogResult(
            texture_name=str(texture_name),
            scale_x=float(self.scale_x_spin.value()),
            scale_y=float(self.scale_y_spin.value()),
            density_x=float(self.density_x_spin.value()),
            density_y=float(self.density_y_spin.value()),
            rotation=float(self.rotation_spin.value()),
            global_scale=float(self.global_scale_spin.value()),
            colors=[row.get_rgb() for row in self._color_rows],
            color_strengths=[row.get_strength() for row in self._color_rows],
            white_background=self.white_background_checkbox.isChecked(),
            background_brightness=float(self.background_brightness_spin.value()),
            generate_square=self.generate_texture_radio.isChecked(),
            width=int(self.width_spin.value()),
            height=int(self.height_spin.value()),
            seed=int(self.seed_spin.value()),
        )
    
    def _get_selection_bbox(self) -> tuple[int, int, int, int] | None:
        """Vráti ohraničenie aktuálneho výberu, ak existuje"""
        selection_set = getattr(self._controller, "active_selection", None)

        if selection_set is None or selection_set.is_empty():
            return None

        return selection_set.combined_bbox()
    
    def _get_initial_color(self) -> tuple[int, int, int]:
        """
        Skúsi použiť aktuálnu farbu z aplikácie
        ak nie je dostupná, použije čiernu
        """
        if hasattr(self._controller, "get_current_color_rgba"):
            rgba = self._controller.get_current_color_rgba()
            r, g, b = [int(x) for x in rgba[:3]]
            return (r, g, b)

        return (0, 0, 0)

    def _clear_color_rows(self) -> None:
        """Odstráni všetky aktuálne farebné riadky"""
        while self._color_rows:
            row = self._color_rows.pop()
            self.colors_layout.removeWidget(row)
            row.deleteLater()

    def _apply_initial_texture_params(self, params: TextureAlgorithmParams) -> None:
        """Predvyplní dialóg existujúcimi parametrami textúry"""
        combo_index = self.texture_combo.findData(params.texture_name)
        if combo_index >= 0:
            self.texture_combo.setCurrentIndex(combo_index)

        self.scale_x_spin.setValue(float(params.scale_x))
        self.scale_y_spin.setValue(float(params.scale_y))
        self.density_x_spin.setValue(float(params.density_x))
        self.density_y_spin.setValue(float(params.density_y))
        self.rotation_spin.setValue(float(params.rotation))
        self.global_scale_spin.setValue(float(params.global_scale))
        self.white_background_checkbox.setChecked(bool(params.white_background))
        self.background_brightness_spin.setValue(float(params.background_brightness))
        self.width_spin.setValue(int(params.width))
        self.height_spin.setValue(int(params.height))

        if params.seed is not None:
            self.seed_spin.setValue(int(params.seed))

        self._clear_color_rows()

        colors = params.colors or [self._get_initial_color()]
        strengths = params.color_strengths or []

        for index, color in enumerate(colors):
            self._add_color_row((int(color[0]), int(color[1]), int(color[2])))
            if index < len(self._color_rows):
                strength_value = float(strengths[index]) if index < len(strengths) else 1.0
                self._color_rows[index].strength_spin.setValue(strength_value)

        if self._force_generate_texture_mode:
            self.generate_texture_radio.setChecked(True)
        else:
            if params.generate_square:
                self.generate_texture_radio.setChecked(True)
            elif self._selection_bbox is not None:
                self.fill_selection_radio.setChecked(True)

    def _apply_color_edit_only_mode(self) -> None:
        """Uzamkne všetky parametre okrem farieb pri úprave generated textúry"""
        self.info_label.setText(
            "Upravte barvy již vygenerované textury. "
            "Ostatní parametry zůstávají stejné jako při původním generování"
        )

        self.texture_combo.setEnabled(False)
        self.scale_x_spin.setEnabled(False)
        self.scale_y_spin.setEnabled(False)
        self.density_x_spin.setEnabled(False)
        self.density_y_spin.setEnabled(False)
        self.rotation_spin.setEnabled(False)
        self.global_scale_spin.setEnabled(False)
        self.white_background_checkbox.setEnabled(False)
        self.background_brightness_spin.setEnabled(False)
        self.width_spin.setEnabled(False)
        self.height_spin.setEnabled(False)
        self.seed_spin.setEnabled(False)

    def _add_color_row(self, color: tuple[int, int, int]) -> None:
        """Pridá nový riadok farby, najviac však do limitu MAX_COLORS"""
        if len(self._color_rows) >= MAX_COLORS:
            return

        row = _TextureColorRow(index=len(self._color_rows) + 1, color=color, remove_callback=self._remove_color_row, parent=self.colors_container)
        row.changed.connect(self._mark_texture_preview_outdated)
        self._color_rows.append(row)
        self.colors_layout.addWidget(row)
        self._update_color_rows()
        self._mark_texture_preview_outdated()

    def _remove_color_row(self, row: _TextureColorRow) -> None:
        """Odstráni riadok farby, ale ponechá aspoň jednu farbu"""
        if len(self._color_rows) <= 1:
            return

        self._color_rows.remove(row)
        self.colors_layout.removeWidget(row)
        row.deleteLater()
        self._update_color_rows()
        self._mark_texture_preview_outdated()
           
    def _update_color_rows(self) -> None:
        """Aktualizuje číslovanie farieb a stav tlačidiel"""
        for index, row in enumerate(self._color_rows, start=1):
            row.set_index(index)
            row.set_remove_enabled(len(self._color_rows) > 1)

        if hasattr(self, "btn_add_color"):
            self.btn_add_color.setEnabled(len(self._color_rows) < MAX_COLORS)

        self._update_ok_button()

    def _connect_texture_preview_signals(self) -> None:
        """Prepojí zmeny parametrov so stavom náhľadu"""
        self.texture_combo.currentIndexChanged.connect(self._mark_texture_preview_outdated)

        self.scale_x_spin.valueChanged.connect(self._mark_texture_preview_outdated)
        self.scale_y_spin.valueChanged.connect(self._mark_texture_preview_outdated)
        self.density_x_spin.valueChanged.connect(self._mark_texture_preview_outdated)
        self.density_y_spin.valueChanged.connect(self._mark_texture_preview_outdated)
        self.rotation_spin.valueChanged.connect(self._mark_texture_preview_outdated)
        self.global_scale_spin.valueChanged.connect(self._mark_texture_preview_outdated)

        self.white_background_checkbox.toggled.connect(self._mark_texture_preview_outdated)
        self.background_brightness_spin.valueChanged.connect(self._mark_texture_preview_outdated)

        self.width_spin.valueChanged.connect(self._mark_texture_preview_outdated)
        self.height_spin.valueChanged.connect(self._mark_texture_preview_outdated)
        self.seed_spin.valueChanged.connect(self._mark_texture_preview_outdated)

    def _mark_texture_preview_outdated(self, *_args) -> None:
        """Označí zobrazený náhľad ako neaktuálny"""
        if not hasattr(self, "preview_status_label"):
            return

        if not self._preview_is_current:
            return

        self._preview_is_current = False
        self.preview_status_label.setText(
            "Parametry byly změněny. "
            "Pro aktuální výsledek vygenerujte náhled znovu"
        )

    @staticmethod
    def _calculate_texture_preview_size(width: int, height: int) -> tuple[int, int]:
        """
        Zmenší rozmery pri zachovaní pomeru strán

        najdlhšia strana má najviac 256 px
        """
        width = max(1, int(width))
        height = max(1, int(height))

        scale = min(1.0, TEXTURE_PREVIEW_MAX_SIZE / float(max(width, height)))

        preview_width = max(TEXTURE_PREVIEW_MIN_SIZE, int(round(width * scale)))
        preview_height = max(TEXTURE_PREVIEW_MIN_SIZE, int(round(height * scale)))

        return preview_width, preview_height

    def _build_texture_preview_params(self) -> TextureAlgorithmParams | None:
        """Vytvorí parametre pre menší orientačný náhľad"""
        result = self.get_result()

        if result is None:
            return None

        preview_width, preview_height = self._calculate_texture_preview_size(result.width, result.height)

        return TextureAlgorithmParams(
            texture_name=result.texture_name,
            colors=list(result.colors),
            color_strengths=list(result.color_strengths),
            scale_x=result.scale_x,
            scale_y=result.scale_y,
            density_x=result.density_x,
            density_y=result.density_y,
            rotation=result.rotation,
            global_scale=result.global_scale,
            white_background=result.white_background,
            background_brightness=result.background_brightness,
            generate_square=True,
            width=preview_width,
            height=preview_height,
            seed=result.seed,
        )

    def _on_generate_texture_preview_clicked(self) -> None:
        """Vygeneruje a zobrazí orientačný náhľad textúry"""
        preview_params = self._build_texture_preview_params()

        if preview_params is None:
            self.preview_status_label.setText(
                "Náhled nelze vytvořit. "
                "Zkontrolujte model a zvolené barvy."
            )
            return

        self.btn_generate_texture_preview.setEnabled(False)
        self.preview_status_label.setText("Generuji náhled...")

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()

        try:
            preview_image = AlgorithmRunner.generate_texture_material(preview_params)

            self._show_generated_texture_preview(preview_image)
            self._preview_is_current = True
            self.preview_status_label.setText(
                "Náhled odpovídá aktuálním parametrům "
                f"({preview_params.width}×"
                f"{preview_params.height} px)."
            )
        except Exception as error:
            self._preview_is_current = False
            self.result_preview_label.setPixmap(QPixmap())
            self.result_preview_label.setText("Náhled se nepodařilo vygenerovat")
            self.preview_status_label.setText(f"Chyba při generování náhledu: {error}")
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_generate_texture_preview.setEnabled(True)

    def _show_generated_texture_preview(self, image: np.ndarray) -> None:
        """Zobrazí RGB alebo RGBA výsledok v preview prvku"""
        array = np.asarray(image)

        if array.ndim != 3 or array.shape[2] not in (3, 4):
            raise ValueError("Náhled textury má neplatný formát")

        if array.dtype != np.uint8:
            array = np.clip(array, 0, 255).astype(np.uint8)

        array = np.ascontiguousarray(array)
        height, width, channels = array.shape

        if channels == 4:
            image_format = QImage.Format_RGBA8888
        else:
            image_format = QImage.Format_RGB888

        qimage = QImage(array.data, width, height, int(array.strides[0]), image_format).copy()

        pixmap = QPixmap.fromImage(qimage)
        pixmap = pixmap.scaled(self.result_preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        self.result_preview_label.setText("")
        self.result_preview_label.setPixmap(pixmap)

    def _update_output_mode(self) -> None:
        """Aktualizuje dialóg podľa zvoleného typu výstupu"""
        generate_square = self.generate_texture_radio.isChecked()

        self.square_group.setVisible(generate_square)

        if generate_square:
            self.info_label.setText("Algoritmus vygeneruje samostatný obrázek textury. Po dokončení bude přidán do panelu materiálů aktuálního projektu")
        elif self._selection_bbox is not None:
            x, y, width, height = self._selection_bbox

            self.info_label.setText(
                f"Vybraná oblast: x={x}, y={y}, "
                f"w={width}, h={height}. "
                "Výsledek bude vložen pouze do dosud "
                "nevyplněných poškozených pixelů"
            )
        else:
            self.info_label.setText("Pro doplnění obrazu je nejprve nutné vytvořit výběr. Samostatnou texturu lze generovat i bez výběru.")

        self._update_ok_button()

    def _update_texture_model(self) -> None:
        """Aktualizuje náhľad a parametre zvoleného modelu"""
        texture_name = self.texture_combo.currentData()

        if texture_name is None:
            if not self.model_info_label.text():
                self.model_info_label.setText("Balík neobsahuje žádný dostupný model textury.")

            self.texture_preview.setPixmap(QPixmap())
            self.texture_preview.setText("Náhled není k dispozici")

            self.density_x_spin.setEnabled(False)
            self.density_y_spin.setEnabled(False)
            self.density_note.setText("")

            self._update_ok_button()
            return

        texture_name = str(texture_name)

        density_enabled = texture_name in DENSITY_APPLICABLE_TEXTURES

        self.density_x_spin.setEnabled(density_enabled)
        self.density_y_spin.setEnabled(density_enabled)

        if density_enabled:
            self.density_note.setText("Tento model podporuje samostatnou změnu hustoty v osách X a Y")
        else:
            self.density_x_spin.setValue(0.0)
            self.density_y_spin.setValue(0.0)
            self.density_note.setText("Pro tento model se parametry hustoty nepoužívají.")

        self.model_info_label.setText("V seznamu jsou zobrazeny pouze modely, které jsou skutečně nainstalovány v balíku texture-infill.")

        self._load_texture_preview(texture_name)
        self._update_ok_button()

    def _load_texture_preview(self, texture_name: str) -> None:
        """Načíta náhľadový obrázok zvoleného modelu"""
        suffix = texture_name.removeprefix("texture_")

        preview_path = (
            Path(__file__).resolve().parents[1]
            / "resources"
            / "texture_previews"
            / f"seed_texture_{suffix}.png"
        )

        pixmap = QPixmap(str(preview_path))

        if pixmap.isNull():
            self.texture_preview.setPixmap(QPixmap())
            self.texture_preview.setText("Náhled není k dispozici")
            return

        self.texture_preview.setText("")
        self.texture_preview.setPixmap(pixmap.scaled(self.texture_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _update_background_controls(self) -> None:
        """Povolí jas iba pri nepriehľadnom pozadí"""
        self.background_brightness_spin.setEnabled(self.white_background_checkbox.isChecked())

    def _update_ok_button(self) -> None:
        """Povolí potvrdenie iba pri platných nastaveniach"""
        if not hasattr(self, "buttons"):
            return

        ok_button = self.buttons.button(QDialogButtonBox.Ok)

        if ok_button is None:
            return

        has_model = self.texture_combo.currentData() is not None
        has_colors = bool(self._color_rows)
        valid_output_mode = self.generate_texture_radio.isChecked() or self._selection_bbox is not None

        ok_button.setEnabled(has_model and has_colors and valid_output_mode)

    def _on_add_color_clicked(self) -> None:
        """Pridá ďalšiu farbu podľa aktuálnej farby v aplikácii"""
        self._add_color_row(self._get_initial_color())