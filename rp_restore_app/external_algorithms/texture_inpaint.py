from __future__ import annotations

import argparse
from pathlib import Path
import sys

import cv2
import numpy as np

from infill_generation_demo import generate_infill, generate_infill_mock


def _read_mask_u8(path: str) -> np.ndarray:
    mask = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise RuntimeError(f"Cannot read mask: {path}")

    if float(np.mean(mask > 0)) > 0.5:
        mask = 255 - mask
    mask = (mask > 0).astype(np.uint8) * 255
    return mask


def main() -> int:
    print("WRAPPER PATH:", __file__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_image", required=True)
    ap.add_argument("--mask_selected", required=True)
    ap.add_argument("--mask_all", required=True)  #zatiaľ nepoužijeme, ale nech sedí rozhranie
    ap.add_argument("--output", required=True)
    ap.add_argument("--device", default="cpu")    #zatiaľ ignor
    ap.add_argument("--mock", action="store_true")
    #na neskôr
    ap.add_argument("--ring_outer", type=int, default=30)
    ap.add_argument("--roi_margin", type=int, default=50)
    ap.add_argument("--harmonic_iter", type=int, default=100)
    ap.add_argument("--texture_strength", type=float, default=2.5)
    ap.add_argument("--micro_strength", type=float, default=10.0)
    ap.add_argument("--direction_mode", type=str, default="auto")   # auto/manual
    ap.add_argument("--direction_angle_deg", type=float, default=65.0)
    ap.add_argument("--double_strokes", action="store_true")
    ap.add_argument("--directionality", type=float, default=2.0)
    ap.add_argument("--direction_scale", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=-1)

    args = ap.parse_args()

    img = cv2.imread(args.input_image, cv2.IMREAD_COLOR)  #BGR
    if img is None:
        raise RuntimeError(f"Cannot read input image: {args.input_image}")

    mask_sel = _read_mask_u8(args.mask_selected)

    if mask_sel.shape[:2] != img.shape[:2]:
        raise RuntimeError("mask_selected must have same HxW as input_image")

    #vymažeme vnútro masky, aby algoritmus nepoužil pôvodný obsah
    img_ctx = img.copy()
    img_ctx[mask_sel > 0] = (0, 0, 0)

    seed = None if args.seed < 0 else int(args.seed)

    if args.mock:
        infill = generate_infill_mock(img_ctx, mask_sel, seed=seed)
    else:
        try:
            infill = generate_infill(
                img_ctx,
                mask_sel,
                ring_outer=args.ring_outer,
                roi_margin=args.roi_margin,
                harmonic_iter=args.harmonic_iter,
                texture_strength=args.texture_strength,
                micro_strength=args.micro_strength,
                direction_mode=args.direction_mode,
                direction_angle_deg=args.direction_angle_deg,
                double_strokes=bool(args.double_strokes),
                directionality=args.directionality,
                direction_scale=args.direction_scale,
                seed=seed,
            )
        except Exception as e:
            print(f"WARNING: generate_infill failed, fallback to mock. Error: {e}", file=sys.stderr)
            infill = generate_infill_mock(img_ctx, mask_sel, seed=seed)

    out = img.copy()
    out[mask_sel > 0] = infill[mask_sel > 0]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ok = cv2.imwrite(str(out_path), out)
    if not ok:
        raise RuntimeError(f"Failed to write output image: {out_path}")

    print("OK texture_inpaint")
    print(f"output={out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise