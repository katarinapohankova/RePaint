from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np


Point = tuple[float, float]

def compute_homography(src_points: Sequence[Point], dst_points: Sequence[Point]) -> np.ndarray:
    """Vypočíta homografiu medzi bodmi masky a bodmi obrazu"""
    src_list = list(src_points)
    dst_list = list(dst_points)

    if len(src_list) != len(dst_list):
        raise ValueError("Number of points on mask and image must be the same")
    if len(src_list) < 4:
        raise ValueError("At least 4 point pairs are required to compute homography")

    src = np.array(src_list, dtype=np.float32)
    dst = np.array(dst_list, dtype=np.float32)

    H, _ = cv2.findHomography(src, dst, method=cv2.RANSAC)
    if H is None:
        raise RuntimeError("Homography estimation failed")

    return H


def warp_mask_to_image(mask_rgb: np.ndarray, H: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
    """
    Aplikuje homografiu H na masku a vracia ju v rozlíšení cieľového obrazu
    """
    if mask_rgb.ndim != 3 or mask_rgb.shape[2] not in (3, 4):
        raise ValueError("mask_rgb must be an RGB/RGBA image (H, W, C)")

    H = np.asarray(H, dtype=np.float64)
    if H.shape != (3, 3):
        raise ValueError("H must be a 3x3 homography matrix")

    #target_size je vo formáte (width, height), rovnako ako očakáva OpenCV
    w, h = target_size
    if w <= 0 or h <= 0:
        raise ValueError("target_size must contain positive width and height")

    #ak je RGBA, odstránime alfu
    if mask_rgb.shape[2] == 4:
        mask_rgb = mask_rgb[..., :3]

    warped = cv2.warpPerspective(mask_rgb, H, (int(w), int(h)), flags=cv2.INTER_LINEAR)
    warped = np.clip(warped, 0, 255).astype(np.uint8)
    return warped

def rgb_to_damage_mask(mask_rgb: np.ndarray) -> np.ndarray:
    """Prevedie grayscale, RGB alebo RGBA masku na 2D damage masku"""
    #grayscale masku berieme ako poškodenie všade tam, kde má nenulovú hodnotu
    if mask_rgb.ndim == 2:
        damage = mask_rgb > 0
        return _dilate_damage_mask(damage)

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

    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)

    #za poškodenie považujeme skoro biele a málo saturované pixely
    bright_thr = 240
    sat_diff_thr = 25

    bright = maxc >= bright_thr
    low_sat = (maxc - minc) <= sat_diff_thr
    damage = bright & low_sat

    return _dilate_damage_mask(damage)

def _dilate_damage_mask(damage: np.ndarray) -> np.ndarray:
    """Jemne rozšíri damage masku o susedné pixely"""
    #OpenCV dilate pracuje s uint8 maskou, preto bool masku najprv prevedieme
    damage_u8 = damage.astype(np.uint8) * 255

    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(damage_u8, kernel, iterations=1)

    return dilated > 0