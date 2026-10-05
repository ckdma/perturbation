#!/usr/bin/env python3
"""Invisibly perturb images: spray tiny random noise, shrink, then enlarge back.

By default every image gets one full pass:
  1. spray: every colour value is nudged by a random amount up to +/-3 (out of 255)
  2. shrink the image by 3%
  3. enlarge it back to its exact original size
A fresh random seed is chosen each run (and printed, so a run can be repeated).

Usage:
    python shrink.py photo.jpg                  # full pass, writes photo_perturbed.jpg
    python shrink.py *.jpg *.png                # several files at once
    python shrink.py photo.jpg -o out.png       # choose the output file
    python shrink.py photo.jpg --seed 1234      # repeat an earlier run exactly
    python shrink.py photo.jpg --spray 5 --percent 10   # stronger
    python shrink.py photo.jpg --spray 0        # no noise, only shrink + enlarge back
    python shrink.py photo.jpg --no-restore     # spray + shrink, keep the smaller size
    python shrink.py photo.jpg --enlarge        # spray + make 3% bigger
"""
import argparse
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops


def spray(img: Image.Image, strength: int, rng: random.Random) -> Image.Image:
    """Nudge every colour value by a random amount in [-strength, +strength].

    With a small strength (a few levels out of 255) the pixels change but the
    image looks the same to the eye. Transparency is left untouched.
    """
    if img.mode not in ("L", "LA", "RGB", "RGBA"):
        has_alpha = img.mode.endswith("A") or "transparency" in img.info
        img = img.convert("RGBA" if has_alpha else "RGB")
    bands = list(img.split())
    color_bands = len(bands) - img.mode.endswith("A")
    # Each random byte picks an offset in [-strength, +strength]; split it into
    # a positive part to add and a negative part to subtract, so clamping at
    # 0 and 255 behaves the same in both directions.
    span = 2 * strength + 1
    plus_table = bytes(max(b % span - strength, 0) for b in range(256))
    minus_table = bytes(max(strength - b % span, 0) for b in range(256))
    for i in range(color_bands):
        raw = rng.randbytes(img.width * img.height)
        plus = Image.frombytes("L", img.size, raw.translate(plus_table))
        minus = Image.frombytes("L", img.size, raw.translate(minus_table))
        bands[i] = ImageChops.subtract(ImageChops.add(bands[i], plus), minus)
    return Image.merge(img.mode, bands)


def resize(src: Path, dst: Path, scale: float, restore: bool = False, spray_strength: int = 0,
           rng: random.Random | None = None) -> tuple[tuple[int, int], tuple[int, int]]:
    with Image.open(src) as img:
        old_size = img.size
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        source = spray(img, spray_strength, rng or random.Random()) if spray_strength else img
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
    group.add_argument("-n", "--no-restore", action="store_true",
                       help="shrink only, don't enlarge back to the original size")
    parser.add_argument("-s", "--spray", type=int, default=3, metavar="STRENGTH",
                        help="before resizing, nudge every pixel by a random amount up to +/-STRENGTH "
                             "out of 255 (default: 3, invisible to the eye; 0 turns it off)")
    parser.add_argument("--seed", type=int, help="random seed (default: a new random one each run)")
    args = parser.parse_args()

    if args.output and len(args.inputs) > 1:
        parser.error("--output can only be used with a single input file")
    if not 0 <= args.spray <= 127:
        parser.error("--spray must be between 0 and 127")
    if args.enlarge:
        if args.percent <= 0:
            parser.error("--percent must be greater than 0")
        scale, suffix = 1 + args.percent / 100, "enlarged"
    else:
        if not 0 < args.percent < 100:
            parser.error("--percent must be between 0 and 100")
        scale, suffix = 1 - args.percent / 100, "shrunk" if args.no_restore else "perturbed"
    restore = not (args.enlarge or args.no_restore)

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    print(f"seed: {seed}")
    rng = random.Random(seed)

    failed = 0
    for src in args.inputs:
        dst = args.output or src.with_name(f"{src.stem}_{suffix}{src.suffix}")
        try:
            old, new = resize(src, dst, scale, restore, args.spray, rng)
        except (OSError, ValueError) as e:
            print(f"{src}: skipped ({e})", file=sys.stderr)
            failed += 1
            continue
        print(f"{src} {old[0]}x{old[1]} -> {dst} {new[0]}x{new[1]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
