"""Install the ZIP through Blender's extension operator in an isolated profile."""
import importlib
import math
import os
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
profile = Path(os.environ["BLENDER_USER_RESOURCES"])
repo_dir = profile / "sunner_test_repo"
repo_dir.mkdir(parents=True, exist_ok=True)
assert bpy.ops.preferences.extension_repo_add(
    name="Sunner test", type="LOCAL", use_custom_directory=True,
    custom_directory=str(repo_dir),
) == {"FINISHED"}
repo = bpy.context.preferences.extensions.repos[-1]
assert bpy.ops.extensions.package_install_files(
    filepath=str(ROOT / "dist" / "sunner-0.4.0.zip"), repo=repo.module, enable_on_install=True,
) == {"FINISHED"}
module = f"bl_ext.{repo.module}.sunner"
assert module in bpy.context.preferences.addons
rig = importlib.import_module(module + ".rig")
scene = bpy.context.scene
original = scene.world
assert bpy.ops.sunner.add() == {"FINISHED"}
p = rig.parts(scene)
p["dial"].rotation_euler.x = math.pi
bpy.context.view_layer.update()
assert p["sun"].data.energy > 1
assert bpy.ops.sunner.update_cycle() == {"FINISHED"}
assert not rig.needs_update(p["root"])
p["root"]["season"] = rig.SOLSTICE
assert bpy.ops.sunner.weather_add() == {"FINISHED"}
assert bpy.ops.sunner.weather_preset(preset="RAINY") == {"FINISHED"}
scene.frame_set(12)
assert bpy.ops.sunner.weather_remove() == {"FINISHED"}
assert bpy.ops.sunner.remove() == {"FINISHED"}
assert scene.world == original
assert bpy.ops.preferences.addon_disable(module=module) == {"FINISHED"}
assert bpy.ops.preferences.addon_enable(module=module) == {"FINISHED"}
print("SUNNER_ZIP_INSTALL_OK", module)
