# perturbation

`shrink.py` perturbs images in one step while keeping them looking the same.
For each image, with fresh random settings every time, it:

1. crops 1–3% off the edges and scales back to the original size,
2. shifts brightness, contrast and colour by 2–5%,
3. shrinks by 2–6%, then enlarges back to the original size,
4. adds random noise of up to ±8–12 (out of 255) to every pixel,
5. saves with all metadata removed (EXIF, GPS, camera info, XMP, comments,
   colour profile). The image is turned upright and converted to sRGB first.

## Usage

```bash
pip install pillow
python3 shrink.py photo.jpg              # writes photo_perturbed.jpg
python3 shrink.py *.jpg *.png            # several images at once
```

The original image is never changed. To make the effect stronger or weaker,
edit the ranges at the top of `shrink.py`.
