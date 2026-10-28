"""Focused integration checks against the real Blender 5.2 dependency graph."""

import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sunner
from sunner import rig
from sunner.operators import animate, angle_curves


class CycleTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sunner.register()
        self.scene = bpy.context.scene
        self.original = bpy.data.worlds.new("Original World")
        self.original.node_tree.nodes.new("ShaderNodeValue").name = "Keep this node"
        self.scene.world = self.original
        self.collection = rig.create(self.scene)
        self.p = rig.parts(self.scene)
        bpy.context.view_layer.update()

    def tearDown(self):
        sunner.unregister()

    def phase(self, degrees):
        self.p["dial"].rotation_euler.x = math.radians(degrees)
        bpy.context.view_layer.update()

    def test_rotation_and_sky_agree(self):
        for heading, season in ((0, 0), (1.7, 0), (0.4, rig.SOLSTICE), (2.5, -rig.SOLSTICE)):
            self.p["root"]["season"] = season
            self.p["root"].update_tag()
            for tilt in (0, math.radians(30), math.radians(75)):
                self.p["root"].rotation_euler.y = tilt
                self.p["root"].rotation_euler.z = heading
                for angle in (0, 90, 180, 240, 270, 360, 720):
                    with self.subTest(heading=heading, season=season, tilt=tilt, angle=angle):
                        self.phase(angle)
                        sun = self.p["sun"].matrix_world.to_quaternion() @ Vector((0, 0, 1))
                        moon = self.p["moon"].matrix_world.to_quaternion() @ Vector((0, 0, 1))
                        self.assertLess((sun + moon).length, 1e-5)
                        expected_z = (math.sin(season) * math.sin(tilt) -
                                      math.cos(season) * math.cos(tilt) * math.cos(math.radians(angle)))
                        self.assertAlmostEqual(sun.z, expected_z, places=5)
                        if sun.z >= math.sin(math.radians(-18)):
                            sky = self.p["world"].node_tree.nodes["Sunner atmosphere"]
                            sky_dir = Vector((math.cos(sky.sun_elevation) * math.sin(sky.sun_rotation),
                                              math.cos(sky.sun_elevation) * math.cos(sky.sun_rotation),
                                              math.sin(sky.sun_elevation)))
                            self.assertLess((sky_dir - sun).length, 1e-5)

    def test_light_fades_and_native_drivers(self):
        for angle, sunlight in ((0, False), (89, False), (90, False), (120, True),
                                (180, True), (270, False), (271, False), (360, False)):
            self.phase(angle)
            sun = self.p["sun"].data.energy
            self.assertEqual(sun > 0.001, sunlight, (angle, sun))
            self.assertGreaterEqual(sun, 0)
        for data in (self.p["sun"].data, self.p["moon"].data, self.p["world"].node_tree):
            for curve in data.animation_data.drivers:
                self.assertTrue(curve.driver.is_valid, curve.data_path)
                self.assertTrue(curve.driver.is_simple_expression, curve.driver.expression)
                self.assertLessEqual(len(curve.driver.expression.encode("utf-8")), 255)
        self.assertFalse(self.p["world"].node_tree.nodes["Sunner atmosphere"].sun_disc)
        self.assertEqual(self.p["world"].sun_threshold, 0)

    def test_horizon_and_wrap_are_continuous(self):
        for boundary in (90, 270, 360):
            values = []
            for angle in (boundary - 0.001, boundary + 0.001):
                self.phase(angle)
                tree = self.p["world"].node_tree
                values.append((self.p["sun"].data.energy, self.p["moon"].data.energy,
                               tree.nodes["Sunner daylight"].inputs["Strength"].default_value,
                               tree.nodes["Sunner night"].inputs["Strength"].default_value))
            for a, b in zip(*values):
                self.assertLess(abs(a - b), 0.001)

    def test_opt_in_twilight_gains_are_native_and_idempotent(self):
        root = self.p["root"]
        root.rotation_euler.y = 0
        root["sky_brightness"] = 1.7
        root["night_brightness"] = 1.4
        root.update_tag()
        bpy.context.view_layer.update()

        def contributions():
            tree = self.p["world"].node_tree
            return (self.p["moon"].data.energy,
                    tree.nodes["Sunner daylight"].inputs["Strength"].default_value,
                    tree.nodes["Sunner night"].inputs["Strength"].default_value)

        # Midnight/noon and the -12°/+4° window boundaries stay exactly neutral.
        baseline = {}
        for angle in (0, 78, 94, 180):
            self.phase(angle)
            baseline[angle] = contributions()
        self.phase(86)  # With zero path tilt, solar elevation is exactly -4°.
        unbalanced = contributions()
        self.assertAlmostEqual(unbalanced[1], 0.17, places=5)
        self.assertAlmostEqual(unbalanced[0], 0.168, places=5)
        # -4 degrees is one third of the -8..+4 transition, not its midpoint.
        self.assertAlmostEqual(unbalanced[2], 0.7 * 1.4 * (1 - 7 / 27), places=5)
        rig.configure_twilight(self.scene)
        self.assertTrue(root["twilight_enabled"])
        self.assertEqual(root["sky_brightness"], 1.7)
        self.assertEqual(root["night_brightness"], 1.4)
        for angle, expected in baseline.items():
            self.phase(angle)
            self.assertEqual(contributions(), expected)
        self.phase(86)
        balanced = contributions()
        self.assertAlmostEqual(balanced[1], unbalanced[1] * 3.0, places=5)
        self.assertAlmostEqual(balanced[0], unbalanced[0] * 0.15, places=5)
        self.assertAlmostEqual(balanced[2], unbalanced[2] * 0.15, places=5)

        # Native driver dependencies require update_tag after direct ID-property writes.
        root["twilight_sky_gain"] = 2.0
        root["twilight_moon_gain"] = 0.4
        root.update_tag()
        bpy.context.view_layer.update()
        updated = contributions()
        self.assertAlmostEqual(updated[1], unbalanced[1] * 2.0, places=5)
        self.assertAlmostEqual(updated[0], unbalanced[0] * 0.4, places=5)
        self.assertAlmostEqual(updated[2], unbalanced[2] * 0.4, places=5)

        root["twilight_enabled"] = False
        root.update_tag()
        bpy.context.view_layer.update()
        self.assertEqual(contributions(), unbalanced)

        nodes = self.p["world"].node_tree.nodes
        node_count = len(nodes)
        rig.configure_twilight(self.scene)
        bpy.context.view_layer.update()
        once = contributions()
        rig.configure_twilight(self.scene)
        bpy.context.view_layer.update()
        self.assertEqual(len(nodes), node_count)
        self.assertEqual(contributions(), once)
        curves = [self.p["moon"].data.animation_data.drivers.find("energy")]
        curves.extend(curve for curve in self.p["world"].node_tree.animation_data.drivers
                      if any(v.targets[0].data_path.startswith('["twilight_')
                             for v in curve.driver.variables))
        self.assertEqual(len(curves), 3)
        for curve in curves:
            self.assertTrue(curve.driver.is_valid)
            self.assertTrue(curve.driver.is_simple_expression)
            names = [variable.name for variable in curve.driver.variables]
            self.assertEqual(len(names), len(set(names)))

    def test_update_operator_upgrades_an_older_cycle_only_on_request(self):
        root = self.p["root"]
        for name in rig.OPTIONAL_CONTROLS:
            del root[name]
        root["night_brightness"] = 2.5
        self.assertTrue(rig.needs_update(root))
        self.assertEqual(bpy.ops.sunner.update_cycle(), {"FINISHED"})
        self.assertFalse(rig.needs_update(root))
        self.assertFalse(root["twilight_enabled"])
        self.assertEqual((root["twilight_sky_gain"], root["twilight_moon_gain"]), (3.0, 0.15))
        self.assertEqual((root["season"], root["stars"], root["discs"]), (0.0, 1.0, 1.0))
        self.assertEqual(root["night_brightness"], 2.5)
        self.assertEqual(bpy.ops.sunner.update_cycle(), {"FINISHED"})

    def test_tampere_midsummer_white_night(self):
        root = self.p["root"]
        root.rotation_euler.y = math.radians(61.5)
        root["season"] = rig.SOLSTICE
        root.update_tag()
        for angle, elevation in ((180, 90 - 61.5 + 23.44), (0, 61.5 + 23.44 - 90)):
            self.phase(angle)
            sun = self.p["sun"].matrix_world.to_quaternion() @ Vector((0, 0, 1))
            self.assertAlmostEqual(math.degrees(math.asin(sun.z)), elevation, places=3)
        # Five degrees below the horizon at midnight: no direct sun, a bright twilight sky.
        self.assertEqual(self.p["sun"].data.energy, 0)
        self.assertGreater(self.p["world"].node_tree.nodes["Sunner daylight"].inputs["Strength"].default_value, 0.01)

    def render(self, engine, direction, lens=50, **controls):
        """Render a tiny linear EXR towards a world direction; return its RGB pixels."""
        scene = self.scene
        for name, value in controls.items():
            self.p["root"][name] = value
        self.p["root"].update_tag()
        camera = scene.camera
        if camera is None:
            camera = bpy.data.objects.new("Probe camera", bpy.data.cameras.new("Probe camera"))
            scene.collection.objects.link(camera)
            scene.camera = camera
        camera.data.lens = lens
        camera.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        scene.render.engine = engine
        scene.render.resolution_x = scene.render.resolution_y = 32
        scene.render.resolution_percentage = 100
        scene.cycles.samples = 16
        scene.cycles.use_denoising = False
        scene.eevee.taa_render_samples = 4
        scene.render.image_settings.file_format = "OPEN_EXR"
        with tempfile.TemporaryDirectory(prefix="sunner-render-") as temp:
            scene.render.filepath = str(Path(temp) / "probe.exr")
            bpy.ops.render.render(write_still=True)
            image = bpy.data.images.load(scene.render.filepath)
            pixels = list(image.pixels)
            bpy.data.images.remove(image)
        return [pixels[i:i + 3] for i in range(0, len(pixels), 4)]

    def test_discs_follow_lights_and_add_no_illumination(self):
        root = self.p["root"]
        root.rotation_euler.y = math.radians(50)
        self.phase(200)
        ground = bpy.data.objects.new("Ground", bpy.data.meshes.new("Ground"))
        ground.data.from_pydata([(-50, -50, 0), (50, -50, 0), (50, 50, 0), (-50, 50, 0)], [], [(0, 1, 2, 3)])
        ground.location.z = -5
        self.scene.collection.objects.link(ground)
        sun = self.p["sun"].matrix_world.to_quaternion() @ Vector((0, 0, 1))
        for engine in ("CYCLES", "BLENDER_EEVEE"):
            with self.subTest(engine=engine):
                centre = 16 * 32 + 16
                lit = self.render(engine, sun, lens=400, discs=1.0)[centre]
                plain = self.render(engine, sun, lens=400, discs=0.0)[centre]
                self.assertGreater(sum(lit), 10 * sum(plain), (lit, plain))
                floor = [sum(map(sum, self.render(engine, (0, 0, -1), discs=value))) for value in (0.0, 10.0)]
                self.assertAlmostEqual(floor[1] / floor[0], 1.0, delta=0.02)
        # The moon disc is exactly opposite and visible only at night.
        self.phase(20)
        moon = -(self.p["sun"].matrix_world.to_quaternion() @ Vector((0, 0, 1)))
        self.assertGreater(moon.z, 0)
        centre = self.render("CYCLES", moon, lens=400, discs=1.0)[16 * 32 + 16]
        self.assertGreater(sum(centre), 1.0)

    def test_stars_appear_at_night_only(self):
        self.p["root"].rotation_euler.y = math.radians(61.5)
        for angle, visible in ((0, True), (180, False)):
            self.phase(angle)
            peaks = [max(map(sum, self.render("CYCLES", (0, 0.3, 1), lens=20, stars=value)))
                     for value in (0.0, 1.0)]
            if visible:
                self.assertGreater(peaks[1], 2 * peaks[0], peaks)
            else:
                self.assertAlmostEqual(peaks[1], peaks[0], delta=0.02 * peaks[0])

    def test_twilight_rejects_shared_world_and_moon_data(self):
        root = self.p["root"]
        other_scene = bpy.data.scenes.new("Twilight World User")
        other_scene.world = self.p["world"]
        with self.assertRaisesRegex(rig.RigError, "outside"):
            rig.configure_twilight(self.scene)
        self.assertFalse(root["twilight_enabled"])
        other_scene.world = None
        moon_user = bpy.data.objects.new("Twilight moon data user", self.p["moon"].data)
        self.scene.collection.objects.link(moon_user)
        with self.assertRaisesRegex(rig.RigError, "outside"):
            rig.configure_twilight(self.scene)
        self.assertFalse(root["twilight_enabled"])

    def test_idempotent_add_select_and_rename(self):
        count = len(bpy.data.objects)
        self.assertEqual(bpy.ops.sunner.add(), {"FINISHED"})
        self.assertEqual(len(bpy.data.objects), count)
        self.assertEqual(bpy.context.object, self.p["dial"])
        for data in self.p.values():
            data.name = "Renamed " + data.name
        self.collection.name = "Renamed collection"
        self.phase(180)
        self.assertAlmostEqual(rig.parts(self.scene)["sun"].data.energy, 3)

    def test_removal_preserves_world_and_unrelated_lights(self):
        other = bpy.data.objects.new("Other light", bpy.data.lights.new("Other", "SUN"))
        self.scene.collection.objects.link(other)
        original_nodes = len(self.original.node_tree.nodes)
        self.assertEqual(bpy.ops.sunner.remove(), {"FINISHED"})
        self.assertEqual(self.scene.world, self.original)
        self.assertEqual(len(self.original.node_tree.nodes), original_nodes)
        self.assertIn(other.name, bpy.data.objects)
        self.assertNotIn(rig.KEY, self.scene)
        self.assertFalse(any(w.name.startswith("Sunner") for w in bpy.data.worlds))
        self.assertEqual(len(bpy.data.lights), 1)

    def test_world_changed_by_user_is_not_replaced(self):
        replacement = bpy.data.worlds.new("Replacement")
        self.scene.world = replacement
        rig.remove(self.scene)
        self.assertEqual(self.scene.world, replacement)
        self.assertIn("Original World", bpy.data.worlds)

    def test_no_original_world_and_incomplete_rig_removal(self):
        rig.remove(self.scene)
        self.scene.world = None
        rig.create(self.scene)
        p = rig.parts(self.scene)
        bpy.data.objects.remove(p["moon"], do_unlink=True)
        with self.assertRaises(rig.RigError):
            rig.parts(self.scene)
        rig.remove(self.scene)
        self.assertIsNone(self.scene.world)
        self.assertEqual(len(bpy.data.lights), 0)

    def test_creation_failure_rolls_back(self):
        rig.remove(self.scene)
        counts = (len(bpy.data.objects), len(bpy.data.lights), len(bpy.data.worlds))
        with patch("sunner.rig.build_lighting", side_effect=RuntimeError("deliberate test failure")):
            with self.assertRaisesRegex(RuntimeError, "deliberate"):
                rig.create(self.scene)
        self.assertEqual(self.scene.world, self.original)
        self.assertNotIn(rig.KEY, self.scene)
        self.assertEqual(counts, (len(bpy.data.objects), len(bpy.data.lights), len(bpy.data.worlds)))

    def test_shared_reference_blocks_destructive_removal(self):
        other_scene = bpy.data.scenes.new("Other scene")
        other_scene.world = self.p["world"]
        with self.assertRaisesRegex(rig.RigError, "outside"):
            rig.remove(self.scene)
        self.assertEqual(other_scene.world, self.p["world"])
        self.assertIn(rig.KEY, self.scene)

    def test_animation_frame_jumps_and_brightness(self):
        self.phase(0)
        animate(self.scene, 1, 240)
        root = self.p["root"]
        root["sun_brightness"] = 1.0
        root.keyframe_insert('["sun_brightness"]', frame=1)
        root["sun_brightness"] = 2.0
        root.keyframe_insert('["sun_brightness"]', frame=121)
        for frame, expected_angle in ((121, math.pi), (1, 0), (241, math.tau), (481, 2 * math.tau), (121, math.pi)):
            self.scene.frame_set(frame)
            self.assertAlmostEqual(self.p["dial"].rotation_euler.x, expected_angle, places=5)
        self.assertAlmostEqual(self.p["sun"].data.energy, 6, places=5)
        self.assertEqual((self.scene.frame_start, self.scene.frame_end), (1, 240))
        self.assertEqual(len(angle_curves(self.p["dial"])[0][1].keyframe_points), 2)

    def test_animation_replacement_and_shared_action(self):
        self.phase(0)
        animate(self.scene, 1, 240)
        with self.assertRaisesRegex(rig.RigError, "confirm"):
            animate(self.scene, 1, 120)
        dial = self.p["dial"]
        other = bpy.data.objects.new("Action user", None)
        self.scene.collection.objects.link(other)
        other.animation_data_create()
        original_action = dial.animation_data.action
        other.animation_data.action = original_action
        other.animation_data.action_slot = dial.animation_data.action_slot
        animate(self.scene, 1, 120, replace=True)
        self.assertNotEqual(dial.animation_data.action, original_action)
        self.assertEqual(other.animation_data.action, original_action)
        self.scene.frame_set(121)
        self.assertAlmostEqual(dial.rotation_euler.x, math.tau, places=5)
        self.assertAlmostEqual(other.rotation_euler.x, math.pi, places=5)

    def test_driver_length_rejected_before_assignment(self):
        from sunner.lighting import drive
        with self.assertRaisesRegex(ValueError, "255-byte"):
            drive(None, "energy", "1" * 256, {})

    def test_twilight_operator_preserves_legacy_cycle_when_ownership_is_unsafe(self):
        root = self.p["root"]
        for name in rig.OPTIONAL_CONTROLS:
            del root[name]
        other_scene = bpy.data.scenes.new("Twilight World User")
        other_scene.world = self.p["world"]
        with self.assertRaisesRegex(RuntimeError, "Sunner sky is used outside this rig"):
            bpy.ops.sunner.update_cycle()
        self.assertNotIn("twilight_enabled", root)

    def test_twilight_rejects_replaced_moon_data(self):
        external = bpy.data.lights.new("User moon", "SUN")
        external.energy = 7.0
        self.p["moon"].data = external
        with self.assertRaisesRegex(rig.RigError, "replaced"):
            rig.configure_twilight(self.scene)
        self.assertEqual(external.energy, 7.0)
        self.assertIsNone(external.animation_data)
        self.assertFalse(self.p["root"]["twilight_enabled"])

    def test_scene_render_settings_remain_untouched(self):
        rig.remove(self.scene)
        self.scene.view_settings.exposure = 2.5
        self.scene.render.engine = "BLENDER_EEVEE"
        view_transform = self.scene.view_settings.view_transform
        rig.create(self.scene)
        self.assertEqual(self.scene.view_settings.exposure, 2.5)
        self.assertEqual(self.scene.render.engine, "BLENDER_EEVEE")
        self.assertEqual(self.scene.view_settings.view_transform, view_transform)

    def test_saved_rig_evaluates_without_extension(self):
        self.phase(0)
        animate(self.scene, 1, 240)
        rig.configure_twilight(self.scene)
        with tempfile.TemporaryDirectory(prefix="sunner-test-") as temp:
            blend = Path(temp) / "cycle.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(blend))
            result = subprocess.run([
                bpy.app.binary_path, "--background", "--factory-startup", "--disable-autoexec",
                str(blend), "--python-exit-code", "1", "--python", str(ROOT / "tests" / "check_saved_rig.py"),
            ], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("SAVED_RIG_WITHOUT_ADDON_OK", result.stdout)
            self.assertIn("REOPENED_WORLD_RESTORATION_OK", result.stdout)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(CycleTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
print("SUNNER_INTEGRATION_OK")
