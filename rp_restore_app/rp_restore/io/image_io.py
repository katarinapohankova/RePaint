from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


PathLike = str | Path


def load_image(path: PathLike) -> np.ndarray:
    """
    Načíta obrázok z disku a vráti ho ako RGBA numpy pole tvaru (H, W, 4)
    """
    with Image.open(path) as img:
        img = img.convert("RGBA")
        arr = np.array(img, dtype=np.uint8)
    return arr

def load_working_image(path: PathLike, max_size: int = 4000) -> tuple[np.ndarray, float]:
    """
    Načíta pracovnú kópiu obrázka vo formáte RGBA
    ak je obrázok väčší než max_size na dlhšej strane, zmenší ho a vráti aj použitý scale
    """
    if max_size <= 0:
        raise ValueError("max_size must be positive")

    with Image.open(path) as img:
        img = img.convert("RGBA")

        orig_w, orig_h = img.size
        long_side = max(orig_w, orig_h)

        if long_side <= max_size:
            scale = 1.0
            resized = img
        else:
            scale = max_size / float(long_side)
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))
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
    ext = path.suffix.lower()

    a = np.asarray(arr)

    if not (a.ndim == 2 or (a.ndim == 3 and a.shape[2] in (3, 4))):
        raise ValueError("Unsupported image shape for save_image")

    #JPG musí byť uint8 a bez alpha kanála
    if ext in (".jpg", ".jpeg"):
        if a.ndim == 3 and a.shape[2] == 4:
            a = a[..., :3]
        if a.dtype != np.uint8:
            #ak je uint16, zmapujeme ho do 8-bit
            if a.dtype == np.uint16:
                a = (a / 256).astype(np.uint8)
            else:
                a = np.clip(a, 0, 255).astype(np.uint8)

        img = Image.fromarray(a, mode="RGB" if a.ndim == 3 else "L")
        img.save(path, format="JPEG", quality=95, subsampling=0)
        return

    #PNG/TIFF
    if a.dtype == np.uint16 and a.ndim == 2:
        img = Image.fromarray(a, mode="I;16")
    else:
        #pre RGB/RGBA ukladáme uint8
        if a.dtype != np.uint8:
            if a.dtype == np.uint16:
                a = (a / 256).astype(np.uint8)
            else:
                a = np.clip(a, 0, 255).astype(np.uint8)

        if a.ndim == 2:
            img = Image.fromarray(a, mode="L")
        elif a.shape[2] == 3:
            img = Image.fromarray(a, mode="RGB")
        else:
            img = Image.fromarray(a, mode="RGBA")

    if ext in (".png",):
        img.save(path, format="PNG")
    elif ext in (".tif", ".tiff"):
        img.save(path, format="TIFF")
    else:
        img.save(path)


def save_mask(path: PathLike, mask: np.ndarray) -> None:
    """
    Uloží 2D bool masku ako čiernobiely obrázok
    """
    path = Path(path)

    if mask.ndim != 2:
        raise ValueError("Mask must be a 2D array")

    if mask.dtype != bool:
        mask = mask.astype(bool)

    arr = np.where(mask, 255, 0).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")
    img.save(path)
