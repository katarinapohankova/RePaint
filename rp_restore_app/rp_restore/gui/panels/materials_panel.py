from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor, QPixmap, QImage, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QSlider, QColorDialog, QGridLayout, QToolButton, QRadioButton, QButtonGroup, QGroupBox, QFrame, QScrollArea

from rp_restore.core.texture_brush import generate_brush_stamp


class MaterialsPanel(QWidget):
    """
    Panel pre materiály:
      -prepínač: Brush vs Textura
      -textúrové nastavenia (scale/strength/rotation) + výber textúry + preview
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._controller = None
        self._current_color = QColor(0, 0, 0)
        self._selected_texture_name: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        #---Brush size--
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Velikost štětce:"))
        self.brush_slider = QSlider(Qt.Horizontal)
        self.brush_slider.setRange(1, 200)
        self.brush_slider.setValue(10)
        self.brush_slider.valueChanged.connect(self._on_brush_size_changed)
        row2.addWidget(self.brush_slider)
        layout.addLayout(row2)

        #---Mode--- exkluzívne
        mode_box = QGroupBox("Režim")
        mode_layout = QHBoxLayout(mode_box)

        self.rb_brush = QRadioButton("Štětec")
        self.rb_texture = QRadioButton("Textura")
        self.rb_brush.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.rb_brush)
        self.mode_group.addButton(self.rb_texture)

        self.rb_brush.toggled.connect(self._on_mode_changed)
        self.rb_texture.toggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self.rb_brush)
        mode_layout.addWidget(self.rb_texture)
        layout.addWidget(mode_box)

        #---Texture controls--- aktívne iba pri zvolenom Texture
        self.texture_controls = QWidget()
        tex_layout = QVBoxLayout(self.texture_controls)
        tex_layout.setContentsMargins(0, 0, 0, 0)
        tex_layout.setSpacing(8)

        #štýl textúry
        style_box = QGroupBox("Styl textury")
        style_layout = QHBoxLayout(style_box)

        self.rb_texture_transparent = QRadioButton("Transparentní")
        self.rb_texture_color = QRadioButton("Barevná")
        self.rb_texture_transparent.setChecked(True)

        self.texture_style_group = QButtonGroup(self)
        self.texture_style_group.setExclusive(True)
        self.texture_style_group.addButton(self.rb_texture_transparent)
        self.texture_style_group.addButton(self.rb_texture_color)

        self.rb_texture_transparent.toggled.connect(self._on_texture_style_changed)
        self.rb_texture_color.toggled.connect(self._on_texture_style_changed)

        style_layout.addWidget(self.rb_texture_transparent)
        style_layout.addWidget(self.rb_texture_color)
        tex_layout.addWidget(style_box)

        tex_layout.addWidget(QLabel("Textury:"))

        self.tex_grid_widget = QWidget()
        self.tex_grid_layout = QGridLayout(self.tex_grid_widget)
        self.tex_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.tex_grid_layout.setSpacing(6)
        tex_layout.addWidget(self.tex_grid_widget)

        #scale
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Hustota:"))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(25, 400)  #0.25..4.00
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        r1.addWidget(self.scale_slider)
        tex_layout.addLayout(r1)

        #strength
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Síla:"))
        self.strength_slider = QSlider(Qt.Horizontal)
        self.strength_slider.setRange(0, 100)
        self.strength_slider.setValue(100)
        self.strength_slider.valueChanged.connect(self._on_strength_changed)
        r2.addWidget(self.strength_slider)
        tex_layout.addLayout(r2)

        #rotation
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Rotace:"))
        self.rot_slider = QSlider(Qt.Horizontal)
        self.rot_slider.setRange(-180, 180)
        self.rot_slider.setValue(0)
        self.rot_slider.valueChanged.connect(self._on_rotation_changed)
        r3.addWidget(self.rot_slider)
        tex_layout.addLayout(r3)

        tex_layout.addWidget(QLabel("Náhled:"))
        self.preview = QLabel()
        self.preview.setFixedSize(180, 180)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("border: 1px solid #555; background: #222;")
        tex_layout.addWidget(self.preview)

        layout.addWidget(self.texture_controls)

        layout.addStretch(1)

        #default = brush mode
        self._apply_mode_ui()

    #prepojenie s controllerom
    def set_controller(self, controller) -> None:
        self._controller = controller

    def refresh_from_project(self, project) -> None:
        if self._controller is None or project is None:
            return

        #brush size
        if hasattr(self._controller, "get_brush_size"):
            self.brush_slider.blockSignals(True)
            self.brush_slider.setValue(int(self._controller.get_brush_size()))
            self.brush_slider.blockSignals(False)

        #textures
        self._rebuild_textures_grid(project)

        #sliders z controller.texture_settings
        ts = getattr(self._controller, "texture_settings", None)
        if ts is not None:
            self.scale_slider.blockSignals(True)
            self.strength_slider.blockSignals(True)
            self.rot_slider.blockSignals(True)
            self.scale_slider.setValue(int(round(float(ts.scale) * 100)))
            self.strength_slider.setValue(int(round(float(ts.strength) * 100)))
            self.rot_slider.setValue(int(round(float(getattr(ts, "rotation_deg", 0.0)))))
            self.scale_slider.blockSignals(False)
            self.strength_slider.blockSignals(False)
            self.rot_slider.blockSignals(False)

            style = getattr(ts, "texture_style", "transparent")

            self.rb_texture_transparent.blockSignals(True)
            self.rb_texture_color.blockSignals(True)

            self.rb_texture_transparent.setChecked(style == "transparent")
            self.rb_texture_color.setChecked(style == "color")

            self.rb_texture_transparent.blockSignals(False)
            self.rb_texture_color.blockSignals(False)

        self._update_preview(project)

    def _on_brush_size_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.set_brush_size(int(value))

    #palette buttons
    def _clear_layout(self, grid: QGridLayout) -> None:
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    #brush/texture
    def _on_mode_changed(self) -> None:
        self._apply_mode_ui()
        if self._controller is None:
            return
        self._controller.paint_mode = "texture" if self.rb_texture.isChecked() else "brush"

    def _apply_mode_ui(self) -> None:
        tex_enabled = self.rb_texture.isChecked()
        self.texture_controls.setVisible(tex_enabled)

    #texture
    def _rebuild_textures_grid(self, project) -> None:
        self._clear_layout(self.tex_grid_layout)

        textures = getattr(project, "textures", {})
        cols = 4
        thumb = 64

        ts = getattr(self._controller, "texture_settings", None)
        if ts is not None and ts.texture is not None:
            self._selected_texture_name = ts.texture.name

        names = sorted(textures.keys())

        for idx, name in enumerate(sorted(textures.keys())):
            tex = textures[name].image  #RGBA

            h, w, _ = tex.shape
            qimg = QImage(tex.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
            pix = QPixmap.fromImage(qimg).scaled(thumb, thumb, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

            btn = QToolButton()
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(thumb, thumb))
            btn.setFixedSize(thumb + 10, thumb + 10)
            btn.setToolTip(name)

            if self._selected_texture_name == name:
                btn.setStyleSheet("border: 2px solid #4aa3ff;")
            else:
                btn.setStyleSheet("border: 1px solid #555;")

            btn.clicked.connect(lambda checked=False, n=name: self._select_texture(n))

            r = idx // cols
            c = idx % cols
            self.tex_grid_layout.addWidget(btn, r, c)

        add_idx = len(names)
        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("Přidat texturu do projektu")
        add_btn.setFixedSize(thumb + 10, thumb + 10)
        add_btn.setStyleSheet("QToolButton { border: 1px dashed #777; font-weight: bold; }"
                              "QToolButton:hover { border: 2px solid #4aa3ff; }")
        add_btn.clicked.connect(self._on_add_texture_clicked)

        r = add_idx // cols
        c = add_idx % cols
        self.tex_grid_layout.addWidget(add_btn, r, c)

    def _on_add_texture_clicked(self) -> None:
        """
        kliknuté na + v zozname textúr
        """
        if self._controller is None:
            return

        if hasattr(self._controller, "add_texture_from_file_via_dialog"):
            self._controller.add_texture_from_file_via_dialog(parent=self)

    def _select_texture(self, name: str) -> None:
        if self._controller is None or self._controller.project is None:
            return
        tex = self._controller.project.textures.get(name)
        self._controller.texture_settings.texture = tex
        self._selected_texture_name = name
        self._rebuild_textures_grid(self._controller.project)
        self._update_preview(self._controller.project)

    def _on_scale_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.texture_settings.scale = max(0.25, min(4.0, value / 100.0))
        self._update_preview(self._controller.project)

    def _on_strength_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.texture_settings.strength = max(0.0, min(1.0, value / 100.0))
        self._update_preview(self._controller.project)

    def _on_rotation_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.texture_settings.rotation_deg = float(value)
        self._update_preview(self._controller.project)

    def _update_preview(self, project) -> None:
        if self._controller is None:
            self.preview.clear()
            return

        ts = self._controller.texture_settings
        if ts.texture is None:
            self.preview.setText("Žádná textura")
            return

        r, g, b , a = project.get_current_color_rgba()
        ts.color = (r, g, b)

        stamp = generate_brush_stamp(ts, size=96, offset_x=0, offset_y=0)

        h, w, _ = stamp.shape
        qimg = QImage(stamp.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
        pix = QPixmap.fromImage(qimg).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pix)

    def _on_texture_style_changed(self) -> None:
        """
        Prepína medzi transparentnou a farebnou textúrou
        """
        if self._controller is None:
            return

        style = "color" if self.rb_texture_color.isChecked() else "transparent"

        if hasattr(self._controller, "set_texture_style"):
            self._controller.set_texture_style(style)
        else:
            self._controller.texture_settings.texture_style = style

        if self._controller.project is not None:
            self._update_preview(self._controller.project)

    def set_brush_size_value(self, size: int) -> None:
        self.brush_slider.blockSignals(True)
        self.brush_slider.setValue(int(size))
        self.brush_slider.blockSignals(False)
