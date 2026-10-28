"""Run in a fresh Blender process with --disable-autoexec and no Sunner import."""
import math

import bpy

assert not hasattr(bpy.types, "SUNNER_PT_cycle"), "Sunner UI must not be registered"
scene = bpy.context.scene
collection = scene["sunner_rig"]
assert collection["previous_world"].name == "Original World"
assert collection["previous_world"].node_tree.nodes.get("Keep this node")
assert scene.world == collection["world"]
root = collection["root"]
assert root["twilight_enabled"]
assert root["twilight_sky_gain"] == 3.0
assert root["twilight_moon_gain"] == 0.15
for frame, sun_is_up in ((121, True), (1, False), (61, False), (121, True), (241, False)):
    scene.frame_set(frame)
    sun = collection["sun"].data.energy
    moon = collection["moon"].data.energy
    assert math.isfinite(sun) and math.isfinite(moon)
    assert (sun > 1) == sun_is_up, (frame, sun, moon)
    for data in (collection["sun"].data, collection["moon"].data, scene.world.node_tree):
        for curve in data.animation_data.drivers:
            assert curve.driver.is_valid
            assert curve.driver.is_simple_expression
print("SAVED_RIG_WITHOUT_ADDON_OK")

# Only after proving native evaluation, import the removal API and restore the World.
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sunner.rig import remove
remove(scene)
assert scene.world.name == "Original World"
assert scene.world.node_tree.nodes.get("Keep this node")
assert "sunner_rig" not in scene
print("REOPENED_WORLD_RESTORATION_OK")
