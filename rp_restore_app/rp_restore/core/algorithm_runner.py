from __future__ import annotations

from dataclasses import dataclass
import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

import numpy as np

import subprocess
import tempfile
import sys
import os
import uuid
import shutil

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
    window_bbox: tuple[int,int,int,int] | None = None #(x,y,w,h) pre realistic
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
    _ALGO_DIR_DEV = _REPO_ROOT / "external_algorithms"

    # REALISTIC_CMD = [sys.executable, str(_ALGO_DIR / "realistic_inpaint.py")]  # zatiaľ placeholder
    # TEXTURE_CMD = [sys.executable, str(_ALGO_DIR / "texture_inpaint.py")]

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

        #mock pre REALISTIC (s window_bbox)
        if request.algorithm_type == AlgorithmType.REALISTIC and request.window_bbox is not None:
            x, y, ww, wh = request.window_bbox
            if ww <= 0 or wh <= 0:
                empty = np.zeros((1, 1, 4), dtype=np.uint8)
                return AlgorithmResult(output_patch=empty, bbox=(0, 0, 1, 1), log_messages=["MOCK invalid window_bbox"])

            #hnedá farba 
            rgb_color = np.array([150, 100, 60], dtype=np.uint8)

            patch_rgba = np.zeros((wh, ww, 4), dtype=np.uint8)
            patch_rgba[..., :3] = rgb_color
            patch_rgba[..., 3] = 255

            return AlgorithmResult(output_patch=patch_rgba, bbox=(x, y, ww, wh), log_messages=[f"MOCK REALISTIC window {ww}x{wh} filled"])

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

        #tmp priecinok
        base_tmp = Path(os.environ.get("LOCALAPPDATA", ".")) / "RP-Restore" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)

        tmpdir_path = base_tmp / f"run_{uuid.uuid4().hex}"
        tmpdir_path.mkdir(parents=True, exist_ok=True)

        log_msgs: List[str] = []

        try:
            input_image_path = tmpdir_path / "input_image.png"
            mask_selected_path = tmpdir_path / "mask_selected.png"
            mask_all_path = tmpdir_path / "mask_all.png"
            output_path = tmpdir_path / "output.png"

            #uložíme current_image
            image_io.save_image(input_image_path, current)

            #uložíme masky
            image_io.save_mask(mask_selected_path, sel)
            image_io.save_mask(mask_all_path, rem)

            python_for_algo = cls._get_algorithms_python()
            algo_dir = cls._get_algo_dir()

            #výber príkazu podľa typu algoritmu
            if request.algorithm_type == AlgorithmType.TEXTURE:
                #TEXTURE -teraz skript vracia full image (H,W,3/4) a my vyrezeme patch podľa selection ale to sa asi zmení na iba generovanie textúry
                ys, xs = np.where(sel)
                if ys.size == 0:
                    raise ValueError("Selection is empty – nothing to process")

                y_min = int(ys.min())
                y_max = int(ys.max())
                x_min = int(xs.min())
                x_max = int(xs.max())
                bbox = (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)

                script_path = algo_dir / "texture_inpaint.py"
                cmd = [python_for_algo, str(script_path)]

            elif request.algorithm_type == AlgorithmType.REALISTIC:
                #REALISTIC -vyžaduje window_bbox a vracia patch okna (w,h)
                if request.window_bbox is None:
                    raise ValueError("REALISTIC algorithm requires request.window_bbox")

                wx, wy, ww, wh = request.window_bbox
                if ww <= 0 or wh <= 0:
                    raise ValueError("window_bbox is invalid (w/h <= 0)")
                if ww > 1024 or wh > 1024:
                    raise ValueError("window_bbox exceeds max size 1024x1024")

                #okno musí byť v hraniciach obrazu
                if wx < 0 or wy < 0 or wx + ww > w or wy + wh > h:
                    raise ValueError("window_bbox is out of image bounds")

                bbox = (wx, wy, ww, wh)

                script_path = algo_dir / "realistic_inpaint.py"
                cmd = [python_for_algo, str(script_path)]

                #pridáme parametre okna
                cmd += ["--window_x", str(wx), "--window_y", str(wy), "--window_w", str(ww), "--window_h", str(wh)]

            else:
                raise RuntimeError(f"Unsupported algorithm type: {request.algorithm_type}")

            #spoločné CLI argumenty
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

            _debug_log("RUN CMD: " + " ".join(cmd))

            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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

            if request.algorithm_type == AlgorithmType.TEXTURE:
                #očakávame full image -> vyrežeme podľa bbox selection
                x0, y0, bw, bh = bbox
                output_patch = output_img[y0:y0+bh, x0:x0+bw, :]
                return AlgorithmResult(output_patch=output_patch, bbox=bbox, log_messages=log_msgs)

            else:
                #REALISTIC -očakávame patch presne veľkosti okna (wh, ww)
                wx, wy, ww, wh = bbox
                if output_img.shape[0] != wh or output_img.shape[1] != ww:
                    #ak by náhodou vrátili full image
                    raise RuntimeError(f"Realistic output has wrong size. Expected ({wh},{ww}), got {output_img.shape[:2]}")
                return AlgorithmResult(output_patch=output_img, bbox=bbox, log_messages=log_msgs)

        finally:
            shutil.rmtree(tmpdir_path, ignore_errors=True)
            
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
    @classmethod
    def _get_algorithms_python(cls) -> str:
        if cls._is_frozen():
            exe_dir = Path(sys.executable).resolve().parent
            py = exe_dir / "_internal" / "algo_venv" / "Scripts" / "python.exe"
            return str(py)
        return sys.executable
    
    @staticmethod
    def _is_frozen() -> bool:
        return bool(getattr(sys, "frozen", False))

    @classmethod
    def _get_algo_dir(cls) -> Path:
        if cls._is_frozen():
            exe_dir = Path(sys.executable).resolve().parent
            return exe_dir / "_internal" / "external_algorithms"
        return cls._ALGO_DIR_DEV

def _debug_log(msg: str) -> None:
    log_dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "RP-Restore"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "debug_algo.log"
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
