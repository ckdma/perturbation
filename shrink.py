#!/usr/bin/env python3
"""Invisibly perturb images in one step.

    python shrink.py photo.jpg [more images...]    -> photo_perturbed.jpg

For each image: nudge every pixel by a tiny random amount, shrink it by 3%,
enlarge it back to its original size, and save it with all metadata removed.
"""
import io
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageCms, ImageOps

SPRAY = 3      # max change per colour value, out of 255 (invisible to the eye)
SHRINK = 3     # percent to shrink before enlarging back


def perturb(src: Path, rng: random.Random) -> Path:
    with Image.open(src) as img:
        fmt = img.format
        img = ImageOps.exif_transpose(img)  # turn upright before the EXIF is dropped

        # Convert to plain sRGB so colours stay the same without the colour profile.
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

        # Spray: add a random offset in [-SPRAY, +SPRAY] to every colour value.
        span = 2 * SPRAY + 1
        plus_table = bytes(max(b % span - SPRAY, 0) for b in range(256))
        minus_table = bytes(max(SPRAY - b % span, 0) for b in range(256))
        bands = list(img.split())
        for i in range(3):  # R, G, B; alpha is left alone
            raw = rng.randbytes(img.width * img.height)
            plus = Image.frombytes("L", img.size, raw.translate(plus_table))
            minus = Image.frombytes("L", img.size, raw.translate(minus_table))
            bands[i] = ImageChops.subtract(ImageChops.add(bands[i], plus), minus)
        img = Image.merge(img.mode, bands)

        # Shrink, then enlarge back to the exact original size.
        size = img.size
        small = (max(1, round(size[0] * (1 - SHRINK / 100))), max(1, round(size[1] * (1 - SHRINK / 100))))
        img = img.resize(small, Image.LANCZOS).resize(size, Image.LANCZOS)

    # Save a fresh image holding only the pixels, so no metadata comes along.
    clean = Image.frombytes(img.mode, img.size, img.tobytes())
    if clean.mode == "RGBA" and fmt in ("JPEG", "MPO"):
        clean = clean.convert("RGB")
    dst = src.with_name(f"{src.stem}_perturbed{src.suffix}")
    clean.save(dst, **({"quality": 95} if fmt in ("JPEG", "MPO", "WEBP") else {}))
    return dst


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1
    rng = random.Random(random.SystemRandom().randrange(2**32))
    failed = 0
    for arg in sys.argv[1:]:
        try:
            print(f"{arg} -> {perturb(Path(arg), rng)}")
        except (OSError, ValueError) as e:
            print(f"{arg}: skipped ({e})", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
