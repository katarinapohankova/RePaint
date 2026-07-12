from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QSlider, QGridLayout, QToolButton, QRadioButton, QButtonGroup, QGroupBox, QCheckBox

from rp_restore.core.texture_brush import generate_brush_stamp


class MaterialsPanel(QWidget):
    """
    Panel pre nastavenie štetca, gumy, rozmazania a textúr
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._controller = None
        self._selected_texture_name: str | None = None
        self._texture_buttons: dict[str, QToolButton] = {}

        self._deform_status_timer = QTimer(self)
        self._deform_status_timer.setSingleShot(True)
        self._deform_status_timer.timeout.connect(self._clear_deformation_status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        #veľkosť štetca
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Velikost štětce:"))

        self.brush_minus_btn = QPushButton("−")
        self.brush_minus_btn.setFixedWidth(28)
        self.brush_minus_btn.setToolTip("Zmenšit štětec")
        self.brush_minus_btn.clicked.connect(lambda: self._change_brush_size_by(-1))
        row2.addWidget(self.brush_minus_btn)

        self.brush_slider = QSlider(Qt.Horizontal)
        self.brush_slider.setRange(1, 200)
        self.brush_slider.setValue(10)
        self.brush_slider.valueChanged.connect(self._on_brush_size_changed)
        row2.addWidget(self.brush_slider)

        self.brush_plus_btn = QPushButton("+")
        self.brush_plus_btn.setFixedWidth(28)
        self.brush_plus_btn.setToolTip("Zvětšit štětec")
        self.brush_plus_btn.clicked.connect(lambda: self._change_brush_size_by(1))
        row2.addWidget(self.brush_plus_btn)

        layout.addLayout(row2)

        #nastavenia štetca, gumy a rozmazania
        brush_box = QGroupBox("Štětec / guma / rozmazání")
        brush_layout = QVBoxLayout(brush_box)

        hardness_row = QHBoxLayout()
        hardness_row.addWidget(QLabel("Tvrdost:"))
        self.hardness_slider = QSlider(Qt.Horizontal)
        self.hardness_slider.setRange(0, 100)
        self.hardness_slider.setValue(100)
        self.hardness_slider.valueChanged.connect(self._on_hardness_changed)
        hardness_row.addWidget(self.hardness_slider)
        brush_layout.addLayout(hardness_row)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Krytí:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider)

        self.overlap_checkbox = QCheckBox("Vrstvit v tahu")
        self.overlap_checkbox.setChecked(True)
        self.overlap_checkbox.setToolTip("Pokud je zapnuto, dá se tah vrstvit, ale maximálně do hodnoty Krytí")
        self.overlap_checkbox.toggled.connect(self._on_overlap_changed)
        opacity_row.addWidget(self.overlap_checkbox)

        brush_layout.addLayout(opacity_row)

        flow_row = QHBoxLayout()
        flow_row.addWidget(QLabel("Hustota:"))
        self.flow_slider = QSlider(Qt.Horizontal)
        self.flow_slider.setRange(0, 100)
        self.flow_slider.setValue(100)
        self.flow_slider.valueChanged.connect(self._on_flow_changed)
        flow_row.addWidget(self.flow_slider)
        brush_layout.addLayout(flow_row)

        layout.addWidget(brush_box)

        blend_row = QHBoxLayout()
        blend_row.addWidget(QLabel("Síla rozmazání:"))

        self.blend_strength_slider = QSlider(Qt.Horizontal)
        self.blend_strength_slider.setRange(0, 100)
        self.blend_strength_slider.setValue(50)
        self.blend_strength_slider.valueChanged.connect(self._on_blend_strength_changed)

        blend_row.addWidget(self.blend_strength_slider)
        brush_layout.addLayout(blend_row)

        blend_source_row = QHBoxLayout()
        blend_source_row.addWidget(QLabel("Zdroj rozmazání:"))

        self.rb_blend_active_paint = QRadioButton("Vrstva malby")
        self.rb_blend_bg_and_paint = QRadioButton("Původní obraz + vrstva malby")
        self.rb_blend_active_paint.setChecked(True)

        self.blend_source_group = QButtonGroup(self)
        self.blend_source_group.setExclusive(True)
        self.blend_source_group.addButton(self.rb_blend_active_paint)
        self.blend_source_group.addButton(self.rb_blend_bg_and_paint)

        blend_source_row.addWidget(self.rb_blend_active_paint)
        blend_source_row.addWidget(self.rb_blend_bg_and_paint)

        brush_layout.addLayout(blend_source_row)

        self.rb_blend_active_paint.toggled.connect(self._on_blend_source_mode_changed)
        self.rb_blend_bg_and_paint.toggled.connect(self._on_blend_source_mode_changed)

        #prepínač medzi štetcom a textúrou
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

        #nastavenia textúry
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

        #hustota textúry
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Hustota:"))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(25, 400)  #0.25..4.00
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        r1.addWidget(self.scale_slider)
        tex_layout.addLayout(r1)

        #sila textúry
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Síla:"))
        self.strength_slider = QSlider(Qt.Horizontal)
        self.strength_slider.setRange(0, 100)
        self.strength_slider.setValue(100)
        self.strength_slider.valueChanged.connect(self._on_strength_changed)
        r2.addWidget(self.strength_slider)
        tex_layout.addLayout(r2)

        #rotácia textúry
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Rotace:"))
        self.rot_slider = QSlider(Qt.Horizontal)
        self.rot_slider.setRange(-180, 180)
        self.rot_slider.setValue(0)
        self.rot_slider.valueChanged.connect(self._on_rotation_changed)
        r3.addWidget(self.rot_slider)
        tex_layout.addLayout(r3)

        #deformácia textúry
        deform_box = QGroupBox("Deformace textury")
        deform_layout = QVBoxLayout(deform_box)

        dx_row = QHBoxLayout()
        dx_row.addWidget(QLabel("Šířka:"))

        self.deform_x_slider = QSlider(Qt.Horizontal)
        self.deform_x_slider.setRange(25, 400)
        self.deform_x_slider.setValue(100)
        self.deform_x_slider.valueChanged.connect(self._on_deform_x_changed)
        dx_row.addWidget(self.deform_x_slider)

        self.deform_x_value_label = QLabel("100 %")
        self.deform_x_value_label.setFixedWidth(48)
        dx_row.addWidget(self.deform_x_value_label)

        deform_layout.addLayout(dx_row)

        dy_row = QHBoxLayout()
        dy_row.addWidget(QLabel("Výška:"))

        self.deform_y_slider = QSlider(Qt.Horizontal)
        self.deform_y_slider.setRange(25, 400)
        self.deform_y_slider.setValue(100)
        self.deform_y_slider.valueChanged.connect(self._on_deform_y_changed)
        dy_row.addWidget(self.deform_y_slider)

        self.deform_y_value_label = QLabel("100 %")
        self.deform_y_value_label.setFixedWidth(48)
        dy_row.addWidget(self.deform_y_value_label)

        deform_layout.addLayout(dy_row)

        deform_btn_row = QHBoxLayout()

        self.btn_reset_deformation = QPushButton("Resetovat deformaci")
        self.btn_reset_deformation.clicked.connect(self._on_reset_deformation_clicked)
        deform_btn_row.addWidget(self.btn_reset_deformation)

        self.btn_add_deformed_texture = QPushButton("Přidat mezi textury")
        self.btn_add_deformed_texture.clicked.connect(self._on_add_deformed_texture_clicked)
        deform_btn_row.addWidget(self.btn_add_deformed_texture)

        deform_layout.addLayout(deform_btn_row)

        self.deformation_status_label = QLabel("")
        self.deformation_status_label.setStyleSheet("color: #d66;")
        deform_layout.addWidget(self.deformation_status_label)

        tex_layout.addWidget(deform_box)

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
        """Nastaví controller panelu"""
        self._controller = controller

    def refresh_from_project(self, project) -> None:
        """Aktualizuje hodnoty panelu podľa controlleru a projektu"""
        if self._controller is None or project is None:
            return
        #blend
        if hasattr(self._controller, "get_blend_strength"):
            self.blend_strength_slider.blockSignals(True)
            self.blend_strength_slider.setValue(int(round(self._controller.get_blend_strength() * 100)))
            self.blend_strength_slider.blockSignals(False)

        if hasattr(self._controller, "get_blend_source_mode"):
            self.set_blend_source_mode_value(self._controller.get_blend_source_mode())
            
        #brush size
        if hasattr(self._controller, "get_brush_size"):
            self.brush_slider.blockSignals(True)
            self.brush_slider.setValue(int(self._controller.get_brush_size()))
            self.brush_slider.blockSignals(False)

        if hasattr(self._controller, "get_brush_hardness"):
            self.hardness_slider.blockSignals(True)
            self.hardness_slider.setValue(int(round(self._controller.get_brush_hardness() * 100)))
            self.hardness_slider.blockSignals(False)

        if hasattr(self._controller, "get_brush_opacity"):
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(int(round(self._controller.get_brush_opacity() * 100)))
            self.opacity_slider.blockSignals(False)

        if hasattr(self._controller, "get_brush_allow_overlap"):
            self.overlap_checkbox.blockSignals(True)
            self.overlap_checkbox.setChecked(bool(self._controller.get_brush_allow_overlap()))
            self.overlap_checkbox.blockSignals(False)

        if hasattr(self._controller, "get_brush_flow"):
            self.flow_slider.blockSignals(True)
            self.flow_slider.setValue(int(round(self._controller.get_brush_flow() * 100)))
            self.flow_slider.blockSignals(False)

        #textures
        self._rebuild_textures_grid(project)

        #sliders z controller.texture_settings
        ts = getattr(self._controller, "texture_settings", None)
        if ts is not None:
            self.scale_slider.blockSignals(True)
            self.strength_slider.blockSignals(True)
            self.rot_slider.blockSignals(True)
            self.deform_x_slider.blockSignals(True)
            self.deform_y_slider.blockSignals(True)
            self.scale_slider.setValue(int(round(float(ts.scale) * 100)))
            self.strength_slider.setValue(int(round(float(ts.strength) * 100)))
            self.rot_slider.setValue(int(round(float(getattr(ts, "rotation_deg", 0.0)))))
            self.deform_x_slider.setValue(int(round(float(getattr(ts, "deformation_scale_x", 1.0)) * 100)))
            self.deform_y_slider.setValue(int(round(float(getattr(ts, "deformation_scale_y", 1.0)) * 100)))
            self.scale_slider.blockSignals(False)
            self.strength_slider.blockSignals(False)
            self.rot_slider.blockSignals(False)
            self.deform_x_slider.blockSignals(False)
            self.deform_y_slider.blockSignals(False)
            self._update_deformation_value_labels()

            style = getattr(ts, "texture_style", "transparent")

            self.rb_texture_transparent.blockSignals(True)
            self.rb_texture_color.blockSignals(True)

            self.rb_texture_transparent.setChecked(style == "transparent")
            self.rb_texture_color.setChecked(style == "color")

            self.rb_texture_transparent.blockSignals(False)
            self.rb_texture_color.blockSignals(False)

            self._update_deformation_controls_state()

        self._update_preview(project)

    def _on_brush_size_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.set_brush_size(int(value))

    def _on_hardness_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.set_brush_hardness(value / 100.0)

    def _on_opacity_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.set_brush_opacity(value / 100.0)

    def _on_overlap_changed(self, checked: bool) -> None:
        if self._controller is None:
            return
        if hasattr(self._controller, "set_brush_allow_overlap"):
            self._controller.set_brush_allow_overlap(bool(checked))
            
    def _on_flow_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.set_brush_flow(value / 100.0)

    def _on_blend_strength_changed(self, value: int) -> None:
        if self._controller is None:
            return

        if hasattr(self._controller, "set_blend_strength"):
            self._controller.set_blend_strength(value / 100.0)

    def set_blend_strength_value(self, value: int) -> None:
        self.blend_strength_slider.blockSignals(True)
        self.blend_strength_slider.setValue(int(value))
        self.blend_strength_slider.blockSignals(False)

    def _on_blend_source_mode_changed(self) -> None:
        if self._controller is None:
            return

        mode = "background_and_active_paint" if self.rb_blend_bg_and_paint.isChecked() else "active_paint"

        if hasattr(self._controller, "set_blend_source_mode"):
            self._controller.set_blend_source_mode(mode)

    def set_blend_source_mode_value(self, mode: str) -> None:
        self.rb_blend_active_paint.blockSignals(True)
        self.rb_blend_bg_and_paint.blockSignals(True)

        self.rb_blend_active_paint.setChecked(mode == "active_paint")
        self.rb_blend_bg_and_paint.setChecked(mode == "background_and_active_paint")

        self.rb_blend_active_paint.blockSignals(False)
        self.rb_blend_bg_and_paint.blockSignals(False)

    def _change_brush_size_by(self, delta: int) -> None:
        """
        Zmení veľkosť štetca tlačidlami + / - v paneli
        """
        if self._controller is None:
            return
        
        value = int(self.brush_slider.value()) + int(delta)
        value = max(self.brush_slider.minimum(), min(self.brush_slider.maximum(), value))

        self.brush_slider.setValue(value)
        self._controller.set_brush_size(value)

    def _clear_layout(self, grid: QGridLayout) -> None:
        """Odstráni všetky widgety z grid layoutu"""
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _on_mode_changed(self) -> None:
        self._apply_mode_ui()
        if self._controller is None:
            return
        self._controller.paint_mode = "texture" if self.rb_texture.isChecked() else "brush"
        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def _apply_mode_ui(self) -> None:
        """Zobrazí alebo skryje nastavenia textúry podľa zvoleného režimu"""
        tex_enabled = self.rb_texture.isChecked()
        self.texture_controls.setVisible(tex_enabled)

    #texture
    def _rebuild_textures_grid(self, project) -> None:
        self._clear_layout(self.tex_grid_layout)

        self._texture_buttons = {}

        textures = getattr(project, "textures", {})
        cols = 4
        thumb = 64

        ts = getattr(self._controller, "texture_settings", None)
        if ts is not None and ts.texture is not None:
            self._selected_texture_name = ts.texture.name

        names = list(textures.keys())

        for idx, name in enumerate(names):
            tex_obj = textures[name]
            tex = tex_obj.image #RGBA

            h, w, _ = tex.shape
            qimg = QImage(tex.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
            pix = QPixmap.fromImage(qimg).scaled(thumb, thumb, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

            btn = QToolButton()
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(thumb, thumb))
            btn.setFixedSize(thumb + 10, thumb + 10)
            tooltip = name
            if getattr(tex_obj, "is_generated", False):
                src = getattr(tex_obj, "source_texture_name", None)
                sx = int(round(float(getattr(tex_obj, "deformation_scale_x", 1.0)) * 100))
                sy = int(round(float(getattr(tex_obj, "deformation_scale_y", 1.0)) * 100))
                tooltip += f"\nVznikla z: {src}\nŠířka: {sx}%\nVýška: {sy}%"

            btn.setToolTip(tooltip)

            if self._selected_texture_name == name:
                btn.setStyleSheet("border: 2px solid #4aa3ff;")
            else:
                btn.setStyleSheet("border: 1px solid #555;")

            btn.clicked.connect(lambda checked=False, n=name: self._select_texture(n))
            self._texture_buttons[name] = btn

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
        """Otvorí dialóg na pridanie novej textúry"""
        if self._controller is None:
            return

        if hasattr(self._controller, "add_texture_from_file_via_dialog"):
            self._controller.add_texture_from_file_via_dialog(parent=self)

    def _select_texture(self, name: str) -> None:
        if self._controller is None or self._controller.project is None:
            return
        self._selected_texture_name = name
        self._clear_deformation_status()

        if hasattr(self._controller, "set_texture"):
            self._controller.set_texture(name)
        else:
            tex = self._controller.project.textures.get(name)
            self._controller.texture_settings.texture = tex

        self._rebuild_textures_grid(self._controller.project)
        self._update_deformation_controls_state()
        self._update_preview(self._controller.project)
        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def _on_scale_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.texture_settings.scale = max(0.25, min(4.0, value / 100.0))
        self._update_preview(self._controller.project)
        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def _on_strength_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.texture_settings.strength = max(0.0, min(1.0, value / 100.0))
        self._update_preview(self._controller.project)
        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def _on_rotation_changed(self, value: int) -> None:
        if self._controller is None:
            return
        self._controller.texture_settings.rotation_deg = float(value)
        self._update_preview(self._controller.project)
        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()
    
    def _update_deformation_value_labels(self) -> None:
        """Aktualizuje percentuálne hodnoty deformácie pri slideroch"""
        self.deform_x_value_label.setText(f"{int(self.deform_x_slider.value())} %")
        self.deform_y_value_label.setText(f"{int(self.deform_y_slider.value())} %")
        
    def _update_deformation_controls_state(self) -> None:
        if self._controller is None:
            return

        ts = getattr(self._controller, "texture_settings", None)
        tex = getattr(ts, "texture", None)

        can_deform = bool(tex is not None and getattr(tex, "can_deform", True))

        self.deform_x_slider.setEnabled(can_deform)
        self.deform_y_slider.setEnabled(can_deform)
        self.btn_reset_deformation.setEnabled(can_deform)

        has_non_default = False
        if ts is not None:
            has_non_default = abs(float(getattr(ts, "deformation_scale_x", 1.0)) - 1.0) > 1e-6 or abs(float(getattr(ts, "deformation_scale_y", 1.0)) - 1.0) > 1e-6

        self.btn_add_deformed_texture.setEnabled(can_deform and has_non_default)

        if tex is not None and not can_deform:
            self.deformation_status_label.setText("Tato textura je již uložená deformovaná varianta a nedá se dále deformovat")
        elif not self.deformation_status_label.text().startswith("Taková deformovaná textura"):
            self.deformation_status_label.setText("")

    def _set_deformation_status(self, text: str, timeout_ms: int = 2200) -> None:
        self.deformation_status_label.setText(text)

        if timeout_ms > 0:
            self._deform_status_timer.start(timeout_ms)

    def _clear_deformation_status(self) -> None:
        """Vymaže stavovú správu pri deformácii textúry"""
        self.deformation_status_label.setText("")

        if self._controller is not None:
            self._update_deformation_controls_state()

    def _flash_texture_button(self, texture_name: str) -> None:
        btn = self._texture_buttons.get(texture_name)
        if btn is None:
            return

        btn.setStyleSheet("border: 2px solid red;")

        def _restore() -> None:
            if self._selected_texture_name == texture_name:
                btn.setStyleSheet("border: 2px solid #4aa3ff;")
            else:
                btn.setStyleSheet("border: 1px solid #555;")

        QTimer.singleShot(700, _restore)

    def _on_deform_x_changed(self, value: int) -> None:
        if self._controller is None:
            return

        if hasattr(self._controller, "set_texture_deformation"):
            self._controller.set_texture_deformation(scale_x=value / 100.0)

        self._update_deformation_controls_state()
        self._update_deformation_value_labels()
        self._update_preview(self._controller.project)

        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def _on_deform_y_changed(self, value: int) -> None:
        if self._controller is None:
            return

        if hasattr(self._controller, "set_texture_deformation"):
            self._controller.set_texture_deformation(scale_y=value / 100.0)

        self._update_deformation_controls_state()
        self._update_deformation_value_labels()
        self._update_preview(self._controller.project)

        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def _on_reset_deformation_clicked(self) -> None:
        if self._controller is None:
            return

        if hasattr(self._controller, "reset_texture_deformation"):
            self._controller.reset_texture_deformation()

        self.deform_x_slider.blockSignals(True)
        self.deform_y_slider.blockSignals(True)

        self.deform_x_slider.setValue(100)
        self.deform_y_slider.setValue(100)

        self.deform_x_slider.blockSignals(False)
        self.deform_y_slider.blockSignals(False)

        self._update_deformation_value_labels()

        self._update_deformation_controls_state()
        self._update_preview(self._controller.project)

        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def _on_add_deformed_texture_clicked(self) -> None:
        if self._controller is None:
            return

        if not hasattr(self._controller, "add_current_deformed_texture_to_project"):
            return

        success, new_name, duplicate_name = self._controller.add_current_deformed_texture_to_project()

        if duplicate_name is not None:
            self._set_deformation_status("Taková deformovaná textura už existuje")
            self._flash_texture_button(duplicate_name)
            return

        if not success or new_name is None:
            return

        self._selected_texture_name = new_name
        self.refresh_from_project(self._controller.project)
        self._set_deformation_status("Deformovaná textura byla přidána mezi textury")

    def _update_preview(self, project) -> None:
        """Aktualizuje náhľad aktuálnej textúry"""
        if self._controller is None:
            self.preview.clear()
            return

        ts = self._controller.texture_settings
        if ts.texture is None:
            self.preview.setText("Žádná textura")
            return

        r, g, b , _ = project.get_current_color_rgba()
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

        if hasattr(self._controller, "update_current_tool_cursor"):
            self._controller.update_current_tool_cursor()

    def set_brush_size_value(self, size: int) -> None:
        self.brush_slider.blockSignals(True)
        self.brush_slider.setValue(int(size))
        self.brush_slider.blockSignals(False)
