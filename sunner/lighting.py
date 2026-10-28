# SPDX-License-Identifier: GPL-3.0-or-later
"""Native drivers and World nodes. No Python is required during playback."""

# All quantities come from the same local orbit, Rz(heading) Ry(tilt) Rx(phase).
ELEVATION = "asin(clamp(-cos(tilt)*cos(phase), -1, 1))"
BASE_X = "(-sin(tilt)*cos(phase))"
BASE_Y = "sin(phase)"
X = f"(cos(heading)*{BASE_X}-sin(heading)*{BASE_Y})"
Y = f"(sin(heading)*{BASE_X}+cos(heading)*{BASE_Y})"
SUN_STRENGTH = 3.0
SKY_STRENGTH = 0.1
MOON_STRENGTH = 0.12
TWILIGHT_WINDOW = "smoothstep(-12,-4,{e})*(1-smoothstep(-4,4,{e}))"


def drive(owner, path, expression, variables, index=None):
    """Use explicit RNA dependencies and Blender's safe expression subset."""
    if len(expression.encode("utf-8")) > 255:
        raise ValueError("Native driver expression exceeds Blender's 255-byte limit")
    curve = owner.driver_add(path) if index is None else owner.driver_add(path, index)
    driver = curve.driver
    driver.type = "SCRIPTED"
    for existing in list(driver.variables):
        driver.variables.remove(existing)
    for name, (data, data_path) in variables.items():
        variable = driver.variables.new()
        variable.name = name
        variable.type = "SINGLE_PROP"
        variable.targets[0].id_type = data.id_type
        variable.targets[0].id = data
        variable.targets[0].data_path = data_path
    driver.expression = expression
    return curve


def _orbit(root, dial):
    return {
        "phase": (dial, "rotation_euler[0]"),
        "tilt": (root, "rotation_euler[1]"),
    }


def _control(root, name):
    return {name: (root, f'["{name}"]')}


def _twilight_targets(world):
    tree = world.node_tree
    if tree is None:
        raise ValueError("Sunner World has no node tree")
    daylight = tree.nodes.get("Sunner daylight")
    night = tree.nodes.get("Sunner night")
    if (daylight is None or daylight.bl_idname != "ShaderNodeBackground" or
            night is None or night.bl_idname != "ShaderNodeBackground"):
        raise ValueError("Sunner World nodes are missing; undo their deletion or remove the rig")
    return daylight, night


def _drive_twilight(world, root, dial, moon):
    """Replace affected drivers from their base formulas; never stack a gain."""
    daylight, night = _twilight_targets(world)
    # Short variable names and degree thresholds keep each native expression
    # below Blender's 255-byte storage limit without adding derived time state.
    e = "degrees(" + ELEVATION.replace("tilt", "t").replace("phase", "p").replace(" ", "") + ")"
    window = TWILIGHT_WINDOW.format(e=e)
    gain = f"(1+a*(g-1)*({window}))"
    variables = {
        "p": (dial, "rotation_euler[0]"),
        "t": (root, "rotation_euler[1]"),
        "a": (root, '["twilight_enabled"]'),
    }
    moon_variables = variables | {
        "b": (root, '["night_brightness"]'),
        "g": (root, '["twilight_moon_gain"]'),
    }
    sky_variables = variables | {
        "b": (root, '["sky_brightness"]'),
        "g": (root, '["twilight_sky_gain"]'),
    }
    drive(moon, "energy", f"{MOON_STRENGTH}*b*smoothstep(0,4,-({e}))*{gain}", moon_variables)
    drive(daylight.inputs["Strength"], "default_value",
          f"{SKY_STRENGTH}*b*smoothstep(-18,-6,{e})*{gain}", sky_variables)
    drive(night.inputs["Strength"], "default_value",
          f"0.7*b*(1-smoothstep(-8,4,{e}))*{gain}", moon_variables)


def configure_twilight(world, root, dial, moon):
    """Install the optional native gain drivers on an existing managed World."""
    _drive_twilight(world, root, dial, moon)


def build_lighting(world, root, dial, sun, moon):
    orbit = _orbit(root, dial)

    sun.normalize = moon.normalize = True
    sun.use_temperature = True
    sun.color = (1, 1, 1)
    e = ELEVATION
    drive(sun, "energy", (
        f"{SUN_STRENGTH}*sun_brightness*smoothstep(0,radians(3),{e})"
        f"*(0.18+0.82*smoothstep(0,radians(25),{e}))"
    ), orbit | _control(root, "sun_brightness"))
    drive(sun, "temperature", (
        f"6000-3200*warmth*(1-smoothstep(0,radians(30),{e}))"
    ), orbit | _control(root, "warmth"))
    for i, tint in enumerate((0.78, 0.86, 1.0)):
        drive(moon, "color", f"1-({1-tint})*moon_tint", _control(root, "moon_tint"), i)
    for light in (sun, moon):
        drive(light, "angle", "radians(0.53)*softness", _control(root, "softness"))

    world.sun_threshold = 0.0
    tree = world.node_tree
    tree.nodes.clear()

    def node(kind, name, location):
        result = tree.nodes.new(kind)
        result.name = result.label = name
        result.location = location
        return result

    sky = node("ShaderNodeTexSky", "Sunner atmosphere", (-650, 300))
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = False
    sky.altitude = 0
    sky.air_density = sky.ozone_density = 1
    drive(sky, "sun_elevation", f"max(radians(-18),{e})", orbit)
    # Blender's Sky Texture uses clockwise azimuth measured from +Y.
    drive(sky, "sun_rotation", f"atan2({X},{Y})", orbit | {
        "heading": (root, "rotation_euler[2]"),
    })
    drive(sky, "aerosol_density", "haze", _control(root, "haze"))

    daylight = node("ShaderNodeBackground", "Sunner daylight", (-300, 300))
    tree.links.new(sky.outputs["Color"], daylight.inputs["Color"])

    coords = node("ShaderNodeTexCoord", "Night direction", (-900, -200))
    separate = node("ShaderNodeSeparateXYZ", "Night elevation", (-700, -200))
    gradient = node("ShaderNodeValToRGB", "Night gradient", (-480, -160))
    tree.links.new(coords.outputs["Normal"], separate.inputs["Vector"])
    tree.links.new(separate.outputs["Z"], gradient.inputs["Fac"])
    gradient.color_ramp.elements[0].position = 0
    gradient.color_ramp.elements[0].color = (0.025, 0.034, 0.055, 1)
    gradient.color_ramp.elements[1].position = 1
    gradient.color_ramp.elements[1].color = (0.006, 0.010, 0.023, 1)

    night = node("ShaderNodeBackground", "Sunner night", (-100, -100))
    tree.links.new(gradient.outputs["Color"], night.inputs["Color"])
    add = node("ShaderNodeAddShader", "Day and night", (180, 220))
    tree.links.new(daylight.outputs[0], add.inputs[0])
    tree.links.new(night.outputs[0], add.inputs[1])
    _drive_twilight(world, root, dial, moon)
    output = node("ShaderNodeOutputWorld", "Sunner output", (400, 220))
    tree.links.new(add.outputs[0], output.inputs["Surface"])

