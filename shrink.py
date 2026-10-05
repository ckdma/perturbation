#!/usr/bin/env python3
"""Perturb images in one step while keeping them looking the same.

    python3 shrink.py photo.jpg [more images...]    -> photo_perturbed.jpg

For each image, with fresh random settings every time:
  1. crop a little off the edges and scale back to the original size
  2. nudge brightness, contrast and colour slightly
  3. shrink by a few percent, then enlarge back to the original size
  4. spray random noise on every pixel (last, so the resize can't smooth it away)
  5. save with all metadata removed
"""
import io
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageCms, ImageEnhance, ImageOps

# Each image gets a random value from each range. Raise the numbers for a stronger effect.
CROP = (1.0, 3.0)     # percent cropped off the edges in total, before scaling back up
TONE = (2.0, 5.0)     # percent change to brightness, contrast and colour (up or down)
SHRINK = (2.0, 6.0)   # percent to shrink before enlarging back
SPRAY = (8, 12)       # max noise per colour value, out of 255


def to_srgb_rgb(img: Image.Image) -> Image.Image:
    """Turn the image upright and into plain sRGB RGB/RGBA, so it looks the same once metadata is gone."""
    img = ImageOps.exif_transpose(img)
    icc = img.info.get("icc_profile")
    if icc and img.mode in ("L", "RGB", "RGBA", "CMYK"):
        try:
            img = ImageCms.profileToProfile(
                img, ImageCms.ImageCmsProfile(io.BytesIO(icc)), ImageCms.createProfile("sRGB"),
                outputMode="RGBA" if img.mode == "RGBA" else "RGB")
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode or "transparency" in img.info else "RGB")
    return img


def spray(img: Image.Image, strength: int, rng: random.Random) -> Image.Image:
    """Add a random offset in [-strength, +strength] to every colour value; alpha is left alone."""
    span = 2 * strength + 1
    plus_table = bytes(max(b % span - strength, 0) for b in range(256))
    minus_table = bytes(max(strength - b % span, 0) for b in range(256))
    bands = list(img.split())
    for i in range(3):
        raw = rng.randbytes(img.width * img.height)
        plus = Image.frombytes("L", img.size, raw.translate(plus_table))
        minus = Image.frombytes("L", img.size, raw.translate(minus_table))
        bands[i] = ImageChops.subtract(ImageChops.add(bands[i], plus), minus)
    return Image.merge(img.mode, bands)


def perturb(src: Path, rng: random.Random) -> tuple[Path, str]:
    crop = rng.uniform(*CROP)
    tone = [rng.choice((-1, 1)) * rng.uniform(*TONE) for _ in range(3)]
    shrink = rng.uniform(*SHRINK)
    noise = rng.randint(*SPRAY)

    with Image.open(src) as original:
        fmt = original.format
        img = to_srgb_rgb(original)
    size = img.size
    w, h = size

    # 1. Crop a random amount, split randomly between the edges, then scale back up.
    dx, dy = w * crop / 100, h * crop / 100
    left, top = rng.uniform(0, dx), rng.uniform(0, dy)
    img = img.resize(size, Image.LANCZOS, box=(left, top, w - (dx - left), h - (dy - top)))

    # 2. Small brightness / contrast / colour shifts.
    for enhancer, change in zip((ImageEnhance.Brightness, ImageEnhance.Contrast, ImageEnhance.Color), tone):
        img = enhancer(img).enhance(1 + change / 100)

    # 3. Shrink, then enlarge back to the exact original size.
    small = (max(1, round(w * (1 - shrink / 100))), max(1, round(h * (1 - shrink / 100))))
    img = img.resize(small, Image.LANCZOS).resize(size, Image.LANCZOS)

    # 4. Spray noise last, so nothing smooths it out.
    img = spray(img, noise, rng)

    # 5. Save a fresh image holding only the pixels, so no metadata comes along.
    clean = Image.frombytes(img.mode, img.size, img.tobytes())
    dst = src.with_name(f"{src.stem}_perturbed{src.suffix}")
    out_fmt = Image.registered_extensions().get(dst.suffix.lower(), fmt)  # format follows the file name
    if clean.mode == "RGBA" and out_fmt == "JPEG":
        clean = clean.convert("RGB")
    clean.save(dst, **({"quality": 95} if out_fmt in ("JPEG", "WEBP") else {}))

    summary = (f"crop {crop:.1f}%, brightness {tone[0]:+.1f}%, contrast {tone[1]:+.1f}%, "
               f"colour {tone[2]:+.1f}%, shrink {shrink:.1f}%, spray +/-{noise}")
    return dst, summary


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1
    rng = random.Random(random.SystemRandom().randrange(2**32))
    failed = 0
    for arg in sys.argv[1:]:
        try:
            dst, summary = perturb(Path(arg), rng)
            print(f"{arg} -> {dst}  ({summary})")
        except (OSError, ValueError) as e:
            print(f"{arg}: skipped ({e})", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
