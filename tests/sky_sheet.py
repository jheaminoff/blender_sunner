"""Tile examples/sky/<engine>/*.png into examples/sky/contact-sheet.jpg using Blender only."""
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1] / "examples" / "sky"
rows = [sorted((ROOT / engine).glob("*.png")) for engine in ("cycles", "blender_eevee")]
images = [[bpy.data.images.load(str(path)) for path in row] for row in rows]
w, h = images[0][0].size
columns = max(len(row) for row in images)
scale = 2  # Every second pixel keeps the sheet small.
sw, sh = w // scale, h // scale
sheet = bpy.data.images.new("Sky sheet", sw * columns, sh * len(images))
pixels = [0.0] * (sw * columns * sh * len(images) * 4)
for r, row in enumerate(images):
    top = len(images) - 1 - r  # Blender images start at the bottom row.
    for c, image in enumerate(row):
        source = image.pixels[:]
        for y in range(sh):
            for x in range(sw):
                s = ((y * scale) * w + x * scale) * 4
                d = (((top * sh + y) * sw * columns) + c * sw + x) * 4
                pixels[d:d + 4] = source[s:s + 4]
sheet.pixels = pixels
sheet.filepath_raw = str(ROOT / "contact-sheet.jpg")
sheet.file_format = "JPEG"
sheet.save()
print("SKY_SHEET_OK", sheet.filepath_raw)
