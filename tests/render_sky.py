"""Render the 0.4 sky features: season, stars and discs. Writes examples/sky/<engine>/."""

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sunner.rig import SOLSTICE, create, parts

parser = argparse.ArgumentParser()
parser.add_argument("--engine", choices=("CYCLES", "BLENDER_EEVEE"), default="CYCLES")
parser.add_argument("--only", help="Render one shot by name")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = args.engine
scene.render.resolution_x, scene.render.resolution_y = 960, 540
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "None"
scene.cycles.samples = 64
scene.cycles.use_denoising = False  # The denoiser would smear one-pixel stars.

grey = bpy.data.materials.new("Neutral grey")
grey.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.35, 0.35, 1)
ground = bpy.data.meshes.new("Ground")
ground.from_pydata([(-5000, -5000, 0), (5000, -5000, 0), (5000, 5000, 0), (-5000, 5000, 0)], [], [(0, 1, 2, 3)])
ground.materials.append(grey)
scene.collection.objects.link(bpy.data.objects.new("Ground", ground))
for x, y, height in ((-6, 10, 6), (3, 14, 10), (10, 8, 4), (-12, 18, 8)):
    block = bpy.data.meshes.new("Block")
    block.from_pydata([(x + dx, y + dy, z) for z in (0, height) for dy in (-1.5, 1.5) for dx in (-1.5, 1.5)], [],
                      [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])
    block.materials.append(grey)
    scene.collection.objects.link(bpy.data.objects.new("Block", block))
camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
camera.location = (0, -12, 1.7)
scene.collection.objects.link(camera)
scene.camera = camera

create(scene)
rig = parts(scene)
root, dial = rig["root"], rig["dial"]
output = ROOT / "examples" / "sky" / args.engine.lower()
output.mkdir(parents=True, exist_ok=True)


def sun_direction():
    return rig["sun"].matrix_world.to_quaternion() @ Vector((0, 0, 1))


def aim(direction, pitch, lens):
    """Look horizontally towards a world direction, then pitch up by the given degrees."""
    flat = Vector((direction.x, direction.y, 0)).normalized()
    target = flat * math.cos(math.radians(pitch)) + Vector((0, 0, math.sin(math.radians(pitch))))
    camera.rotation_euler = target.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = lens


# name, tilt (latitude), season, day angle, camera aim, pitch, lens
SHOTS = (
    ("01-equinox-sunset-disc", 61.5, 0.0, 268, "sun", 3, 120),
    ("02-midwinter-noon", 61.5, -SOLSTICE, 180, "blocks", 0, 28),
    ("03-midsummer-noon", 61.5, SOLSTICE, 180, "blocks", 0, 28),
    ("04-midsummer-white-night", 61.5, SOLSTICE, 0, "sun", 5, 24),
    ("05-moonrise-disc", 61.5, -SOLSTICE, 240, "moon", 10, 200),
    ("06-winter-stars", 61.5, -SOLSTICE, 0, "north", 35, 20),
)
for name, tilt, season, angle, target, pitch, lens in SHOTS:
    if args.only and args.only != name:
        continue
    root.rotation_euler = (0, math.radians(tilt), 0)
    root["season"] = season
    root.update_tag()
    dial.rotation_euler.x = math.radians(angle)
    bpy.context.view_layer.update()
    if target == "blocks":
        camera.location = (22, -8, 9)
        camera.rotation_euler = (Vector((-2, 12, 2)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = lens
    else:
        camera.location = (0, -12, 1.7)
        direction = {"sun": sun_direction(), "moon": -sun_direction(), "north": Vector((-1, 0, 0))}[target]
        aim(direction, pitch, lens)
    elevation = math.degrees(math.asin(sun_direction().z))
    print(f"SHOT {name} sun_elevation={elevation:.2f} sun={rig['sun'].data.energy:.3f} "
          f"moon={rig['moon'].data.energy:.3f}", flush=True)
    scene.render.filepath = str(output / f"{name}.png")
    bpy.ops.render.render(write_still=True)
print("SKY_RENDERS_OK")
