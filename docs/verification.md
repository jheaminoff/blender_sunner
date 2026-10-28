# Sunner verification

## 0.4 seasons, stars and discs

Verified on Blender **5.2.3 LTS**, macOS arm64, 2026-10-28.

- **34 integration tests passed:** 22 cycle tests and 12 weather tests. New checks: sun direction against the closed-form declination formula across heading/tilt/season, the Tampere midsummer white night (52° noon, −5° midnight, no direct sun, lit sky), sun/moon discs visible in tiny Cycles and EEVEE renders while a ground plane's illumination stays within 2% with discs at 0 or 10, stars at night only, and the Update cycle path on a rig stripped of all optional controls (saved values kept).
- The saved-file test still evaluates every driver with Python auto-run disabled and no extension. All driver expressions remain simple expressions under 255 bytes.
- A 0.1 ZIP rig accepts `configure_twilight` (which now runs `update`) and weather.
- Foreground UI: undo/redo checks as before, plus a capture of the real Sunner sidebar tab after Update cycle ([cycle panel](../examples/cycle-panel-preview.png)).
- [Season, star and disc contact sheet](../examples/sky/contact-sheet.jpg): top row Cycles (64 samples, no denoising), bottom row EEVEE; equinox sunset disc, midwinter and midsummer noon at 61.5°, midsummer white night, moonrise with stars, midwinter star field.
- `dist/sunner-0.4.0.zip` validated; isolated-profile install ran add/update/season/weather/remove and disable/re-enable.
- Normal local installation updated to 0.4.0 with `tools/install_local.py` after the same installer passed in an isolated profile; a normal-profile background start registered `bl_ext.sunner_local.sunner`. Preferences were backed up first; no scene was opened or saved. Restart any running Blender to load it.
- Defect found during the work: the first star and disc shader used `Texture Coordinate > Normal`, which in World shaders points away from the view direction, so neither appeared in renders. Switched to `Generated`; the render tests above guard it.

## 0.3 twilight balance

Built 2026-09-16 and covered by the cycle suite (opt-in gains, idempotence, shared/replaced data rejection, legacy upgrade) and foreground Advanced-panel captures. Its release checks were completed together with 0.4.

## 0.2 weather

Verified on Blender **5.2.1 LTS**, macOS arm64, 2026-09-14.

- **25 integration tests passed:** 13 cycle tests and 12 weather tests. Logs: [cycle](integration-results.txt), [weather](weather-integration-results.txt).
- Weather checks cover owned-data cleanup and sharing, rollback, invalid ownership references, deleted objects, camera deletion/rebinding, native driver validity, centimetre-scale scenes, frame/FPS-driven wind, preset animation, saved-file evaluation with auto-run disabled and no extension, and adding weather to a rig built from the retained 0.1 ZIP.
- Foreground checks passed cycle+weather undo/redo, weather-removal undo, whole-rig-removal undo, disable/re-enable and [weather panel capture](../examples/weather-panel-preview.png). This is a registered popup capture, not automated mouse navigation of the sidebar. Longer labels truncate in its narrow default width; widen the sidebar when needed.
- **16 weather renders inspected:** eight Cycles and eight EEVEE frames, [contact sheet](../examples/weather/contact-sheet.jpg). Each engine's Clear image is pixel-identical to its no-weather image. The example is [sunner-weather.blend](../examples/sunner-weather.blend).
- Manifest and `dist/sunner-0.2.0.zip` validated. Clean-profile install exercised add/weather/preset/remove. The local updater passed initial and repeat installation, preserved a non-default preference, checked every installed file against the ZIP, and loaded the enabled weather panel on normal startup in the isolated profile.
- The read-only review found three lifecycle issues: an invalid weather pointer could be treated as ownership, a deleted rain constraint broke Bind, and deleting a bound camera did not disable rain. All were corrected and covered by passing regressions. No second reviewer pass was requested; acceptance used the actual fixes and deterministic checks.

### Normal local installation

The Captain authorized installation and ongoing verified add-on updates. Version 0.2.0 was installed and enabled as `bl_ext.sunner_local.sunner` under `~/Library/Application Support/Blender/5.2/extensions/sunner_local/sunner`. Every installed file matched the ZIP; its SHA-256 is `a9f4d91d73028e76575d2f986551459d15d667b2cb1eac9acc5f5f0fa08cbc79`.

Saved preferences were backed up to `~/Library/Application Support/Blender/5.2/config/sunner-backups/20260914T115248.570575Z/userpref.blend` with private permissions. The local receipt is `config/sunner-install.json`. Existing enabled add-on entries were preserved. A fresh process loaded the installed weather panel using a private copy of those saved preferences, without loading the user's startup scene. The unrelated Tampere streamer was unavailable only in that temporary profile's empty relative repository; its real installed source remains present and untouched.

An existing Blender GUI was left running; **restart it to load Sunner**. No saved scene, startup scene, Blender application binary, or public repository was changed by installation.

### Render-cost evidence

These are single small smoke-test renders, **not** a city benchmark. 320×200, 16 samples, two CPU threads, AgX/Look None/exposure 0; Cycles denoising enabled. EEVEE volume shadows were explicitly enabled in the test scene, not by the extension. Cold-start and cache differences affect timings.

| Engine | No weather / Clear | Weather frames | Peak process RSS |
| --- | --- | --- | --- |
| Cycles | 2.28 / 1.85 s | 6.30–7.77 s | 855 MiB |
| EEVEE | 1.16 / 0.89 s | 6.08–9.56 s | 390 MiB |

Raw timings are under `examples/weather/<engine>/metrics.json`. Runs were serial, without city assets, within the Tampere conversion session's approved small-process budget. The script checks macOS memory pressure before each frame and stops if it rises; process RSS is not a measurement of all unified GPU/system memory.

### Weather limitations and fixes

- Fog is the dominant cost. Shafts need occlusion and useful viewing geometry; the sample shows atmospheric scattering and cloud/building shadowing, not guaranteed dramatic beams in every shot. EEVEE needs volume shadows enabled; results differ from Cycles.
- Clouds are a finite thin procedural surface, not volumetric storm clouds. Region-edge opacity fading avoids a hard clipped cloud boundary. Rain has no collision, splash or automatic wet materials; night rain remains illumination-dependent.
- Native driver output quantized tiny fog/scaling values to zero in centimetre scenes. Those divisions now happen in shader math after receiving normally sized driver values. Unit-scale regression passed.
- Rain visibility and instance count use native fallback driver values through the camera constraint's target, so deleted cameras or constraints disable rain without handlers. Explicit Bind reconstructs a missing owned constraint.

## 0.1 lighting baseline

Verified locally on Blender **5.2.1 LTS**, macOS arm64, on 2026-09-14. The extension supports the 5.2 series; other Blender versions and operating systems were not tested.

## Results

| Check | Result |
| --- | --- |
| Blender integration suite | 13 tests passed |
| Native light/sky drivers | Valid simple expressions; direction agreement across heading, tilt, and multiple turns |
| Saved rig, fresh Blender, `--disable-autoexec`, no extension registered | Lighting and animation evaluated correctly |
| Original World after reopening | Reference and nodes retained; removal restored it in the fresh process |
| Scene safety | Add is idempotent; renames work; unrelated lights/World nodes remain; shared references block unsafe removal |
| Incomplete rig cleanup | Removing a manually deleted moon object's remaining owned light data passed |
| Animation | Linear turn, offset repeat, frame jumps, brightness keys, shared-action copying, overwrite confirmation passed |
| Foreground UI smoke | Add/select, add undo/redo, remove undo, disable/re-enable, registered panel capture passed |
| Manifest and ZIP validation | Passed Blender extension validation |
| ZIP installation | Installed through Blender's extension operator into an isolated temporary profile; add/rotate/remove and disable/re-enable passed |
| Lighting renders | Eight phases in each of Cycles and EEVEE, 16 images total; contact sheet inspected |
| Focused read-only review | No material code issues reported; suggested reopened-World removal coverage was added and passed |

Commands are documented in [README](../README.md#development). Integration output is retained in [integration-results.txt](integration-results.txt). GUI outcomes are in [ui-smoke.json](../examples/ui-smoke.json).

## Visual inspection

[Contact sheet](../examples/contact-sheet.jpg): dawn, morning, noon, golden hour, dusk, twilight, blue hour, and midnight. All use AgX, Look None, exposure 0. Cycles uses 32 samples and denoising. Each source image is 480 × 320.

The sun direction and cast shadows change together. Morning/evening light is warm, midday is near-neutral with a blue sky, and night retains restrained moon illumination. Neither engine shows a second direct-sun shadow. Near-horizon numerical checks additionally verify continuous energy/blend transitions.

EEVEE's ambient contact shadows/reflections differ from Cycles, most noticeably at dawn/dusk when the direct lights are off. Sunner deliberately does not bake probes or change ray-tracing settings. Scene-specific EEVEE lighting setup remains the user's choice.

[Panel preview](../examples/panel-preview.png) captures the registered panel as a popup after the undo checks. The native sidebar tab's registration was verified, but automatic tab selection did not reliably change the visible layout during capture, so this is not presented as a mouse-driven sidebar end-to-end test. The narrow default popup truncates some longer labels; the normal sidebar can be widened.

## Defects found and corrected

- Newly linked objects were not immediately present in `context.view_layer.objects`. Add initially reported that the collection was excluded. `select_dial()` now updates the view layer before checking/selecting the new dial.
- Deleting a moon object erased its collection object reference but left the light data and drivers. Cleanup initially treated those drivers as external references. The collection now retains separate light-data ownership, so incomplete rigs remove safely. Covered by regression.
- Background preview assembly selected an interpreter without Pillow. The renders and example had completed; the contact sheet was regenerated with the verified pyenv 3.12.8 interpreter. Pillow is a developer-only dependency.
- The GUI test left a `wm.call_panel` popup open while programmatic undo/removal deleted its referenced RNA data. Blender crashed in UI text drawing. The test now performs all undo/removal operations before opening and capturing the panel, then quits without further scene mutation. The revised foreground test completed successfully. No popup is part of Sunner's normal sidebar workflow.

## Delivery and limits

- ZIP: `dist/sunner-0.1.0.zip`, validated and installed from the final source.
- Example: `examples/sunner.blend`, including the 240-frame cycle beginning in late afternoon.
- Source: `sunner/`, licensed GPL-3.0-or-later.
- No real user Blender profile was modified by the ZIP installation tests. No public repository or marketplace publication was performed.
- This is focused functional and visual verification, not a long-duration playback benchmark or a cross-platform certification. Visible celestial discs, weather, lunar phases, automatic exposure, and geographic accuracy remain out of scope.
