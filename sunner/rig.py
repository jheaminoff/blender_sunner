# SPDX-License-Identifier: GPL-3.0-or-later
"""One scene-owned rig. Existing World nodes are never edited."""

import math

import bpy

from .lighting import build_lighting, configure_twilight as configure_twilight_drivers

KEY = "sunner_rig"
SCHEMA = 1
CONTROLS = {
    "sun_brightness": (1.0, 0.0, 10.0, "Sun brightness multiplier"),
    "sky_brightness": (1.0, 0.0, 10.0, "Daytime sky brightness multiplier"),
    "night_brightness": (1.0, 0.0, 10.0, "Artistic moon and night sky brightness, not physical moonlight"),
    "haze": (1.0, 0.0, 5.0, "Sky aerosol density; does not add distance fog"),
    "warmth": (1.0, 0.0, 1.0, "Warmth of low sunlight"),
    "moon_tint": (0.35, 0.0, 1.0, "Cool tint of moonlight; zero is neutral"),
    "softness": (1.0, 0.1, 10.0, "Sun and moon angular size multiplier"),
}
TWILIGHT_CONTROLS = {
    "twilight_enabled": (False, None, None, "Enable the optional twilight balance"),
    "twilight_sky_gain": (3.0, 1.0, 10.0, "Daylight multiplier at -4° solar elevation"),
    "twilight_moon_gain": (0.15, 0.0, 1.0, "Moon and night multiplier at -4° solar elevation"),
}


class RigError(ValueError):
    pass


def get_rig(scene):
    collection = scene.get(KEY)
    if collection is None:
        return None
    if not isinstance(collection, bpy.types.Collection) or collection.get("sunner_schema") != SCHEMA:
        raise RigError("Invalid Sunner rig reference; inspect the scene's custom properties")
    return collection


def parts(scene):
    collection = get_rig(scene)
    if collection is None:
        raise RigError("Add a Sunner cycle first")
    result = {}
    for name in ("root", "dial", "sun", "moon", "world"):
        data = collection.get(name)
        expected = bpy.types.World if name == "world" else bpy.types.Object
        if not isinstance(data, expected):
            raise RigError(f"Sunner {name} is missing; undo its deletion or remove the rig")
        result[name] = data
    if any(name not in result["root"] for name in CONTROLS):
        raise RigError("Sunner controls are missing; undo the custom-property deletion")
    return result


def create(scene):
    existing = get_rig(scene)
    if existing is not None:
        parts(scene)
        return existing
    collection = bpy.data.collections.new("Sunner cycle")
    collection["sunner_schema"] = SCHEMA
    scene.collection.children.link(collection)
    scene[KEY] = collection
    # An ID reference holds a real user, so the previous World survives save/reload.
    if scene.world:
        collection["previous_world"] = scene.world
    try:
        _populate(scene, collection)
    except Exception:
        # Creation is synchronous; nothing else can have adopted these new objects.
        remove(scene)
        raise
    return collection


def _populate(scene, collection):
    def obj(role, name, data=None, parent=None):
        value = bpy.data.objects.new(name, data)
        collection[role] = value
        collection.objects.link(value)
        value.parent = parent
        value.rotation_mode = "XYZ"
        value.lock_location = value.lock_scale = (True, True, True)
        return value

    root = obj("root", "Sunner heading and tilt")
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = 2.0
    root.rotation_euler.y = math.radians(30)
    root.lock_rotation = (True, False, False)
    dial = obj("dial", "Sunner day dial", parent=root)
    dial.empty_display_type = "SINGLE_ARROW"
    dial.empty_display_size = 3.0
    dial.show_in_front = True
    dial.rotation_euler.x = math.radians(240)
    dial.lock_rotation = (False, True, True)
    for name, (default, low, high, description) in CONTROLS.items():
        root[name] = default
        root.id_properties_ui(name).update(min=low, max=high, description=description)
    _ensure_twilight_controls(root)
    # Keep data ownership separate from object references, which vanish on deletion.
    collection["sun_light"] = bpy.data.lights.new("Sunner sunlight", "SUN")
    collection["moon_light"] = bpy.data.lights.new("Sunner moonlight", "SUN")
    sun = obj("sun", "Sunner sun", collection["sun_light"], dial)
    moon = obj("moon", "Sunner moon", collection["moon_light"], dial)
    sun.rotation_euler.y = math.pi
    sun.hide_select = moon.hide_select = True
    sun.lock_rotation = moon.lock_rotation = (True, True, True)
    # Positions only separate viewport icons. SUN illumination has no distance falloff.
    sun.location.z, moon.location.z = -4, 4
    world = bpy.data.worlds.new("Sunner sky")
    collection["world"] = world
    build_lighting(world, root, dial, sun.data, moon.data)
    scene.world = world


def _ensure_twilight_controls(root):
    """Add opt-in controls without changing values already saved on an upgraded rig."""
    for name, (default, low, high, description) in TWILIGHT_CONTROLS.items():
        if name not in root:
            root[name] = default
        options = {"description": description}
        if low is not None:
            options["min"] = low
        if high is not None:
            options["max"] = high
        root.id_properties_ui(name).update(**options)


def _twilight_gain(value, name, minimum, maximum):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise RigError(f"{name} must be between {minimum:g} and {maximum:g}")
    return float(value)


def _check_twilight_ownership(scene, collection, result):
    """The World and moon light data must still belong exclusively to this rig."""
    owned_moon = collection.get("moon_light")
    if not isinstance(owned_moon, bpy.types.Light) or result["moon"].data != owned_moon:
        raise RigError("Sunner moon light data was replaced; restore its owned light before configuring twilight")
    allowed = {collection, scene, result["moon"]}
    for data in (result["world"], result["moon"].data):
        outside = bpy.data.user_map(subset={data}).get(data, set()) - allowed
        if outside:
            raise RigError(f"{data.name} is used outside this rig; unlink those references before configuring twilight")


def configure_twilight(scene, sky_gain=3.0, moon_gain=0.15):
    """Enable native twilight gains without changing the authoritative day dial."""
    sky_gain = _twilight_gain(sky_gain, "sky_gain", 1.0, 10.0)
    moon_gain = _twilight_gain(moon_gain, "moon_gain", 0.0, 1.0)
    collection = get_rig(scene)
    if collection is None:
        raise RigError("Add a Sunner cycle first")
    result = parts(scene)
    _check_twilight_ownership(scene, collection, result)
    _ensure_twilight_controls(result["root"])
    try:
        configure_twilight_drivers(result["world"], result["root"], result["dial"], result["moon"].data)
    except ValueError as error:
        raise RigError(str(error)) from error
    root = result["root"]
    root["twilight_sky_gain"] = sky_gain
    root["twilight_moon_gain"] = moon_gain
    root["twilight_enabled"] = True
    # Scripted ID-property writes at a fixed dial angle need an explicit dependency refresh.
    root.update_tag()


def check_removal(owned, allowed_users):
    """Validate the complete ownership set before unlinking any scene data."""
    for data in owned:
        if isinstance(data, bpy.types.Collection):
            if set(data.children) - owned or set(data.objects) - owned:
                raise RigError("Move non-Sunner objects and collections out of the Sunner collection first")
    for data, users in bpy.data.user_map(subset=owned).items():
        if users - owned - allowed_users:
            raise RigError(f"{data.name} is used outside this rig; unlink those references before removal")
    if any(data.use_fake_user for data in owned):
        raise RigError("A Sunner data-block is protected by a fake user; clear it before removal")


def remove(scene):
    """Remove the whole rig, including optional weather, only after checking all users."""
    collection = get_rig(scene)
    if collection is None:
        raise RigError("No Sunner cycle to remove")
    roles = ("root", "dial", "sun", "moon", "world", "sun_light", "moon_light")
    owned = {collection} | {collection[key] for key in roles if collection.get(key) is not None}
    if collection.get("weather"):
        from . import weather
        owned.update(weather.owned(collection["weather"]))
    check_removal(owned, {scene})
    if scene.world == collection.get("world"):
        scene.world = collection.get("previous_world")
    del scene[KEY]
    bpy.data.batch_remove(ids=owned)

