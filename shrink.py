#!/usr/bin/env python3
"""Shrink (or enlarge) an image's width and height by a percentage (default 3%).

Usage:
    python shrink.py input.jpg                  # writes input_shrunk.jpg
    python shrink.py input.jpg -o out.png
    python shrink.py input.jpg --percent 5
    python shrink.py a.jpg b.png c.webp         # several files at once
    python shrink.py input.jpg --enlarge        # 3% bigger, writes input_enlarged.jpg
    python shrink.py input.jpg --restore        # 3% smaller, then back to original size,
                                                # writes input_restored.jpg
    python shrink.py input.jpg --spray 2 -r     # dots on 2% of pixels, then shrink + restore,
                                                # writes input_sprayed_restored.jpg
"""
import argparse
import random
import sys
from pathlib import Path

from PIL import Image


def spray(img: Image.Image, amount: float, rng: random.Random) -> Image.Image:
    """Set `amount` percent of pixels to black or white at random (salt-and-pepper noise)."""
    if img.mode in ("L", "LA", "RGB", "RGBA"):
        img = img.copy()
    else:
        has_alpha = img.mode.endswith("A") or "transparency" in img.info
        img = img.convert("RGBA" if has_alpha else "RGB")
    px = img.load()
    w, h = img.size
    has_alpha = img.mode.endswith("A")
    color_bands = len(img.getbands()) - has_alpha
    for i in rng.sample(range(w * h), round(w * h * amount / 100)):
        x, y = i % w, i // w
        v = rng.choice((0, 255))
        if img.mode == "L":
            px[x, y] = v
        else:
            color = (v,) * color_bands
            px[x, y] = color + (px[x, y][-1],) if has_alpha else color
    return img


def resize(src: Path, dst: Path, scale: float, restore: bool = False, spray_amount: float = 0,
           rng: random.Random | None = None) -> tuple[tuple[int, int], tuple[int, int]]:
    with Image.open(src) as img:
        old_size = img.size
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        source = spray(img, spray_amount, rng or random.Random()) if spray_amount else img
        resized = source.resize(new_size, Image.LANCZOS)
        if restore:
            resized = resized.resize(old_size, Image.LANCZOS)
            new_size = old_size
        save_kwargs = {}
        if "exif" in img.info:
            save_kwargs["exif"] = img.info["exif"]
        if "icc_profile" in img.info:
            save_kwargs["icc_profile"] = img.info["icc_profile"]
        if img.format == "JPEG":
            save_kwargs["quality"] = 95
        resized.save(dst, **save_kwargs)
    return old_size, new_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Shrink or enlarge images by a percentage.")
    parser.add_argument("inputs", nargs="+", type=Path, help="image file(s) to resize")
    parser.add_argument("-o", "--output", type=Path, help="output path (only with a single input)")
    parser.add_argument("-p", "--percent", type=float, default=3.0, help="percent to resize by (default: 3)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-e", "--enlarge", action="store_true", help="make the image bigger instead of smaller")
    group.add_argument("-r", "--restore", action="store_true",
                       help="shrink, then enlarge back to the exact original size")
    parser.add_argument("-s", "--spray", type=float, default=0, metavar="PERCENT",
                        help="before resizing, turn this percent of pixels into random black/white dots")
    parser.add_argument("--seed", type=int, help="random seed, so --spray gives the same dots every run")
    args = parser.parse_args()

    if args.output and len(args.inputs) > 1:
        parser.error("--output can only be used with a single input file")
    if not 0 <= args.spray <= 100:
        parser.error("--spray must be between 0 and 100")
    if args.enlarge:
        if args.percent <= 0:
            parser.error("--percent must be greater than 0")
        scale, suffix = 1 + args.percent / 100, "enlarged"
    else:
        if not 0 < args.percent < 100:
            parser.error("--percent must be between 0 and 100")
        scale, suffix = 1 - args.percent / 100, "restored" if args.restore else "shrunk"

    if args.spray:
        suffix = f"sprayed_{suffix}"
    rng = random.Random(args.seed)

    for src in args.inputs:
        dst = args.output or src.with_name(f"{src.stem}_{suffix}{src.suffix}")
        old, new = resize(src, dst, scale, args.restore, args.spray, rng)
        print(f"{src} {old[0]}x{old[1]} -> {dst} {new[0]}x{new[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
