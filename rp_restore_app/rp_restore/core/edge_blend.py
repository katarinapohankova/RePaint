from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None


def _gaussian_blur_f32(img: np.ndarray, ksize: int, sigma: float) -> np.ndarray:
    if ksize % 2 == 0:
        ksize += 1

    if cv2 is not None:
        return cv2.GaussianBlur(img, (ksize, ksize), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REPLICATE)

    out = img.astype(np.float32)
    r = max(1, ksize // 2)
    kernel = np.ones(2 * r + 1, dtype=np.float32) / float(2 * r + 1)

    for _ in range(3):
        out = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), 0, out)
        out = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), 1, out)

    return out


def _distance_to_edge(edge_remove_mask: np.ndarray) -> np.ndarray:
    inv = (~edge_remove_mask).astype(np.uint8)

    if cv2 is not None:
        return cv2.distanceTransform(inv, distanceType=cv2.DIST_L2, maskSize=3).astype(np.float32)

    dist = np.full(edge_remove_mask.shape, 1e6, dtype=np.float32)
    dist[edge_remove_mask] = 0.0
    return dist


def blend_across_edge(composited_rgb: np.ndarray, damage_mask: np.ndarray, edge_remove_mask: np.ndarray, filled_mask: np.ndarray, buffer: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Vytvorí plynulý farebný prechod cez miesto, kde bola hrana
    """
    buffer = int(max(1, buffer))

    if composited_rgb.ndim != 3 or composited_rgb.shape[2] < 3:
        raise ValueError("composited_rgb must be (H, W, 3)")

    h, w = damage_mask.shape
    if edge_remove_mask.shape != (h, w) or filled_mask.shape != (h, w):
        raise ValueError("masks must have the same shape")

    if not edge_remove_mask.any():
        return None, None

    dist = _distance_to_edge(edge_remove_mask)

    band = (dist <= float(buffer)) & damage_mask
    if not band.any():
        return None, None

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
    blended = num / safe_den[..., None]

    support_ok = den > 0.05
    band_valid = band & support_ok

    if not band_valid.any():
        return None, None

    blended_rgb = np.clip(blended, 0, 255).astype(np.uint8)
    return band_valid, blended_rgb