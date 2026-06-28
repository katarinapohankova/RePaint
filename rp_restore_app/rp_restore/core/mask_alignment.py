from __future__ import annotations

from typing import Sequence, Tuple

import cv2
import numpy as np


Point = Tuple[float, float]

def compute_homography(src_points: Sequence[Point], dst_points: Sequence[Point]) -> np.ndarray:
    """
    Vypočíta homografiu H tak, že body v src_points (napr. maska) sa mapujú na body v dst_points (napr. obraz)
    - vyžaduje aspoň 4 páry bodov,
    - funguje pre N >= 4 bodov pomocou cv2.findHomography + ransac
    """
    src_list = list(src_points)
    dst_list = list(dst_points)

    if len(src_list) != len(dst_list):
        raise ValueError("Number of points on mask and image must be the same")
    if len(src_list) < 4:
        raise ValueError("At least 4 point pairs are required to compute homography")

    src = np.array(src_list, dtype=np.float32)
    dst = np.array(dst_list, dtype=np.float32)

    H, inliers = cv2.findHomography(src, dst, method=cv2.RANSAC)
    if H is None:
        raise RuntimeError("Homography estimation failed")

    return H


def warp_mask_to_image(mask_rgb: np.ndarray, H: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
    """
    Aplikuje homografiu H na masku a vracia ju v rozlíšení target_size (width, height) v RGB (uint8)
    """
    #mask_rgb -np.ndarray (H, W, 3) alebo (H, W, 4)
    if mask_rgb.ndim != 3:
        raise ValueError("mask_rgb must be an RGB/RGBA image (H, W, C)")

    h = target_size[1]
    w = target_size[0]

    #ak je RGBA, prevedieme na RGB
    if mask_rgb.shape[2] == 4:
        mask_rgb = mask_rgb[..., :3]

    warped = cv2.warpPerspective(mask_rgb, H, (w, h), flags=cv2.INTER_LINEAR)
    warped = np.clip(warped, 0, 255).astype(np.uint8)
    return warped

def rgb_to_damage_mask(mask_rgb: np.ndarray) -> np.ndarray:
    """
    Prevedie RGB (alebo RGBA) masku na 2D bool damage masku (true = poškodené miesto)
    - okrem toho masku jemne zväčšíme (okraje vloženej masky nie sú úplne biele)
    """

    #ak už je binárny /grayscale obraz
    if mask_rgb.ndim == 2:
        damage = mask_rgb > 0
        #malé rozšírenie okolo existujúcich bielych pixelov
        damage_u8 = damage.astype(np.uint8) * 255
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(damage_u8, kernel, iterations=1)
        return dilated > 0

    if mask_rgb.ndim != 3:
        raise ValueError("mask_rgb must be 2D or 3D image")

    #odstránime alfu, ak je RGBA
    if mask_rgb.shape[2] == 4:
        rgb = mask_rgb[..., :3]
    else:
        rgb = mask_rgb

    #zaistíme uint8
    if rgb.dtype != np.uint8:
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    #kanály
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)

    #"skoro biela"
    BRIGHT_THR = 240
    SAT_DIFF_THR = 25 #max rozdiel medzi R,G,B

    bright = maxc >= BRIGHT_THR
    low_sat = (maxc - minc) <= SAT_DIFF_THR

    damage = bright & low_sat

    #málo rozšírime masku v okolí bielych pixelov
    damage_u8 = damage.astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(damage_u8, kernel, iterations=1)

    damage_dilated = dilated > 0
    return damage_dilated