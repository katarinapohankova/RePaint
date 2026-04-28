from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.core.texture_brush import Texture


def _encode_png(arr: np.ndarray) -> bytes:
    """
    Prevedie numpy array na PNG v pamäti a vráti bytes
    """
    if arr.ndim == 2:
        mode = "L"
    elif arr.ndim == 3 and arr.shape[2] == 3:
        mode = "RGB"
    elif arr.ndim == 3 and arr.shape[2] == 4:
        mode = "RGBA"
    else:
        raise ValueError("Unsupported array shape for PNG encoding")

    img = Image.fromarray(arr, mode=mode)
    with BytesIO() as bio:
        img.save(bio, format="PNG")
        return bio.getvalue()


def _decode_png_to_rgba(data: bytes) -> np.ndarray:
    """
    Načíta PNG bytes a vráti RGBA numpy (H, W, 4, uint8)
    """
    with BytesIO(data) as bio:
        img = Image.open(bio).convert("RGBA")
        return np.array(img, dtype=np.uint8)


def _decode_png_to_mask(data: bytes) -> np.ndarray:
    """
    Načíta PNG bytes a vráti 2D bool masku
    """
    with BytesIO(data) as bio:
        img = Image.open(bio).convert("L")
        arr = np.array(img, dtype=np.uint8)
        return arr > 0


class ProjectSerializer:
    """
    Ukladanie Project do .zip súboru
    """

    @staticmethod
    def save_to_zip(project: Project, zip_path: str | Path) -> None:
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        layers_meta: list[dict] = []

        #základná veľkosť plátna (z background vrstvy, ak existuje)
        canvas_width = canvas_height = None
        bg_layer = project.get_background_layer()
        if bg_layer is not None:
            canvas_width, canvas_height = bg_layer.size

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            #uloženie vrstiev
            for idx, layer in enumerate(project.layers):
                rel_path = f"layers/layer_{idx:03d}_{layer.meta.id}.png"

                png_bytes = _encode_png(layer.image)
                zf.writestr(rel_path, png_bytes)

                layers_meta.append(
                    {
                        "id": layer.meta.id,
                        "name": layer.meta.name,
                        "role": layer.meta.role.value,
                        "visible": layer.meta.visible,
                        "opacity": layer.meta.opacity,
                        "order": layer.meta.order,
                        "image_path": rel_path,
                    }
                )

            #uloženie masiek poškodenia
            damage_original_path: Optional[str] = None
            damage_filled_path: Optional[str] = None

            if project.damage_original_mask is not None:
                damage_original_path = "masks/damage_original.png"
                arr = np.where(project.damage_original_mask, 255, 0).astype(np.uint8)
                zf.writestr(damage_original_path, _encode_png(arr))

            if project.damage_filled_mask is not None:
                damage_filled_path = "masks/damage_filled.png"
                arr = np.where(project.damage_filled_mask, 255, 0).astype(np.uint8)
                zf.writestr(damage_filled_path, _encode_png(arr))

            #meta JSON
            meta: dict = {
                "version": "0.1",
                "project_name": project.project_name,
                "canvas_size": {
                    "width": canvas_width,
                    "height": canvas_height,
                },
                "layers": layers_meta,
                "damage_original_mask_path": damage_original_path,
                "damage_filled_mask_path": damage_filled_path,
                "history_for_report": project.history_for_report,

                "palette": [
                    list(color) for color in getattr(project, "palette_colors", [])
                ],
                "current_color": list(getattr(project, "current_color_rgba", (0, 0, 0, 255))),
                                "colorchecker": {
                    "enabled": bool(getattr(project, "color_correction_enabled", False)),
                    "matrix": (
                        getattr(project, "color_correction_matrix", None).tolist()
                        if getattr(project, "color_correction_matrix", None) is not None
                        else None
                    ),
                },
                "texture_style": getattr(project, "texture_style", "transparent")
            }

            #textúry
            textures_meta: list[dict] = []
            if hasattr(project, "textures") and project.textures:
                for name, tex in project.textures.items():
                    rel = f"textures/{name}.png"
                    zf.writestr(rel, _encode_png(tex.image))
                    textures_meta.append({"name": name, "filename": rel})

            meta["textures"] = textures_meta

            zf.writestr("project.json", json.dumps(meta, indent=2, ensure_ascii=False))


class ProjectLoader:
    """
    Načítanie Project zo .zip súboru
    """

    @staticmethod
    def load_from_zip(zip_path: str | Path) -> Project:
        zip_path = Path(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            #načítanie meta
            try:
                raw = zf.read("project.json")
            except KeyError:
                raise RuntimeError("project.json not found in project zip")

            meta = json.loads(raw.decode("utf-8"))

            project_name = meta.get("project_name", zip_path.stem)
            project = Project(project_name)

            project.texture_style = meta.get("texture_style", "transparent")
            if project.texture_style not in ("transparent", "color"):
                project.texture_style = "transparent"

            #načítanie vrstiev
            for layer_info in meta.get("layers", []):
                image_path = layer_info["image_path"]
                try:
                    data = zf.read(image_path)
                except KeyError:
                    raise RuntimeError(f"Layer image {image_path} missing from zip")

                img_rgba = _decode_png_to_rgba(data)

                layer_meta = LayerMeta(
                    id=layer_info["id"],
                    name=layer_info["name"],
                    role=LayerRole(layer_info["role"]),
                    visible=layer_info.get("visible", True),
                    opacity=layer_info.get("opacity", 1.0),
                    order=layer_info.get("order", 0),
                    path=image_path,
                )
                layer = Layer(layer_meta, img_rgba)
                project.add_layer(layer)

            #načítanie masiek
            damage_original_path = meta.get("damage_original_mask_path")
            damage_filled_path = meta.get("damage_filled_mask_path")

            if damage_original_path is not None:
                try:
                    data = zf.read(damage_original_path)
                    mask_original = _decode_png_to_mask(data)
                    project.set_damage_masks(mask_original)
                except KeyError:
                    pass

            if damage_filled_path is not None and project.damage_original_mask is not None:
                try:
                    data = zf.read(damage_filled_path)
                    mask_filled = _decode_png_to_mask(data)
                    if mask_filled.shape == project.damage_filled_mask.shape:
                        project.damage_filled_mask = mask_filled
                except KeyError:
                    pass

            #história pre report
            project.history_for_report = meta.get("history_for_report", [])
            #paleta a aktuálna farba
            palette = meta.get("palette")
            if palette is not None:
                project.palette_colors = [
                    tuple(int(c) for c in rgba)
                    for rgba in palette
                    if isinstance(rgba, (list, tuple)) and len(rgba) == 4
                ]

            current_color = meta.get("current_color")
            if isinstance(current_color, (list, tuple)) and len(current_color) == 4:
                project.current_color_rgba = tuple(int(c) for c in current_color)

            #ColorChecker
            cc = meta.get("colorchecker")
            if isinstance(cc, dict):
                enabled = bool(cc.get("enabled", False))
                matrix = cc.get("matrix", None)

                try:
                    if matrix is None:
                        project.set_color_correction_matrix(None)
                        project.set_color_correction_enabled(False)
                    else:
                        m = np.array(matrix, dtype=np.float32)
                        project.set_color_correction_matrix(m)
                        project.set_color_correction_enabled(enabled)
                except Exception:
                    #ak chyba, radšej korekciu vypneme
                    project.set_color_correction_matrix(None)
                    project.set_color_correction_enabled(False)

            #textúry
            project.textures = {}
            for info in meta.get("textures", []):
                fname = info["filename"]
                name = info["name"]
                try:
                    data = zf.read(fname)
                except KeyError:
                    continue
                img_rgba = _decode_png_to_rgba(data)
                #uložíme RGB/RGBA
                project.textures[name] = Texture(name=name, image=img_rgba)

            return project
