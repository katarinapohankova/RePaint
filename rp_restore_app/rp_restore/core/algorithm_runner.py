from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import numpy as np

import subprocess
import tempfile
import sys

from rp_restore.io import image_io


class AlgorithmType(str, Enum):
    REALISTIC = "realistic"
    TEXTURE = "texture"


@dataclass
class AlgorithmRequest:
    original_image: np.ndarray  #(H, W, 3) alebo (H, W, 4)
    current_image: np.ndarray   #(H, W, 3) alebo (H, W, 4)
    selected_mask: np.ndarray   #2Dbool, rovnaký tvar ako obraz
    remaining_mask: np.ndarray  #2D bool
    algorithm_type: AlgorithmType
    device: str = "cpu" # "cpu" | "cuda"
    mock: bool = False  #True = nepúšťaj subprocess, sprav demo výstup


@dataclass
class AlgorithmResult:
    output_patch: np.ndarray    #(h, w, 4) RGBA
    bbox: tuple[int, int, int, int]     #(x, y, w, h)
    log_messages: List[str]


class AlgorithmRunner:
    """
    Spúšťa externé algoritmy

    CLI argumenty:
      --input_image <path>   #current_image
      --mask_selected   <path>   #binárna maska vybratej oblasti
      --mask_all    <path>   #binárna maska všetkých zostávajúcich poškodených miest
      --output  <path>   #výstupný obrázok (celý obraz alebo len patch)
      --device  cpu|cuda
      --mock    (voliteľný prepínač)

    predpokladáme, že výstup je obrázok rovnakého rozmeru ako input_image
    z neho vyrežeme patch podľa bbox vypočítaného zo selected_mask
    """

    #toto sa musí prispôsobiť algoritmom
    # REALISTIC_CMD = ["python", "realistic_inpaint.py"]
    # TEXTURE_CMD = ["python", "texture_inpaint.py"]
    _REPO_ROOT = Path(__file__).resolve().parents[2]  # rp_restore/core -> rp_restore -> repo root
    _ALGO_DIR = _REPO_ROOT / "external_algorithms"

    REALISTIC_CMD = [sys.executable, str(_ALGO_DIR / "realistic_inpaint.py")]  # zatiaľ placeholder
    TEXTURE_CMD = [sys.executable, str(_ALGO_DIR / "texture_inpaint.py")]

    @classmethod
    def run(cls, request: AlgorithmRequest) -> AlgorithmResult:
        if request.mock:
            return cls._run_mock(request)

        return cls._run_external(request)

    #MOCK režim 
    @classmethod
    def _run_mock(cls, request: AlgorithmRequest) -> AlgorithmResult:
        """
        nevolá externý skript, ale
          - vezme current_image
          - podľa typu algoritmu vyberie farbu na zafarbenie (realistic -hnedá, texture -zelená)
          - a vyplní vybranú oblasť tou farbou
        """
        current = cls._ensure_rgb(request.current_image)
        h, w, _ = current.shape

        sel = request.selected_mask

        #bbox selection
        ys, xs = np.where(sel)
        if ys.size == 0:
            empty = np.zeros((1, 1, 4), dtype=np.uint8)
            return AlgorithmResult(output_patch=empty, bbox=(0, 0, 1, 1), log_messages=["MOCK Empty selection"])

        y_min = int(ys.min())
        y_max = int(ys.max())
        x_min = int(xs.min())
        x_max = int(xs.max())
        bbox = (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)

        #farby podľa typu algoritmu
        if request.algorithm_type == AlgorithmType.REALISTIC:
            #hnedá
            rgb_color = np.array([150, 100, 60], dtype=np.uint8)
        else:
            #zelená 
            rgb_color = np.array([60, 150, 90], dtype=np.uint8)

        patch_h = bbox[3]
        patch_w = bbox[2]

        patch_rgba = np.zeros((patch_h, patch_w, 4), dtype=np.uint8)
        patch_rgba[..., :3] = rgb_color
        patch_rgba[..., 3] = 255

        return AlgorithmResult(
            output_patch=patch_rgba,
            bbox=bbox,
            log_messages=[
                f"MOCK Algorithm {request.algorithm_type.value} "
                f"filled selection with fixed color {rgb_color.tolist()}"
            ],
        )

    #spustenie externého skriptu
    @classmethod
    def _run_external(cls, request: AlgorithmRequest) -> AlgorithmResult:
        current = cls._ensure_rgb(request.current_image)
        h, w, _ = current.shape

        sel = request.selected_mask
        rem = request.remaining_mask

        if sel.shape != (h, w) or rem.shape != (h, w):
            raise ValueError("Masks must have the same shape as current_image (H, W)")

        ys, xs = np.where(sel)
        if ys.size == 0:
            raise ValueError("Selection is empty – nothing to process")

        #bbox selection
        y_min = int(ys.min())
        y_max = int(ys.max())
        x_min = int(xs.min())
        x_max = int(xs.max())
        bbox = (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)

        # debug_root = Path("tmp")  
        # debug_root.mkdir(parents=True, exist_ok=True)

        # tmpdir_path = Path(tempfile.mkdtemp(prefix="algo_", dir=str(debug_root)))
        with tempfile.TemporaryDirectory() as tmpdir:
        # try:
            tmpdir_path = Path(tmpdir)

            input_image_path = tmpdir_path / "input_image.png"
            mask_selected_path = tmpdir_path / "mask_selected.png"
            mask_all_path = tmpdir_path / "mask_all.png"
            output_path = tmpdir_path / "output.png"

            #uložíme current_image
            image_io.save_image(input_image_path, current)

            #uložíme masky
            image_io.save_mask(mask_selected_path, sel)
            image_io.save_mask(mask_all_path, rem)

            #výber príkazu podľa typu algoritmu
            if request.algorithm_type == AlgorithmType.REALISTIC:
                cmd = cls.REALISTIC_CMD.copy()
            else:
                cmd = cls.TEXTURE_CMD.copy()

            cmd += [
                "--input_image",
                str(input_image_path),
                "--mask_selected",
                str(mask_selected_path),
                "--mask_all",
                str(mask_all_path),
                "--output",
                str(output_path),
                "--device",
                request.device,
            ]

            if request.mock:
                cmd.append("--mock")

            #spustíme subprocess
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            log_msgs: List[str] = []
            if proc.stdout:
                log_msgs.extend(proc.stdout.strip().splitlines())
            if proc.stderr:
                log_msgs.append("stderr")
                log_msgs.extend(proc.stderr.strip().splitlines())

            if proc.returncode != 0:
                raise RuntimeError(
                    f"Algorithm process failed with code {proc.returncode}\n"
                    + "\n".join(log_msgs)
                )

            #načítame výstupný obrázok
            output_img = image_io.load_image(output_path)  #RGBA (H, W, 4)
        # finally:
        #     pass
        
        #vyrežeme patch podľa bbox
        x, y, w_box, h_box = bbox
        output_patch = output_img[y : y + h_box, x : x + w_box, :]

        return AlgorithmResult(output_patch=output_patch, bbox=bbox, log_messages=log_msgs)

    @staticmethod
    def _ensure_rgb(image: np.ndarray) -> np.ndarray:
        """
        zabezpečí, že obraz je (H, W, 3) RGB, uint8
        """
        arr = image
        if arr.ndim != 3:
            raise ValueError("Expected 3D image array")

        if arr.shape[2] == 4:
            arr = arr[..., :3]

        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8)

        return arr
