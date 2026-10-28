"""Bounded synthetic weather comparison. No external scene assets are loaded."""

import argparse
import json
import math
from pathlib import Path
import resource
import subprocess
import sys
import time

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sunner import rig, weather

parser = argparse.ArgumentParser()
parser.add_argument("--engine", choices=("CYCLES", "BLENDER_EEVEE"), default="CYCLES")
parser.add_argument("--save", action="store_true")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = args.engine
scene.render.threads_mode = "FIXED"
scene.render.threads = 2
scene.render.resolution_x, scene.render.resolution_y = 320, 200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.cycles.samples = 16
scene.cycles.use_denoising = True
# Explicit test-scene choice. Sunner exposes this checkbox but never changes it silently.
scene.eevee.use_volumetric_shadows = True
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "None"
scene.view_settings.exposure = 0

mat = bpy.data.materials.new("Weather test concrete")
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.32, 0.36, 0.4, 1)
bsdf.inputs["Roughness"].default_value = 0.7
bpy.ops.mesh.primitive_plane_add(size=20000)
bpy.context.object.data.materials.append(mat)
for x, y, height, width in [(-18,-12,14,6), (0,0,18,7), (20,15,12,5), (-22,30,24,8),
                             (5,44,16,7), (36,50,28,6), (-40,65,25,5), (4,78,30,7)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x,y,height/2))
    bpy.context.object.scale = (width,width,height)
    bpy.context.object.data.materials.append(mat)
bpy.ops.object.camera_add(location=(35,-95,25))
scene.camera = bpy.context.object
scene.camera.rotation_euler = (Vector((0,15,7))-scene.camera.location).to_track_quat("-Z","Y").to_euler()
scene.camera.data.lens = 35
scene.camera.data.clip_end = 10000
rig.create(scene)
p = rig.parts(scene)
p["dial"].rotation_euler.x = math.radians(120)
output = ROOT / "examples" / "weather" / args.engine.lower()
output.mkdir(parents=True, exist_ok=True)
records = []


def render(label):
    if sys.platform == "darwin":
        pressure = subprocess.check_output(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"], text=True).strip()
        if pressure != "1":
            raise RuntimeError("Host memory pressure rose; defer weather rendering")
    scene.frame_set(24)
    bpy.context.view_layer.update()
    scene.render.filepath = str(output / f"{label}.png")
    print(f"START {args.engine} {label}", flush=True)
    start = time.monotonic()
    bpy.ops.render.render(write_still=True)
    elapsed = time.monotonic() - start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        rss *= 1024
    records.append({"label": label, "seconds": round(elapsed,3), "peak_rss_bytes": rss})
    (output / "metrics.json").write_text(json.dumps(records, indent=2))
    print(f"OK {args.engine} {label} {elapsed:.2f}s peakRSS={rss/1024**2:.0f}MiB", flush=True)
    if rss > 1.25 * 1024**3:
        raise RuntimeError("Small-process memory budget exceeded; defer remaining renders")


render("00-no-weather")
w = weather.create(scene)
r = w["root"]
r["extent"] = 350.0
r["fog_height"] = 65.0
r["fog_distance"] = 200.0
r["cloud_height"] = 100.0
r["cloud_size"] = 120.0
r["rain_radius"] = 12.0
r["rain_height"] = 25.0
for index, preset in enumerate(("CLEAR", "MISTY", "CLOUDY", "OVERCAST", "RAINY"), 1):
    weather.preset(scene, preset)
    render(f"{index:02d}-{preset.lower()}")
weather.preset(scene, "CLOUDY")
r["fog_amount"] = 0.8
r["shafts"] = 0.8
render("06-shafts")
weather.preset(scene, "RAINY")
p["dial"].rotation_euler.x = 0
render("07-rainy-night")

if args.save:
    p["dial"].rotation_euler.x = math.radians(120)
    weather.preset(scene, "CLOUDY")
    scene.frame_set(24)
    bpy.context.view_layer.update()
    scene.render.filepath = "//weather-frame-"
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
            area.spaces.active.show_region_ui = True
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "examples" / "sunner-weather.blend"))
print("WEATHER_RENDER_CHECK_OK", flush=True)
