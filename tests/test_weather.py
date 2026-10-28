"""Weather integration tests use tiny scenes and do not render or load city assets."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sunner
from sunner import rig, weather


class WeatherTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sunner.register()
        self.scene = bpy.context.scene
        self.original = bpy.data.worlds.new("Original")
        self.scene.world = self.original
        self.camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
        self.scene.collection.objects.link(self.camera)
        self.scene.camera = self.camera
        rig.create(self.scene)
        self.base = rig.parts(self.scene)
        self.w = weather.create(self.scene)
        self.root = self.w["root"]
        self.scene.frame_set(1)

    def tearDown(self):
        sunner.unregister()

    def update(self):
        self.root.update_tag()
        self.scene.frame_set(self.scene.frame_current)
        bpy.context.view_layer.update()

    def drops(self):
        return [instance.matrix_world.translation.copy()
                for instance in bpy.context.evaluated_depsgraph_get().object_instances
                if instance.is_instance and instance.parent.original == self.w["rain"]]

    def test_clear_and_lighting_independence(self):
        sun_energy = self.base["sun"].data.energy
        node_count = len(self.base["world"].node_tree.nodes)
        count = len(bpy.data.objects)
        self.assertEqual(weather.create(self.scene), self.w)
        self.assertEqual(len(bpy.data.objects), count)
        for key in ("fog", "cloud", "rain"):
            self.assertTrue(self.w[key].hide_render)
        weather.preset(self.scene, "OVERCAST")
        self.update()
        self.assertEqual(self.base["sun"].data.energy, sun_energy)
        self.assertEqual(len(self.base["world"].node_tree.nodes), node_count)
        self.assertFalse(self.base["world"].node_tree.nodes["Sunner output"].inputs["Volume"].is_linked)
        self.assertFalse(self.w["fog"].hide_render)
        self.assertFalse(self.w["cloud"].hide_render)

    def test_metres_and_region_origin(self):
        self.scene.unit_settings.scale_length = 0.01
        self.root["extent"] = 1000.0
        self.root["fog_height"] = 150.0
        self.root.location = (12, 34, 56)
        weather.preset(self.scene, "MISTY")
        self.update()
        self.assertAlmostEqual(self.w["fog"].scale.x, 100000)
        self.assertAlmostEqual(self.w["fog"].scale.z, 15000)
        self.assertAlmostEqual(self.w["cloud"].location.z, 30000)
        self.assertEqual(tuple(self.w["fog"].matrix_world.translation), (12, 34, 56))
        nodes = self.w["fog_material"].node_tree.nodes
        distance = nodes["Visibility in scene units"].outputs[0].default_value
        amount = nodes["Fog amount"].outputs[0].default_value
        self.assertAlmostEqual(distance, 100000)
        self.assertAlmostEqual(3.912 * amount / distance, 3.912 * 0.55 * 0.01 / 1000, places=8)
        self.assertEqual(nodes["DIVIDE"].operation, "DIVIDE")
        scale = self.w["cloud_material"].node_tree.nodes["Cloud size in scene units"].outputs[0].default_value
        self.assertAlmostEqual(scale, 25000)

    def test_rain_is_bounded_and_frame_deterministic(self):
        weather.preset(self.scene, "RAINY")
        self.root["rain_radius"] = 5.0
        self.root["rain_height"] = 8.0
        self.camera.location = (50, 60, 70)
        self.update()
        first = self.drops()
        self.assertEqual(len(first), 1434)
        for point in first:
            self.assertLessEqual(abs(point.x - 50), 5.01)
            self.assertLessEqual(abs(point.y - 60), 5.01)
            self.assertLessEqual(abs(point.z - 70), 4.01)
        self.scene.frame_set(35)
        moved = self.drops()
        self.assertGreater((moved[0] - first[0]).length, 0.1)
        self.scene.frame_set(1)
        again = self.drops()
        self.assertLess((first[0] - again[0]).length, 1e-5)
        self.assertEqual(len(bpy.data.objects), 9)  # camera + four core + four weather objects

    def test_camera_rebind_and_native_drivers(self):
        self.scene.camera = None
        weather.bind_camera(self.scene)
        with self.assertRaisesRegex(rig.RigError, "camera"):
            weather.preset(self.scene, "RAINY")
        self.scene.camera = self.camera
        weather.bind_camera(self.scene)
        weather.bind_camera(self.scene)
        weather.preset(self.scene, "RAINY")
        self.update()
        self.assertFalse(self.w["rain"].hide_render)
        owners = [self.w[k] for k in ("fog", "cloud", "rain", "rain_nodes")]
        owners += [self.w[k].node_tree for k in ("fog_material", "cloud_material")]
        for owner in owners:
            for curve in owner.animation_data.drivers:
                self.assertTrue(curve.driver.is_valid, (owner.name, curve.data_path))
                self.assertTrue(curve.driver.is_simple_expression)
                names = [v.name for v in curve.driver.variables]
                self.assertEqual(len(names), len(set(names)))
        rain_driver = self.w["rain"].animation_data.drivers.find("hide_render")
        self.assertEqual(len(rain_driver.driver.variables), 2)
        self.assertTrue(rain_driver.driver.variables["camera_lens"].targets[0].use_fallback_value)

    def test_deleted_constraint_rebinds_and_deleted_camera_disables_rain(self):
        rain = self.w["rain"]
        rain.constraints.remove(rain.constraints["Rain camera"])
        with self.assertRaisesRegex(rig.RigError, "camera"):
            weather.preset(self.scene, "RAINY")
        weather.bind_camera(self.scene)
        weather.preset(self.scene, "RAINY")
        self.update()
        self.assertEqual(len(self.drops()), 1434)
        bpy.data.objects.remove(self.camera, do_unlink=True)
        self.update()
        self.assertTrue(rain.hide_render)
        self.assertEqual(len(self.drops()), 0)
        self.assertTrue(rain.animation_data.drivers.find("hide_render").driver.is_valid)

    def test_invalid_weather_pointer_cannot_delete_user_data(self):
        owner = rig.get_rig(self.scene)
        obj = bpy.data.objects.new("Unrelated object", None)
        self.scene.collection.objects.link(obj)
        collection = bpy.data.collections.new("Unrelated collection")
        self.scene.collection.children.link(collection)
        for unrelated in (obj, collection):
            owner[weather.KEY] = unrelated
            for operation in (weather.remove, rig.remove):
                with self.assertRaisesRegex(rig.RigError, "Invalid"):
                    operation(self.scene)
            self.assertIn(obj.name, bpy.data.objects)
            self.assertIn(collection.name, bpy.data.collections)
        owner[weather.KEY] = self.w

    def test_animated_presets_and_wind(self):
        self.scene.tool_settings.use_keyframe_insert_auto = True
        weather.preset(self.scene, "CLEAR")
        self.scene.frame_set(25)
        weather.preset(self.scene, "RAINY")
        self.update()
        self.assertAlmostEqual(self.root["rain_amount"], 0.7)
        self.scene.frame_set(1)
        self.assertAlmostEqual(self.root["rain_amount"], 0)
        self.assertTrue(self.w["rain"].hide_render)
        self.scene.frame_set(25)
        self.assertAlmostEqual(self.root["rain_amount"], 0.7)
        drift = self.w["cloud_material"].node_tree.nodes["Cloud wind"].inputs[1].default_value[0]
        self.assertNotEqual(drift, 0)

    def test_safe_weather_and_full_rig_removal(self):
        bpy.data.objects.remove(self.w["cloud"], do_unlink=True)
        weather.remove(self.scene)
        self.assertIsNone(weather.get(self.scene))
        self.assertEqual(self.scene.world, self.base["world"])
        self.assertEqual(len(bpy.data.meshes), 0)
        self.assertEqual(len(bpy.data.materials), 0)
        self.assertFalse(any(g.name.startswith("Sunner") for g in bpy.data.node_groups))
        weather.create(self.scene)
        rig.remove(self.scene)
        self.assertEqual(self.scene.world, self.original)
        self.assertEqual(len(bpy.data.objects), 1)
        self.assertEqual(len(bpy.data.meshes), 0)
        self.assertEqual(len(bpy.data.materials), 0)

    def test_external_users_block_both_removals_atomically(self):
        other = bpy.data.objects.new("User mesh", bpy.data.meshes.new("User mesh"))
        self.scene.collection.objects.link(other)
        other.data.materials.append(self.w["fog_material"])
        for operation in (weather.remove, rig.remove):
            with self.assertRaisesRegex(rig.RigError, "outside"):
                operation(self.scene)
            self.assertEqual(self.scene.world, self.base["world"])
            self.assertEqual(weather.get(self.scene), self.w)
        other.data.materials.clear()
        self.w.objects.link(other)
        with self.assertRaisesRegex(rig.RigError, "non-Sunner"):
            weather.remove(self.scene)

    def test_creation_failure_rolls_back_weather_only(self):
        weather.remove(self.scene)
        counts = (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials))
        with patch("sunner.weather._rain", side_effect=RuntimeError("test failure")):
            with self.assertRaisesRegex(RuntimeError, "test failure"):
                weather.create(self.scene)
        self.assertIsNone(weather.get(self.scene))
        self.assertEqual(self.scene.world, self.base["world"])
        self.assertEqual(counts, (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials)))

    def test_original_release_rig_accepts_optional_weather(self):
        rig.remove(self.scene)
        with tempfile.TemporaryDirectory() as temp:
            with zipfile.ZipFile(ROOT / "dist" / "sunner-0.1.0.zip") as archive:
                archive.extractall(temp)
            spec = importlib.util.spec_from_file_location("sunner_v01", Path(temp) / "__init__.py",
                                                         submodule_search_locations=[temp])
            module = importlib.util.module_from_spec(spec)
            sys.modules["sunner_v01"] = module
            spec.loader.exec_module(module)
            old_rig = sys.modules["sunner_v01.rig"]
            old_rig.create(self.scene)
            rig.configure_twilight(self.scene)
            self.assertTrue(rig.parts(self.scene)["root"]["twilight_enabled"])
            weather.create(self.scene)
            self.scene.frame_set(10)
            rig.remove(self.scene)
            self.assertEqual(self.scene.world, self.original)

    def test_saved_weather_without_addon(self):
        weather.preset(self.scene, "RAINY")
        self.update()
        with tempfile.TemporaryDirectory(prefix="sunner-weather-") as temp:
            path = Path(temp) / "weather.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(path))
            script = '''import bpy
s=bpy.context.scene
w=s["sunner_rig"]["weather"]
assert not hasattr(bpy.types,"SUNNER_PT_weather")
for frame in (1,32,5):
 s.frame_set(frame)
 assert len([i for i in bpy.context.evaluated_depsgraph_get().object_instances if i.is_instance])==1434
 for d in (w["rain_nodes"],w["cloud_material"].node_tree,w["fog_material"].node_tree):
  assert all(f.driver.is_valid and f.driver.is_simple_expression for f in d.animation_data.drivers)
print("NATIVE_WEATHER_OK")
'''
            result = subprocess.run([bpy.app.binary_path, "--background", "--factory-startup", "--threads", "1",
                                     "--disable-autoexec", str(path), "--python-exit-code", "1", "--python-expr", script],
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("NATIVE_WEATHER_OK", result.stdout)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WeatherTests))
if not result.wasSuccessful():
    raise SystemExit(1)
print("SUNNER_WEATHER_INTEGRATION_OK")
