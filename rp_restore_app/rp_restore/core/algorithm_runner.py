from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np

from rp_restore.io import image_io


class AlgorithmType(str, Enum):
    REALISTIC = "realistic"
    TEXTURE = "texture"

class RealisticFillMode(str, Enum):
    BASIC = "basic"
    GUIDED = "guided"


@dataclass
class TextureAlgorithmParams:
    """Parametre odovzdávané textúrovému algoritmu"""

    texture_name: str = "texture_J"

    colors: list[tuple[int, int, int]] | None = None
    color_strengths: list[float] | None = None

    scale_x: float = 1.0
    scale_y: float = 1.0
    density_x: float = 0.0
    density_y: float = 0.0
    rotation: float = 0.0
    global_scale: float = 1.0

    white_background: bool = True
    background_brightness: float = 1.0

    generate_square: bool = False
    width: int = 1024
    height: int = 1024

    seed: int | None = 42


@dataclass
class AlgorithmRequest:
    """Vstupné dáta a nastavenia pre spustenie algoritmu"""

    original_image: np.ndarray  #(H, W, 3) alebo (H, W, 4)
    current_image: np.ndarray  #(H, W, 3) alebo (H, W, 4)
    selected_mask: np.ndarray  #2D bool, rovnaký tvar ako obraz alebo výrez
    remaining_mask: np.ndarray  #2D bool
    algorithm_type: AlgorithmType
    window_bbox: tuple[int, int, int, int] | None = None  #(x, y, w, h) pre realistic fill
    device: str = "cpu"  #"cpu" alebo "cuda"
    mock: bool = False
    partial_noise: float = 0.7
    seed: int | None = None
    realistic_mode: RealisticFillMode = RealisticFillMode.BASIC
    progress_callback: Callable[[str, int | None, int | None], None] | None = None
    texture_params: TextureAlgorithmParams | None = None


@dataclass
class AlgorithmResult:
    """Výsledný patch algoritmu a sprievodné log správy"""

    output_patch: np.ndarray  #(h, w, 4) RGBA
    bbox: tuple[int, int, int, int]  #(x, y, w, h)
    log_messages: list[str]

class RemoteRestorationAccessError(RuntimeError):
    """
    Chyba prístupových údajov alebo endpointu remote služby
    používa sa na odlíšenie zlého API kľúča alebo endpoint URL od bežných chýb algoritmu
    """

class AlgorithmRunner:
    """
    Spúšťa externé algoritmy používané aplikáciou

    Realistické doplnenie sa spúšťa cez remote klienta painting_inpaint.remote
    Texturové doplnenie sa spúšťa cez lokálne nainštalovaný balík texture_infill
    Mock režim vytvára jednoduchý farebný výstup bez volania externého algoritmu
    """

    _REMOTE_REALISTIC_MAX_PIXELS = 2_073_600
    _REMOTE_REALISTIC_PROMPT = "DURER_RESTO"
    _REMOTE_REALISTIC_NUM_INFERENCE_STEPS = 30
    _REMOTE_REALISTIC_GUIDANCE_SCALE = 30.0
    _REMOTE_REALISTIC_LORA_SCALE = 1.0

    @classmethod
    def run(cls, request: AlgorithmRequest) -> AlgorithmResult:
        """Spustí algoritmus podľa typu requestu"""
        if request.mock:
            return cls._run_mock(request)

        if request.algorithm_type == AlgorithmType.REALISTIC:
            return cls._run_remote_realistic(request)
        if request.algorithm_type == AlgorithmType.TEXTURE:
            return cls._run_texture_generator(request)

        raise ValueError(f"Unsupported algorithm type: {request.algorithm_type}")

    @classmethod
    def _run_mock(cls, request: AlgorithmRequest) -> AlgorithmResult:
        """
        Vytvorí jednoduchý demo výstup bez volania externého algoritmu
        realistic fill použije hnedú farbu, texture fill použije zelenú farbu
        """
        current = cls._ensure_rgb(request.current_image)
        h, w, _ = current.shape

        sel = request.selected_mask

        #mock pre REALISTIC s ručne zvoleným oknom
        if request.algorithm_type == AlgorithmType.REALISTIC and request.window_bbox is not None:
            x, y, ww, wh = request.window_bbox
            if ww <= 0 or wh <= 0:
                empty = np.zeros((1, 1, 4), dtype=np.uint8)
                return AlgorithmResult(output_patch=empty, bbox=(0, 0, 1, 1), log_messages=["MOCK invalid window_bbox"])

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

        if request.algorithm_type == AlgorithmType.REALISTIC:
            rgb_color = np.array([150, 100, 60], dtype=np.uint8)
        else:
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
    
    @staticmethod
    def get_available_texture_names() -> list[str]:
        """
        Vráti názvy modelov dostupných v nainštalovanom balíku texture_infill
        """
        try:
            from importlib.resources import files

            models_dir = files("texture_infill").joinpath("models")
        except (ImportError, ModuleNotFoundError, TypeError) as e:
            raise RuntimeError("Balík texture-infill není nainstalovaný nebo jej nelze načíst") from e

        model_suffix = "_transformer_weight.pth"
        texture_names: list[str] = []

        try:
            for item in models_dir.iterdir():
                if item.is_file() and item.name.endswith(model_suffix):
                    texture_name = item.name[:-len(model_suffix)]
                    texture_names.append(texture_name)
        except OSError as e:
            raise RuntimeError("Nepodařilo se načíst modely texturového algoritmu") from e

        return sorted(texture_names)

    @classmethod
    def generate_texture_material(cls, texture_params: TextureAlgorithmParams) -> np.ndarray:
        """
        Vygeneruje samostatnú textúru určenú na pridanie do panelu materiálov
        výsledkom je RGBA obraz požadovanej šírky a výšky
        """
        if texture_params.width <= 0 or texture_params.height <= 0:
            raise ValueError("Texture width and height must be positive")

        arguments = cls._create_texture_arguments(texture_params, generate_square=True)

        tex_image = np.zeros((1, 1, 3), dtype=np.uint8)
        tex_mask = np.zeros((1, 1), dtype=np.uint8)

        output = cls._call_texture_infill(tex_image, tex_mask, arguments)

        return cls._normalize_texture_output(output, expected_height=int(texture_params.height), expected_width=int(texture_params.width))

    @classmethod
    def _run_texture_generator(cls, request: AlgorithmRequest) -> AlgorithmResult:
        """
        Spustí nainštalovaný balík texture-infill nad aktívnym výberom používateľa
        """
        current = cls._ensure_rgb(request.current_image)
        image_height, image_width, _ = current.shape

        selected_mask = request.selected_mask.astype(bool)
        remaining_mask = request.remaining_mask.astype(bool)

        if selected_mask.shape != (image_height, image_width):
            raise ValueError("Texture selection mask has an invalid shape")

        if remaining_mask.shape != (image_height, image_width):
            raise ValueError("Texture remaining mask has an invalid shape")

        #algoritmus sa môže aplikovať iba na pixely, ktoré sú vo výbere a zároveň ešte patria medzi nevyplnené poškodené pixely
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

        #algoritmu stačí poslať ohraničujúci výrez
        image_crop = current[y_min:y_max, x_min:x_max, :]

        mask_crop = np.where(apply_mask[y_min:y_max, x_min:x_max], 255, 0).astype(np.uint8)

        #pri nepriehľadnom pozadí algoritmus vracia RGB
        #pri priehľadnom pozadí vracia RGBA, preto aj vstup bude ako štvor-kanálový obraz
        if texture_params.white_background:
            algorithm_image = image_crop
        else:
            algorithm_image = np.zeros((image_crop.shape[0], image_crop.shape[1], 4), dtype=np.uint8)
            algorithm_image[..., :3] = image_crop
            algorithm_image[..., 3] = 255

        arguments = cls._create_texture_arguments(texture_params, generate_square=False)

        output = cls._call_texture_infill(algorithm_image, mask_crop, arguments)

        patch_rgba = cls._normalize_texture_output(output, expected_height=bbox[3], expected_width=bbox[2])

        return AlgorithmResult(
            output_patch=patch_rgba,
            bbox=bbox,
            log_messages=[
                f"Texture: {texture_params.texture_name}",
                f"Colors: {arguments.colors}",
                f"Color strengths: {arguments.color_strengths}",
                f"Scale: ({arguments.scale_x}, {arguments.scale_y})",
                f"Density: ({arguments.density_x}, {arguments.density_y})",
                f"Rotation: {arguments.rotation}",
                f"Global scale: {arguments.global_scale}",
                f"Opaque background: {arguments.white_background}",
                f"Background brightness: {arguments.background_brightness}",
                f"Seed: {arguments.seed}",
            ],
        )

    @staticmethod
    def _create_texture_arguments(texture_params: TextureAlgorithmParams, generate_square: bool):
        """
        Prevedie parametre aplikácie na triedu Arguments z balíka texture-infill
        """
        try:
            from texture_infill.arguments import Arguments
        except ImportError as e:
            raise RuntimeError("Balík texture-infill není nainstalovaný v aktuálním prostředí") from e

        colors = texture_params.colors or []

        if not colors:
            raise ValueError("Texture algorithm requires at least one color")

        normalized_colors: list[tuple[int, int, int]] = []
        for color in colors:
            if len(color) != 3:
                raise ValueError("Each texture color must be an RGB triplet")

            normalized_color = tuple(max(0, min(255, int(channel))) for channel in color)
            normalized_colors.append(normalized_color)

        strengths = texture_params.color_strengths

        if strengths is None:
            normalized_strengths = [1.0 for _ in normalized_colors]
        else:
            if len(strengths) != len(normalized_colors):
                raise ValueError("The number of color strengths must match the number of colors")

            normalized_strengths = [max(0.0, min(1.0, float(value))) for value in strengths]

        return Arguments(
            texture_name=texture_params.texture_name,
            count=len(normalized_colors),
            scale_x=float(texture_params.scale_x),
            scale_y=float(texture_params.scale_y),
            density_x=float(texture_params.density_x),
            density_y=float(texture_params.density_y),
            rotation=float(texture_params.rotation),
            global_scale=float(texture_params.global_scale),
            colors=normalized_colors,
            color_strengths=normalized_strengths,
            white_background=bool(texture_params.white_background),
            background_brightness=max(0.0, min(1.0, float(texture_params.background_brightness))),
            generate_square=generate_square,
            width=int(texture_params.width),
            height=int(texture_params.height),
            seed=texture_params.seed,
        )

    @staticmethod
    def _ensure_numba_cache_dir() -> None:
        """
        Nastaví vlastný zapisovateľný cache priečinok pre numba

        (Niektoré časti balíka texture-infill používajú numba cache a pri určitých inštaláciách na Windowse môže zlyhať zapisovanie do pôvodného __pycache__ priečinka balíka, preto cache presmerujeme do lokálneho priečinka aplikácie)
        """
        cache_dir_env = os.environ.get("NUMBA_CACHE_DIR")

        if cache_dir_env:
            cache_dir = Path(cache_dir_env)
        else:
            base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home()))
            cache_dir = base_dir / "RePaint" / "numba_cache"
            os.environ["NUMBA_CACHE_DIR"] = str(cache_dir)

        cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _call_texture_infill(image: np.ndarray, mask: np.ndarray, arguments) -> np.ndarray:
        """
        Zavolá verejnú funkciu generate_infill z nainštalovaného balíka texture_infill
        """
        AlgorithmRunner._ensure_numba_cache_dir()

        try:
            from texture_infill.texture_infill import generate_infill
        except ImportError as e:
            raise RuntimeError("Balík texture-infill není nainstalovaný v aktuálním prostředí") from e

        output = generate_infill(image, mask, arguments)

        if isinstance(output, tuple):
            output = output[0]

        return np.asarray(output)

    @staticmethod
    def _normalize_texture_output(output: np.ndarray, expected_height: int, expected_width: int) -> np.ndarray:
        """
        Skontroluje výstup textúrového algoritmu a prevedie ho na RGBA uint8
        """
        arr = np.asarray(output)

        if arr.ndim != 3 or arr.shape[:2] != (expected_height, expected_width):
            raise RuntimeError(
                "Texture algorithm returned invalid output shape: "
                f"{arr.shape}; expected ({expected_height}, {expected_width})"
            )

        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)

        if arr.shape[2] == 4:
            return arr.copy()

        if arr.shape[2] == 3:
            rgba = np.zeros((expected_height, expected_width, 4), dtype=np.uint8)
            rgba[..., :3] = arr
            rgba[..., 3] = 255
            return rgba

        raise RuntimeError(f"Texture algorithm returned an unsupported number of channels: {arr.shape[2]}")
    
    @staticmethod
    def _looks_like_remote_access_error(error: Exception) -> bool:
        """
        Rozpozná chyby, ktoré pravdepodobne znamenajú zlý API key, zlý endpoint alebo problém s autorizáciou remote služby
        """
        text = f"{type(error).__name__}: {error}".lower()

        access_error_tokens = (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "authentication",
            "authorization",
            "api key",
            "api_key",
            "apikey",
            "invalid key",
            "invalid credentials",
            "invalid token",
            "modal_endpoint_url",
            "endpoint url",
            "configuration",
        )

        return any(token in text for token in access_error_tokens)

    @classmethod
    def _run_remote_realistic(cls, request: AlgorithmRequest) -> AlgorithmResult:
        """
        Spustí realistické doplnenie cez remote klienta painting_inpaint.remote

        V request.current_image sa očakáva iba výrez obrazu.
        V request.selected_mask sa očakáva výrez masky rovnakého rozmeru.
        request.window_bbox sa používa na vloženie výsledného patchu späť do obrazu.

        Podporované režimy:
        - BASIC: rýchlejší fill model, volá restore_file()
        - GUIDED: pomalší model vedený štruktúrou alebo náčrtom, volá restore_guided_file()
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
            from painting_inpaint.remote import RemoteRestorationError, RestorationClient
        except ImportError as e:
            raise RuntimeError("Balík painting-inpaint-remote není nainstalovaný") from e

        base_tmp = Path(os.environ.get("LOCALAPPDATA", ".")) / "RePaint" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)

        tmpdir_path = base_tmp / f"remote_realistic_{uuid.uuid4().hex}"
        tmpdir_path.mkdir(parents=True, exist_ok=True)

        log_msgs: list[str] = []

        try:
            input_patch_path = tmpdir_path / "input_patch.png"
            mask_patch_path = tmpdir_path / "mask_patch.png"

            image_io.save_image(input_patch_path, image_patch)
            image_io.save_mask(mask_patch_path, mask_patch)

            def _on_progress(event) -> None:
                """
                Uloží priebežnú hlášku z remote algoritmu a pošle ju späť controlleru
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
                if request.realistic_mode == RealisticFillMode.GUIDED:
                    result = client.restore_guided_file(
                        str(input_patch_path),
                        str(mask_patch_path),
                        on_progress=_on_progress,
                        seed=request.seed,
                    )
                else:
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
                if cls._looks_like_remote_access_error(e):
                    raise RemoteRestorationAccessError(
                        "Přihlášení k remote službě se nepodařilo. "
                        "Zkontrolujte endpoint URL a API key."
                    ) from e

                raise RuntimeError(f"Remote realistic fill failed: {e}") from e

            output_img = np.array(result.image.convert("RGBA"), dtype=np.uint8)

            if output_img.shape[0] != ph or output_img.shape[1] != pw:
                raise RuntimeError(
                    "Remote realistic output has wrong size. "
                    f"Expected ({ph}, {pw}), got {output_img.shape[:2]}"
                )

            status = getattr(result, "status", None)
            job_id = getattr(result, "job_id", None)

            if status is not None:
                log_msgs.append(f"Remote status: {status}")
            if job_id is not None:
                log_msgs.append(f"Remote job id: {job_id}")

            log_msgs.append(f"realistic_mode: {request.realistic_mode.value}")

            if request.realistic_mode == RealisticFillMode.BASIC:
                log_msgs.append(f"partial_noise: {partial_noise}")
            if request.seed is not None:
                log_msgs.append(f"seed: {request.seed}")

            return AlgorithmResult(output_patch=output_img, bbox=request.window_bbox, log_messages=log_msgs)

        finally:
            shutil.rmtree(tmpdir_path, ignore_errors=True)

    @staticmethod
    def _ensure_rgb(image: np.ndarray) -> np.ndarray:
        """
        Zabezpečí, že obraz je RGB uint8 pole tvaru (H, W, 3)
        """
        arr = image
        if arr.ndim != 3:
            raise ValueError("Expected 3D image array")

        if arr.shape[2] == 4:
            arr = arr[..., :3]
        elif arr.shape[2] != 3:
            raise ValueError("Expected RGB or RGBA image array")

        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)

        return arr
