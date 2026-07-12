from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


TextureCacheKey = tuple[int, tuple[int, ...], str, float, float, float, float]


@dataclass
class Texture:
    """Jedna textúra dostupná v paneli materiálov"""

    name: str
    image: np.ndarray  #RGB alebo RGBA obraz textúry

    is_generated: bool = False  #True pri uložených deformovaných variantoch
    source_texture_name: str | None = None      #názov pôvodnej textúry
    deformation_scale_x: float = 1.0    #uložená deformácia v osi x
    deformation_scale_y: float = 1.0    #uložená deformácia v osi y
    can_deform: bool = True #uložené deformované varianty už ďalej nedeformujeme

    def __post_init__(self) -> None:
        """Skontroluje základný tvar obrázka textúry"""
        if self.image.ndim != 3:
            raise ValueError("Texture image must be HxWxC")

        if self.image.shape[2] not in (3, 4):
            raise ValueError("Texture image must have 3 or 4 channels")

        if self.image.dtype != np.uint8:
            raise ValueError("Texture image must have dtype uint8")


@dataclass
class TextureSettings:
    """Aktuálne nastavenia používania textúry pri kreslení a výplni"""

    texture: Texture | None = None
    scale: float = 1.0  #0.25 .. 4.0
    color: tuple[int, int, int] = (255, 255, 255)  #tint RGB
    strength: float = 1.0  #0..1
    rotation_deg: float = 0.0
    deformation_scale_x: float = 1.0
    deformation_scale_y: float = 1.0
    texture_style: str = "transparent"  #transparent alebo color

    #cache transformovanej textúry, aby sa pri kreslení neprepočítavala stále znova
    _cached_tex_key: TextureCacheKey | None = field(default=None, init=False, repr=False)
    _cached_tex_rgb: np.ndarray | None = field(default=None, init=False, repr=False)


def _to_gray01(tex_rgb: np.ndarray) -> np.ndarray:
    """Prevedie RGB textúru v rozsahu 0-1 na jasovú zložku"""
    return 0.299 * tex_rgb[..., 0] + 0.587 * tex_rgb[..., 1] + 0.114 * tex_rgb[..., 2]


def clear_texture_cache(settings: TextureSettings) -> None:
    """Vymaže cache transformovanej textúry"""
    settings._cached_tex_key = None
    settings._cached_tex_rgb = None


def deform_texture_image(image: np.ndarray, deformation_scale_x: float, deformation_scale_y: float) -> np.ndarray:
    """Vytvorí novú textúru zmenou veľkosti v osi x a y"""
    if image.ndim != 3:
        raise ValueError("Texture must be HxWxC")

    if image.shape[2] not in (3, 4):
        raise ValueError("Texture must have 3 or 4 channels")

    if image.dtype != np.uint8:
        raise ValueError("Texture must have dtype uint8")

    h, w = image.shape[:2]

    #deformáciu obmedzíme zdola, aby nevznikol nulový rozmer textúry
    sx = float(max(0.05, deformation_scale_x))
    sy = float(max(0.05, deformation_scale_y))

    new_w = max(1, int(round(w * sx)))
    new_h = max(1, int(round(h * sy)))

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    return resized.astype(np.uint8)


def _get_transformed_texture_rgb(settings: TextureSettings) -> np.ndarray:
    """Vráti transformovanú textúru ako float32 RGB obraz v rozsahu 0-1"""
    if settings.texture is None:
        raise ValueError("TextureSettings.texture is None")

    source = settings.texture.image

    if source.ndim != 3:
        raise ValueError("Texture must be HxWxC")

    if source.shape[2] not in (3, 4):
        raise ValueError("Texture must have 3 or 4 channels")

    #uložené deformované varianty už nepoužívajú ďalšiu deformáciu zo sliderov
    texture_can_deform = bool(getattr(settings.texture, "can_deform", True))
    effective_deform_x = (
        float(getattr(settings, "deformation_scale_x", 1.0))
        if texture_can_deform
        else 1.0
    )
    effective_deform_y = (
        float(getattr(settings, "deformation_scale_y", 1.0))
        if texture_can_deform
        else 1.0
    )

    #cache závisí od zdrojového obrázka aj aktuálnych transformácií
    key: TextureCacheKey = (
        id(source),
        tuple(source.shape),
        str(source.dtype),
        float(settings.scale),
        float(effective_deform_x),
        float(effective_deform_y),
        float(settings.rotation_deg),
    )

    if settings._cached_tex_key == key and settings._cached_tex_rgb is not None:
        return settings._cached_tex_rgb

    #pri výpočte textúry používame iba RGB časť
    if source.shape[2] == 4:
        tex = source[..., :3]
    else:
        tex = source

    tex_f = tex.astype(np.float32) / 255.0
    th, tw, _ = tex_f.shape

    #scale určuje veľkosť zrna textúry
    scale = float(max(0.05, settings.scale))

    deform_x = float(max(0.05, effective_deform_x))
    deform_y = float(max(0.05, effective_deform_y))

    new_w = max(1, int(round(tw * scale * deform_x)))
    new_h = max(1, int(round(th * scale * deform_y)))

    #textúru škálujeme a prípadne deformujeme v osiach x/y
    if new_w != tw or new_h != th:
        tex_f = cv2.resize(tex_f, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    rot = float(settings.rotation_deg)

    #rotácia používa wrap režim, aby textúra po okrajoch nadväzovala
    if abs(rot) > 0.01:
        h_tex, w_tex = tex_f.shape[:2]
        matrix = cv2.getRotationMatrix2D((w_tex / 2, h_tex / 2), rot, 1.0)
        tex_f = cv2.warpAffine(tex_f, matrix, (w_tex, h_tex), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        tex_f = tex_f.astype(np.float32)

    settings._cached_tex_key = key
    settings._cached_tex_rgb = tex_f
    return tex_f


def generate_fill_pattern(settings: TextureSettings, w: int, h: int, offset_x: int = 0, offset_y: int = 0) -> np.ndarray:
    """Vygeneruje RGBA textúrový pattern ukotvený v súradniciach obrazu"""
    if w <= 0 or h <= 0:
        raise ValueError("Pattern width and height must be positive")

    tex_f = _get_transformed_texture_rgb(settings)
    th, tw, _ = tex_f.shape

    #offset ukotví textúru v súradniciach obrazu, aby ťahy na seba nadväzovali
    yy = (np.arange(h) + int(offset_y)) % th
    xx = (np.arange(w) + int(offset_x)) % tw
    patch = tex_f[np.ix_(yy, xx)]

    gray = _to_gray01(patch)
    gray = np.clip(gray, 0.0, 1.0)

    color = np.array(settings.color, dtype=np.float32) / 255.0
    strength = float(np.clip(settings.strength, 0.0, 1.0))

    out = np.zeros((h, w, 4), dtype=np.uint8)

    style = getattr(settings, "texture_style", "transparent")

    if style == "color":
        #v color režime jas textúry mení odtieň zvolenej farby
        variation = 0.35 * strength
        shade_factor = 1.0 + (gray - 0.5) * 2.0 * variation
        shade_factor = np.clip(shade_factor, 0.55, 1.45)

        rgb = color[None, None, :] * shade_factor[..., None]
        rgb = np.clip(rgb, 0.0, 1.0)

        alpha = strength * (0.88 + 0.12 * (1.0 - gray))
        alpha = np.clip(alpha, 0.0, 1.0)

        out[..., 0:3] = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
        out[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
        return out

    #v transparentnom režime jas textúry určuje alfu ťahu
    alpha = (1.0 - gray) * float(settings.strength)
    alpha = np.clip(alpha, 0.0, 1.0)

    out[..., 0:3] = np.clip(color[None, None, :] * 255.0, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return out


def generate_brush_stamp(settings: TextureSettings, size: int, offset_x: int = 0, offset_y: int = 0) -> np.ndarray:
    """Vygeneruje kruhový RGBA odtlačok textúrového štetca"""
    if size <= 0:
        raise ValueError("Brush stamp size must be positive")

    pattern = generate_fill_pattern(settings, size, size, offset_x=offset_x, offset_y=offset_y)

    y, x = np.ogrid[:size, :size]
    cx = (size - 1) / 2
    cy = (size - 1) / 2
    radius = size / 2
    circle = ((x - cx) ** 2 + (y - cy) ** 2) <= radius ** 2

    stamp = pattern.copy()

    #mimo kruhu vynulujeme alfu, aby odtlačok zodpovedal tvaru štetca
    stamp[..., 3] = np.where(circle, stamp[..., 3], 0).astype(np.uint8)

    return stamp