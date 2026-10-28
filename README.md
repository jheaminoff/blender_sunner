# Sunner

A small Blender extension for daylight, twilight, seasons, moonlight, stars and optional scene weather. Rotate one day dial; the lights and sky follow together.

**Blender 5.2.x (tested on 5.2.3 LTS). Cycles and EEVEE.** No external assets, Python dependencies, network access, or background handlers.

- [Installable ZIP](dist/sunner-0.4.0.zip)
- [Season, star and disc renders](examples/sky/contact-sheet.jpg)
- [Weather example](examples/sunner-weather.blend) and [weather contact sheet](examples/weather/contact-sheet.jpg)
- [Example scene](examples/sunner.blend)
- [Lighting contact sheet](examples/contact-sheet.jpg)
- [Design and sources](docs/design.md)
- [Verification notes](docs/verification.md)

## Install and use

1. In Blender Preferences, open **Get Extensions**, use its menu's **Install from Disk**, and select `dist/sunner-0.4.0.zip`.
2. Enable Sunner. In the 3D Viewport, press **N** and open the **Sunner** tab.
3. Choose **Add cycle**. Sunner assigns a new sky and retains your original World for restoration.
4. Use **Rendered** shading, or Material Preview with **Scene World** and **Scene Lights** enabled.
5. Adjust **Day angle**, or choose **Select day dial** and press **R, X, X** to rotate around its local X axis.

Sunner leaves existing lights alone. Disable competing outdoor Sun lights yourself if they produce unwanted extra illumination or shadows.

| Day angle | Approximate time |
| --- | --- |
| 0° | Midnight |
| 90° | Sunrise |
| 180° | Noon |
| 270° | Sunset |
| 360° | Midnight again |

The clock is an orientation aid, not local civil time. You can rotate beyond one turn or backwards.

## Controls

| Control | Effect |
| --- | --- |
| Heading | Turns the whole orbit around world Z |
| Path tilt | Lowers the midday sun; set it to your latitude (61.5° for Tampere) |
| Season | Sun declination: +23.4° midsummer, 0° equinox, −23.4° midwinter |
| Sun brightness | Direct sunlight multiplier |
| Sky brightness | Daylight and twilight World contribution |
| Night brightness | Moonlight and night sky together |
| Haze | Atmospheric aerosols in the sky, not fog between scene objects |
| Stars | Procedural star field; appears after civil twilight and turns with the dial |
| Discs | Visible sun and moon discs; camera rays only, they add no light |
| Sunset warmth | How strongly low sunlight warms |
| Moon cool tint | Neutral moonlight at zero, restrained blue tint at one |
| Shadow softness | Angular size of both lights |
| Twilight balance | Opt-in dusk/dawn rebalance; disabled by default |
| Twilight sky gain | Daylight multiplier at −4° solar elevation when twilight balance is on |
| Twilight moon gain | Moon and night-sky multiplier at −4° solar elevation when twilight balance is on |

### Seasons, stars and discs

With Path tilt at your latitude, **Season** moves the sun's whole daily path north or south. At Tampere (61.5°) midsummer gives a 52° noon and a white night 5° below the horizon at midnight; midwinter gives a 5° noon. Both lights leave the dial's plane together, so the moon stays opposite the sun (the full-moon approximation). The day dial remains the only time control.

**Stars** sit in the dial's frame, so they wheel around the celestial pole as the night passes, and fade in between −6° and −12° solar elevation. They are a decorative random field, not a real catalogue. Turn Cycles denoising off or down for star shots; the denoiser treats one-pixel stars as noise.

**Discs** draw the sun (tinted by its temperature) and the full moon in the sky, sized by Shadow softness and scaled by each light's own fading energy. They are visible only to camera rays, so the explicit Sun lights stay the sole direct light; this works in both Cycles and EEVEE. Set Discs to 0 to hide them.

### Updating older cycles

Cycles created by earlier versions are not changed when the extension updates. Choose **Update cycle** in the Sunner panel to add season, stars, discs and twilight balance. It keeps saved control values and the day dial, and rebuilds only Sunner's own World nodes. New controls start neutral (season 0) except stars and discs, which start at 1; set them to 0 to keep the old look. Scripts can call `sunner.rig.update(scene)`.

### Optional twilight balance

Cycles include native twilight drivers but leave **Twilight balance** off. Enable it in **Sunner → Advanced** to lift daylight sky contribution and restrain moon/night contribution around dawn and dusk. Its gain controls are evaluated from the existing day dial, heading, and path tilt; it adds no time property, callback, or scene migration.

At noon and midnight the twilight window has zero gain, so enabling it preserves the existing baseline at those phases. Uncheck **Twilight balance** to return to that baseline at every angle; the gain values remain available for later adjustment.

Scripts can enable it with `sunner.rig.configure_twilight(scene, sky_gain=3.0, moon_gain=0.15)`, which also runs `update()` on older cycles. Both validate that the managed World and light data are still exclusively owned before changing them; shared or replaced data is rejected rather than modified.

Defaults are calibrated under **AgX, Look None, exposure 0**. Sunner does not alter exposure, view transform, render engine, cameras, compositor, or other lights. Large exposure offsets will change the intended appearance.

Night is deliberately dark but brighter than physically accurate moonlight at daytime exposure. Increase Night brightness for a more readable night shot.

## Optional weather

Open **Sunner → Weather → Add weather**, then choose **Clear, Misty, Cloudy, Overcast, or Rainy**. Existing rigs do not acquire weather automatically when the extension is updated.

- **Fog** is a bounded, height-fading volume. Set Region width, Region origin and Fog height to cover your shot. Weather lengths are in metres, accounting for scene unit scale; Region origin uses scene coordinates.
- **Clouds** are a thin, wind-driven procedural layer with softened region edges, not volumetric cloud banks. Cloud coverage and height control appearance and shadowing. The layer spans five times the fog region's width to catch angled sunlight.
- **Shaft emphasis** controls forward scattering in the fog. Beams require sunlight or moonlight and occlusion from buildings or clouds; it does not generate decorative sky lasers. In EEVEE, enable the panel's native **Volume shadows** checkbox for shafts. Sunner never enables it silently.
- **Rain** uses up to 2,048 native Geometry Nodes instances around the bound scene camera. Choose **Bind rain to scene camera** after switching cameras. Deleting the bound camera disables rain automatically. Rainy requires a bound camera; creating a camera is your choice.
- **Wind** moves clouds and rain using frame time and scene FPS, including backwards scrubbing. No simulation cache or Python frame callback is involved.
- **Weather detail** exposes fog visibility distance, cloud scale and rain-region/streak controls. Clear sets all three effect amounts to zero. Presets change the same keyframeable controls; Auto Keying is respected. Animated keys can replace a non-keyed preset on the next frame change.

Use **Remove weather** to remove only weather, or **Remove cycle** to remove everything Sunner owns and restore the previous World. Both support undo and refuse removal when external data depends on owned weather objects/materials. User cameras, building/water materials, exposure, compositor and existing lights are untouched.

### Cost and limits

Rain is camera-local, with no collisions, splashes or wet-surface changes. Clouds are a finite thin layer; neither horizon-to-horizon storm coverage nor realistic flight through clouds is promised. Shafts depend on shot geometry and engine settings. Night rain needs enough illumination to be visible.

Fog is the main cost. At 320×200 in the small test scene, clear renders took about 1–2 seconds and weather 6–10 seconds, with peak process RSS below 1 GiB. These are smoke-test timings, not city-scale performance guarantees. Keep the region no larger than your shot requires, and start with Clear or a low fog amount. [Measurements and limitations](docs/verification.md#02-weather).

## Animate

Hover over **Day angle** and insert a normal Blender keyframe, or use **Animate one day**.

The animation action starts at the current day angle, keys one full turn with linear interpolation, and repeats using a native Cycles modifier. It also sets the scene playback range. For a 240-frame cycle starting at frame 1, the matching endpoint is keyed at 241, while frames 1–240 play/render. This avoids duplicating the first image at the loop boundary.

Existing day-angle keys are not replaced without checking **Replace day-angle keys**. Other action channels remain intact; shared actions are copied before editing. A dial already controlled by NLA or drivers must be animated manually.

Dawn/Noon/Dusk/Night buttons set the dial and insert a key when Blender Auto Keying is on. Without Auto Keying, they only change the current value, which existing animation may replace when the frame changes.

The example includes a 240-frame loop beginning in late afternoon. Existing rigs continue to evaluate without the extension enabled, even with Python auto-run disabled. The extension is needed for its panel and editing operators, not for rendering a saved rig.

## Restore the scene

Use **Remove cycle**. If Sunner's World is still assigned, the original World is restored. If you assigned a different World, that choice is preserved.

Removal deletes only owned objects, light data, and the owned World/collection. It refuses to proceed if other scene data references the rig or if you placed unrelated objects in its collection. Resolve those references or move the extra objects out first. Add and Remove support Blender undo.

Disabling the extension removes its UI, not scene content. Renaming generated objects does not break the rig. Do not reparent, constrain, change rotation modes, or scale the rig's controls: the supported orbit is the heading/tilt parent plus the day dial's local X rotation.

## Deliberate limits

- One rig per scene. Sharing a rig across scenes is not an independent second cycle.
- The moon stays opposite the sun, a full-moon approximation. No lunar phases or moon surface texture.
- Stars are a random field, not real constellations. Weather is optional and artist-controlled, not meteorological simulation.
- Latitude (Path tilt) and season are artist controls. There is no date/time-zone/location solver, automatic exposure, or light-probe baking.
- EEVEE and Cycles differ in indirect lighting and contact shadows. Sunner does not alter scene-specific probes or ray-tracing settings to conceal those differences.
- The sky uses the native model down to -18° solar elevation, then holds that value while its daylight contribution reaches zero. A simple gradient supplies the night sky.
- Blender 5.2 is the tested API. The manifest excludes 5.3 and later until they are verified.

## Python integration

When using the source checkout in a Blender script:

```python
import math
import sys
import bpy

sys.path.insert(0, "/path/to/blender_sunner")
from sunner.rig import create, parts, remove

scene = bpy.context.scene
create(scene)                     # Idempotent; does not delete other lights.
p = parts(scene)
p["dial"].rotation_euler.x = math.radians(240)
p["root"].rotation_euler.z = math.radians(30)
p["root"]["night_brightness"] = 2.0
bpy.context.view_layer.update()

# remove(scene)                   # Restore the previous World and remove owned data.
```

After keyframing, evaluate with `scene.frame_set(frame)`. `parts()` returns `root`, `dial`, `sun`, `moon`, and `world` data references. Normal construction replaces the active World but leaves its node tree untouched. Exceptions use `sunner.rig.RigError` for invalid or unsafe editing operations.

Weather can be added to a saved 0.1 rig without rebuilding its lighting:

```python
from sunner import weather
w = weather.create(scene)            # Idempotent; the cycle must already exist.
w["root"]["extent"] = 1000.0         # Metres, not scene coordinates.
w["root"].location = (0, 0, 0)       # Place at the region's ground level.
weather.preset(scene, "CLOUDY")
# weather.bind_camera(scene)         # Bind/rebind to scene.camera for rain.
# weather.remove(scene)              # Leave the cycle and its World intact.
bpy.context.view_layer.update()
```

## Local installation maintenance

On this workstation, verified Sunner releases are also installed and enabled in the normal Blender profile:

```bash
blender --background --factory-startup --threads 1 --python-exit-code 1 \
  --python tools/install_local.py -- --zip dist/sunner-0.4.0.zip
```

The installer reads existing preferences explicitly, backs them up locally, installs through Blender's extension operator, checks installed files against the ZIP, and saves enablement. Backups and `sunner-install.json` stay under Blender's local configuration directory, not in this repository. It does not open startup/saved scenes or upgrade the Blender application. Restart an already-open Blender to load updated code. Test the ZIP in an isolated profile before running this against normal preferences.

## Development

Run commands from the repository root unless noted:

```bash
blender --background --factory-startup --python-exit-code 1 --python tests/test_cycle.py
blender --background --factory-startup --python-exit-code 1 --python tests/test_weather.py

# Disposable foreground window for undo/redo and panel verification.
blender --factory-startup --enable-event-simulate --python-exit-code 1 --python tests/test_ui.py
# Check examples/ui-smoke.json as well as the foreground process result.

# Generate the example and render comparisons.
blender --background --factory-startup --python-exit-code 1 --python tests/render_samples.py -- --engine CYCLES --save
blender --background --factory-startup --python-exit-code 1 --python tests/render_samples.py -- --engine BLENDER_EEVEE
python3 tests/contact_sheet.py     # Developer-only Pillow dependency.

# Season, star and disc renders, plus a contact sheet built with Blender only.
blender --background --factory-startup --python-exit-code 1 --python tests/render_sky.py -- --engine CYCLES
blender --background --factory-startup --python-exit-code 1 --python tests/render_sky.py -- --engine BLENDER_EEVEE
blender --background --factory-startup --python-exit-code 1 --python tests/sky_sheet.py

# Small weather comparison, serial processes only. Script stops if macOS memory pressure rises.
blender --background --factory-startup --threads 2 --python-exit-code 1 --python tests/render_weather.py -- --engine CYCLES --save
blender --background --factory-startup --threads 2 --python-exit-code 1 --python tests/render_weather.py -- --engine BLENDER_EEVEE
python3 tests/contact_sheet.py --weather

mkdir -p dist
(cd sunner && blender --command extension validate && blender --command extension build --output-dir ../dist)
blender --command extension validate dist/sunner-0.4.0.zip

# Use an isolated profile so the installation test does not modify yours.
profile=$(mktemp -d /tmp/sunner-install.XXXXXX)
BLENDER_USER_RESOURCES="$profile" blender --background --factory-startup --python-exit-code 1 --python tests/test_install.py
```

The foreground UI test uses explicit undo checkpoints around operators invoked from Python. After the undo checks, it captures the registered panel as a popup in `examples/weather-panel-preview.png`. This avoids screen-coordinate-dependent tab selection. Test scripts create disposable scenes; never run them inside a scene you want to retain.

License: [GPL-3.0-or-later](sunner/LICENSE). Source: <https://github.com/jheaminoff/blender_sunner>. Not published on the Blender Extensions platform.
