# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit, undoable editing operations. Playback uses only native Blender data."""

import math

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty

from . import rig


def select_dial(context):
    dial = rig.parts(context.scene)["dial"]
    context.view_layer.update()
    if dial.name not in context.view_layer.objects:
        raise rig.RigError("Enable the Sunner collection in this view layer first")
    for obj in context.selected_objects:
        obj.select_set(False)
    dial.hide_set(False)
    dial.select_set(True)
    context.view_layer.objects.active = dial


def angle_curves(dial):
    animation = dial.animation_data
    if not animation or not animation.action or not animation.action_slot:
        return []
    result = []
    for layer in animation.action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(animation.action_slot)
            if bag:
                result.extend((bag, curve) for curve in bag.fcurves
                              if curve.data_path == "rotation_euler" and curve.array_index == 0)
    return result


def animate(scene, start, duration, replace=False):
    """Key one full turn and loop with an offset; never duplicate the endpoint frame."""
    if duration < 2:
        raise rig.RigError("A cycle needs at least two frames")
    dial = rig.parts(scene)["dial"]
    animation = dial.animation_data
    if animation and (animation.nla_tracks or animation.drivers):
        raise rig.RigError("The day dial has NLA tracks or drivers; animate its angle manually")
    if angle_curves(dial) and not replace:
        raise rig.RigError("Day angle already has keyframes; confirm Replace day-angle keys")
    initial = dial.rotation_euler.x
    if animation and animation.action and animation.action.users > 1:
        slot_handle = animation.action_slot_handle
        animation.action = animation.action.copy()
        animation.action_slot_handle = slot_handle
    for bag, curve in angle_curves(dial):
        bag.fcurves.remove(curve)
    for frame, angle in ((start, initial), (start + duration, initial + math.tau)):
        dial.rotation_euler.x = angle
        dial.keyframe_insert("rotation_euler", index=0, frame=frame, group="Sunner day")
    for _, curve in angle_curves(dial):
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"
        modifier = curve.modifiers.new("CYCLES")
        modifier.mode_before = modifier.mode_after = "REPEAT_OFFSET"
    scene.frame_start = start
    scene.frame_end = start + duration - 1
    scene.frame_set(scene.frame_current)


class SUNNER_OT_add(bpy.types.Operator):
    bl_idname = "sunner.add"
    bl_label = "Add cycle"
    bl_description = "Create a daylight rig and assign its sky, preserving the current World"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def invoke(self, context, event):
        if context.scene.get(rig.KEY):
            return self.execute(context)
        return context.window_manager.invoke_confirm(
            self, event, title="Add Sunner cycle?",
            message="Assign a new sky. Your current World will be kept for restoration.",
        )

    def execute(self, context):
        try:
            rig.create(context.scene)
            select_dial(context)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "Cycle ready. Rotate the day dial on its local X axis")
        return {"FINISHED"}


class SUNNER_OT_select(bpy.types.Operator):
    bl_idname = "sunner.select"
    bl_label = "Select day dial"
    bl_description = "Select the controller; use R, X, X to rotate through the day"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            select_dial(context)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class SUNNER_OT_position(bpy.types.Operator):
    bl_idname = "sunner.position"
    bl_label = "Position day dial"
    bl_description = "Set the day angle; inserts a key when Auto Keying is enabled"
    bl_options = {"REGISTER", "UNDO"}

    angle: FloatProperty(subtype="ANGLE")

    def execute(self, context):
        try:
            dial = rig.parts(context.scene)["dial"]
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        turn = math.floor(dial.rotation_euler.x / math.tau)
        dial.rotation_euler.x = turn * math.tau + self.angle
        if context.scene.tool_settings.use_keyframe_insert_auto:
            dial.keyframe_insert("rotation_euler", index=0, group="Sunner day")
        return {"FINISHED"}


class SUNNER_OT_animate(bpy.types.Operator):
    bl_idname = "sunner.animate"
    bl_label = "Animate one day"
    bl_description = "Key and loop one linear turn; sets the scene playback range"
    bl_options = {"REGISTER", "UNDO"}

    start: IntProperty(name="First frame", default=1, min=0, max=100000)
    duration: IntProperty(name="Frames per day", default=240, min=2, max=100000)
    replace: BoolProperty(name="Replace day-angle keys", default=False)

    def invoke(self, context, event):
        self.start = context.scene.frame_start
        self.duration = max(2, context.scene.frame_end - self.start + 1)
        self.replace = False
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "start")
        layout.prop(self, "duration")
        layout.prop(self, "replace")
        layout.label(text="Starts at the current day angle.")
        layout.label(text="Sets playback range; excludes the duplicate endpoint.")

    def execute(self, context):
        try:
            animate(context.scene, self.start, self.duration, self.replace)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class SUNNER_OT_update(bpy.types.Operator):
    bl_idname = "sunner.update_cycle"
    bl_label = "Update cycle"
    bl_description = ("Add this version's controls (twilight balance, season, stars, discs) to an older "
                      "cycle; keeps saved values and rebuilds the managed sky")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            rig.update(context.scene)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "Cycle updated. Set Stars and Discs to 0 to keep the previous look")
        return {"FINISHED"}


class SUNNER_OT_remove(bpy.types.Operator):
    bl_idname = "sunner.remove"
    bl_label = "Remove cycle"
    bl_description = "Remove owned rig data and restore the previous World if Sunner's is still assigned"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event, title="Remove Sunner cycle?",
            message="Remove this rig and restore its previous World, unless you assigned another.",
        )

    def execute(self, context):
        try:
            rig.remove(context.scene)
        except rig.RigError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (
    SUNNER_OT_add,
    SUNNER_OT_select,
    SUNNER_OT_position,
    SUNNER_OT_animate,
    SUNNER_OT_update,
    SUNNER_OT_remove,
)
