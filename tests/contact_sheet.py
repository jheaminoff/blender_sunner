"""Developer-only contact sheet helper; Pillow is not an extension dependency."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("--weather", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = root / "examples" / ("weather" if args.weather else "renders")
labels = ("dawn", "morning", "noon", "golden", "dusk", "twilight", "blue-hour", "midnight")
rows = []
for engine in ("cycles", "blender_eevee"):
    if args.weather:
        entries = [(item["label"], f'{item["seconds"]:.2f}s')
                   for item in json.loads((base / engine / "metrics.json").read_text())]
    else:
        entries = [(f"{i:02d}-{label}", "") for i, label in enumerate(labels)]
    rows.append((engine, entries))
first = Image.open(base / rows[0][0] / (rows[0][1][0][0] + ".png"))
w, h = first.size
sheet = Image.new("RGB", (w * 4, (h + 30) * 4), (24, 27, 31))
draw = ImageDraw.Draw(sheet)
for engine_row, (engine, entries) in enumerate(rows):
    for index, (name, timing) in enumerate(entries):
        image = Image.open(base / engine / f"{name}.png")
        x, y = index % 4 * w, (engine_row * 2 + index // 4) * (h + 30)
        sheet.paste(image, (x, y + 30))
        draw.text((x + 8, y + 8), f"{engine} / {name} {timing}", fill="white")
path = (base if args.weather else root / "examples") / "contact-sheet.jpg"
sheet.save(path, quality=93)
print(path)
