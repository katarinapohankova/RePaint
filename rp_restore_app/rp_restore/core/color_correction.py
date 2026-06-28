from __future__ import annotations

import numpy as np


#Referenčné sRGB hodnoty (8-bit) pre ColorChecker Classic (24 patch)
COLORCHECKER_SRGB_24 = np.array(
    [
        [115,  82,  68], [194, 150, 130], [ 98, 122, 157], [ 87, 108,  67], [133, 128, 177], [103, 189, 170],
        [214, 126,  44], [ 80,  91, 166], [193,  90,  99], [ 94,  60, 108], [157, 188,  64], [224, 163,  46],
        [ 56,  61, 150], [ 70, 148,  73], [175,  54,  60], [231, 199,  31], [187,  86, 149], [  8, 133, 161],
        [243, 243, 242], [200, 200, 200], [160, 160, 160], [122, 122, 121], [ 85,  85,  85], [ 52,  52,  52],
    ],
    dtype=np.float32,
)


def estimate_correction_matrix_affine(measured_colors: np.ndarray, reference_colors: np.ndarray) -> np.ndarray:
    """
    Spočíta affine maticu 3x4: [R G B 1] -> [R' G' B']
    -measured_colors: (N,3) float alebo uint8
    -reference_colors: (N,3) float alebo uint8
    vráti: matrix shape (3,4) float32
    """
    meas = np.asarray(measured_colors, dtype=np.float32)
    ref = np.asarray(reference_colors, dtype=np.float32)

    if meas.ndim != 2 or meas.shape[1] != 3:
        raise ValueError("measured_colors must be shape (N,3)")
    if ref.ndim != 2 or ref.shape[1] != 3:
        raise ValueError("reference_colors must be shape (N,3)")
    if meas.shape[0] != ref.shape[0]:
        raise ValueError("measured_colors and reference_colors must have same N")

    #A = [R G B 1]
    ones = np.ones((meas.shape[0], 1), dtype=np.float32)
    A = np.concatenate([meas, ones], axis=1)  

    #A * X ~= ref, kde X má shape (4,3)
    X, *_ = np.linalg.lstsq(A, ref, rcond=None)
    M = X.T  #(3,4)
    return M.astype(np.float32)


def apply_color_correction(image: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """
    Aplikuje farebnú korekciu na obraz
    -image: HxWx3 uint8 
    -matrix: 3x3 alebo 3x4 
    vráti rovnaký dtype ako vstup
    """
    img = np.asarray(image)
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError("apply_color_correction expects image HxWx3")

    M = np.asarray(matrix, dtype=np.float32)
    if M.shape not in [(3, 3), (3, 4)]:
        raise ValueError("matrix must be 3x3 or 3x4")

    dtype = img.dtype
    if dtype == np.uint16:
        maxv = 65535.0
    else:
        maxv = 255.0

    x = img.astype(np.float32)

    if M.shape == (3, 3):
        y = x @ M.T
    else:
        y = x @ M[:, :3].T + M[:, 3]

    y = np.clip(y, 0.0, maxv)
    return y.astype(dtype)


def rms_rgb(measured: np.ndarray, reference: np.ndarray) -> float:
    """
    RMS chyba v RGB priestore (0..255)
    """
    meas = np.asarray(measured, dtype=np.float32)
    ref = np.asarray(reference, dtype=np.float32)
    diff = meas - ref
    return float(np.sqrt(np.mean(diff * diff)))