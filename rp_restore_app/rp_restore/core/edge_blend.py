from __future__ import annotations

import numpy as np
import cv2



def _gaussian_blur_f32(img: np.ndarray, ksize: int, sigma: float) -> np.ndarray:
    """Rozmaže float obraz pomocou Gaussian blur"""
    if ksize % 2 == 0:
        ksize += 1

    return cv2.GaussianBlur(img, (ksize, ksize), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REPLICATE)

def _distance_to_edge(edge_remove_mask: np.ndarray) -> np.ndarray:
    """Spočíta vzdialenosť pixelov od odstraňovanej hrany"""
    inv = (~edge_remove_mask).astype(np.uint8)

    return cv2.distanceTransform(inv, distanceType=cv2.DIST_L2, maskSize=3).astype(np.float32)

def blend_across_edge(composited_rgb: np.ndarray, damage_mask: np.ndarray, edge_remove_mask: np.ndarray, filled_mask: np.ndarray, buffer: int) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Vytvorí plynulý farebný prechod okolo odstránenej EDGE"""
    buffer = int(max(1, buffer))

    if composited_rgb.ndim != 3 or composited_rgb.shape[2] < 3:
        raise ValueError("composited_rgb must be (H, W, 3)")

    h, w = damage_mask.shape
    if edge_remove_mask.shape != (h, w) or filled_mask.shape != (h, w):
        raise ValueError("masks must have the same shape")

    if not edge_remove_mask.any():
        return None, None

    dist = _distance_to_edge(edge_remove_mask)

    #zjemnňujeme iba pásmo okolo odstránenej hrany v rámci damage masky
    band = (dist <= float(buffer)) & damage_mask
    if not band.any():
        return None, None

    #zdrojom farby sú iba vyplnené pixely v poškodenej oblasti
    known = (filled_mask & damage_mask).astype(np.float32)
    if known.sum() <= 0:
        return None, None

    sigma = max(1.0, buffer / 2.0)
    ksize = int(2 * buffer + 1)
    ksize = min(ksize, 199)

    src = composited_rgb[..., :3].astype(np.float32)

    num = _gaussian_blur_f32(src * known[..., None], ksize, sigma)
    den = _gaussian_blur_f32(known, ksize, sigma)

    safe_den = np.maximum(den, 1e-3)
    #rozmazané farby normalizujeme podľa množstva dostupných zdrojových pixelov
    blended = num / safe_den[..., None]

    #pixely bez dostatočnej podpory z okolia radšej neupravujeme
    support_ok = den > 0.05
    band_valid = band & support_ok

    if not band_valid.any():
        return None, None

    blended_rgb = np.clip(blended, 0, 255).astype(np.uint8)
    return band_valid, blended_rgb