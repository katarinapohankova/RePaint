from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


PathLike = Union[str, Path]


def load_image(path: PathLike) -> np.ndarray:
    """
    načíta obrázok z disku a vráti ho ako numpy RGBA (H, W, 4, uint8)
    """
    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    return arr

def load_working_image(path: str | Path, max_size: int = 5000) -> tuple[np.ndarray, float]:
    
    with Image.open(path) as img:
        img = img.convert("RGBA")

        orig_w, orig_h = img.size
        long_side = max(orig_w, orig_h)

        if long_side <= max_size:
            scale = 1.0
            resized = img
        else:
            scale = max_size / float(long_side)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            resized = img.resize((new_w, new_h), resample=Image.BILINEAR)

        arr = np.array(resized, dtype=np.uint8)

    return arr, scale

def save_image(path: PathLike, arr: np.ndarray) -> None:
    """
    Uloží numpy obrázok na disk
    môže to byť jedno z týchto:
      - 2D (H, W): uloží ako grayscale ("L")
      - 3D (H, W, 3): RGB
      - 3D (H, W, 4): RGBA
    """
    path = Path(path)

    if arr.ndim == 2:
        mode = "L"
    elif arr.ndim == 3 and arr.shape[2] == 3:
        mode = "RGB"
    elif arr.ndim == 3 and arr.shape[2] == 4:
        mode = "RGBA"
    else:
        raise ValueError("unsupported array shape for image saving")

    img = Image.fromarray(arr, mode=mode)
    img.save(path)


def load_mask(path: PathLike) -> np.ndarray:
    """
    Načíta masku poškodenia ako 2D bool pole
    Všetko > 0 sa berie ako True -poškodené
    """
    img = Image.open(path).convert("L")
    arr = np.array(img, dtype=np.uint8)
    return arr > 0


def save_mask(path: PathLike, mask: np.ndarray) -> None:
    """
    Uloží 2D bool masku ako PNG 
    """
    path = Path(path)
    if mask.dtype != bool:
        mask = mask.astype(bool)

    arr = np.where(mask, 255, 0).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")
    img.save(path)
