# SPDX-License-Identifier: GPL-3.0-or-later
"""Native drivers and World nodes. No Python is required during playback."""

# The sun object's evaluated local +Z axis points at the sun. Every quantity reads that
# one world-space direction, so heading, path tilt, season and the day dial always agree.
SUN_AXIS = {"x": "matrix_world[2][0]", "y": "matrix_world[2][1]", "z": "matrix_world[2][2]"}
ELEVATION = "asin(clamp(z,-1,1))"
SUN_STRENGTH = 3.0
SKY_STRENGTH = 0.1
MOON_STRENGTH = 0.12
TWILIGHT_WINDOW = "smoothstep(-12,-4,{e})*(1-smoothstep(-4,4,{e}))"
SUN_DISC = 20.0     # Disc radiance per unit of sunlight energy; camera rays only.
MOON_DISC = 25.0    # Disc radiance per unit of moonlight energy; camera rays only.
DISC_RADIUS = 0.265  # Degrees at shadow softness 1, matching the lights' 0.53° angle.
STAR_SCALE = 180.0
STAR_GAIN = 20.0


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


def _axis(sun, names="z"):
    return {name: (sun, SUN_AXIS[name]) for name in names}


def _control(root, name):
    return {name: (root, f'["{name}"]')}


def _drive_twilight(root, sun, moon_light, daylight, night):
    """Replace affected drivers from their base formulas; never stack a gain."""
    e = f"degrees({ELEVATION})"
    window = TWILIGHT_WINDOW.format(e=e)
    gain = f"(1+a*(g-1)*({window}))"
    variables = _axis(sun) | {"a": (root, '["twilight_enabled"]')}
    moon_variables = variables | {
        "b": (root, '["night_brightness"]'),
        "g": (root, '["twilight_moon_gain"]'),
    }
    sky_variables = variables | {
        "b": (root, '["sky_brightness"]'),
        "g": (root, '["twilight_sky_gain"]'),
    }
    drive(moon_light, "energy", f"{MOON_STRENGTH}*b*smoothstep(0,4,-({e}))*{gain}", moon_variables)
    drive(daylight.inputs["Strength"], "default_value",
          f"{SKY_STRENGTH}*b*smoothstep(-18,-6,{e})*{gain}", sky_variables)
    drive(night.inputs["Strength"], "default_value",
          f"0.7*b*(1-smoothstep(-8,4,{e}))*{gain}", moon_variables)


def build_lighting(world, root, dial, sun, moon):
    """(Re)build every Sunner driver and the managed World's nodes; idempotent."""
    sun_light, moon_light = sun.data, moon.data
    # Season is the sun's declination: both lights leave the dial plane together,
    # so the moon stays exactly opposite, as a full moon does.
    drive(sun, "rotation_euler", "pi+season", _control(root, "season"), 1)
    drive(moon, "rotation_euler", "season", _control(root, "season"), 1)

    e = ELEVATION
    sun_light.normalize = moon_light.normalize = True
    sun_light.use_temperature = True
    sun_light.color = (1, 1, 1)
    drive(sun_light, "energy", (
        f"{SUN_STRENGTH}*sun_brightness*smoothstep(0,radians(3),{e})"
        f"*(0.18+0.82*smoothstep(0,radians(25),{e}))"
    ), _axis(sun) | _control(root, "sun_brightness"))
    drive(sun_light, "temperature", (
        f"6000-3200*warmth*(1-smoothstep(0,radians(30),{e}))"
    ), _axis(sun) | _control(root, "warmth"))
    for i, tint in enumerate((0.78, 0.86, 1.0)):
        drive(moon_light, "color", f"1-({1-tint})*moon_tint", _control(root, "moon_tint"), i)
    for light in (sun_light, moon_light):
        drive(light, "angle", "radians(0.53)*softness", _control(root, "softness"))

    world.sun_threshold = 0.0
    tree = world.node_tree
    tree.nodes.clear()

    def node(kind, name, location):
        result = tree.nodes.new(kind)
        result.name = result.label = name
        result.location = location
        return result

    def link(socket, value):
        if hasattr(value, "is_linked"):
            tree.links.new(value, socket)
        else:
            socket.default_value = value

    def math(operation, a, b, location):
        result = node("ShaderNodeMath", f"{operation.title()} {location[0]},{location[1]}", location)
        result.operation = operation
        link(result.inputs[0], a)
        link(result.inputs[1], b)
        return result.outputs[0]

    def ramp(value, start, end, name, location):
        result = node("ShaderNodeMapRange", name, location)
        result.interpolation_type = "SMOOTHSTEP"
        link(result.inputs["Value"], value)
        link(result.inputs["From Min"], start)
        link(result.inputs["From Max"], end)
        return result.outputs["Result"]

    sky = node("ShaderNodeTexSky", "Sunner atmosphere", (-650, 300))
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = False
    sky.altitude = 0
    sky.air_density = sky.ozone_density = 1
    drive(sky, "sun_elevation", f"max(radians(-18),{e})", _axis(sun))
    # Blender's Sky Texture uses clockwise azimuth measured from +Y.
    drive(sky, "sun_rotation", "atan2(x,y)", _axis(sun, "xy"))
    drive(sky, "aerosol_density", "haze", _control(root, "haze"))

    daylight = node("ShaderNodeBackground", "Sunner daylight", (-300, 300))
    tree.links.new(sky.outputs["Color"], daylight.inputs["Color"])

    coords = node("ShaderNodeTexCoord", "Sky direction", (-1500, -200))
    # In World shaders, Generated is the view direction; Normal is its negation.
    direction = coords.outputs["Generated"]
    separate = node("ShaderNodeSeparateXYZ", "Night elevation", (-1300, -100))
    # Kept as calibrated in 0.1: Normal makes the gradient uniform above the horizon.
    tree.links.new(coords.outputs["Normal"], separate.inputs["Vector"])
    gradient = node("ShaderNodeValToRGB", "Night gradient", (-1100, 0))
    tree.links.new(separate.outputs["Z"], gradient.inputs["Fac"])
    gradient.color_ramp.elements[0].position = 0
    gradient.color_ramp.elements[0].color = (0.025, 0.034, 0.055, 1)
    gradient.color_ramp.elements[1].position = 1
    gradient.color_ramp.elements[1].color = (0.006, 0.010, 0.023, 1)

    # Stars are fixed in the dial's frame, so they wheel around the celestial pole.
    frame = node("ShaderNodeVectorRotate", "Star frame", (-1300, -400))
    frame.rotation_type = "EULER_XYZ"
    frame.invert = True
    tree.links.new(direction, frame.inputs["Vector"])
    for i, (owner, path) in enumerate(((dial, "rotation_euler[0]"), (root, "rotation_euler[1]"),
                                       (root, "rotation_euler[2]"))):
        drive(frame.inputs["Rotation"], "default_value", "r", {"r": (owner, path)}, i)
    field = node("ShaderNodeTexVoronoi", "Star field", (-1100, -400))
    field.inputs["Scale"].default_value = STAR_SCALE
    tree.links.new(frame.outputs["Vector"], field.inputs["Vector"])
    point = ramp(field.outputs["Distance"], 0.1, 0.0, "Star points", (-900, -350))
    magnitude = math("POWER", field.outputs["Color"], 6, (-900, -550))
    height = node("ShaderNodeSeparateXYZ", "Star elevation", (-1100, -200))
    tree.links.new(direction, height.inputs["Vector"])
    horizon = ramp(height.outputs["Z"], 0.0, 0.12, "Star horizon", (-900, -150))
    amount = node("ShaderNodeValue", "Star brightness", (-900, -700)).outputs[0]
    # Stars appear only after civil twilight, between -6° and -12° solar elevation.
    drive(amount, "default_value", f"{STAR_GAIN}*stars*(1-smoothstep(-12,-6,degrees({e})))",
          _control(root, "stars") | _axis(sun))
    star = math("MULTIPLY", math("MULTIPLY", point, magnitude, (-700, -450)),
                math("MULTIPLY", horizon, amount, (-700, -250)), (-500, -350))
    night_sky = node("ShaderNodeVectorMath", "Night sky with stars", (-300, -150))
    night_sky.operation = "ADD"
    tree.links.new(gradient.outputs["Color"], night_sky.inputs[0])
    tree.links.new(star, night_sky.inputs[1])

    night = node("ShaderNodeBackground", "Sunner night", (-100, -100))
    tree.links.new(night_sky.outputs["Vector"], night.inputs["Color"])
    add = node("ShaderNodeAddShader", "Day and night", (180, 220))
    tree.links.new(daylight.outputs[0], add.inputs[0])
    tree.links.new(night.outputs[0], add.inputs[1])
    _drive_twilight(root, sun, moon_light, daylight, night)

    # Visible discs are camera-only, so explicit SUN lights remain the only direct light.
    sun_direction = node("ShaderNodeCombineXYZ", "Sun direction", (-1300, -900))
    for i, name in enumerate("xyz"):
        drive(sun_direction.inputs[i], "default_value", name, _axis(sun, name))
    moon_direction = node("ShaderNodeVectorMath", "Moon direction", (-1100, -1000))
    moon_direction.operation = "SCALE"
    tree.links.new(sun_direction.outputs[0], moon_direction.inputs[0])
    moon_direction.inputs["Scale"].default_value = -1
    radius = node("ShaderNodeValue", "Disc radius", (-1100, -1200)).outputs[0]
    drive(radius, "default_value", f"radians({DISC_RADIUS})*softness", _control(root, "softness"))
    edge = math("MULTIPLY", radius, 0.8, (-900, -1250))
    camera = node("ShaderNodeLightPath", "Camera only", (-900, -1450)).outputs["Is Camera Ray"]
    sun_colour = node("ShaderNodeBlackbody", "Sun disc colour", (-700, -800))
    drive(sun_colour.inputs["Temperature"], "default_value", "k", {"k": (sun_light, "temperature")})
    shader = add
    for name, target, colour, light, gain, y in (
            ("Sun disc", sun_direction.outputs[0], sun_colour.outputs[0], sun_light, SUN_DISC, -900),
            ("Moon disc", moon_direction.outputs["Vector"], (0.9, 0.92, 0.96), moon_light, MOON_DISC, -1150)):
        distance = node("ShaderNodeVectorMath", f"{name} distance", (-700, y))
        distance.operation = "DISTANCE"
        tree.links.new(direction, distance.inputs[0])
        tree.links.new(target, distance.inputs[1])
        mask = math("MULTIPLY", ramp(distance.outputs["Value"], radius, edge, f"{name} edge", (-500, y)),
                    camera, (-300, y))
        tinted = node("ShaderNodeVectorMath", f"{name} mask", (-100, y))
        tinted.operation = "SCALE"
        link(tinted.inputs[0], colour)
        tree.links.new(mask, tinted.inputs["Scale"])
        disc = node("ShaderNodeBackground", name, (100, y))
        tree.links.new(tinted.outputs["Vector"], disc.inputs["Color"])
        drive(disc.inputs["Strength"], "default_value", f"{gain}*discs*v",
              _control(root, "discs") | {"v": (light, "energy")})
        combined = node("ShaderNodeAddShader", f"With {name.lower()}", (350, y))
        tree.links.new(shader.outputs[0], combined.inputs[0])
        tree.links.new(disc.outputs[0], combined.inputs[1])
        shader = combined
    output = node("ShaderNodeOutputWorld", "Sunner output", (600, 220))
    tree.links.new(shader.outputs[0], output.inputs["Surface"])
