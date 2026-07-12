from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

MAX_COLORS = 3

@dataclass
class TextureFillDialogResult:
    """Výsledok nastavení textúrového algoritmu"""

    texture_name: str
    colors: list[tuple[int, int, int]]
    global_scale: float
    rotation: float
    seed: int | None


class _TextureColorRow(QWidget):
    """
    Jeden riadok pre výber jednej farby textúry
    """

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
        self.btn_remove = QPushButton("Odstranit")
        layout.addWidget(self.btn_change)
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

    def _on_remove_clicked(self) -> None:
        """Požiada rodičovský dialóg o odstránenie tohto riadku"""
        self._remove_callback(self)


class TextureFillDialog(QDialog):
    """
    Dialóg pre nastavenie parametrov textúrového algoritmu
    používateľ vyberá typ textúry, jednu až tri farby, mierku, rotáciu a voliteľný seed
    """

    def __init__(self, controller: object, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Texturové doplnění – parametry")
        self._controller = controller
        self._color_rows: list[_TextureColorRow] = []

        layout = QVBoxLayout(self)

        info_text = "Nastavte parametry pro generování textury."
        if hasattr(controller, "get_active_selection_bbox"):
            bbox = controller.get_active_selection_bbox()
            if bbox is not None:
                x, y, w, h = bbox
                info_text += f"\nVybraná oblast: x={x}, y={y}, w={w}, h={h}"

        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        #typ textúry
        texture_row = QHBoxLayout()
        texture_row.addWidget(QLabel("Typ textury:"))

        self.texture_combo = QComboBox()
        self.texture_combo.addItem("texture_H")
        texture_row.addWidget(self.texture_combo)

        layout.addLayout(texture_row)

        #farby
        layout.addWidget(QLabel("Barvy textury:"))

        self.colors_container = QWidget()
        self.colors_layout = QVBoxLayout(self.colors_container)
        self.colors_layout.setContentsMargins(0, 0, 0, 0)
        self.colors_layout.setSpacing(6)
        layout.addWidget(self.colors_container)

        self.btn_add_color = QPushButton("Přidat barvu")
        self.btn_add_color.clicked.connect(self._on_add_color_clicked)
        layout.addWidget(self.btn_add_color)

        #predvolene pridáme prvú farbu podľa aktuálnej farby v aplikácii
        self._add_color_row(self._get_initial_color())

        #global scale
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Global scale:"))

        self.global_scale_spin = QDoubleSpinBox()
        self.global_scale_spin.setRange(0.10, 10.0)
        self.global_scale_spin.setSingleStep(0.10)
        self.global_scale_spin.setDecimals(2)
        self.global_scale_spin.setValue(1.00)
        scale_row.addWidget(self.global_scale_spin)

        layout.addLayout(scale_row)

        #rotácia
        rotation_row = QHBoxLayout()
        rotation_row.addWidget(QLabel("Rotace (°):"))

        self.rotation_spin = QDoubleSpinBox()
        self.rotation_spin.setRange(-180.0, 180.0)
        self.rotation_spin.setSingleStep(1.0)
        self.rotation_spin.setDecimals(1)
        self.rotation_spin.setValue(0.0)
        rotation_row.addWidget(self.rotation_spin)

        layout.addLayout(rotation_row)

        #seed
        seed_row = QHBoxLayout()
        self.seed_checkbox = QCheckBox("Použít seed")
        seed_row.addWidget(self.seed_checkbox)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setValue(111)
        self.seed_spin.setEnabled(False)
        seed_row.addWidget(self.seed_spin)

        self.seed_checkbox.toggled.connect(self.seed_spin.setEnabled)
        layout.addLayout(seed_row)

        note = QLabel(
            "parametry scale_x, scale_y, density_x a density_y "
            "jsou zatím ponechány na interních hodnotách algoritmu"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._update_color_rows()

    def get_result(self) -> TextureFillDialogResult | None:
        """Vráti nastavenia dialógu alebo None, ak nie je zvolená žiadna farba"""
        if not self._color_rows:
            return None

        colors = [row.get_rgb() for row in self._color_rows]

        seed: int | None
        if self.seed_checkbox.isChecked():
            seed = int(self.seed_spin.value())
        else:
            seed = None

        return TextureFillDialogResult(texture_name=self.texture_combo.currentText(), colors=colors, global_scale=float(self.global_scale_spin.value()), rotation=float(self.rotation_spin.value()), seed=seed)

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

    def _add_color_row(self, color: tuple[int, int, int]) -> None:
        """Pridá nový riadok farby, najviac však do limitu MAX_COLORS"""
        if len(self._color_rows) >= MAX_COLORS:
            return

        row = _TextureColorRow(index=len(self._color_rows) + 1, color=color, remove_callback=self._remove_color_row, parent=self.colors_container)
        self._color_rows.append(row)
        self.colors_layout.addWidget(row)
        self._update_color_rows()

    def _remove_color_row(self, row: _TextureColorRow) -> None:
        """Odstráni riadok farby, ale ponechá aspoň jednu farbu"""
        if len(self._color_rows) <= 1:
            return

        self._color_rows.remove(row)
        self.colors_layout.removeWidget(row)
        row.deleteLater()
        self._update_color_rows()

    def _update_color_rows(self) -> None:
        """Aktualizuje číslovanie riadkov a stav tlačidiel"""
        for i, row in enumerate(self._color_rows, start=1):
            row.set_index(i)
            row.set_remove_enabled(len(self._color_rows) > 1)

        if hasattr(self, "btn_add_color"):
            self.btn_add_color.setEnabled(len(self._color_rows) < MAX_COLORS)

        #pri prvom pridaní farby ešte nemusí existovať QDialogButtonBox
        if not hasattr(self, "buttons"):
            return

        ok_btn = self.buttons.button(QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setEnabled(len(self._color_rows) > 0)
            
    def _on_add_color_clicked(self) -> None:
        """Pridá ďalšiu farbu podľa aktuálnej farby v aplikácii"""
        self._add_color_row(self._get_initial_color())