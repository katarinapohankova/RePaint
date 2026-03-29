from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class Texture:
    name: str
    image: np.ndarray  #RGB alebo RGBA uint8


@dataclass
class TextureSettings:
    texture: Optional[Texture] = None
    scale: float = 1.0  #0.25 .. 4.0
    color: Tuple[int, int, int] = (255, 255, 255)  #tint RGB
    strength: float = 1.0  #0..1
    rotation_deg: float = 0.0


def _to_gray01(tex_rgb: np.ndarray) -> np.ndarray:
    return (0.299 * tex_rgb[..., 0] + 0.587 * tex_rgb[..., 1] + 0.114 * tex_rgb[..., 2])


def _get_transformed_texture_rgb(settings: TextureSettings) -> np.ndarray:
    """
    Vráti transformovanú textúru ako float32 RGB v [0..1]
    -cachuje podľa (id(image), scale, rotation_deg).
    """
    if settings.texture is None:
        raise ValueError("TextureSettings.texture is None")

    tex = settings.texture.image
    if tex.ndim != 3:
        raise ValueError("Texture must be HxWxC")
    if tex.shape[2] == 4:
        tex = tex[..., :3]

    key = (id(tex), float(settings.scale), float(settings.rotation_deg))

    cached_key = getattr(settings, "_cached_tex_key", None)
    cached_tex = getattr(settings, "_cached_tex_rgb", None)
    if cached_key == key and cached_tex is not None:
        return cached_tex

    tex_f = tex.astype(np.float32) / 255.0
    th, tw, _ = tex_f.shape

    #scale: >1 = väčšie zrno (textúra sa "zväčší"), <1 = hustejšie
    scale = float(max(0.05, settings.scale))
    new_w = max(1, int(round(tw * scale)))
    new_h = max(1, int(round(th * scale)))

    #resize
    if new_w != tw or new_h != th:
        try:
            import cv2
            tex_f = cv2.resize(tex_f, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        except Exception:
            from PIL import Image
            pil = Image.fromarray((tex_f * 255).astype(np.uint8), mode="RGB")
            pil = pil.resize((new_w, new_h))
            tex_f = np.array(pil).astype(np.float32) / 255.0

    #rotation with wrap
    rot = float(settings.rotation_deg)
    if abs(rot) > 0.01:
        try:
            import cv2
            H, W = tex_f.shape[:2]
            M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, 1.0)
            tex_f = cv2.warpAffine(tex_f, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            tex_f = tex_f.astype(np.float32)
        except Exception:
            from PIL import Image
            pil = Image.fromarray((tex_f * 255).astype(np.uint8), mode="RGB")
            pil = pil.rotate(rot, resample=Image.BILINEAR, expand=False)
            tex_f = np.array(pil).astype(np.float32) / 255.0

    setattr(settings, "_cached_tex_key", key)
    setattr(settings, "_cached_tex_rgb", tex_f)
    return tex_f


def generate_fill_pattern(settings: TextureSettings, w: int, h: int, offset_x: int = 0, offset_y: int = 0) -> np.ndarray:
    """
    RGBA pattern (h,w,4) uint8
    -pattern je ukotvený v súradniciach obrazu cez (offset_x, offset_y) aby nadväzoval pri ťahu štetcom
    """
    tex_f = _get_transformed_texture_rgb(settings)
    th, tw, _ = tex_f.shape

    yy = (np.arange(h) + int(offset_y)) % th
    xx = (np.arange(w) + int(offset_x)) % tw
    patch = tex_f[np.ix_(yy, xx)]  #(h,w,3)

    gray = _to_gray01(patch)
    alpha = (1.0 - gray) * float(settings.strength)
    alpha = np.clip(alpha, 0.0, 1.0)

    color = np.array(settings.color, dtype=np.float32) / 255.0

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0:3] = np.clip(color[None, None, :] * 255.0, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return out


def generate_brush_stamp(settings: TextureSettings, size: int, offset_x: int = 0, offset_y: int = 0) -> np.ndarray:
    """
    RGBA stamp (size,size,4) uint8 – používa rovnaký pattern ako fill, len ho oreže kruhom (aby preview sedelo s brush)
    """
    pat = generate_fill_pattern(settings, size, size, offset_x=offset_x, offset_y=offset_y)

    y, x = np.ogrid[:size, :size]
    cx = (size - 1) / 2
    cy = (size - 1) / 2
    r = size / 2
    circle = ((x - cx) ** 2 + (y - cy) ** 2) <= (r ** 2)

    pat2 = pat.copy()
    pat2[..., 3] = np.where(circle, pat2[..., 3], 0).astype(np.uint8)
    return pat2