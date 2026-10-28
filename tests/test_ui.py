"""Run in disposable foreground Blender with --enable-event-simulate."""
import json
from pathlib import Path
import sys
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sunner
from sunner import rig, weather

OUTPUT = ROOT / "examples" / "ui-smoke.json"
WEATHER_SCREENSHOT = ROOT / "examples" / "weather-panel-preview.png"
LEGACY_ADVANCED_SCREENSHOT = ROOT / "examples" / "advanced-legacy-panel-preview.png"
ENABLED_ADVANCED_SCREENSHOT = ROOT / "examples" / "advanced-enabled-panel-preview.png"
OUTPUT.parent.mkdir(exist_ok=True)
for screenshot in (WEATHER_SCREENSHOT, LEGACY_ADVANCED_SCREENSHOT, ENABLED_ADVANCED_SCREENSHOT):
    screenshot.unlink(missing_ok=True)
OUTPUT.write_text(json.dumps({"ok": False, "status": "running"}))
state = 0
checks = []
receipts = {}


def capture(screenshot, receipt):
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    assert bpy.ops.screen.screenshot(filepath=str(screenshot)) == {"FINISHED"}
    assert screenshot.is_file() and screenshot.stat().st_size > 0
    receipts[receipt] = {"screenshot": screenshot.name, "bytes": screenshot.stat().st_size}


bpy.context.preferences.view.show_splash = False
sunner.register()


def tick():
    global state
    try:
        window = bpy.context.window_manager.windows[0]
        area = next(a for a in window.screen.areas if a.type == "VIEW_3D")
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(window=window, area=area, region=region):
            scene = bpy.context.scene
            if state == 0:
                bpy.ops.ed.undo_push(message="Before Sunner")
                assert bpy.ops.sunner.add() == {"FINISHED"}
                assert bpy.ops.sunner.weather_add() == {"FINISHED"}
                assert bpy.ops.sunner.weather_preset(preset="CLOUDY") == {"FINISHED"}
                bpy.ops.ed.undo_push(message="Add Sunner and weather")
                area.spaces.active.show_region_ui = True
                checks.append("add and select")
            elif state == 1:
                area.tag_redraw()
            elif state == 2:
                assert bpy.ops.ed.undo() == {"FINISHED"}
            elif state == 3:
                assert rig.KEY not in scene
                assert bpy.ops.ed.redo() == {"FINISHED"}
            elif state == 4:
                assert rig.parts(scene)
                checks.append("add cycle and weather undo/redo")
                assert weather.parts(scene)
                assert bpy.ops.sunner.weather_remove() == {"FINISHED"}
                bpy.ops.ed.undo_push(message="Remove weather")
                assert weather.get(scene) is None
            elif state == 5:
                assert bpy.ops.ed.undo() == {"FINISHED"}
            elif state == 6:
                assert weather.parts(scene)
                checks.append("weather removal undo")
                assert bpy.ops.sunner.remove() == {"FINISHED"}
                bpy.ops.ed.undo_push(message="Remove Sunner")
                assert rig.KEY not in bpy.context.scene
            elif state == 7:
                assert bpy.ops.ed.undo() == {"FINISHED"}
            elif state == 8:
                assert rig.parts(scene)
                assert weather.parts(scene)
                checks.append("whole rig removal undo")
                sunner.unregister()
                scene.frame_set(42)
                assert rig.parts(scene)["sun"].data.energy > 0
                sunner.register()
                checks.append("disable and re-enable")
                # All popups are captured after undo/removal: they must not retain stale RNA.
                bpy.ops.wm.call_panel(name="SUNNER_PT_weather", keep_open=False)
            elif state == 9:
                capture(WEATHER_SCREENSHOT, "weather_panel")
                checks.append("registered weather panel capture")
                window.event_simulate(type="ESC", value="PRESS")
                window.event_simulate(type="ESC", value="RELEASE")
            elif state == 10:
                root = rig.parts(scene)["root"]
                for name in rig.TWILIGHT_CONTROLS:
                    del root[name]
                assert not any(name in root for name in rig.TWILIGHT_CONTROLS)
                receipts["advanced_legacy"] = {"twilight_controls_absent": True}
                bpy.ops.wm.call_panel(name="SUNNER_PT_advanced", keep_open=False)
            elif state == 11:
                capture(LEGACY_ADVANCED_SCREENSHOT, "advanced_legacy_panel")
                checks.append("advanced legacy enable-action capture")
                window.event_simulate(type="ESC", value="PRESS")
                window.event_simulate(type="ESC", value="RELEASE")
            elif state == 12:
                assert bpy.ops.sunner.enable_twilight() == {"FINISHED"}
                root = rig.parts(scene)["root"]
                assert root["twilight_enabled"] is True
                assert root["twilight_sky_gain"] == 3.0
                assert root["twilight_moon_gain"] == 0.15
                receipts["advanced_enabled"] = {
                    "twilight_enabled": root["twilight_enabled"],
                    "twilight_sky_gain": root["twilight_sky_gain"],
                    "twilight_moon_gain": root["twilight_moon_gain"],
                }
                bpy.ops.wm.call_panel(name="SUNNER_PT_advanced", keep_open=False)
            elif state == 13:
                capture(ENABLED_ADVANCED_SCREENSHOT, "advanced_enabled_panel")
                checks.append("advanced enabled checkbox and gain-controls capture")
                OUTPUT.write_text(json.dumps({"ok": True, "checks": checks, "receipts": receipts}, indent=2))
                print("SUNNER_UI_OK", checks, flush=True)
                bpy.ops.wm.quit_blender()
                return None
            state += 1
        return 0.7
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        OUTPUT.write_text(json.dumps({"ok": False, "checks": checks, "receipts": receipts, "error": error}, indent=2))
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=2)
