# SPDX-License-Identifier: GPL-3.0-or-later
"""Weather editing stays separate from the native render-time rig."""

import bpy
from bpy.props import EnumProperty

from . import rig, weather


class SUNNER_OT_weather_add(bpy.types.Operator):
    bl_idname = "sunner.weather_add"
    bl_label = "Add weather"
    bl_description = "Add optional fog, clouds and camera-local rain, initially clear"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            weather.create(context.scene)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "Weather ready. Choose a preset and set the region size")
        return {"FINISHED"}


class SUNNER_OT_weather_remove(bpy.types.Operator):
    bl_idname = "sunner.weather_remove"
    bl_label = "Remove weather"
    bl_description = "Remove only weather data; keep the day cycle and lighting"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            weather.remove(context.scene)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class SUNNER_OT_weather_preset(bpy.types.Operator):
    bl_idname = "sunner.weather_preset"
    bl_label = "Apply weather preset"
    bl_description = "Set weather controls; Auto Keying inserts keys for changed controls"
    bl_options = {"REGISTER", "UNDO"}

    preset: EnumProperty(items=[(key, value[0], f"Apply {value[0].lower()} weather")
                                for key, value in weather.PRESETS.items()])

    def execute(self, context):
        try:
            weather.preset(context.scene, self.preset)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class SUNNER_OT_weather_bind(bpy.types.Operator):
    bl_idname = "sunner.weather_bind"
    bl_label = "Bind rain to scene camera"
    bl_description = "Follow the current scene camera; rebind after changing cameras"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.scene.camera is None:
            self.report({"ERROR"}, "Set a scene camera first")
            return {"CANCELLED"}
        try:
            weather.bind_camera(context.scene)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class SUNNER_PT_weather(bpy.types.Panel):
    bl_label = "Weather"
    bl_idname = "SUNNER_PT_weather"
    bl_parent_id = "SUNNER_PT_cycle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sunner"

    @classmethod
    def poll(cls, context):
        try:
            return rig.get_rig(context.scene) is not None
        except rig.RigError:
            return False

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        try:
            if not weather.get(context.scene):
                layout.operator("sunner.weather_add", icon="WORLD")
                return
            collection = weather.parts(context.scene)
        except rig.RigError as error:
            layout.label(text=str(error), icon="ERROR")
            layout.operator("sunner.weather_remove", icon="TRASH")
            return
        root = collection["root"]
        layout.operator_menu_enum("sunner.weather_preset", "preset", text="Apply preset")
        for prop, label in (("fog_amount", "Fog"), ("cloud_coverage", "Clouds"),
                            ("rain_amount", "Rain"), ("shafts", "Shaft emphasis")):
            layout.prop(root, f'["{prop}"]', text=label, slider=True)
        layout.separator()
        layout.prop(root, '["extent"]', text="Region width (m)")
        layout.prop(root, "location", text="Region origin")
        layout.prop(root, '["fog_height"]', text="Fog height (m)")
        layout.prop(root, '["cloud_height"]', text="Cloud height (m)")
        layout.prop(root, '["wind_speed"]', text="Wind (m/s)")
        layout.prop(root, '["wind_direction"]', text="Wind heading")
        bound = collection["rain"].constraints.get("Rain camera")
        if not bound or bound.type != "COPY_LOCATION" or not bound.target or bound.target != context.scene.camera:
            layout.label(text="Rain needs a bound scene camera.", icon="INFO")
        layout.operator("sunner.weather_bind", icon="CAMERA_DATA")
        if context.scene.render.engine == "BLENDER_EEVEE":
            layout.prop(context.scene.eevee, "use_volumetric_shadows", text="Volume shadows")
            if not context.scene.eevee.use_volumetric_shadows:
                layout.label(text="Enable volume shadows for shafts.", icon="INFO")
        layout.operator("sunner.weather_remove", icon="TRASH")


class SUNNER_PT_weather_detail(bpy.types.Panel):
    bl_label = "Weather detail"
    bl_idname = "SUNNER_PT_weather_detail"
    bl_parent_id = "SUNNER_PT_weather"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sunner"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        try:
            return bool(weather.parts(context.scene))
        except rig.RigError:
            return False

    def draw(self, context):
        root = weather.parts(context.scene)["root"]
        layout = self.layout
        layout.use_property_split = True
        for prop, label in (("fog_distance", "Full fog visibility (m)"), ("cloud_size", "Cloud size (m)"),
                            ("rain_radius", "Rain radius (m)"), ("rain_height", "Rain height (m)"),
                            ("rain_speed", "Fall speed (m/s)"), ("streak_length", "Streak length (m)")):
            layout.prop(root, f'["{prop}"]', text=label)
        layout.label(text="Clouds are a thin sheet, not volume clouds.")
        layout.label(text="Rain has no collisions or splashes.")
        layout.label(text="Fog and shadows create natural shafts.")


CLASSES = (SUNNER_OT_weather_add, SUNNER_OT_weather_remove, SUNNER_OT_weather_preset,
           SUNNER_OT_weather_bind, SUNNER_PT_weather, SUNNER_PT_weather_detail)
