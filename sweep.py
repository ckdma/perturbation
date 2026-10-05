#!/usr/bin/env python3
"""Generate a robustness sweep of image perturbations for evaluating a detector.

    python3 sweep.py image.png [more images...] [-o sweep_out] [--seed 0]

Each perturbation is applied on its own at several strengths, so detector scores
can be compared per perturbation type and strength. Every variant is saved with
metadata stripped, and listed in <out>/manifest.csv together with its PSNR
against the original (higher = closer to the original; above ~40 dB is
generally invisible). Run your detector over the files, add its score as a
column, and plot score against strength or PSNR per perturbation.

The "none" variant only strips metadata, as a baseline that separates the
effect of metadata from the effect of pixel changes.
"""
import argparse
import csv
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageStat

from shrink import spray, to_srgb_rgb

# perturbation -> strengths to test
PERTURBATIONS = {
    "none": [0],                          # metadata stripped only
    "jpeg": [95, 85, 75, 60, 40],         # JPEG quality
    "resize": [90, 75, 50, 25],           # percent of original size, then scaled back up
    "blur": [0.5, 1, 2, 3],               # Gaussian blur radius in pixels
    "noise": [4, 8, 16, 32],              # max uniform noise per colour value, out of 255
    "crop": [5, 10, 20],                  # percent cropped off (centred), then scaled back up
    "brightness": [-20, -10, 10, 20],     # percent change
    "contrast": [-20, -10, 10, 20],       # percent change
}


def apply(img: Image.Image, kind: str, level: float, rng: random.Random) -> Image.Image:
    w, h = img.size
    if kind in ("none", "jpeg"):
        return img
    if kind == "resize":
        small = (max(1, round(w * level / 100)), max(1, round(h * level / 100)))
        return img.resize(small, Image.LANCZOS).resize((w, h), Image.LANCZOS)
    if kind == "blur":
        return img.filter(ImageFilter.GaussianBlur(level))
    if kind == "noise":
        return spray(img, int(level), rng)
    if kind == "crop":
        dx, dy = w * level / 200, h * level / 200
        return img.resize((w, h), Image.LANCZOS, box=(dx, dy, w - dx, h - dy))
    if kind == "brightness":
        return ImageEnhance.Brightness(img).enhance(1 + level / 100)
    if kind == "contrast":
        return ImageEnhance.Contrast(img).enhance(1 + level / 100)
    raise ValueError(f"unknown perturbation {kind!r}")


def psnr(a: Image.Image, b: Image.Image) -> float:
    rms = ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).rms
    mse = sum(r * r for r in rms) / len(rms)
    return math.inf if mse == 0 else 10 * math.log10(255 ** 2 / mse)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a perturbation sweep for detector evaluation.")
    parser.add_argument("inputs", nargs="+", type=Path, help="source images")
    parser.add_argument("-o", "--out", type=Path, default=Path("sweep_out"), help="output folder")
    parser.add_argument("--seed", type=int, default=0, help="random seed for the noise (default: 0)")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = args.out / "manifest.csv"
    failed = 0
    with manifest.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "perturbation", "strength", "file", "psnr_db"])
        for src in args.inputs:
            try:
                with Image.open(src) as original:
                    base = to_srgb_rgb(original)
            except (OSError, ValueError) as e:
                print(f"{src}: skipped ({e})", file=sys.stderr)
                failed += 1
                continue
            folder = args.out / src.stem
            folder.mkdir(exist_ok=True)
            for kind, levels in PERTURBATIONS.items():
                for level in levels:
                    img = apply(base, kind, level, rng)
                    clean = Image.frombytes(img.mode, img.size, img.tobytes())  # pixels only, no metadata
                    if kind == "jpeg":
                        dst = folder / f"{kind}_{level}.jpg"
                        clean.convert("RGB").save(dst, quality=level)
                    else:
                        dst = folder / f"{kind}_{level}.png"
                        clean.save(dst)
                    with Image.open(dst) as saved:
                        score = psnr(base, saved)
                    writer.writerow([src, kind, level, dst, "inf" if math.isinf(score) else f"{score:.2f}"])
            print(f"{src} -> {folder}/")
    print(f"manifest: {manifest}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
