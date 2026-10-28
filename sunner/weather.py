# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional bounded atmosphere and camera-local rain, evaluated by native nodes."""

import math
import random

import bpy

from . import rig
from .lighting import drive

KEY = "weather"
CONTROLS = {
    "extent": (1000.0, 10.0, 100000.0, "Width of the weather region, in metres"),
    "fog_amount": (0.0, 0.0, 1.0, "Fog scattering amount; zero disables the volume"),
    "fog_height": (150.0, 1.0, 10000.0, "Fog height above the region origin, in metres"),
    "fog_distance": (1000.0, 10.0, 100000.0, "Approximate ground-level visibility in metres at full fog"),
    "shafts": (0.65, 0.0, 0.85, "Forward scattering; beams still require light and occlusion"),
    "cloud_coverage": (0.0, 0.0, 1.0, "Procedural cloud coverage; zero disables the cloud layer"),
    "cloud_height": (300.0, 5.0, 15000.0, "Cloud layer height above the region origin, in metres"),
    "cloud_size": (250.0, 5.0, 10000.0, "Cloud pattern scale in metres"),
    "rain_amount": (0.0, 0.0, 1.0, "Fraction of 2048 instanced rain streaks near the bound camera"),
    "rain_radius": (20.0, 2.0, 200.0, "Half-width of the camera-local rain region in metres"),
    "rain_height": (25.0, 2.0, 200.0, "Height of the camera-local rain region in metres"),
    "rain_speed": (12.0, 0.1, 50.0, "Rain fall speed in metres per second"),
    "streak_length": (0.4, 0.02, 3.0, "Visible rain streak length in metres, not a simulated drop size"),
    "wind_speed": (2.0, 0.0, 40.0, "Horizontal cloud and rain drift in metres per second"),
    "wind_direction": (0.0, -math.tau, math.tau, "Wind heading in radians, zero along world X"),
}
PRESETS = {
    "CLEAR": ("Clear", {"fog_amount": 0.0, "cloud_coverage": 0.0, "rain_amount": 0.0, "shafts": 0.65}),
    "MISTY": ("Misty", {"fog_amount": 0.55, "cloud_coverage": 0.15, "rain_amount": 0.0, "shafts": 0.7}),
    "CLOUDY": ("Cloudy", {"fog_amount": 0.12, "cloud_coverage": 0.5, "rain_amount": 0.0, "shafts": 0.65}),
    "OVERCAST": ("Overcast", {"fog_amount": 0.2, "cloud_coverage": 0.9, "rain_amount": 0.0, "shafts": 0.25}),
    "RAINY": ("Rainy", {"fog_amount": 0.35, "cloud_coverage": 0.8, "rain_amount": 0.7, "shafts": 0.35}),
}
ROLES = ("root", "fog", "cloud", "rain", "fog_mesh", "cloud_mesh", "rain_mesh",
         "fog_material", "cloud_material", "rain_material", "rain_nodes")


def validate(collection):
    if not isinstance(collection, bpy.types.Collection) or collection.get("sunner_weather_schema") != 1:
        raise rig.RigError("Invalid Sunner weather reference; inspect the rig's custom properties")
    return collection


def get(scene):
    collection = rig.get_rig(scene)
    weather = collection.get(KEY) if collection else None
    return validate(weather) if weather is not None else None


def parts(scene):
    collection = get(scene)
    if not isinstance(collection, bpy.types.Collection):
        raise rig.RigError("Add weather first")
    for role, kind in (("root", bpy.types.Object), ("fog", bpy.types.Object),
                       ("cloud", bpy.types.Object), ("rain", bpy.types.Object)):
        if not isinstance(collection.get(role), kind):
            raise rig.RigError(f"Weather {role} is missing; undo deletion or remove weather")
    if any(name not in collection["root"] for name in CONTROLS):
        raise rig.RigError("Weather controls are missing; undo deletion or remove weather")
    return collection


def owned(collection):
    validate(collection)
    return {collection} | {collection[key] for key in ROLES if collection.get(key) is not None}


def node(tree, kind, name):
    value = tree.nodes.new(kind)
    value.name = value.label = name
    value.location = ((len(tree.nodes) % 5) * 220, -(len(tree.nodes) // 5) * 160)
    return value


def feed(tree, socket, value):
    if isinstance(value, bpy.types.NodeSocket):
        tree.links.new(value, socket)
    else:
        socket.default_value = value


def calc(tree, operation, *values):
    value = node(tree, "ShaderNodeMath", operation)
    value.operation = operation
    for socket, source in zip(value.inputs, values):
        feed(tree, socket, source)
    return value.outputs[0]


def edge_fade(tree, xyz, steepness):
    fades = []
    for axis in ("X", "Y"):
        edge = calc(tree, "MINIMUM", xyz.outputs[axis], calc(tree, "SUBTRACT", 1, xyz.outputs[axis]))
        fades.append(calc(tree, "MINIMUM", 1, calc(tree, "MULTIPLY", edge, steepness)))
    return calc(tree, "MULTIPLY", *fades)


def variable(scene, root, name):
    if name == "u":
        return scene, "unit_settings.scale_length"
    if name == "fps":
        return scene, "render.fps"
    if name == "fps_base":
        return scene, "render.fps_base"
    return root, f'["{name}"]'


def driven(owner, path, expression, scene, root, names, index=None):
    return drive(owner, path, expression,
                 {name: variable(scene, root, name) for name in names.split()}, index)


def value(tree, scene, root, name, expression, names):
    result = node(tree, "ShaderNodeValue", name).outputs[0]
    driven(result, "default_value", expression, scene, root, names)
    return result


def visibility(obj, control, scene, root):
    # Keep viewport nodes evaluable; their shader/geometry inputs turn the effects off.
    driven(obj, "hide_render", f"{control}<=0", scene, root, control)


def create(scene):
    rig.parts(scene)
    if get(scene):
        return parts(scene)
    parent = rig.get_rig(scene)
    collection = bpy.data.collections.new("Sunner weather")
    collection["sunner_weather_schema"] = 1
    parent.children.link(collection)
    parent[KEY] = collection
    try:
        _populate(scene, collection)
    except Exception:
        remove(scene)
        raise
    return collection


def _populate(scene, collection):
    def obj(role, vertices=None, faces=()):
        mesh = None
        if vertices is not None:
            mesh = bpy.data.meshes.new(f"Sunner {role} mesh")
            collection[f"{role}_mesh"] = mesh
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
        result = bpy.data.objects.new(f"Sunner weather {role}", mesh)
        collection[role] = result
        collection.objects.link(result)
        if role != "root":
            result.hide_select = True
        return result

    def material(role):
        mat = bpy.data.materials.new(f"Sunner {role}")
        collection[f"{role}_material"] = mat
        mat.node_tree.nodes.clear()
        collection[role].data.materials.append(mat)
        return mat

    root = obj("root")
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 10 / scene.unit_settings.scale_length
    root.lock_rotation = root.lock_scale = (True, True, True)
    for name, (default, low, high, description) in CONTROLS.items():
        root[name] = default
        root.id_properties_ui(name).update(min=low, max=high, description=description)
    root.id_properties_ui("wind_direction").update(subtype="ANGLE")
    # Unit cube with its base at the region origin. Generated Z runs from ground to ceiling.
    fog = obj("fog", [(x, y, z) for z in (0, 1) for y in (-0.5, 0.5) for x in (-0.5, 0.5)],
              [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])
    fog.parent = root
    fog.display_type = "WIRE"
    cloud = obj("cloud", [(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [(0, 1, 2, 3)])
    cloud.parent = root
    rng = random.Random(1729)
    rain = obj("rain", [(rng.random(), rng.random(), rng.random()) for _ in range(2048)])
    rain.constraints.new("COPY_LOCATION").name = "Rain camera"
    for i in (0, 1):
        driven(fog, "scale", "extent/u", scene, root, "extent u", i)
        driven(cloud, "scale", "5*extent/u", scene, root, "extent u", i)
    driven(fog, "scale", "fog_height/u", scene, root, "fog_height u", 2)
    driven(cloud, "location", "cloud_height/u", scene, root, "cloud_height u", 2)
    visibility(fog, "fog_amount", scene, root)
    visibility(cloud, "cloud_coverage", scene, root)
    _fog(material("fog"), scene, root)
    _cloud(material("cloud"), scene, root)
    _rain(material("rain"), scene, root, collection)
    bind_camera(scene)


def _fog(material, scene, root):
    tree = material.node_tree
    coords = node(tree, "ShaderNodeTexCoord", "Fog bounds")
    xyz = node(tree, "ShaderNodeSeparateXYZ", "Height and edges")
    tree.links.new(coords.outputs["Generated"], xyz.inputs[0])
    height = calc(tree, "POWER", calc(tree, "SUBTRACT", 1, xyz.outputs["Z"]), 2)
    boundary = edge_fade(tree, xyz, 10)
    amount = value(tree, scene, root, "Fog amount", "fog_amount", "fog_amount")
    distance = value(tree, scene, root, "Visibility in scene units", "fog_distance/u", "fog_distance u")
    # Blender F-curves zero very small results. Compute density inside the shader,
    # not in an RNA driver, so centimetre scenes retain the same physical fog.
    density = calc(tree, "DIVIDE", calc(tree, "MULTIPLY", 3.912, amount), distance)
    density = calc(tree, "MULTIPLY", density, height)
    density = calc(tree, "MULTIPLY", density, boundary)
    scatter = node(tree, "ShaderNodeVolumeScatter", "Fog scattering")
    scatter.inputs["Color"].default_value = (0.88, 0.92, 1.0, 1)
    tree.links.new(density, scatter.inputs["Density"])
    driven(scatter.inputs["Anisotropy"], "default_value", "shafts", scene, root, "shafts")
    output = node(tree, "ShaderNodeOutputMaterial", "Fog output")
    tree.links.new(scatter.outputs[0], output.inputs["Volume"])


def _cloud(material, scene, root):
    material.surface_render_method = "DITHERED"
    material.use_transparent_shadow = True
    tree = material.node_tree
    coords = node(tree, "ShaderNodeTexCoord", "World-relative cloud coordinates")
    coords.object = root
    scale = node(tree, "ShaderNodeVectorMath", "Cloud size")
    scale.operation = "SCALE"
    cloud_size = value(tree, scene, root, "Cloud size in scene units", "cloud_size/u", "cloud_size u")
    tree.links.new(calc(tree, "DIVIDE", 1, cloud_size), scale.inputs[3])
    wind = node(tree, "ShaderNodeVectorMath", "Cloud wind")
    wind.operation = "ADD"
    tree.links.new(coords.outputs["Object"], wind.inputs[0])
    tree.links.new(wind.outputs[0], scale.inputs[0])
    for i, trig in ((0, "cos"), (1, "sin")):
        driven(wind.inputs[1], "default_value",
               f"-frame*fps_base/fps*wind_speed*{trig}(wind_direction)/u", scene, root,
               "fps_base fps wind_speed wind_direction u", i)
    noise = node(tree, "ShaderNodeTexNoise", "Cloud pattern")
    noise.inputs["Scale"].default_value = 1
    noise.inputs["Detail"].default_value = 2
    tree.links.new(scale.outputs[0], noise.inputs["Vector"])
    coverage = value(tree, scene, root, "Coverage threshold", "1-cloud_coverage", "cloud_coverage")
    mask = calc(tree, "SUBTRACT", noise.outputs["Fac"], coverage)
    mask = calc(tree, "MINIMUM", 1, calc(tree, "MAXIMUM", 0, calc(tree, "MULTIPLY", mask, 6)))
    edges = node(tree, "ShaderNodeSeparateXYZ", "Cloud boundaries")
    tree.links.new(coords.outputs["Generated"], edges.inputs[0])
    mask = calc(tree, "MULTIPLY", mask, edge_fade(tree, edges, 4))
    transparent = node(tree, "ShaderNodeBsdfTransparent", "Cloud gaps")
    diffuse = node(tree, "ShaderNodeBsdfDiffuse", "Cloud reflection")
    translucent = node(tree, "ShaderNodeBsdfTranslucent", "Soft cloud transmission")
    for bsdf in (diffuse, translucent):
        bsdf.inputs["Color"].default_value = (0.8, 0.82, 0.86, 1)
    cloud = node(tree, "ShaderNodeMixShader", "Thin cloud scattering")
    cloud.inputs[0].default_value = 0.65
    tree.links.new(diffuse.outputs[0], cloud.inputs[1])
    tree.links.new(translucent.outputs[0], cloud.inputs[2])
    mix = node(tree, "ShaderNodeMixShader", "Cloud coverage")
    tree.links.new(mask, mix.inputs[0])
    tree.links.new(transparent.outputs[0], mix.inputs[1])
    tree.links.new(cloud.outputs[0], mix.inputs[2])
    output = node(tree, "ShaderNodeOutputMaterial", "Cloud output")
    tree.links.new(mix.outputs[0], output.inputs["Surface"])


def _rain(material, scene, root, collection):
    tree = material.node_tree
    shader = node(tree, "ShaderNodeBsdfPrincipled", "Rain streaks")
    shader.inputs["Base Color"].default_value = (0.5, 0.6, 0.7, 1)
    shader.inputs["Metallic"].default_value = 0.3
    shader.inputs["Roughness"].default_value = 0.2
    output = node(tree, "ShaderNodeOutputMaterial", "Rain output")
    tree.links.new(shader.outputs[0], output.inputs["Surface"])
    tree = bpy.data.node_groups.new("Sunner rain instances", "GeometryNodeTree")
    collection["rain_nodes"] = tree
    tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    modifier = collection["rain"].modifiers.new("Camera-local rain", "NODES")
    modifier.node_group = tree
    incoming = node(tree, "NodeGroupInput", "Rain seeds")
    position = node(tree, "GeometryNodeInputPosition", "Seed positions")
    xyz = node(tree, "ShaderNodeSeparateXYZ", "Seed coordinates")
    tree.links.new(position.outputs[0], xyz.inputs[0])
    combined = node(tree, "ShaderNodeCombineXYZ", "Wrapped positions")
    for i, axis in enumerate(("X", "Y", "Z")):
        size = "rain_height" if axis == "Z" else "2*rain_radius"
        speed = "-rain_speed" if axis == "Z" else f"wind_speed*{'cos' if axis == 'X' else 'sin'}(wind_direction)"
        offset = value(tree, scene, root, f"{axis} drift", f"frame*fps_base/fps*({speed})/({size})",
                       "fps_base fps rain_speed rain_height" if axis == "Z" else "fps_base fps wind_speed wind_direction rain_radius")
        metres = value(tree, scene, root, f"{axis} region", f"({size})/u",
                       "rain_height u" if axis == "Z" else "rain_radius u")
        wrapped = calc(tree, "FRACT", calc(tree, "ADD", xyz.outputs[axis], offset))
        coord = calc(tree, "MULTIPLY", calc(tree, "SUBTRACT", wrapped, 0.5), metres)
        tree.links.new(coord, combined.inputs[i])
    moved = node(tree, "GeometryNodeSetPosition", "Falling rain")
    tree.links.new(incoming.outputs["Geometry"], moved.inputs["Geometry"])
    tree.links.new(combined.outputs[0], moved.inputs["Position"])
    points = node(tree, "GeometryNodeMeshToPoints", "Rain points")
    points.mode = "VERTICES"
    tree.links.new(moved.outputs[0], points.inputs["Mesh"])
    index = node(tree, "GeometryNodeInputIndex", "Stable drop index")
    count = value(tree, scene, root, "Rain amount", "2048*rain_amount", "rain_amount")
    selected = calc(tree, "LESS_THAN", index.outputs[0], count)
    streak = node(tree, "GeometryNodeMeshCylinder", "Triangular streak")
    streak.inputs["Vertices"].default_value = 3
    streak.inputs["Side Segments"].default_value = 1
    streak.inputs["Fill Segments"].default_value = 1
    driven(streak.inputs["Radius"], "default_value", "0.006/u", scene, root, "u")
    driven(streak.inputs["Depth"], "default_value", "streak_length/u", scene, root, "streak_length u")
    shade = node(tree, "GeometryNodeSetMaterial", "Rain material")
    shade.inputs["Material"].default_value = material
    tree.links.new(streak.outputs["Mesh"], shade.inputs["Geometry"])
    instances = node(tree, "GeometryNodeInstanceOnPoints", "Rain instances")
    tree.links.new(points.outputs[0], instances.inputs["Points"])
    tree.links.new(selected, instances.inputs["Selection"])
    tree.links.new(shade.outputs[0], instances.inputs["Instance"])
    outgoing = node(tree, "NodeGroupOutput", "Rain output")
    tree.links.new(instances.outputs[0], outgoing.inputs["Geometry"])


def bind_camera(scene):
    collection = parts(scene)
    rain, root = collection["rain"], collection["root"]
    constraint = rain.constraints.get("Rain camera")
    if constraint is None:
        constraint = rain.constraints.new("COPY_LOCATION")
        constraint.name = "Rain camera"
    if constraint.type != "COPY_LOCATION":
        raise rig.RigError("Rain camera constraint has been replaced; restore its Copy Location type")
    constraint.target = scene.camera
    # Resolve the binding through the constraint, including camera deletion. A native
    # fallback handles the missing RNA path without handlers or a second binding state.
    variables = {"rain_amount": (root, '["rain_amount"]'),
                 "camera_lens": (rain, 'constraints["Rain camera"].target.data.lens')}
    count = collection["rain_nodes"].nodes["Rain amount"].outputs[0]
    for owner, path, expression in ((rain, "hide_render", "rain_amount<=0 or camera_lens<=0"),
                                     (count, "default_value", "2048*rain_amount if camera_lens>0 else 0")):
        curve = drive(owner, path, expression, variables)
        target = curve.driver.variables["camera_lens"].targets[0]
        target.use_fallback_value = True
        target.fallback_value = 0


def preset(scene, name):
    collection = parts(scene)
    constraint = collection["rain"].constraints.get("Rain camera")
    if name == "RAINY" and (constraint is None or constraint.type != "COPY_LOCATION" or not constraint.target):
        raise rig.RigError("Set a scene camera and bind rain before applying Rainy")
    root = collection["root"]
    for key, setting in PRESETS[name][1].items():
        root[key] = setting
        if scene.tool_settings.use_keyframe_insert_auto:
            root.keyframe_insert(f'["{key}"]', group="Sunner weather")
    root.update_tag()


def remove(scene):
    collection = get(scene)
    if not collection:
        raise rig.RigError("No weather to remove")
    data = owned(collection)
    parent = rig.get_rig(scene)
    rig.check_removal(data, {scene, parent})
    del parent[KEY]
    bpy.data.batch_remove(ids=data)
