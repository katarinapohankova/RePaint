from __future__ import annotations

from typing import Optional, Callable
from pathlib import Path

import numpy as np
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog
from PySide6.QtCore import Qt, QTimer

from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.config.settings import AppSettings
from rp_restore.core.selection import SelectionSet
from rp_restore.core.algorithm_runner import AlgorithmType, AlgorithmRequest, AlgorithmRunner, TextureAlgorithmParams, RealisticFillMode, RemoteRestorationAccessError
from rp_restore.core.history import UndoAction
from rp_restore.core.texture_brush import TextureSettings, Texture, generate_brush_stamp, clear_texture_cache, deform_texture_image
from rp_restore.core import mask_alignment
from rp_restore.core.auto_fill import auto_fill_regions, AutoFillRegion
from rp_restore.core.regions import RegionMap, build_region_map
from rp_restore.core.remote_restoration_config import RemoteRestorationConfigError, apply_remote_restoration_environment, has_remote_restoration_config
from rp_restore.gui.canvas.image_canvas_widget import ImageCanvasWidget
from rp_restore.gui.panels.layers_panel import LayersPanel
from rp_restore.gui.tools.base_tool import BaseTool
from rp_restore.gui.tools.brush_tool import BrushTool
from rp_restore.gui.tools.eraser_tool import EraserTool
from rp_restore.gui.tools.fill_tool import FillTool
from rp_restore.gui.tools.selection_tool import SelectionTool
from rp_restore.gui.tools.edge_tool import EdgeTool
from rp_restore.gui.tools.pipette_tool import PipetteTool
from rp_restore.gui.tools.lasso_tool import LassoTool
from rp_restore.gui.tools.edge_blend_tool import EdgeBlendTool
from rp_restore.gui.tools.blend_tool import BlendTool
from rp_restore.gui.mask_alignment_dialog import MaskAlignmentDialog
from rp_restore.io import image_io
from rp_restore.io.image_io import load_working_image
from rp_restore.io.project_storage import ProjectLoader, ProjectSerializer

class ProjectController:
    """
    Prepája Project s GUI časťou aplikácie
    spravuje aktuálny projekt, aktívnu vrstvu, nástroje, výbery, panely a spúšťanie algoritmov
    """

    def __init__(self, app_settings: AppSettings) -> None:
        self.app_settings = app_settings
        self.project: Optional[Project] = None

        self.canvas: Optional[ImageCanvasWidget] = None
        self._brush_size: int = 10
        self._brush_hardness: float = 1.0
        self._brush_opacity: float = 1.0
        self._brush_flow: float = 1.0
        self._brush_allow_overlap: bool = True

        self._blend_strength: float = 0.5
        self._blend_source_mode: str = "active_paint"

        self._cursor_cache: dict[tuple, QCursor] = {}

        self.selection_region_map_cache: RegionMap | None = None
        self.selection_region_map_cache_layer_id: str | None = None

        self.materials_panel = None
        self.palette_panel = None
        
        self.edge_settings_panel: Optional[object] = None
        self._edge_brush_size: int = 1  #hrúbka EDGE nástroja je zatiaľ pevná
        self._edge_color_rgba: np.ndarray = np.array([0, 0, 0, 255], dtype=np.uint8)
        self._edge_blend_buffer: int = 5
        self.active_layer_id: Optional[str] = None
        self.layers_panel: Optional[LayersPanel] = None
        self.current_tool: Optional[BaseTool] = None
        self.active_selection: SelectionSet | None = None
        self.auto_fill_preview_active: bool = False
        self.auto_fill_threshold: int = 200
        self.auto_fill_region_map: RegionMap | None = None
        self.auto_fill_candidate_region_ids: set[int] = set()
        self.auto_fill_excluded_region_ids: set[int] = set()
        self.auto_fill_preview_layer_id: str | None = None
        #vizualizácia damage masky v canvase
        self.show_damage_overlay: bool = True
        self.damage_overlay_opacity: float = 0.35
        self.algorithm_panel = None

        self.current_project_path: Optional[str] = None

        self._undo_redo_changed_callback: Optional[Callable[[], None]] = None

        self._message_callback: Optional[Callable[[str], None]] = None
        
        self._algorithm_progress_callback = None
        self._algorithm_progress_clear_callback = None
        self._remote_settings_request_callback: Optional[Callable[[Optional[str]], bool]] = None

        self._brush_size_preview_callback: Optional[Callable[[int], None]] = None

        #debounce pre opacity refresh (aby compositing nebežal pri každom ticku slidera)
        self._opacity_debounce_timer: QTimer = QTimer()
        self._opacity_debounce_timer.setSingleShot(True)
        self._opacity_debounce_timer.timeout.connect(self._apply_opacity_debounced_refresh)

        self.texture_settings = TextureSettings(texture=None, scale=1.0, color=(255, 255, 255), strength=1.0, rotation_deg=0.0, deformation_scale_x=1.0, deformation_scale_y=1.0, texture_style="transparent")
        self.texture_mode_enabled: bool = False

        self.paint_mode: str = "brush"

        self._pending_window_bbox: tuple[int,int,int,int] | None = None
        self._pending_window_bbox_listener = None  

        self._layer_preview_overlay_visible: bool = False
        self._current_layer_preview_qimage: QImage | None = None
        self._current_layer_preview_title: str = ""

    def set_canvas(self, canvas: ImageCanvasWidget) -> None:
        self.canvas = canvas

    def set_project(self, project: Project) -> None:
        """Nastaví aktuálny projekt a obnoví súvisiace panely"""
        self.project = project
        self.project.undo_manager.on_change = self._on_undo_manager_changed
        self.invalidate_selection_region_map_cache()
        self.clear_auto_fill_preview()
        self.hide_layer_preview_overlay()

        self.texture_settings.texture_style = getattr(project, "texture_style", "transparent")

        self.reset_tools_to_default()
        self._brush_hardness = float(getattr(project, "brush_hardness", 1.0))
        self._brush_opacity = float(getattr(project, "brush_opacity", 1.0))
        self._brush_flow = float(getattr(project, "brush_flow", 1.0))
        self._brush_allow_overlap = bool(getattr(project, "brush_allow_overlap", True))

        #default aktívna vrstva bude preferovaná BACKGROUND, inak prvá vrstva v zozname
        self.active_layer_id = None
        if self.project.layers:
            bg = self.project.get_background_layer()
            if bg is not None:
                self.active_layer_id = bg.meta.id
            else:
                self.active_layer_id = self.project.layers[0].meta.id
        self.refresh_canvas()

        if self.canvas is not None:
            self.canvas.fit_to_window()

        self.refresh_layers_panel()
        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(project)
        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(project)
        if self.edge_settings_panel is not None and hasattr(self.edge_settings_panel, "refresh_from_controller"):
            self.edge_settings_panel.refresh_from_controller(self)
    
    def set_texture(self, texture_name: str | None) -> None:
        if self.project is None:
            self.texture_settings.texture = None
            self.texture_settings.deformation_scale_x = 1.0
            self.texture_settings.deformation_scale_y = 1.0
            clear_texture_cache(self.texture_settings)
            return
        if texture_name is None:
            self.texture_settings.texture = None
            self.texture_settings.deformation_scale_x = 1.0
            self.texture_settings.deformation_scale_y = 1.0
            clear_texture_cache(self.texture_settings)
            return
        tex = self.project.textures.get(texture_name)
        self.texture_settings.texture = tex

        if tex is not None and not getattr(tex, "can_deform", True):
            #uložená deformovaná textúra sa už ďalej nedeformuje
            #v paneli sa zobrazia hodnoty, s ktorými vznikla
            self.texture_settings.deformation_scale_x = float(getattr(tex, "deformation_scale_x", 1.0))
            self.texture_settings.deformation_scale_y = float(getattr(tex, "deformation_scale_y", 1.0))
        else:
            #pri pôvodnej textúre začína deformácia od 100 % / 100 %
            self.texture_settings.deformation_scale_x = 1.0
            self.texture_settings.deformation_scale_y = 1.0

        clear_texture_cache(self.texture_settings)

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)
        
        self.update_current_tool_cursor()

    def set_texture_deformation(self, scale_x: float | None = None, scale_y: float | None = None) -> None:
        """
        Nastaví dočasnú deformáciu aktuálne vybranej textúry
        (iba pri pôvodných textúrach, nie pri už deformovaných)
        """
        tex = getattr(self.texture_settings, "texture", None)
        if tex is None:
            return

        if not getattr(tex, "can_deform", True):
            return

        if scale_x is not None:
            self.texture_settings.deformation_scale_x = max(0.25, min(4.0, float(scale_x)))

        if scale_y is not None:
            self.texture_settings.deformation_scale_y = max(0.25, min(4.0, float(scale_y)))

        clear_texture_cache(self.texture_settings)

    def reset_texture_deformation(self) -> None:
        """
        Vráti dočasnú deformáciu aktuálnej textúry na 100 % / 100 %
        """
        self.texture_settings.deformation_scale_x = 1.0
        self.texture_settings.deformation_scale_y = 1.0
        clear_texture_cache(self.texture_settings)

    def _find_duplicate_deformed_texture(self, source_texture_name: str, deformation_scale_x: float, deformation_scale_y: float) -> Texture | None:
        """
        Nájde už existujúcu deformovanú textúru vytvorenú z rovnakej pôvodnej textúry s rovnakými hodnotami deformácie
        """
        if self.project is None:
            return None

        sx = round(float(deformation_scale_x), 4)
        sy = round(float(deformation_scale_y), 4)

        for tex in self.project.textures.values():
            if not getattr(tex, "is_generated", False):
                continue

            if getattr(tex, "source_texture_name", None) != source_texture_name:
                continue

            tex_sx = round(float(getattr(tex, "deformation_scale_x", 1.0)), 4)
            tex_sy = round(float(getattr(tex, "deformation_scale_y", 1.0)), 4)

            if tex_sx == sx and tex_sy == sy:
                return tex

        return None

    def _make_deformed_texture_name(self, source_name: str, scale_x: float, scale_y: float) -> str:
        sx = int(round(float(scale_x) * 100))
        sy = int(round(float(scale_y) * 100))
        base_name = f"{source_name}_x{sx}_y{sy}"
        return self._make_unique_texture_name(base_name)

    def _insert_texture_after(self, source_name: str, new_texture: Texture) -> None:
        """
        Vloží novú textúru hneď za textúru, z ktorej vznikla
        """
        if self.project is None:
            return

        old_items = list(self.project.textures.items())
        new_items: list[tuple[str, Texture]] = []
        inserted = False

        for name, tex in old_items:
            new_items.append((name, tex))

            if name == source_name:
                new_items.append((new_texture.name, new_texture))
                inserted = True

        if not inserted:
            new_items.append((new_texture.name, new_texture))

        self.project.textures = dict(new_items)

    def add_current_deformed_texture_to_project(self) -> tuple[bool, str | None, str | None]:
        """
        Uloží aktuálnu dočasne deformovanú textúru ako novú textúru projektu
        -vracia:
        (True, new_name, None)  -textúra bola vytvorená
        (False, None, duplicate)    -taká textúra už existuje
        (False, None, None) -textúru nemožno vytvoriť
        """
        if self.project is None:
            return False, None, None

        source_tex = getattr(self.texture_settings, "texture", None)
        if source_tex is None:
            return False, None, None

        if not getattr(source_tex, "can_deform", True):
            return False, None, None

        sx = float(getattr(self.texture_settings, "deformation_scale_x", 1.0))
        sy = float(getattr(self.texture_settings, "deformation_scale_y", 1.0))

        if abs(sx - 1.0) < 1e-6 and abs(sy - 1.0) < 1e-6:
            return False, None, None

        duplicate = self._find_duplicate_deformed_texture(source_tex.name, sx, sy)
        if duplicate is not None:
            return False, None, duplicate.name

        new_image = deform_texture_image(source_tex.image, deformation_scale_x=sx, deformation_scale_y=sy)

        new_name = self._make_deformed_texture_name(source_tex.name, sx, sy)

        new_tex = Texture(
            name=new_name,
            image=new_image,
            is_generated=True,
            source_texture_name=source_tex.name,
            deformation_scale_x=sx,
            deformation_scale_y=sy,
            can_deform=False,
            generated_by_algorithm=bool(getattr(source_tex, "generated_by_algorithm", False)),
            color_mode=str(getattr(source_tex, "color_mode", "tint")),
            generated_colors=getattr(source_tex, "generated_colors", None),
            generated_color_strengths=getattr(source_tex, "generated_color_strengths", None),
            algorithm_params=getattr(source_tex, "algorithm_params", None),
        )

        self._insert_texture_after(source_tex.name, new_tex)

        #nová textúra sa hneď vyberie
        self.texture_settings.texture = new_tex
        self.texture_settings.deformation_scale_x = sx
        self.texture_settings.deformation_scale_y = sy
        clear_texture_cache(self.texture_settings)

        self.project.mark_dirty()

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

        self.update_current_tool_cursor()

        return True, new_name, None

    def set_texture_style(self, style: str) -> None:
        """
        Nastaví spôsob generovania textúry:
            - transparent - pôvodná priesvitná textúra
            - color - farebná textúra s odtieňmi
        """
        if style not in ("transparent", "color"):
            style = "transparent"

        self.texture_settings.texture_style = style

        if self.project is not None:
            self.project.texture_style = style
            self.project.mark_dirty()

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    def _load_default_textures_into_project(self, project: Project, max_tex_size: int = 512) -> None:
        """
        Načíta default textúry z rp_restore/resources/textures do project.textures
        """
        rp_restore_dir = Path(__file__).resolve().parents[1]
        tex_dir = rp_restore_dir / "resources" / "textures"
        if not tex_dir.is_dir():
            return

        project.textures = {}

        exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        for p in sorted(tex_dir.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue

            try:
                #načítame ako working (zmenšenie na max_tex_size)
                arr, _ = load_working_image(str(p), max_size=max_tex_size)
                #chceme RGBA alebo aspoň RGB
                if arr.ndim == 3 and arr.shape[2] == 3:
                    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
                    rgba[..., :3] = arr
                    rgba[..., 3] = 255
                    arr = rgba
                elif arr.ndim == 2:
                    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
                    rgba[..., 0] = arr
                    rgba[..., 1] = arr
                    rgba[..., 2] = arr
                    rgba[..., 3] = 255
                    arr = rgba

                name = p.stem
                project.textures[name] = Texture(name=name, image=arr)
            except Exception:
                #textúra sa nepodarila načítať, preskočíme
                continue
    
    def add_texture_from_file_via_dialog(self, parent=None) -> None:
        """
        Otvorí dialóg a pridá vybraný obrázok ako textúru iba do aktuálneho projektu
        """
        if self.project is None:
            return

        path, _ = QFileDialog.getOpenFileName(
            parent,
            "Přidat texturu",
            "",
            "Obrázky (*.png *.jpg *.jpeg *.tif *.tiff);;Všechny soubory (*.*)",
        )
        if not path:
            return

        try:
            self.add_texture_from_file(path)
        except Exception as e:
            self.show_tool_message(f"Texturu se nepodařilo přidat: {e}")

    def add_texture_from_file(self, path: str, max_tex_size: int = 512) -> None:
        """
        Pridá textúru do aktuálneho projektu
        (nekopíruje ju do default resources, iba do project.textures)
        """
        if self.project is None:
            return

        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(str(p))

        arr, _ = load_working_image(str(p), max_size=max_tex_size)

        #normalizácia na RGBA
        if arr.ndim == 2:
            rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
            rgba[..., 0] = arr
            rgba[..., 1] = arr
            rgba[..., 2] = arr
            rgba[..., 3] = 255
            arr = rgba
        elif arr.ndim == 3 and arr.shape[2] == 3:
            rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
            rgba[..., :3] = arr
            rgba[..., 3] = 255
            arr = rgba
        elif arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr.astype(np.uint8)
        else:
            raise ValueError("Unsupported texture image format")

        base_name = p.stem or "texture"
        name = self._make_unique_texture_name(base_name)

        tex = Texture(name=name, image=arr)
        self.project.textures[name] = tex
        self.project.mark_dirty()
        self.set_texture(name)

    def generate_texture_and_add_to_project(self, texture_params: TextureAlgorithmParams, replace_texture_name: str | None = None) -> str | None:
        """
        Vygeneruje samostatnú textúru pomocou externého algoritmu a pridá ju medzi materiály aktuálneho projektu

        vráti názov pridanej textúry alebo None pri chybe
        """
        project = self.project

        if project is None:
            self.show_tool_message("Nejprve otevřete nebo vytvořte projekt")
            return None

        texture_params.generate_square = True

        self._show_algorithm_progress("Generuji samostatnou texturu...", None, None)

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()

        try:
            texture_image = (AlgorithmRunner.generate_texture_material(texture_params))
        except Exception as error:
            self.show_tool_message(f"Texturu se nepodařilo vygenerovat: {error}")
            return None
        finally:
            QApplication.restoreOverrideCursor()
            self._clear_algorithm_progress()

        texture_array = np.asarray(texture_image)

        if texture_array.ndim != 3 or texture_array.shape[2] not in (3, 4):
            self.show_tool_message("Algoritmus vrátil neplatný formát textury")
            return None

        expected_size = (int(texture_params.height),int(texture_params.width))

        if texture_array.shape[:2] != expected_size:
            self.show_tool_message("Algoritmus vrátil texturu s nesprávnými rozměry")
            return None

        if texture_array.dtype != np.uint8:
            texture_array = np.clip(texture_array, 0, 255).astype(np.uint8)

        if texture_array.shape[2] == 3:
            rgba = np.zeros((texture_array.shape[0], texture_array.shape[1], 4), dtype=np.uint8)
            rgba[..., :3] = texture_array
            rgba[..., 3] = 255
            texture_array = rgba
        else:
            texture_array = texture_array.copy()

        seed_suffix = ""

        if texture_params.seed is not None:
            seed_suffix = f"_seed{texture_params.seed}"

        if replace_texture_name is None:
            base_name = (
                f"generated_{texture_params.texture_name}_"
                f"{texture_params.width}x{texture_params.height}"
                f"{seed_suffix}"
            )
            texture_name = self._make_unique_texture_name(base_name)
        else:
            texture_name = replace_texture_name

        generated_colors = texture_params.colors or []
        generated_strengths = texture_params.color_strengths or []

        texture = Texture(
            name=texture_name,
            image=texture_array,
            generated_by_algorithm=True,
            color_mode="preserve",
            generated_colors=[(int(color[0]), int(color[1]), int(color[2])) for color in generated_colors],
            generated_color_strengths=[float(value) for value in generated_strengths],
            algorithm_params=self._texture_params_to_metadata_dict(texture_params),
        )

        project.textures[texture_name] = texture
        project.mark_dirty()

        #textúra sa po pridaní alebo nahradení automaticky označí ako aktuálne vybraný materiál
        self.set_texture(texture_name)

        if replace_texture_name is None:
            self.show_tool_message(f"Textura „{texture_name}“ byla přidána do materiálů")
        else:
            self.show_tool_message(f'Barvy textury „{texture_name}“ byly aktualizovány')

        return texture_name
    
    @staticmethod
    def _texture_params_to_metadata_dict(texture_params: TextureAlgorithmParams) -> dict[str, object]:
        colors = texture_params.colors or []
        color_strengths = texture_params.color_strengths or []

        return {
            "texture_name": str(texture_params.texture_name),
            "colors": [[int(c[0]), int(c[1]), int(c[2])] for c in colors],
            "color_strengths": [float(value) for value in color_strengths],
            "scale_x": float(texture_params.scale_x),
            "scale_y": float(texture_params.scale_y),
            "density_x": float(texture_params.density_x),
            "density_y": float(texture_params.density_y),
            "rotation": float(texture_params.rotation),
            "global_scale": float(texture_params.global_scale),
            "white_background": bool(texture_params.white_background),
            "background_brightness": float(texture_params.background_brightness),
            "generate_square": bool(texture_params.generate_square),
            "width": int(texture_params.width),
            "height": int(texture_params.height),
            "seed": None if texture_params.seed is None else int(texture_params.seed),
        }

    @staticmethod
    def _texture_params_from_metadata_dict(data: dict[str, object]) -> TextureAlgorithmParams | None:
        try:
            colors_raw = data.get("colors", [])
            colors: list[tuple[int, int, int]] = []

            if isinstance(colors_raw, list):
                for item in colors_raw:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        colors.append((int(item[0]), int(item[1]), int(item[2])))

            strengths_raw = data.get("color_strengths", [])
            color_strengths: list[float] = []

            if isinstance(strengths_raw, list):
                color_strengths = [float(value) for value in strengths_raw]

            return TextureAlgorithmParams(
                texture_name=str(data.get("texture_name", "texture_J")),
                colors=colors,
                color_strengths=color_strengths,
                scale_x=float(data.get("scale_x", 1.0)),
                scale_y=float(data.get("scale_y", 1.0)),
                density_x=float(data.get("density_x", 0.0)),
                density_y=float(data.get("density_y", 0.0)),
                rotation=float(data.get("rotation", 0.0)),
                global_scale=float(data.get("global_scale", 1.0)),
                white_background=bool(data.get("white_background", True)),
                background_brightness=float(data.get("background_brightness", 1.0)),
                generate_square=bool(data.get("generate_square", True)),
                width=int(data.get("width", 1024)),
                height=int(data.get("height", 1024)),
                seed=None if data.get("seed") is None else int(data.get("seed")),
            )
        except Exception:
            return None
        
    def _make_unique_texture_name(self, base_name: str) -> str:
        """
        Vytvorí jedinečný názov textúry v aktuálnom projekte
        """
        if self.project is None:
            return base_name

        existing = set(getattr(self.project, "textures", {}).keys())

        safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in base_name).strip("_")
        if not safe:
            safe = "texture"

        if safe not in existing:
            return safe

        i = 2
        while f"{safe}_{i}" in existing:
            i += 1
        return f"{safe}_{i}"
    
    def edit_generated_texture_colors(self, texture_name: str, parent=None) -> None:
        """
        Otvorí dialóg s pôvodnými parametrami generated textúry a po potvrdení ju pregeneruje s novými farbami
        """
        if self.project is None:
            return

        texture = self.project.textures.get(texture_name)
        if texture is None:
            return

        if not bool(getattr(texture, "generated_by_algorithm", False)):
            self.show_tool_message("Barvy lze upravovat pouze u textur vygenerovaných algoritmem")
            return

        metadata = getattr(texture, "algorithm_params", None)
        if not isinstance(metadata, dict):
            self.show_tool_message("U této textury nejsou uložené parametry pro opětovné vygenerování")
            return

        initial_params = self._texture_params_from_metadata_dict(metadata)
        if initial_params is None:
            self.show_tool_message("Nepodařilo se načíst původní parametry textury")
            return

        from rp_restore.gui.texture_fill_dialog import TextureFillDialog

        dialog = TextureFillDialog(controller=self, parent=parent, initial_params=initial_params, force_generate_texture_mode=True, color_edit_only=True)

        if dialog.exec() != QDialog.Accepted:
            return

        result = dialog.get_result()
        if result is None:
            self.show_tool_message("Parametry textury nejsou platné")
            return

        new_params = TextureAlgorithmParams(
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
            generate_square=True,
            width=result.width,
            height=result.height,
            seed=result.seed,
        )

        self.generate_texture_and_add_to_project(new_params, replace_texture_name=texture_name)

    def set_materials_panel(self, panel: object) -> None:
        self.materials_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)
    
    def set_edge_settings_panel(self, panel: object) -> None:
        """
        Prepojí controller s EdgeSettingsPanelom
        """
        self.edge_settings_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)

    def set_palette_panel(self, panel: object) -> None:
        self.palette_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)

    def get_current_color_rgba(self) -> np.ndarray:
        """
        vráti aktuálnu farbu ako numpy RGBA 
        """
        if self.project is None:
            return np.array([0, 0, 0, 255], dtype=np.uint8)
        r, g, b, a = self.project.get_current_color_rgba()
        return np.array([r, g, b, a], dtype=np.uint8)

    def set_current_color_rgba(self, color: tuple[int, int, int, int]) -> None:
        if self.project is None:
            return
        self.project.set_current_color_rgba(color)
        if hasattr(self, "texture_settings"):
            r, g, b, a = self.project.get_current_color_rgba()
            self.texture_settings.color = (r, g, b)

        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(self.project)
        #refresh panelov pracujúcich s farbou
        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

        self.update_current_tool_cursor()
    
    def add_color_to_palette_rgba(self, color: tuple[int, int, int, int], avoid_duplicates: bool = True) -> None:
        """
        Pridá ľubovoľnú farbu do palety
        """
        if self.project is None:
            return

        if avoid_duplicates:
            if color in self.project.get_palette_colors():
                return

        self.project.add_palette_color(color)
        self.project.mark_dirty()

        #refresh palety
        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(self.project)

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    def remove_color_from_palette(self, index: int) -> None:
        """
        Odstráni farbu z palety podľa indexu
        """
        if self.project is None:
            return

        palette = self.project.get_palette_colors()
        if index < 0 or index >= len(palette):
            return

        #priamo upravíme zoznam
        self.project.palette_colors.pop(index)
        self.project.mark_dirty()

        if self.palette_panel is not None and hasattr(self.palette_panel, "refresh_from_project"):
            self.palette_panel.refresh_from_project(self.project)

        if self.materials_panel is not None and hasattr(self.materials_panel, "refresh_from_project"):
            self.materials_panel.refresh_from_project(self.project)

    #Edge farba a nastavenia
    def get_edge_color_rgba(self) -> np.ndarray:
        return self._edge_color_rgba.copy()

    def set_edge_color_rgba(self, color: tuple[int, int, int, int]) -> None:
        arr = np.array(color, dtype=np.int32)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        self._edge_color_rgba = arr
        if self.edge_settings_panel is not None and hasattr(self.edge_settings_panel, "refresh_from_controller"):
            self.edge_settings_panel.refresh_from_controller(self)
        
        self.update_current_tool_cursor()

    def get_brush_size(self) -> int:
        return int(self._brush_size)

    def set_brush_size(self, size: int) -> None:
        self._brush_size = max(1, int(size))
    
        if self.materials_panel is not None and hasattr(self.materials_panel, "set_brush_size_value"):
            self.materials_panel.set_brush_size_value(self._brush_size)

        if self._brush_size_preview_callback is not None:
            self._brush_size_preview_callback(self._brush_size)

        self.update_current_tool_cursor()

    def get_edge_blend_buffer(self) -> int:
        return int(self._edge_blend_buffer)

    def set_edge_blend_buffer(self, value: int) -> None:
        self._edge_blend_buffer = max(1, min(100, int(value)))

        if self.edge_settings_panel is not None and hasattr(self.edge_settings_panel, "refresh_from_controller"):
            self.edge_settings_panel.refresh_from_controller(self)
        self.update_current_tool_cursor()

    def adjust_brush_size(self, delta: int) -> None:
        """
        Zväčší alebo zmenší veľkosť štetca o delta
        """
        self.set_brush_size(self._brush_size + int(delta))

    def get_brush_allow_overlap(self) -> bool:
        return bool(self._brush_allow_overlap)

    def set_brush_allow_overlap(self, allow: bool) -> None:
        self._brush_allow_overlap = bool(allow)

        if self.project is not None:
            self.project.brush_allow_overlap = self._brush_allow_overlap
            self.project.mark_dirty()
            
    def get_brush_hardness(self) -> float:
        return float(self._brush_hardness)

    def set_brush_hardness(self, value: float) -> None:
        self._brush_hardness = max(0.0, min(1.0, float(value)))
        if self.project is not None:
            self.project.brush_hardness = self._brush_hardness
            self.project.mark_dirty()
        
        self.update_current_tool_cursor()

    def get_brush_opacity(self) -> float:
        return float(self._brush_opacity)

    def set_brush_opacity(self, value: float) -> None:
        self._brush_opacity = max(0.0, min(1.0, float(value)))
        if self.project is not None:
            self.project.brush_opacity = self._brush_opacity
            self.project.mark_dirty()
        
        self.update_current_tool_cursor()

    def get_brush_flow(self) -> float:
        return float(self._brush_flow)

    def set_brush_flow(self, value: float) -> None:
        self._brush_flow = max(0.0, min(1.0, float(value)))
        if self.project is not None:
            self.project.brush_flow = self._brush_flow
            self.project.mark_dirty()
        
        self.update_current_tool_cursor()

    def get_blend_strength(self) -> float:
        return float(self._blend_strength)

    def set_blend_strength(self, value: float) -> None:
        self._blend_strength = max(0.0, min(1.0, float(value)))

        if self.materials_panel is not None and hasattr(self.materials_panel, "set_blend_strength_value"):
            self.materials_panel.set_blend_strength_value(int(round(self._blend_strength * 100)))
        self.update_current_tool_cursor()

    def get_blend_source_mode(self) -> str:
        return getattr(self, "_blend_source_mode", "active_paint")


    def set_blend_source_mode(self, mode: str) -> None:
        if mode not in ("active_paint", "background_and_active_paint"):
            mode = "active_paint"

        self._blend_source_mode = mode

        if self.materials_panel is not None and hasattr(self.materials_panel, "set_blend_source_mode_value"):
            self.materials_panel.set_blend_source_mode_value(mode)

    def set_layers_panel(self, panel: LayersPanel) -> None:
        """Prepojí controller s panelom vrstiev"""
        self.layers_panel = panel
        panel.set_controller(self)

        if hasattr(panel, "preview_clicked"):
            panel.preview_clicked.connect(self.toggle_layer_preview_overlay)

    def set_algorithm_progress_callback(self, callback) -> None:
        self._algorithm_progress_callback = callback

    def set_algorithm_progress_clear_callback(self, callback) -> None:
        self._algorithm_progress_clear_callback = callback

    def _show_algorithm_progress(self, message: str, current: int | None = None, total: int | None = None) -> None:
        if self._algorithm_progress_callback is not None:
            self._algorithm_progress_callback(message, current, total)

    def _clear_algorithm_progress(self) -> None:
        if self._algorithm_progress_clear_callback is not None:
            self._algorithm_progress_clear_callback()

    def set_remote_settings_request_callback(self, callback: Callable[[Optional[str]], bool]) -> None:
        """
        Nastaví callback, ktorý vie otvoriť dialóg nastavení remote služby.

        Controller sám nevytvára hlavné okno dialógu, iba si cez callback vypýta,
        aby GUI otvorilo nastavenia, keď chýbajú údaje pre realistic fill.
        """
        self._remote_settings_request_callback = callback

    def _ensure_remote_restoration_config(self) -> bool:
        """
        Skontroluje, či sú dostupné údaje pre remote realistické doplnenie.

        Ak chýbajú, požiada GUI o otvorenie nastavení.
        """
        if has_remote_restoration_config():
            return True

        if self._remote_settings_request_callback is None:
            self.show_tool_message("Chybí nastavení remote služby pro realistické doplnění")
            return False

        return bool(self._remote_settings_request_callback("Pro použití realistického doplnění je potřeba nastavit endpoint URL a API key remote služby."))
    
    def toggle_layer_preview_overlay(self) -> None:
        """
        Zapne alebo vypne veľký náhľad aktívnej vrstvy na canvase
        """
        if self._layer_preview_overlay_visible:
            self.hide_layer_preview_overlay()
        else:
            self.show_layer_preview_overlay()


    def show_layer_preview_overlay(self) -> None:
        """
        Zobrazí veľký náhľad aktívnej vrstvy na canvase
        """
        if self.canvas is None:
            return

        if self._current_layer_preview_qimage is None:
            self.update_layer_preview()

        if self._current_layer_preview_qimage is None:
            return

        self._layer_preview_overlay_visible = True

        if hasattr(self.canvas, "set_layer_preview_overlay"):
            self.canvas.set_layer_preview_overlay(self._current_layer_preview_qimage, self._current_layer_preview_title)


    def hide_layer_preview_overlay(self) -> None:
        """
        Skryje veľký náhľad aktívnej vrstvy z canvasu
        """
        self._layer_preview_overlay_visible = False

        if self.canvas is not None and hasattr(self.canvas, "clear_layer_preview_overlay"):
            self.canvas.clear_layer_preview_overlay()
            
    def set_current_tool(self, tool_type: str) -> None:
        """
        Nastaví aktuálny nástroj podľa typu
        """
        if self.canvas is None:
            return
        self.clear_auto_fill_preview()
        self._auto_switch_active_layer_for_tool(tool_type)
        if tool_type == "brush":
            self.current_tool = BrushTool(self, self.canvas)
        elif tool_type == "eraser":
            self.current_tool = EraserTool(self, self.canvas)
        elif tool_type == "fill":
            self.current_tool = FillTool(self, self.canvas)
        elif tool_type == "selection":
            self.current_tool = SelectionTool(self, self.canvas)
        elif tool_type == "edge":
            self.current_tool = EdgeTool(self, self.canvas)
        elif tool_type == "pipette":
            self.current_tool = PipetteTool(self, self.canvas)
        elif tool_type == "lasso":
            self.current_tool = LassoTool(self, self.canvas)
        elif tool_type == "edge_blend":
            self.current_tool = EdgeBlendTool(self, self.canvas)
        elif tool_type == "blend":
            self.current_tool = BlendTool(self, self.canvas)
        else:
            self.current_tool = None

        self.update_current_tool_cursor()

    def reset_tools_to_default(self) -> None:
        """
        Reset nástrojov pri otvorení alebo zmene projektu
        zruší selection a nastaví predvolený nástroj na brush
        """
        self.active_selection = None
        self.set_current_tool("brush")

    def has_active_selection(self) -> bool:
        """
        Vráti True, ak existuje neprázdny výber oblastí
        """
        return self.active_selection is not None and not self.active_selection.is_empty()

    def clear_active_selection(self) -> None:
        """
        Zruší aktuálny výber oblastí
        """
        self.active_selection = None

    def set_selection(self, selection_set: SelectionSet | None) -> None:
        """
        Nastaví aktuálny SelectionSet a obnoví canvas aj AlgorithmPanel
        """
        self.active_selection = selection_set

        #informujeme AlgorithmPanel
        if self.algorithm_panel is not None and hasattr(self.algorithm_panel, "refresh_from_selection"):
            self.algorithm_panel.refresh_from_selection(selection_set)

        #refresh canvas
        self.refresh_canvas()

    def get_active_selection_bbox(self) -> tuple[int, int, int, int] | None:
        """
        Vráti spoločný bbox aktuálneho výberu
        """
        if self.active_selection is None or self.active_selection.is_empty():
            if hasattr(self, "show_tool_message"):
                self.show_tool_message("Nejprve vyberte poškozenou oblast")
            return None
        return self.active_selection.combined_bbox()

    def request_manual_window_bbox(self, on_done, max_size: int = 1440) -> None:
        """
        Aktivuje v canvase režim ručného výberu okna
        """
        if self.canvas is None:
            return
        self.show_tool_message("Tažením myší na plátně vyberte okno (max. 1440×1440)")

        def _done(bbox):
            #nastavíme pending bbox, aby sa dal posúvať
            if bbox is not None:
                self.set_pending_window_bbox(bbox)
            on_done(bbox)

        self.canvas.start_window_pick(on_done=_done, max_size=max_size)

    def run_realistic_fill_window(self, window_bbox: tuple[int,int,int,int], use_mock: bool = False, partial_noise: float = 0.7, seed: int | None = None, realistic_mode: RealisticFillMode = RealisticFillMode.BASIC) -> None:
        """
        Spustí realistic fill pre zvolené okno
        - ak je selection: aplikuje len do selection
        - ak nie je selection: aplikuje do damage masky v okne
        """
        project = self.project
        if project is None:
            return

        if project.damage_original_mask is None:
            self.show_tool_message("Projekt nemá masku poškození")
            return

        if not use_mock and not self._ensure_remote_restoration_config():
            self.show_tool_message("Realistické doplnění nebylo spuštěno – chybí nastavení remote služby")
            return

        x, y, w, h = window_bbox
        if w <= 0 or h <= 0:
            self.show_tool_message("Neplatné okno")
            return
        if w > 1440 or h > 1440:
            self.show_tool_message(f"Okno je příliš veliké ({w}×{h}). Maximum je 1440×1440")
            return

        dmg = project.damage_original_mask.astype(bool)
        H, W = dmg.shape

        #orezanie okna do hraníc obrazu
        x0 = max(0, min(x, W))
        y0 = max(0, min(y, H))
        x1 = max(x0, min(x + w, W))
        y1 = max(y0, min(y + h, H))

        if x1 <= x0 or y1 <= y0:
            self.show_tool_message("Okno je mimo obraz")
            return

        ww = x1 - x0
        wh = y1 - y0

        #okno musí obsahovať aspoň 1 damage pixel
        if not bool(dmg[y0:y1, x0:x1].any()):
            self.show_tool_message("Zvolené okno neobsahuje žádné poškození")
            return

        #selection je voliteľná
        has_selection = (self.active_selection is not None and not self.active_selection.is_empty())

        if has_selection:
            apply_mask_full = self.active_selection.combined_mask().astype(bool)
        else:
            #bez selection -aspoň damage v okne ako selected_mask
            apply_mask_full = dmg

        #výber cieľovej PAINT vrstvy
        target_layer = self.get_active_paint_layer_for_autofill()
        if target_layer is None:
            self.show_tool_message("Není dostupná vrstva malby")
            return

        #remaining maska pre konkrétnu paint vrstvu
        #tým zabezpečíme, že realistic fill sa aplikuje iba tam, kde táto konkrétna vrstva ešte nemá vyplnené pixely
        layer_remaining_full = project.get_layer_damage_remaining_mask(target_layer.meta.id)
        if layer_remaining_full is None:
            self.show_tool_message("Nepodařilo se zjistit zbývající masku aktivní vrstvy malby")
            return

        #aplikovať chceme iba tam, kde selection/damage dovoľuje zásah a zároveň je to na tejto paint vrstve ešte nevyplnené
        apply_mask_full = apply_mask_full & layer_remaining_full

        #remote realistic algoritmus dostane iba výsek zvoleného okna
        selected_mask_patch = apply_mask_full[y0:y1, x0:x1]

        if not bool(selected_mask_patch.any()):
            self.show_tool_message("Ve zvoleném okně už na této vrstvě není nic k doplnění")
            return

        #Základný režim používa výsek pôvodného obrazu.
        #Vedený režim používa aktuálny zložený obraz, aby obsahoval aj prípadný ručný náčrt.
        if realistic_mode == RealisticFillMode.GUIDED:
            image_patch = project.composited_region((x0, y0, ww, wh))
        else:
            original = project.get_original_image()
            if original is None:
                self.show_tool_message("Nezdařilo se načíst původní obraz")
                return
            image_patch = original[y0:y1, x0:x1].copy()

        #request pre runner
        request = AlgorithmRequest(
            original_image=image_patch,
            current_image=image_patch,
            selected_mask=selected_mask_patch,
            remaining_mask=selected_mask_patch,
            algorithm_type=AlgorithmType.REALISTIC,
            device="cpu",
            mock=use_mock,
            window_bbox=(x0, y0, ww, wh),
            partial_noise=partial_noise,
            seed=seed,
            realistic_mode=realistic_mode,
            progress_callback=self._show_algorithm_progress,
        )

        if realistic_mode == RealisticFillMode.GUIDED:
            self._show_algorithm_progress("Spouštím vedené realistické doplnění...", None, None)
        else:
            self._show_algorithm_progress("Spouštím realistické doplnění...", None, None)

        try:
            if not use_mock:
                apply_remote_restoration_environment()
        except RemoteRestorationConfigError as e:
            self.show_tool_message(f"Nastavení remote služby není platné: {e}")
            return

        try:
            result = AlgorithmRunner.run(request)
        except RemoteRestorationAccessError:
            self.show_tool_message(
                "Přihlášení k remote službě se nepodařilo. Zkontrolujte endpoint URL a API key."
            )

            if self._remote_settings_request_callback is not None:
                self._remote_settings_request_callback(
                    "Přihlášení k remote službě se nepodařilo. "
                    "Zkontrolujte endpoint URL a API key a uložte nastavení znovu."
                )

            return
        except Exception as e:
            self.show_tool_message(f"Realistické doplnění selhalo: {e}")
            return
        finally:
            self._clear_algorithm_progress()

        patch = result.output_patch
        bx, by, bw, bh = result.bbox

        #prevod patch na RGBA pre paint vrstvu
        if patch.ndim != 3:
            self.show_tool_message("Algoritmus vrátil neplatný výstup")
            return

        if patch.shape[0] != bh or patch.shape[1] != bw:
            self.show_tool_message("Algoritmus vrátil patch se špatnými rozměry")
            return

        if patch.shape[2] == 3:
            patch_rgba = np.zeros((bh, bw, 4), dtype=np.uint8)
            patch_rgba[..., :3] = patch
            patch_rgba[..., 3] = 255
        else:
            patch_rgba = patch.astype(np.uint8)

        #maska aplikácie v okne (selection alebo damage)
        local_apply = apply_mask_full[by:by+bh, bx:bx+bw]

        before = target_layer.clone_subregion(bx, by, bw, bh)

        sub = target_layer.image[by:by+bh, bx:bx+bw, :]
        sub[local_apply] = patch_rgba[local_apply]

        after = target_layer.clone_subregion(bx, by, bw, bh)

        if np.array_equal(before, after):
            self.show_tool_message("Realistické doplnění neprovedlo žádnou změnu")
            return

        description = "Vedené realistické doplnění" if realistic_mode == RealisticFillMode.GUIDED else "Realistické doplnění"
        action = UndoAction(description=description, layer_id=target_layer.meta.id, layer_role=target_layer.meta.role, bbox=(bx, by, bw, bh), before=before, after=after)
        project.undo_manager.push_action(action)

        filled_mask = np.zeros_like(dmg, dtype=bool)
        filled_mask[by:by + bh, bx:bx + bw] = local_apply
        project.mark_region_as_filled_on_layer(target_layer.meta.id, filled_mask)
        self.invalidate_selection_region_map_cache()

        project.mark_dirty()
        self.refresh_canvas()
        self.set_pending_window_bbox(None)
        if realistic_mode == RealisticFillMode.GUIDED:
            self.show_tool_message("Vedené realistické doplnění bylo dokončeno")
        else:
            self.show_tool_message("Realistické doplnění bylo dokončeno")

    def set_pending_window_bbox_listener(self, cb) -> None:
        """Dialog si zaregistruje callback, aby dostával aktualizácie bboxu"""
        self._pending_window_bbox_listener = cb

    def clear_pending_window_bbox_listener(self) -> None:
        """Odpojí listener pre zmeny pending okna"""
        self._pending_window_bbox_listener = None

    def set_pending_window_bbox(self, bbox: tuple[int,int,int,int] | None) -> None:
        """Nastaví alebo zruší pending okno pre realistické doplnenie"""
        self._pending_window_bbox = bbox
        if self.canvas is not None:
            self.canvas.set_pending_window_bbox(bbox)
        if self._pending_window_bbox_listener is not None:
            self._pending_window_bbox_listener(bbox)

    def get_pending_window_bbox(self) -> tuple[int,int,int,int] | None:
        """Vráti aktuálne pending okno pre realistické doplnenie"""
        return self._pending_window_bbox

    def on_pending_window_bbox_changed(self, bbox: tuple[int,int,int,int]) -> None:
        """Volá canvas pri posúvaní pending okna"""
        self._pending_window_bbox = bbox

        #update dialógu
        if self._pending_window_bbox_listener is not None:
            self._pending_window_bbox_listener(bbox)

    def clear_selection(self) -> None:
        self.set_selection(None)

    def set_show_damage_overlay(self, show: bool) -> None:
        """
        Zapne / vypne vizualizáciu damage_remaining_mask na canvase
        """
        self.show_damage_overlay = show
        self.refresh_canvas()

    def set_damage_overlay_opacity(self, opacity: float) -> None:
        """
        opacity je 0.0 – 1.0
        """
        self.damage_overlay_opacity = max(0.0, min(1.0, float(opacity)))
        self.refresh_canvas()

    def set_algorithm_panel(self, panel: object) -> None:
        """
        Prepojí controller s AlgorithmPanelom
        """
        self.algorithm_panel = panel
        if hasattr(panel, "set_controller"):
            panel.set_controller(self)

    def set_undo_redo_changed_callback(self, callback: Callable[[], None]) -> None:
        self._undo_redo_changed_callback = callback

    def set_message_callback(self, callback: Callable[[str], None]) -> None:
        """
        Nastaví callback na zobrazovanie krátkych hlášok pre používateľa
        (tool warnings a pod.)
        """
        self._message_callback = callback

    def set_brush_size_preview_callback(self, callback: Callable[[int], None]) -> None:
        """
        Nastaví callback pre zobrazenie náhľadu veľkosti štetca
        """
        self._brush_size_preview_callback = callback

    def show_tool_message(self, text: str) -> None:
        """
        Zobrazí krátku hlášku o používaní nástrojov
        """
        if self._message_callback is not None:
            self._message_callback(text)
        else:
            print(text)

    #refresh metódy

    def _get_damage_overlay_mask_for_view(self) -> np.ndarray | None:
        """
        Vráti masku, ktorú chceme zobrazovať ako overlay
        vracia globálnu remaining masku podľa viditeľných vrstiev
        """
        if self.project is None:
            return None
        return self.project.get_damage_remaining_mask_for_visible_layers()
    
    def _auto_switch_active_layer_for_tool(self, tool_type: str) -> None:
        """
        Automaticky prepne aktívnu vrstvu podľa zvoleného nástroja
        edge používa EDGE vrstvu, kresliace nástroje používajú PAINT vrstvu
        """
        if self.project is None:
            return

        def find_first(role: LayerRole) -> str | None:
            for layer in self.project.layers:
                if layer.meta.role == role:
                    return layer.meta.id
            return None

        #edge tool -> EDGE vrstva
        if tool_type == "edge":
            edge_layer = self.project.get_edge_layer()
            if edge_layer is not None:
                self.set_active_layer(edge_layer.meta.id)

        #kresliace nástroje -> PAINT vrstva
        if tool_type in ("brush", "edge_blend", "blend"):
            if self.active_layer_id is not None:
                active = self.get_layer_by_id(self.active_layer_id)
                if active is not None and active.meta.role == LayerRole.PAINT:
                    return
            paint_id = find_first(LayerRole.PAINT)
            if paint_id is not None:
                self.set_active_layer(paint_id)

    def refresh_canvas(self) -> None:
        if self.project is None or self.canvas is None:
            return

        #numpy (H, W, 3, uint8)
        image_rgb = self.project.composited_image()

        #overlay poškodených oblastí (damage_remaining_mask)
        if self.show_damage_overlay:
            remaining = self._get_damage_overlay_mask_for_view()
            if remaining is not None:
                h_img, w_img, _ = image_rgb.shape
                h_mask, w_mask = remaining.shape

                #len ak sedí veľkosť – aby to nespadlo, keby maska bola zlá
                if h_mask == h_img and w_mask == w_img:
                    #vybielený náhľad poškodených oblastí
                    overlay_color = np.array([255, 255, 255], dtype=np.float32)
                    alpha = self.damage_overlay_opacity  #0 = nič, 1 = úplne biele

                    region = remaining
                    orig = image_rgb[region].astype(np.float32)
                    blended = orig * (1.0 - alpha) + overlay_color * alpha
                    image_rgb[region] = blended.clip(0, 255).astype(np.uint8)
                #inak overlay ignorujeme -maska nesedí
        qimage = self._numpy_rgb_to_qimage(image_rgb)
        self.canvas.set_image(qimage)
        #selection overlay
        if self.active_selection is not None and not self.active_selection.is_empty():
            try:
                sel_mask = self.active_selection.combined_mask()
            except ValueError:
                sel_mask = None
        else:
            sel_mask = None
        self.canvas.set_selection_mask(sel_mask)

    def refresh_canvas_region(self, bbox: tuple[int, int, int, int]) -> None:
        """
        Rýchla verzia refreshu iba v oblasti bbox = (x, y, w, h)
        výsledný patch vloží do existujúceho QImage v canvase
        """
        if self.project is None or self.canvas is None:
            return

        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return

        #composited patch z core
        region_rgb = self.project.composited_region(bbox)
        #damage overlay len pre túto oblasť
        if self.show_damage_overlay:
            remaining = self._get_damage_overlay_mask_for_view()
            if remaining is not None:
                y0, x0 = y, x
                y1, x1 = y + h, x + w

                Hmask, Wmask = remaining.shape
                #orezať do hraníc masky
                y0c = max(0, min(y0, Hmask))
                y1c = max(0, min(y1, Hmask))
                x0c = max(0, min(x0, Wmask))
                x1c = max(0, min(x1, Wmask))

                if y1c > y0c and x1c > x0c:
                    sub_mask = remaining[y0c:y1c, x0c:x1c]
                    h_sub, w_sub = sub_mask.shape
                    h_img, w_img, _ = region_rgb.shape

                    if h_sub == h_img and w_sub == w_img:
                        overlay_color = np.array([255, 255, 255], dtype=np.float32)
                        alpha = self.damage_overlay_opacity

                        region = sub_mask
                        orig = region_rgb[region].astype(np.float32)
                        blended = orig * (1.0 - alpha) + overlay_color * alpha
                        region_rgb[region] = blended.clip(0, 255).astype(np.uint8)

        #konverzia patchu na QImage
        patch_qimage = self._numpy_rgb_to_qimage(region_rgb)
        #patch do canvasu
        self.canvas.patch_region(patch_qimage, x, y)

    def set_active_layer(self, layer_id: str) -> None:
        """
        Nastaví aktívnu vrstvu podľa jej id a obnoví súvisiace panely
        """
        if self.project is None:
            return

        if self.active_layer_id == layer_id:
            return

        #overíme, či vrstva s takým ID existuje
        if not any(layer.meta.id == layer_id for layer in self.project.layers):
            return

        self.active_layer_id = layer_id
        self.refresh_layers_panel()
        self.clear_auto_fill_preview()
        self.update_layer_preview()
        self.invalidate_selection_region_map_cache()

    def add_paint_layer(self) -> None:
        """
        Vytvorí novú prázdnu PAINT vrstvu nad existujúcimi vrstvami
        a nastaví ju ako aktívnu
        """
        if self.project is None:
            return

        bg = self.project.get_background_layer()
        if bg is None:
            return

        h, w, c = bg.image.shape
        new_image = np.zeros((h, w, c), dtype=np.uint8)

        #index novej paint vrstvy
        paint_count = sum(1 for layer in self.project.layers if layer.meta.role == LayerRole.PAINT)
        index = paint_count + 1

        layer_id = f"paint_{index}"
        meta = LayerMeta(id=layer_id, name=f"Malba {index}", role=LayerRole.PAINT)
        new_layer = Layer(meta, new_image)

        self.project.add_layer(new_layer)
        self.project.mark_dirty()
        self.active_layer_id = layer_id
        self.invalidate_selection_region_map_cache()

        self.refresh_layers_panel()
        self.refresh_canvas()
    
    def get_layer_by_id(self, layer_id: str) -> Layer | None:
        if self.project is None:
            return None
        for layer in self.project.layers:
            if layer.meta.id == layer_id:
                return layer
        return None
    
    def on_layer_visibility_changed(self, layer_id: str, visible: bool) -> None:
        layer = self.get_layer_by_id(layer_id)
        if layer is None or self.project is None:
            return

        layer.meta.visible = bool(visible)

        self.invalidate_selection_region_map_cache()
        self.refresh_canvas()
        self.refresh_layers_panel()
        self.update_layer_preview()

        self.project.mark_dirty()

    def on_layer_delete_requested(self, layer_id: str) -> bool:
        """
        Zmaže paint vrstvu
        -vráti True, ak sa podarilo
        """
        if self.project is None:
            return False

        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return False

        if layer.meta.role != LayerRole.PAINT:
            self.show_tool_message("Tuto vrstvu nelze smazat")
            return False

        try:
            self.project.remove_layer(layer_id)
            self.project.mark_dirty()
        except Exception as e:
            self.show_tool_message(f"Vrstvu se nepodařilo smazat: {e}")
            return False

        #ak sme zmazali aktívnu vrstvu, nastavíme inú aktívnu
        if self.active_layer_id == layer_id:
            #preferujme prvú PAINT, inak background
            paint_layers = self.project.get_paint_layers()
            if paint_layers:
                self.active_layer_id = paint_layers[-1].meta.id
            else:
                bg = self.project.get_background_layer()
                self.active_layer_id = bg.meta.id if bg else None

        self.refresh_layers_panel()
        self.refresh_canvas()
        return True

    def on_layer_opacity_changed(self, layer_id: str, opacity: float) -> None:
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return

        layer.meta.opacity = float(max(0.0, min(1.0, opacity)))
        self._opacity_debounce_timer.start(80)
        self.project.mark_dirty()

    def _apply_opacity_debounced_refresh(self) -> None:
        """
        Zavolá sa po debounce timeoute pri zmene krytia vrstvy
        """
        self.refresh_canvas()

    def rename_layer(self, layer_id: str, new_name: str) -> None:
        """
        Premenuje vrstvu s daným id
        """
        if self.project is None:
            return

        for layer in self.project.layers:
            if layer.meta.id == layer_id:
                layer.meta.name = new_name
                self.project.mark_dirty()
                break

        self.refresh_layers_panel()


    def refresh_layers_panel(self) -> None:
        if self.project is None or self.layers_panel is None:
            return

        self.layers_panel.refresh_from_project(self.project, self.active_layer_id)
        self.update_layer_preview()

    def update_layer_preview(self) -> None:
        if self.project is None or self.layers_panel is None:
            return

        if self.active_layer_id is None:
            self._current_layer_preview_qimage = None
            self._current_layer_preview_title = ""
            self.hide_layer_preview_overlay()
            if hasattr(self.layers_panel, "set_preview"):
                self.layers_panel.set_preview(None)
            return

        layer = self.get_layer_by_id(self.active_layer_id)
        if layer is None:
            self._current_layer_preview_qimage = None
            self._current_layer_preview_title = ""
            self.hide_layer_preview_overlay()
            if hasattr(self.layers_panel, "set_preview"):
                self.layers_panel.set_preview(None)
            return

        #RGBA -> RGB cez alfa blending na tmavé pozadie
        rgba = layer.image.astype(np.float32)
        rgb = rgba[..., :3]
        alpha = rgba[..., 3:4] / 255.0
        bg = np.zeros_like(rgb) + 222.0  #bledé pozadie
        out = rgb * alpha + bg * (1.0 - alpha)
        out = np.clip(out, 0, 255).astype(np.uint8)

        qimg = self._numpy_rgb_to_qimage(out)

        self._current_layer_preview_qimage = qimg.copy()
        self._current_layer_preview_title = layer.meta.name

        if hasattr(self.layers_panel, "set_preview"):
            #zmenší sa už v LayersPanel.set_preview, takže tu netreba
            self.layers_panel.set_preview(qimg)
        
        if self._layer_preview_overlay_visible and self.canvas is not None:
            if hasattr(self.canvas, "set_layer_preview_overlay"):
                self.canvas.set_layer_preview_overlay(self._current_layer_preview_qimage, self._current_layer_preview_title)

    def on_canvas_mouse_press(self, img_x: int, img_y: int, buttons: Qt.MouseButtons, modifiers: Qt.KeyboardModifier) -> None:
        if buttons & Qt.LeftButton:
            handled = self.toggle_auto_fill_candidate_at(img_x, img_y)
            if handled:
                return
        if self.current_tool is None:
            return
        self.current_tool.on_mouse_press(img_x, img_y, buttons, modifiers)

    def on_canvas_mouse_move(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if self.current_tool is None:
            return
        self.current_tool.on_mouse_move(img_x, img_y, buttons, modifiers)

    def on_canvas_mouse_release(self, img_x: int, img_y: int, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> None:
        if self.current_tool is None:
            return
        self.current_tool.on_mouse_release(img_x, img_y, buttons, modifiers)

    def _numpy_rgb_to_qimage(self, arr: np.ndarray) -> QImage:
        """
        Konvertuje numpy RGB obraz na QImage RGB888
        .copy() zabezpečí, že QImage má vlastnú kópiu dát
        """
        if arr.dtype != np.uint8 or arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError("Expected RGB image of shape (H, W, 3) with dtype=uint8")

        h, w, ch = arr.shape
        bytes_per_line = ch * w
        qimage = QImage(arr.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return qimage.copy()
    
    #load/save projektu
    def create_project_from_files(self, image_path: str, mask_path: Optional[str] = None) -> Project:
        """
        Vytvorí nový Project zo zadaného obrázka (a voliteľne damage masky)
        """
        
        working_arr, scale = load_working_image(image_path, max_size=4000)

        bg_meta = LayerMeta(id="background", name="Původní obraz", role=LayerRole.BACKGROUND)
        bg_layer = Layer(bg_meta, working_arr.copy())

        paint_img = np.zeros_like(working_arr, dtype=np.uint8)
        paint_meta = LayerMeta(id="paint_1", name="Malba 1", role=LayerRole.PAINT)
        paint_layer = Layer(paint_meta, paint_img)

        edge_img = np.zeros_like(working_arr, dtype=np.uint8)
        edge_meta = LayerMeta(id="edge_1", name="Hrany 1", role=LayerRole.EDGE)
        edge_layer = Layer(edge_meta, edge_img)

        project_name = Path(image_path).stem
        project = Project(project_name)

        self._load_default_textures_into_project(project)

        project.base_image_path = Path(image_path)
        project.base_image_scale = scale
        project.base_image_working = working_arr    

        project.add_layer(bg_layer)
        project.add_layer(paint_layer)
        project.add_layer(edge_layer)

        h_img, w_img, _ = working_arr.shape
        if mask_path:
            mask_preview_arr, _ = load_working_image(mask_path, max_size=4000)

            #otvoríme dialóg na zarovnanie
            parent = QApplication.activeWindow()
            dlg = MaskAlignmentDialog(working_arr, mask_preview_arr, parent=parent)
            result = dlg.exec()

            if result != QDialog.Accepted:
                raise RuntimeError("Zarovnání masky bylo zrušeno uživatelem")
            
            image_points, mask_points = dlg.get_points()
            H = mask_alignment.compute_homography(src_points=mask_points, dst_points=image_points)
            wrapped_mask_rgb = mask_alignment.warp_mask_to_image(mask_rgb=mask_preview_arr, H=H, target_size=(w_img, h_img))

            damage_mask = mask_alignment.rgb_to_damage_mask(wrapped_mask_rgb)
            project.set_damage_masks(damage_mask)

        self.set_project(project)
        self.current_project_path = None
        return project

    def open_project(self, zip_path: str) -> Project:
        """
        Načíta projekt zo .zip súboru a nastaví ho ako aktuálny
        """

        zip_path_obj = Path(zip_path)

        project = ProjectLoader.load_from_zip(zip_path_obj)
        project.project_name = zip_path_obj.stem
        self.set_project(project)
        path_text = zip_path_obj.as_posix()
        self.current_project_path = path_text
        self.app_settings.add_recent_project(path_text)
        return project

    def save_project_as(self, zip_path: str) -> None:
        """
        Uloží projekt do nového .zip súboru a aktualizuje current_project_path
        """
        if self.project is None:
            return
        
        zip_path_obj = Path(zip_path)

        self.project.project_name = zip_path_obj.stem

        ProjectSerializer.save_to_zip(self.project, zip_path_obj)
        path_text = zip_path_obj.as_posix()
        self.current_project_path = path_text
        self.app_settings.add_recent_project(path_text)
        self.project.mark_saved()

    def save_project(self) -> bool:
        """
        Uloží projekt na aktuálnu cestu

        vráti True, ak sa uložil, False ak nemá nastavenú cestu
        """
        if self.project is None:
            return False

        if not self.current_project_path:
            return False

        zip_path_obj = Path(self.current_project_path)
        self.project.project_name = zip_path_obj.stem

        ProjectSerializer.save_to_zip(self.project, zip_path_obj)
        path_text = zip_path_obj.as_posix()
        self.current_project_path = path_text
        self.app_settings.add_recent_project(path_text)
        
        self.project.mark_saved()
        return True
    
    def has_open_project(self) -> bool:
        return self.project is not None

    def is_project_dirty(self) -> bool:
        return self.project is not None and bool(getattr(self.project, "is_dirty", False))

    def save_project_with_dialog_if_needed(self) -> bool:
        """
        Ak projekt nemá cestu, vyžiada Save As dialóg
        inak spraví obyčajný Save
        vracia True pri úspechu, False pri zrušení alebo chybe
        """
        if self.project is None:
            return False

        #ak nemáme path, tak Save As dialog
        if not self.current_project_path:
            parent = QApplication.activeWindow()
            zip_path, _ = QFileDialog.getSaveFileName(
                parent,
                "Uložit projekt jako",
                "",
                "RP projekty (*.zip);;Všechny soubory (*.*)",
            )
            if not zip_path:
                return False

            if not zip_path.lower().endswith(".zip"):
                zip_path += ".zip"

            try:
                self.save_project_as(zip_path)
            except Exception as e:
                self.show_tool_message(f"Chyba při ukládání: {e}")
                return False

            #po úspechu mark_saved
            self.project.mark_saved()
            return True

        #inak obyčajný save
        ok = self.save_project()
        if ok:
            self.project.mark_saved()
        return ok

    def close_project(self) -> None:
        """
        Zavrie aktuálny projekt v controlleri

        - zabudne referenciu na Project
        - zruší aktívnu vrstvu, selection a nástroj
        - vyčistí stav controlleru
        """
        self.project = None
        self.active_layer_id = None
        self.active_selection = None
        self.current_tool = None
        self.current_project_path = None

        if self._undo_redo_changed_callback is not None:
            self._undo_redo_changed_callback()

    def run_auto_fill_small_regions(self, area_threshold: int = 200) -> int:
        """
        Spustí auto-fill malých oblastí na aktívnej PAINT vrstve
        (alebo na prvej paint vrstve, ak aktívna nie je paint)

        vráti počet vyplnených oblastí
        """
        if self.project is None:
            return 0

        #cieľová vrstva – preferujeme aktívnu, ak je PAINT
        target_layer = self.get_active_paint_layer_for_autofill()
        if target_layer is None:
            return 0
        
        mode = self.get_auto_fill_mode()

        regions_to_fill: list[AutoFillRegion] = []
        region_map = None

        if mode == "selection":
            damage_rem = self.project.get_layer_damage_remaining_mask(target_layer.meta.id)
            if damage_rem is None:
                return 0
            edge_layer = self.project.get_edge_layer()
            region_map = build_region_map(damage_rem, edge_layer)
            regions_to_fill = self._build_autofill_regions_from_selection()
        elif mode == "preview":
            if self.auto_fill_region_map is None:
                return 0
            region_map = self.auto_fill_region_map
            regions_to_fill = self._build_autofill_regions_from_preview()
        else: 
            return 0

        if not regions_to_fill or region_map is None:
            return 0
        count = auto_fill_regions(self.project, target_layer, region_map, regions_to_fill)

        if count > 0:
            self.invalidate_selection_region_map_cache()
            if mode == "selection":
                self.clear_active_selection()
            else:
                self.clear_auto_fill_preview()
            self.refresh_canvas()

        return count
    
    def run_algorithm_on_selection(self, algorithm_type: AlgorithmType, use_mock: bool = False, texture_params: TextureAlgorithmParams | None = None) -> None:
        """
        Spustí externý algoritmus nad aktuálnym výberom
        pripraví AlgorithmRequest, zavolá AlgorithmRunner.run a výsledný patch vloží do cieľovej PAINT vrstvy
        """
        project = self.project
        if project is None or self.active_selection is None or self.active_selection.is_empty():
            return

        target_layer = self.get_active_paint_layer_for_autofill()
        if target_layer is None:
            self.show_tool_message("Není dostupná vrstva malby")
            return

        original = project.get_original_image()
        current = project.get_current_composited_image()
        remaining_mask = project.get_layer_damage_remaining_mask(target_layer.meta.id)

        if original is None or current is None or remaining_mask is None:
            return

        selected_mask = self.active_selection.combined_mask().astype(bool)
        remaining_mask = remaining_mask.astype(bool)

        if selected_mask.shape != remaining_mask.shape:
            self.show_tool_message("Výběr a maska poškození nemají stejnou velikost")
            return

        apply_mask = selected_mask & remaining_mask
        if not bool(apply_mask.any()):
            self.show_tool_message("Ve vybrané oblasti už na této vrstvě není nic k doplnění")
            return

        request = AlgorithmRequest(original_image=original, current_image=current, selected_mask=selected_mask, remaining_mask=remaining_mask, algorithm_type=algorithm_type, device="cpu", mock=use_mock, texture_params=texture_params)

        if algorithm_type == AlgorithmType.TEXTURE:
            progress_message = ("Spouštím texturové doplnění...")
        else:
            progress_message = ("Spouštím externí algoritmus...")

        self._show_algorithm_progress(progress_message, None, None)

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()

        try:
            result = AlgorithmRunner.run(request)
        except Exception as error:
            self.show_tool_message(f"Chyba algoritmu: {error}")
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._clear_algorithm_progress()

        x, y, w, h = result.bbox
        if w <= 0 or h <= 0:
            self.show_tool_message("Algoritmus vrátil neplatný výřez")
            return

        patch = result.output_patch
        if patch.ndim != 3 or patch.shape[0] != h or patch.shape[1] != w:
            self.show_tool_message("Algoritmus vrátil patch se špatnými rozměry")
            return

        if patch.shape[2] == 3:
            patch_rgba = np.zeros((h, w, 4), dtype=np.uint8)
            patch_rgba[..., :3] = patch
            patch_rgba[..., 3] = 255
        elif patch.shape[2] == 4:
            patch_rgba = patch.astype(np.uint8)
        else:
            self.show_tool_message("Algoritmus vrátil neplatný počet kanálů")
            return

        local_apply = apply_mask[y:y + h, x:x + w]
        if local_apply.shape != (h, w) or not bool(local_apply.any()):
            self.show_tool_message("Algoritmus nevrátil žádné použitelné pixely pro aktuální výběr")
            return

        visible_output = patch_rgba[..., 3] > 0
        local_apply = local_apply & visible_output

        if not bool(local_apply.any()):
            self.show_tool_message("Výstup algoritmu neobsahuje žádné viditelné pixely")
            return

        before = target_layer.clone_subregion(x, y, w, h)

        sub_img = target_layer.image[y:y + h, x:x + w, :]
        sub_img[local_apply] = patch_rgba[local_apply]

        after = target_layer.clone_subregion(x, y, w, h)

        if np.array_equal(before, after):
            self.show_tool_message("Algoritmus neprovedl žádnou změnu")
            return

        if algorithm_type == AlgorithmType.TEXTURE:
            description = "Texturové doplnění"
        elif algorithm_type == AlgorithmType.REALISTIC:
            description = "Realistické doplnění"
        else:
            description = f"Doplnění algoritmem {algorithm_type.value}"

        action = UndoAction(description=description, layer_id=target_layer.meta.id, layer_role=target_layer.meta.role, bbox=(x, y, w, h), before=before, after=after)
        project.undo_manager.push_action(action)

        filled_mask = np.zeros_like(apply_mask, dtype=bool)
        filled_mask[y:y + h, x:x + w] = local_apply
        project.mark_region_as_filled_on_layer(target_layer.meta.id, filled_mask)
        self.invalidate_selection_region_map_cache()

        project.history_for_report.append(
            {
                "type": "algorithm_fill",
                "algorithm": algorithm_type.value,
                "bbox": (x, y, w, h),
                "log": result.log_messages,
            }
        )

        project.mark_dirty()
        self.refresh_canvas()
        if algorithm_type == AlgorithmType.TEXTURE:
            self.show_tool_message("Texturové doplnění bylo dokončeno")
        
    def can_undo(self) -> bool:
        return self.project is not None and self.project.can_undo()

    def can_redo(self) -> bool:
        return self.project is not None and self.project.can_redo()
    
    def _on_undo_manager_changed(self) -> None:
        """
        Volá sa pri push_action /undo /redo
        -nastaví dirty
        -MainWindow aktualizuje enabled stav Undo/Redo
        """
        if self.project is not None:
            self.project.mark_dirty()
        
        if self._undo_redo_changed_callback is not None:
            self._undo_redo_changed_callback()

    #export
    def export_image(self, path: str, resolution: str = "working") -> None:
        if self.project is None:
            return
        img = self.project.get_export_image()
        image_io.save_image(path, img)

    #ColorChecker
    def set_color_correction_matrix(self, matrix: np.ndarray | None) -> None:
        if self.project is None:
            return
        self.project.set_color_correction_matrix(matrix)
        #ak nastavíme matrix, default zapneme
        if matrix is not None:
            self.project.set_color_correction_enabled(True)
        else:
            self.project.set_color_correction_enabled(False)

        self.project.mark_dirty()
        self.refresh_canvas()

    def set_color_correction_enabled(self, enabled: bool) -> None:
        if self.project is None:
            return
        if enabled and not self.project.has_color_correction():
            return
        self.project.set_color_correction_enabled(enabled)
        self.project.mark_dirty()
        self.refresh_canvas()

    def has_color_correction(self) -> bool:
        return self.project is not None and self.project.has_color_correction()
    
    #autofill
    def get_active_paint_layer_for_autofill(self) -> Layer | None:
        """
        Vráti paint vrstvu, na ktorej sa má robiť auto-fill preview/fill
        -najprv berieme:
            -aktívnu vrstvu, ak je PAINT
            -prvú PAINT vrstvu v projekte
        """
        if self.project is None:
            return None

        if self.active_layer_id is not None:
            for layer in self.project.layers:
                if layer.meta.id == self.active_layer_id and layer.meta.role == LayerRole.PAINT:
                    return layer

        for layer in self.project.layers:
            if layer.meta.role == LayerRole.PAINT:
                return layer

        return None

    def clear_auto_fill_preview(self) -> None:
        """
        Zruší auto-fill preview stav
        """
        self.auto_fill_preview_active = False
        self.auto_fill_region_map = None
        self.auto_fill_candidate_region_ids.clear()
        self.auto_fill_excluded_region_ids.clear()
        self.auto_fill_preview_layer_id = None

        if self.canvas is not None:
            self.canvas.clear_auto_fill_preview_regions()

    def set_auto_fill_threshold(self, threshold: int) -> None:
        """
        Nastaví nový threshold pre auto-fill preview
        + reset ručne vyradených oblastí
        + prepočítanie kandidátov
        """
        threshold = max(1, int(threshold))
        self.auto_fill_threshold = threshold
        self.auto_fill_excluded_region_ids.clear()
        self.update_auto_fill_preview()
    
    def update_auto_fill_preview(self) -> None:
        """
        Prepočíta kandidátov pre auto-fill small podľa current threshold
        -postaví RegionMap nad damage_remaining maskou cieľovej PAINT vrstvy
        - uloží region_id kandidátov do controlleru
        - zapne preview režim
        """
        self.clear_auto_fill_preview()

        if self.project is None:
            return
        target_layer = self.get_active_paint_layer_for_autofill()
        if target_layer is None:
            return
        damage_rem = self.project.get_layer_damage_remaining_mask(target_layer.meta.id)
        if damage_rem is None:
            return

        edge_layer = self.project.get_edge_layer()
        region_map = build_region_map(damage_rem, edge_layer)

        candidate_ids = set(region_map.get_region_ids_smaller_than(self.auto_fill_threshold))
        self.auto_fill_region_map = region_map
        self.auto_fill_candidate_region_ids = candidate_ids
        self.auto_fill_preview_layer_id = target_layer.meta.id
        self.auto_fill_preview_active = True

        self._refresh_auto_fill_preview_overlay()

    def get_effective_auto_fill_region_ids(self) -> list[int]:
        """
        Vráti region_id, ktoré sa majú reálne vyplniť cez auto-fill preview režim (bez vyradených oblastí)
        """
        ids = self.auto_fill_candidate_region_ids - self.auto_fill_excluded_region_ids
        return sorted(ids)
    
    def toggle_auto_fill_candidate_at(self, x: int, y: int) -> bool:
        """
        Keď je aktívny auto-fill preview režim, kliknutie na kandidáta ju:
        -vyradí z auto-fill, ak bola aktívna
        -alebo ju znovu zaradí, ak už bola vyradená
        vráti True, ak sa niečo zmenilo
        """
        if not self.auto_fill_preview_active:
            return False

        if self.auto_fill_region_map is None:
            return False

        region_id = self.auto_fill_region_map.get_region_id_at(x, y)
        if region_id == 0:
            return False

        if region_id not in self.auto_fill_candidate_region_ids:
            return False

        if region_id in self.auto_fill_excluded_region_ids:
            self.auto_fill_excluded_region_ids.remove(region_id)
        else:
            self.auto_fill_excluded_region_ids.add(region_id)

        self._refresh_auto_fill_preview_overlay()
        return True
    
    def _refresh_auto_fill_preview_overlay(self) -> None:
        """
        Pošle canvas aktuálny stav auto-fill preview -všetkých kandidátov regióny a aj tie, ktoré sú ručne vyradené
        """
        if self.canvas is None:
            return

        self.canvas.set_auto_fill_preview_regions(self.auto_fill_region_map, self.auto_fill_candidate_region_ids, self.auto_fill_excluded_region_ids)

    def _build_autofill_regions_from_preview(self) -> list[AutoFillRegion]:
        """
        Vytvorí zoznam AutoFillRegion z aktuálneho threshold preview režimu
        """
        result: list[AutoFillRegion] = []

        if self.auto_fill_region_map is None:
            return result

        effective_ids = self.get_effective_auto_fill_region_ids()
        for region_id in effective_ids:
            if not self.auto_fill_region_map.has_region(region_id):
                continue

            bbox = self.auto_fill_region_map.get_region_bbox(region_id)
            if bbox is None:
                continue

            result.append(AutoFillRegion(region_id=region_id, bbox=bbox))

        return result
    
    def _build_autofill_regions_from_selection(self) -> list[AutoFillRegion]:
        """
        Vytvorí zoznam AutoFillRegion z aktívneho SelectionSetu
        """
        result: list[AutoFillRegion] = []

        if self.active_selection is None or self.active_selection.is_empty():
            return result

        for sel in self.active_selection.selections:
            result.append(AutoFillRegion(region_id=sel.region_id, bbox=sel.bbox))

        return result
    
    def has_auto_fill_preview_candidates(self) -> bool:
        """
        Vráti True, ak existuje auto-fill preview a sú v ňom nejakí kandidáti
        """
        return self.auto_fill_preview_active and self.auto_fill_region_map is not None and len(self.get_effective_auto_fill_region_ids()) > 0
    

    def get_auto_fill_mode(self) -> str | None:
        """
        Vráti aktuálny režim auto-fill:
        -"selection" -ak existuje active_selection
        -"preview" -ak neexistuje selection, ale existuje preview kandidátov
        -None
        """
        if self.has_active_selection():
            return "selection"
        if self.has_auto_fill_preview_candidates():
            return "preview"

        return None

    def invalidate_selection_region_map_cache(self) -> None:
        """
        Zruší cached RegionMap pre selection
        """
        self.selection_region_map_cache = None
        self.selection_region_map_cache_layer_id = None

    def get_selection_region_map_for_active_layer(self) -> RegionMap | None:
        """
        Vráti RegionMap pre selection na aktuálnej vrstve
        -na PAINT vrstve používa layer_damage_remaining_mask
        -na BACKGROUND (alebo iné) používa damage_original_mask
        """
        if self.project is None:
            return None

        layer_id = self.active_layer_id
        if layer_id is None:
            return None

        if self.selection_region_map_cache is not None and self.selection_region_map_cache_layer_id == layer_id:
            return self.selection_region_map_cache

        #zoberieme aktívnu vrstvu
        layer = next((l for l in self.project.layers if l.meta.id == layer_id), None)
        if layer is None:
            return None

        if layer.meta.role == LayerRole.PAINT:
            mask = self.project.get_layer_damage_remaining_mask(layer_id)
        else:
            #ostatné
            mask = self.project.damage_original_mask

        if mask is None:
            return None

        edge_layer = self.project.get_edge_layer()
        region_map = build_region_map(mask, edge_layer)

        self.selection_region_map_cache = region_map
        self.selection_region_map_cache_layer_id = layer_id

        return region_map
    
    def update_current_tool_cursor(self) -> None:
        if self.canvas is None:
            return
        if self.current_tool is None:
            self.canvas.unsetCursor()
            return

        cur = self.current_tool.get_cursor()
        if cur is None:
            self.canvas.unsetCursor()
        else:
            self.canvas.setCursor(cur)
        
    def _brush_radius_to_screen_px(self, radius_img_px: int) -> int:
        zoom = 1.0
        if self.canvas is not None and hasattr(self.canvas, "zoom_factor"):
            zoom = float(self.canvas.zoom_factor)
        return int(max(4, round(radius_img_px * zoom)))
    
    def _make_brush_cursor(self, radius_img_px: int, color_rgba: tuple[int, int, int, int], outline: QColor | None = None) -> QCursor:
        #parametre z materials
        hardness = float(self.get_brush_hardness())
        opacity = float(self.get_brush_opacity())
        flow = float(self.get_brush_flow())

        r_screen = self._brush_radius_to_screen_px(radius_img_px)
        r_screen = int(max(6, min(256, r_screen))) 
        d = 2 * r_screen + 1

        key = ("brush", d, color_rgba, round(hardness, 3), round(opacity, 3), round(flow, 3))
        if key in self._cursor_cache:
            return self._cursor_cache[key]

        pm = QPixmap(d, d)
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)

        #alfa -viditeľnosť
        vis = float(opacity) * float(flow)
        vis = max(0.02, vis) 
        alpha_core = int(255 * vis)

        #radius jadra podľa hardness
        core_r = int(round(r_screen * hardness))
        if core_r < 1:
            core_r = 1
        if core_r > r_screen:
            core_r = r_screen

        base = QColor(*color_rgba[:3])
        for rr in range(r_screen, 0, -1):
            if rr <= core_r:
                a = alpha_core
            else:
                t = (rr - core_r) / max(1, (r_screen - core_r))
                a = int(alpha_core * (1.0 - t))
            c = QColor(base)
            c.setAlpha(a)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(r_screen - rr, r_screen - rr, 2 * rr, 2 * rr)

        #obrys pre viditeľnosť
        if outline is None:
            outline = QColor(0, 0, 0, 220)
        pen = QPen(outline)
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(1, 1, d - 2, d - 2)

        p.end()

        cur = QCursor(pm, r_screen, r_screen)
        self._cursor_cache[key] = cur
        return cur

    def _make_texture_cursor(self, radius_img_px: int) -> QCursor:
        """
        Texture kurzor -stamp sa generuje v IMAGE px (size_img), potom sa škáluje do SCREEN px podľa zoomu
        """
        ts = getattr(self, "texture_settings", None)
        project = getattr(self, "project", None)
        if ts is None or getattr(ts, "texture", None) is None or project is None:
            #fallback na normálny brush kurzor
            rgba = tuple(int(x) for x in self.get_current_color_rgba()[:4])
            return self._make_brush_cursor(radius_img_px, rgba)

        r_img = int(radius_img_px)
        r_img = max(1, r_img)
        size_img = 2 * r_img + 1

        #pri zoome
        zoom = 1.0
        if getattr(self, "canvas", None) is not None and hasattr(self.canvas, "zoom_factor"):
            zoom = float(self.canvas.zoom_factor)

        size_screen = int(max(12, round(size_img * zoom)))

        #materials parametre 
        hardness = float(self.get_brush_hardness())
        opacity = float(self.get_brush_opacity())
        flow = float(self.get_brush_flow())

        vis = opacity * flow
        vis = max(0.02, vis)  #minimum

        cur_color = self.get_current_color_rgba()
        r, g, b, a = [int(x) for x in cur_color[:4]]
        key = (
            "texture_cursor",
            size_img,
            size_screen,
            getattr(ts.texture, "name", None),
            round(float(ts.scale), 4),
            round(float(ts.strength), 4),
            round(float(getattr(ts, "rotation_deg", 0.0)), 4),
            getattr(ts, "texture_style", "transparent"),
            (r, g, b),
            round(hardness, 4),
            round(vis, 4),
        )
        if hasattr(self, "_cursor_cache") and key in self._cursor_cache:
            return self._cursor_cache[key]

        if hasattr(ts, "color"):
            ts.color = (r, g, b)

        #RGBA stamp v IMAGE px
        stamp = generate_brush_stamp(ts, size=size_img, offset_x=0, offset_y=0)

        stamp = np.ascontiguousarray(stamp, dtype=np.uint8)
        h, w, ch = stamp.shape
        if ch != 4:
            rgba_fallback = (r, g, b, 255)
            return self._make_brush_cursor(radius_img_px, rgba_fallback)

        yy, xx = np.ogrid[:h, :w]
        cx = w // 2
        cy = h // 2
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

        core_r = max(1.0, hardness * r_img)
        edge_r = float(r_img)

        mask = np.ones((h, w), dtype=np.float32)
        mask[dist > edge_r] = 0.0

        soft_zone = (dist > core_r) & (dist <= edge_r)
        mask[soft_zone] = (edge_r - dist[soft_zone]) / max(1e-6, (edge_r - core_r))

        alpha = stamp[..., 3].astype(np.float32) / 255.0
        alpha = alpha * mask * vis
        stamp[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)

        bytes_per_line = stamp.strides[0]
        qimg = QImage(stamp.data, w, h, bytes_per_line, QImage.Format_RGBA8888).copy()

        pm = QPixmap.fromImage(qimg)

        if size_screen != size_img:
            pm = pm.scaled(size_screen, size_screen, Qt.KeepAspectRatio, Qt.FastTransformation)
        
        #obrys pre viditeľnosť
        outline = QColor(0, 0, 0, 220)

        p2 = QPainter(pm)
        p2.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(outline)
        pen.setWidth(2)
        p2.setPen(pen)
        p2.setBrush(Qt.NoBrush)

        #obrys po okraji pixmapy
        p2.drawEllipse(1, 1, pm.width() - 2, pm.height() - 2)
        p2.end()

        cur = QCursor(pm, size_screen // 2, size_screen // 2)

        if hasattr(self, "_cursor_cache"):
            self._cursor_cache[key] = cur

        return cur
    
    def _make_edge_cursor(self) -> QCursor:
        size_img = 1
        r_screen = self._brush_radius_to_screen_px(size_img)
        r_screen = int(max(4, min(48, r_screen)))
        d = 2 * r_screen + 1

        col_arr = self.get_edge_color_rgba()
        r, g, b, a = [int(x) for x in col_arr[:4]]
        key = ("edge", d, r, g, b, a)
        if key in self._cursor_cache:
            return self._cursor_cache[key]

        pm = QPixmap(d, d)
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)

        fill = QColor(r, g, b, 255)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawEllipse(1, 1, d - 2, d - 2)

        pen = QPen(QColor(0, 0, 0, 220))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(1, 1, d - 2, d - 2)

        p.end()

        cur = QCursor(pm, r_screen, r_screen)
        self._cursor_cache[key] = cur
        return cur


    def _make_edge_blend_cursor(self) -> QCursor:
        """
        kurzor pre nástroj zjemnenia hrany:
        - malý vnútorný kruh -stroke_radius EdgeBlendToolu, teda kde sa zachytáva hrana
        - veľký vonkajší kruh -buffer zjemnenia z EdgeSettingsPanelu
        """
        buffer = int(self.get_edge_blend_buffer())

        stroke_radius = 2
        if self.current_tool is not None and hasattr(self.current_tool, "stroke_radius"):
            stroke_radius = int(getattr(self.current_tool, "stroke_radius", 2))

        inner_radius_img = max(1, stroke_radius)
        outer_radius_img = max(inner_radius_img + 1, buffer)

        inner_radius_screen = int(max(3, min(128, self._brush_radius_to_screen_px(inner_radius_img))))
        outer_radius_screen = int(max(inner_radius_screen + 4, min(300, self._brush_radius_to_screen_px(outer_radius_img))))

        d = 2 * outer_radius_screen + 7
        center = d // 2

        key = ("edge_blend", inner_radius_screen, outer_radius_screen)
        if key in self._cursor_cache:
            return self._cursor_cache[key]

        pm = QPixmap(d, d)
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)

        #veľký kruh
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 80)))
        p.drawEllipse(center - outer_radius_screen, center - outer_radius_screen, 2 * outer_radius_screen, 2 * outer_radius_screen)

        pen_outer = QPen(QColor(180, 180, 180, 140))
        pen_outer.setWidth(2)
        pen_outer.setStyle(Qt.DashLine)
        p.setPen(pen_outer)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(center - outer_radius_screen, center - outer_radius_screen, 2 * outer_radius_screen, 2 * outer_radius_screen)

        #malý kruh
        pen_inner = QPen(QColor(255, 255, 255, 240))
        pen_inner.setWidth(2)
        p.setPen(pen_inner)
        p.setBrush(QBrush(QColor(0, 0, 0, 90)))
        p.drawEllipse(center - inner_radius_screen, center - inner_radius_screen, 2 * inner_radius_screen, 2 * inner_radius_screen)

        p.end()

        cur = QCursor(pm, center, center)
        self._cursor_cache[key] = cur
        return cur
    
    def _make_blend_cursor(self, radius_img_px: int) -> QCursor:
        """
        Kurzor pre Blend nástroj
        """
        r_screen = self._brush_radius_to_screen_px(radius_img_px)
        r_screen = int(max(6, min(256, r_screen)))
        d = 2 * r_screen + 1

        strength = float(self.get_blend_strength())
        key = ("blend", d, round(strength, 3))

        if key in self._cursor_cache:
            return self._cursor_cache[key]

        pm = QPixmap(d, d)
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)

        #polopriehľadný neutrálny kurzor
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 45)))
        p.drawEllipse(1, 1, d - 2, d - 2)

        pen = QPen(QColor(255, 255, 255, 210))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(1, 1, d - 2, d - 2)

        #vnútorný krížik
        pen2 = QPen(QColor(255, 255, 255, 150))
        pen2.setWidth(1)
        p.setPen(pen2)
        p.drawLine(r_screen, max(2, r_screen - 5), r_screen, min(d - 2, r_screen + 5))
        p.drawLine(max(2, r_screen - 5), r_screen, min(d - 2, r_screen + 5), r_screen)

        p.end()

        cur = QCursor(pm, r_screen, r_screen)
        self._cursor_cache[key] = cur
        return cur