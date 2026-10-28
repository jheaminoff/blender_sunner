# SPDX-License-Identifier: GPL-3.0-or-later
"""Small sidebar over the actual animatable rig properties."""

import math

import bpy

from . import rig


class SUNNER_PT_cycle(bpy.types.Panel):
    bl_label = "Sunner"
    bl_idname = "SUNNER_PT_cycle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sunner"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        if not context.scene.get(rig.KEY):
            layout.operator("sunner.add", icon="LIGHT_SUN")
            layout.label(text="Rotate a dial through day and night.")
            layout.label(text="Your current World will be preserved.")
            return
        try:
            parts = rig.parts(context.scene)
        except rig.RigError as error:
            layout.label(text=str(error), icon="ERROR")
            layout.operator("sunner.remove", icon="TRASH")
            return
        root, dial = parts["root"], parts["dial"]
        layout.prop(dial, "rotation_euler", index=0, text="Day angle")
        minutes = round((dial.rotation_euler.x % math.tau) / math.tau * 1440) % 1440
        layout.label(text=f"Approx. {minutes // 60:02d}:{minutes % 60:02d}  /  360° per day")
        row = layout.row(align=True)
        for label, degrees in (("Dawn", 90), ("Noon", 180), ("Dusk", 270), ("Night", 0)):
            row.operator("sunner.position", text=label).angle = math.radians(degrees)
        layout.operator("sunner.select", icon="RESTRICT_SELECT_OFF")
        layout.label(text="Rotate locally: R, X, X")
        layout.separator()
        layout.prop(root, "rotation_euler", index=2, text="Heading")
        layout.prop(root, "rotation_euler", index=1, text="Path tilt")
        if not 0 <= root.rotation_euler.y <= math.radians(75):
            layout.label(text="Recommended tilt: 0–75°", icon="INFO")
        if rig.needs_update(root):
            layout.operator("sunner.update_cycle", icon="FILE_REFRESH")
            layout.label(text="Adds season, stars, discs and twilight.", icon="INFO")
        else:
            layout.prop(root, '["season"]', text="Season")
            layout.label(text="Tilt = latitude. ±23.4° = solstices.")
        layout.separator()
        for prop, label in (("sun_brightness", "Sun brightness"), ("sky_brightness", "Sky brightness"),
                            ("night_brightness", "Night brightness"), ("haze", "Haze"),
                            ("stars", "Stars"), ("discs", "Discs")):
            if prop in root:
                layout.prop(root, f'["{prop}"]', text=label)
        layout.separator()
        layout.operator("sunner.animate", icon="TIME")
        layout.operator("sunner.remove", icon="TRASH")
        if context.scene.world != parts["world"]:
            layout.label(text="Another World is active; only lights follow.", icon="INFO")
        if abs(context.scene.view_settings.exposure) > 3:
            layout.label(text="Existing exposure may obscure the cycle.", icon="INFO")
        shading = getattr(context.space_data, "shading", None)  # None in popups.
        if shading is None:
            return
        if shading.type == "SOLID" or shading.type == "WIREFRAME":
            layout.label(text="Use Rendered shading to see the cycle.", icon="INFO")
        elif shading.type == "MATERIAL" and not (shading.use_scene_world and shading.use_scene_lights):
            layout.label(text="Enable Scene World and Scene Lights.", icon="INFO")


class SUNNER_PT_advanced(bpy.types.Panel):
    bl_label = "Advanced"
    bl_idname = "SUNNER_PT_advanced"
    bl_parent_id = "SUNNER_PT_cycle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sunner"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        try:
            return bool(rig.parts(context.scene))
        except rig.RigError:
            return False

    def draw(self, context):
        root = rig.parts(context.scene)["root"]
        layout = self.layout
        layout.use_property_split = True
        for prop, label in (("warmth", "Sunset warmth"), ("moon_tint", "Moon cool tint"),
                            ("softness", "Shadow softness")):
            layout.prop(root, f'["{prop}"]', text=label)
        layout.separator()
        if "twilight_enabled" in root:
            layout.prop(root, '["twilight_enabled"]', text="Twilight balance")
            layout.prop(root, '["twilight_sky_gain"]', text="Twilight sky gain")
            layout.prop(root, '["twilight_moon_gain"]', text="Twilight moon gain")
        else:
            layout.operator("sunner.update_cycle", icon="FILE_REFRESH")
            layout.label(text="Older cycles stay unchanged until updated.", icon="INFO")
        layout.label(text="Night brightness is an artistic lift.")
        layout.label(text="Haze colours the sky; it is not scene fog.")


CLASSES = (SUNNER_PT_cycle, SUNNER_PT_advanced)
