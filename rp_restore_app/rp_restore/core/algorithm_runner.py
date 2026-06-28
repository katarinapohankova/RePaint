from __future__ import annotations

from dataclasses import dataclass
import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

import numpy as np

import subprocess
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
    partial_noise: float = 0.7
    seed: Optional[int] = None
    progress_callback: Optional[callable] = None
    texture_params: Optional[TextureAlgorithmParams] = None

@dataclass
class TextureAlgorithmParams:
    texture_name: str = "texture_H"
    colors: list[tuple[int, int, int]] | None = None
    global_scale: float = 1.0
    rotation: float = 0.0
    seed: Optional[int] = None


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
    _REMOTE_REALISTIC_MAX_PIXELS = 2_073_600
    _REMOTE_REALISTIC_PROMPT = "DURER_RESTO"
    _REMOTE_REALISTIC_NUM_INFERENCE_STEPS = 30
    _REMOTE_REALISTIC_GUIDANCE_SCALE = 30.0
    _REMOTE_REALISTIC_LORA_SCALE = 1.0

    # REALISTIC_CMD = [sys.executable, str(_ALGO_DIR / "realistic_inpaint.py")]  # zatiaľ placeholder
    # TEXTURE_CMD = [sys.executable, str(_ALGO_DIR / "texture_inpaint.py")]

    @classmethod
    def run(cls, request: AlgorithmRequest) -> AlgorithmResult:
        if request.mock:
            return cls._run_mock(request)

        if request.algorithm_type == AlgorithmType.REALISTIC:
            return cls._run_remote_realistic(request)
        if request.algorithm_type == AlgorithmType.TEXTURE:
            return cls._run_texture_generator(request)

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
    
    @classmethod
    def _run_texture_generator(cls, request: AlgorithmRequest) -> AlgorithmResult:
        """
        Spustí texture algoritmus z priečinka
        - dočasne pridáme jeho priečinky do sys.path a nastavíme pracovný priečinok na priečinok algoritmu
        -dočasne vypneme cv2.imshow/cv2.waitKey, aby aplikácia nezamrzla
        (potom sa to upraví aby to fungovalo keď bude algoritmus ako python package)
        """
        current = cls._ensure_rgb(request.current_image)
        h, w, _ = current.shape

        selected_mask = request.selected_mask.astype(bool)
        remaining_mask = request.remaining_mask.astype(bool)

        if selected_mask.shape != (h, w) or remaining_mask.shape != (h, w):
            raise ValueError("Texture masks must have the same shape as current_image")

        apply_mask = selected_mask & remaining_mask

        if not bool(apply_mask.any()):
            raise ValueError("Selection does not contain any remaining damaged pixels")

        ys, xs = np.where(apply_mask)
        y_min = int(ys.min())
        y_max = int(ys.max()) + 1
        x_min = int(xs.min())
        x_max = int(xs.max()) + 1

        bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

        texture_params = request.texture_params or TextureAlgorithmParams()

        colors = texture_params.colors
        if not colors:
            raise ValueError("Texture algorithm requires at least one color")

        normalized_colors: list[tuple[int, int, int]] = []
        for color in colors:
            if len(color) < 3:
                raise ValueError("Each texture color must be an RGB triplet")

            r, g, b = color[:3]
            normalized_colors.append((int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b)))))

        texture_pipeline_dir = cls._get_algo_dir() / "texture_generation_pipeline"

        if not texture_pipeline_dir.exists():
            raise RuntimeError(f"Texture generation pipeline was not found: {texture_pipeline_dir}")

        texture_pipeline_parent = texture_pipeline_dir.parent

        old_cwd = Path.cwd()
        added_paths: list[str] = []

        #musí byť na sys.path aj samotný priečinok texture_generation_pipeline
        for path in (texture_pipeline_parent, texture_pipeline_dir):
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
                added_paths.append(path_str)

        old_imshow = None
        old_wait_key = None

        try:
            #počas behu ho spúšťame z jeho vlastného priečinka
            os.chdir(texture_pipeline_dir)

            try:
                import cv2

                old_imshow = cv2.imshow
                old_wait_key = cv2.waitKey

                #v aplikácii nechceme otvárať debug openCV okná
                cv2.imshow = lambda *args, **kwargs: None
                cv2.waitKey = lambda *args, **kwargs: 1
            except Exception:
                old_imshow = None
                old_wait_key = None

            try:
                from external_algorithms.texture_generation_pipeline.texture_generator_pipeline import (Parameters, generate_infill)
            except ImportError as e:
                raise RuntimeError(
                    "Texture generation pipeline could not be imported "
                    f"import error: {e!r}"
                ) from e

            params = Parameters(
                texture_name=texture_params.texture_name,
                colors=normalized_colors,
                count=len(normalized_colors),

                #tieto parametre zatiaľ nechávame na konkrétnych hodnotách
                scale_x=1.0,
                scale_y=1.0,
                density_x=0.0,
                density_y=0.0,

                rotation=float(texture_params.rotation),
                global_scale=float(texture_params.global_scale),
                seed=texture_params.seed,
            )

            mask_for_algorithm = np.where(apply_mask, 255, 0).astype(np.uint8)

            output_full = generate_infill(current, mask_for_algorithm, params)

            #pre istotu ošetríme aj prípad, keby algoritmus vrátil tuple
            if isinstance(output_full, tuple):
                output_full = output_full[0]

            if output_full.ndim != 3 or output_full.shape[:2] != (h, w):
                raise RuntimeError(f"Texture algorithm returned invalid output shape: {output_full.shape}")

            output_rgb = output_full[..., :3].astype(np.uint8)

            x, y, bw, bh = bbox
            output_patch = output_rgb[y:y + bh, x:x + bw, :]

            patch_rgba = np.zeros((bh, bw, 4), dtype=np.uint8)
            patch_rgba[..., :3] = output_patch
            patch_rgba[..., 3] = 255

            return AlgorithmResult(
                output_patch=patch_rgba,
                bbox=bbox,
                log_messages=[
                    f"Texture: {texture_params.texture_name}",
                    f"Colors: {normalized_colors}",
                    f"global_scale: {texture_params.global_scale}",
                    f"rotation: {texture_params.rotation}",
                    f"seed: {texture_params.seed}",
                ],
            )

        finally:
            os.chdir(old_cwd)

            if old_imshow is not None and old_wait_key is not None:
                try:
                    import cv2

                    cv2.imshow = old_imshow
                    cv2.waitKey = old_wait_key
                except Exception:
                    pass

            for path_str in added_paths:
                try:
                    sys.path.remove(path_str)
                except ValueError:
                    pass

    @classmethod
    def _run_remote_realistic(cls, request: AlgorithmRequest) -> AlgorithmResult:
        """
        Spustí realistic fill cez remote klienta painting_inpaint.remote
        V request.current_image už očakávame výsek obrazu
        V request.selected_mask -výsek masky rovnakého rozmeru
        (request.window_bbox sa používa iba interne, aby sme vedeli vrátiť patch na správne miesto v aplikácii)
        """
        if request.window_bbox is None:
            raise ValueError("REALISTIC algorithm requires request.window_bbox")

        image_patch = cls._ensure_rgb(request.current_image)
        ph, pw, _ = image_patch.shape

        mask_patch = request.selected_mask.astype(bool)
        if mask_patch.shape != (ph, pw):
            raise ValueError("selected_mask must have the same shape as current_image patch (H, W)")

        if pw <= 0 or ph <= 0:
            raise ValueError("Realistic fill patch has invalid size")

        if pw * ph > cls._REMOTE_REALISTIC_MAX_PIXELS:
            raise ValueError(
                f"Realistic fill patch is too large ({pw}×{ph}) "
                f"limit is {cls._REMOTE_REALISTIC_MAX_PIXELS} pixels"
            )

        if not bool(mask_patch.any()):
            raise ValueError("Selected mask patch is empty")

        partial_noise = max(0.0, min(1.0, float(request.partial_noise)))

        try:
            from painting_inpaint.remote import RestorationClient, RemoteRestorationError
        except ImportError as e:
            raise RuntimeError(
                "Balík painting-inpaint-remote není nainstalovaný "
            ) from e

        base_tmp = Path(os.environ.get("LOCALAPPDATA", ".")) / "RP-Restore" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)

        tmpdir_path = base_tmp / f"remote_realistic_{uuid.uuid4().hex}"
        tmpdir_path.mkdir(parents=True, exist_ok=True)

        log_msgs: List[str] = []

        try:
            input_patch_path = tmpdir_path / "input_patch.png"
            mask_patch_path = tmpdir_path / "mask_patch.png"

            image_io.save_image(input_patch_path, image_patch)
            image_io.save_mask(mask_patch_path, mask_patch)

            def _on_progress(event) -> None:
                """
                Callback pre priebežné hlášky z algoritmu
                Zatiaľ ich len ukladáme do logu výsledku
                """
                message = getattr(event, "message", None)
                current_step = getattr(event, "current", None)
                total_steps = getattr(event, "total", None)

                if current_step is not None and total_steps is not None:
                    if message:
                        log_msgs.append(f"{message} ({current_step}/{total_steps})")
                    else:
                        log_msgs.append(f"Step {current_step}/{total_steps}")
                elif message:
                    log_msgs.append(str(message))

                if request.progress_callback is not None:
                    request.progress_callback(str(message) if message else "", current_step, total_steps)

            client = RestorationClient.from_env(provider="modal")

            try:
                result = client.restore_file(
                    str(input_patch_path),
                    str(mask_patch_path),
                    on_progress=_on_progress,
                    prompt=cls._REMOTE_REALISTIC_PROMPT,
                    partial_noise=partial_noise,
                    num_inference_steps=cls._REMOTE_REALISTIC_NUM_INFERENCE_STEPS,
                    guidance_scale=cls._REMOTE_REALISTIC_GUIDANCE_SCALE,
                    seed=request.seed,
                    lora_scale=cls._REMOTE_REALISTIC_LORA_SCALE,
                    output_format="png",
                )
            except RemoteRestorationError as e:
                raise RuntimeError(f"Remote realistic fill failed: {e}") from e

            output_img = np.array(result.image.convert("RGBA"), dtype=np.uint8)

            if output_img.shape[0] != ph or output_img.shape[1] != pw:
                raise RuntimeError(
                    f"Remote realistic output has wrong size "
                    f"Expected ({ph}, {pw}), got {output_img.shape[:2]}"
                )

            status = getattr(result, "status", None)
            job_id = getattr(result, "job_id", None)

            if status is not None:
                log_msgs.append(f"Remote status: {status}")
            if job_id is not None:
                log_msgs.append(f"Remote job id: {job_id}")

            log_msgs.append(f"partial_noise: {partial_noise}")
            if request.seed is not None:
                log_msgs.append(f"seed: {request.seed}")

            return AlgorithmResult(output_patch=output_img, bbox=request.window_bbox, log_messages=log_msgs)

        finally:
            shutil.rmtree(tmpdir_path, ignore_errors=True)

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
