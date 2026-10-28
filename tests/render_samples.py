"""Build the example and render a small, fixed-exposure lighting contact sheet."""

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sunner.rig import create, parts

parser = argparse.ArgumentParser()
parser.add_argument("--engine", choices=("CYCLES", "BLENDER_EEVEE"), default="CYCLES")
parser.add_argument("--quick", action="store_true")
parser.add_argument("--save", action="store_true")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = args.engine
scene.render.resolution_x = 480
scene.render.resolution_y = 320
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "None"
scene.view_settings.exposure = 0
scene.cycles.samples = 32
scene.cycles.use_denoising = True


def material(name, color, metallic=0):
    mat = bpy.data.materials.new(name)
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.35
    shader.inputs["Metallic"].default_value = metallic
    return mat


grey = material("Neutral grey", (0.35, 0.35, 0.35))
clay = material("Warm clay", (0.45, 0.12, 0.05))
metal = material("Brushed metal", (0.6, 0.6, 0.6), 0.85)
bpy.ops.mesh.primitive_plane_add(size=20000)
bpy.context.object.name = "Ground"
bpy.context.object.data.materials.append(grey)
for loc, mat in [((-2, 0, 1), grey), ((1, 0, 1), clay), ((3.5, 1, 0.7), metal)]:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=loc)
    obj = bpy.context.object
    if loc[2] == 0.7:
        obj.scale = (0.7,) * 3
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 3.5, 1.5))
bpy.context.object.scale = (0.8, 0.8, 3)
bpy.context.object.data.materials.append(grey)
bpy.ops.object.camera_add(location=(9, -16, 5))
camera = bpy.context.object
camera.rotation_euler = (Vector((0, 1, 2.5)) - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.lens = 40
scene.camera = camera
create(scene)
rig = parts(scene)
output = ROOT / "examples" / "renders" / args.engine.lower()
output.mkdir(parents=True, exist_ok=True)
for old in output.glob("*.png"):
    old.unlink()
samples = [(90, "dawn"), (180, "noon"), (270, "dusk"), (360, "midnight")]
if not args.quick:
    samples = [(90, "dawn"), (100, "morning"), (180, "noon"), (260, "golden"), (270, "dusk"), (277, "twilight"), (290, "blue-hour"), (360, "midnight")]
for index, (angle, name) in enumerate(samples):
    print(f"START {args.engine} {name}", flush=True)
    rig["dial"].rotation_euler.x = math.radians(angle)
    scene.frame_set(scene.frame_current)
    bpy.context.view_layer.update()
    print("ENERGIES", rig["sun"].data.energy, rig["moon"].data.energy, flush=True)
    scene.render.filepath = str(output / f"{index:02d}-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"OK {args.engine} {name}", flush=True)

if args.save:
    from sunner.operators import animate, select_dial
    rig["dial"].rotation_euler.x = math.radians(240)
    animate(scene, 1, 240)
    scene.frame_set(1)
    select_dial(bpy.context)
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
            area.spaces.active.shading.type = "MATERIAL"
            area.spaces.active.shading.use_scene_world = True
            area.spaces.active.shading.use_scene_lights = True
            area.spaces.active.show_region_ui = True
    scene.render.filepath = "//sunner-frame-"
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "examples" / "sunner.blend"))
