#!/usr/bin/env python3
"""Shrink an image's width and height by a percentage (default 3%).

Usage:
    python shrink.py input.jpg                  # writes input_shrunk.jpg
    python shrink.py input.jpg -o out.png
    python shrink.py input.jpg --percent 5
    python shrink.py a.jpg b.png c.webp         # several files at once
"""
import argparse
import sys
from pathlib import Path

from PIL import Image


def shrink(src: Path, dst: Path, percent: float) -> tuple[tuple[int, int], tuple[int, int]]:
    scale = 1 - percent / 100
    with Image.open(src) as img:
        old_size = img.size
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        resized = img.resize(new_size, Image.LANCZOS)
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
    parser = argparse.ArgumentParser(description="Shrink images by a percentage.")
    parser.add_argument("inputs", nargs="+", type=Path, help="image file(s) to shrink")
    parser.add_argument("-o", "--output", type=Path, help="output path (only with a single input)")
    parser.add_argument("-p", "--percent", type=float, default=3.0, help="percent to shrink by (default: 3)")
    args = parser.parse_args()

    if args.output and len(args.inputs) > 1:
        parser.error("--output can only be used with a single input file")
    if not 0 < args.percent < 100:
        parser.error("--percent must be between 0 and 100")

    for src in args.inputs:
        dst = args.output or src.with_name(f"{src.stem}_shrunk{src.suffix}")
        old, new = shrink(src, dst, args.percent)
        print(f"{src} {old[0]}x{old[1]} -> {dst} {new[0]}x{new[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
