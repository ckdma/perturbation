# perturbation

`shrink.py` invisibly perturbs images in one step. For each image it:

1. nudges every pixel by a tiny random amount (up to ±3 out of 255),
2. shrinks it by 3%,
3. enlarges it back to its exact original size,
4. saves it with all metadata removed (EXIF, GPS, camera info, XMP, comments,
   colour profile). The image is turned upright and converted to sRGB first,
   so it still looks the same.

## Usage

```bash
pip install pillow
python shrink.py photo.jpg              # writes photo_perturbed.jpg
python shrink.py *.jpg *.png            # several images at once
```

The original image is never changed. To make the effect stronger or weaker,
edit `SPRAY` and `SHRINK` at the top of `shrink.py`.
