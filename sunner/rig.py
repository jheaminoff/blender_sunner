# SPDX-License-Identifier: GPL-3.0-or-later
"""One scene-owned rig. Existing World nodes are never edited."""

import math

import bpy

from .lighting import build_lighting

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
# Added after 0.1; older rigs gain them only through update().
SOLSTICE = math.radians(23.44)
OPTIONAL_CONTROLS = {
    "twilight_enabled": (False, None, None, "Enable the optional twilight balance"),
    "twilight_sky_gain": (3.0, 1.0, 10.0, "Daylight multiplier at -4° solar elevation"),
    "twilight_moon_gain": (0.15, 0.0, 1.0, "Moon and night multiplier at -4° solar elevation"),
    "season": (0.0, -SOLSTICE, SOLSTICE, "Sun declination: +23.4° midsummer, 0° equinox, -23.4° midwinter"),
    "stars": (1.0, 0.0, 10.0, "Star field brightness; fades with daylight"),
    "discs": (1.0, 0.0, 10.0, "Visible sun and moon disc brightness; camera rays only"),
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
    _ensure_optional_controls(root)
    # Keep data ownership separate from object references, which vanish on deletion.
    collection["sun_light"] = bpy.data.lights.new("Sunner sunlight", "SUN")
    collection["moon_light"] = bpy.data.lights.new("Sunner moonlight", "SUN")
    sun = obj("sun", "Sunner sun", collection["sun_light"], dial)
    moon = obj("moon", "Sunner moon", collection["moon_light"], dial)
    sun.hide_select = moon.hide_select = True
    sun.lock_rotation = moon.lock_rotation = (True, True, True)
    # Positions only separate viewport icons. SUN illumination has no distance falloff.
    sun.location.z, moon.location.z = -4, 4
    world = bpy.data.worlds.new("Sunner sky")
    collection["world"] = world
    build_lighting(world, root, dial, sun, moon)
    scene.world = world


def _ensure_optional_controls(root):
    """Add newer controls without changing values already saved on an upgraded rig."""
    for name, (default, low, high, description) in OPTIONAL_CONTROLS.items():
        if name not in root:
            root[name] = default
        options = {"description": description}
        if low is not None:
            options["min"] = low
        if high is not None:
            options["max"] = high
        root.id_properties_ui(name).update(**options)
    root.id_properties_ui("season").update(subtype="ANGLE")


def needs_update(root):
    return any(name not in root for name in OPTIONAL_CONTROLS)


def _twilight_gain(value, name, minimum, maximum):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise RigError(f"{name} must be between {minimum:g} and {maximum:g}")
    return float(value)


def _check_ownership(scene, collection, result):
    """The World and light data must still belong exclusively to this rig."""
    for role, key in (("sun", "sun_light"), ("moon", "moon_light")):
        owned = collection.get(key)
        if not isinstance(owned, bpy.types.Light) or result[role].data != owned:
            raise RigError(f"Sunner {role} light data was replaced; restore its owned light before updating")
    for data, allowed in ((result["world"], {collection, scene}),
                          # The World's disc drivers read the lights' energy and colour.
                          (result["sun"].data, {collection, result["sun"], result["world"]}),
                          (result["moon"].data, {collection, result["moon"], result["world"]})):
        outside = bpy.data.user_map(subset={data}).get(data, set()) - allowed
        if outside:
            raise RigError(f"{data.name} is used outside this rig; unlink those references before updating")


def update(scene):
    """Bring an older rig's controls, drivers and managed World nodes to this version.

    Saved control values and the day dial are kept; the managed World's nodes are rebuilt.
    """
    collection = get_rig(scene)
    if collection is None:
        raise RigError("Add a Sunner cycle first")
    result = parts(scene)
    _check_ownership(scene, collection, result)
    root = result["root"]
    _ensure_optional_controls(root)
    build_lighting(result["world"], root, result["dial"], result["sun"], result["moon"])
    # Scripted ID-property writes at a fixed dial angle need an explicit dependency refresh.
    root.update_tag()
    return result


def configure_twilight(scene, sky_gain=3.0, moon_gain=0.15):
    """Enable native twilight gains without changing the authoritative day dial."""
    sky_gain = _twilight_gain(sky_gain, "sky_gain", 1.0, 10.0)
    moon_gain = _twilight_gain(moon_gain, "moon_gain", 0.0, 1.0)
    root = update(scene)["root"]
    root["twilight_sky_gain"] = sky_gain
    root["twilight_moon_gain"] = moon_gain
    root["twilight_enabled"] = True
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

