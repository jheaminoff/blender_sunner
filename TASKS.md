# Sunner implementation tasks

Design: [docs/design.md](docs/design.md).

Implemented as Sunner 0.1.0. The approved first-release checklist is complete; see [README](README.md) for delivery and [verification](docs/verification.md) for the checks actually run.

## 0. Confirm scope

- [x] Approve Blender 5.2 as the initial target, with Cycles and EEVEE.
- [x] Confirm that illumination and sky without visible sun/moon discs are sufficient for version one.
- [x] Approve fixed opposing sun/moon positions and an artistic night-brightness lift.

Done when the first-release scope is agreed. Do not quietly add astronomy or weather features.

## 1. Prove the complete lighting interaction

- [x] Build a minimal in-Blender prototype with a heading/tilt parent, rotatable day dial, opposing Sun lights, and an owned multiple-scattering World.
- [x] Disable native sky sun-disc lighting and EEVEE World sun extraction on that World.
- [x] Drive the light orientation and sky direction from the same unbounded dial rotation. Verify the local -Z light emission convention and sky azimuth mapping.
- [x] Add initial horizon fades and a simple night-sky blend, driven from elevation.
- [x] Check native sky behaviour below the horizon and determine the useful twilight blend range.
- [x] Render a ground plane, upright shadow caster, and neutral sphere at dawn, noon, dusk, and midnight in both engines.

Done when rotating one object produces matching sky/light directions and a complete day/night transition. No UI polish yet. Record any actual engine/API limitation before choosing a workaround.

## 2. Turn the prototype into a safe extension

- [x] Add registration and `blender_manifest.toml`, with the agreed version floor and confirmed maintainer/license metadata.
- [x] Implement undoable Add/Select/Remove operators and one-rig-per-scene behaviour.
- [x] Preserve the original World, including its survival across save/reload after replacement.
- [x] Track ownership with persistent references/tags. Keep unrelated scene data untouched.
- [x] Restore the original World only if Sunner's World is still assigned. Remove only owned, safe-to-remove data.
- [x] Leave generated lighting functional when the extension is disabled.

Done when adding, undoing, saving/reopening, and removing the rig do not damage the user's previous World or unrelated lights. Report incomplete rig data instead of overwriting it.

## 3. Calibrate the look

- [x] Tune solar temperature and atmospheric attenuation against elevation.
- [x] Tune smooth horizon transitions and sky-to-night blending. Remove popping, abrupt hue changes, and below-ground direct illumination.
- [x] Calibrate sun/sky gains and a restrained readable night under a documented view transform and fixed exposure.
- [x] Add animatable Sun brightness, Sky brightness, Night brightness, and Haze controls.
- [x] Add advanced sunset warmth, moon tint, and shadow softness only as direct parameters of the existing model.
- [x] Document that night brightness is artistic, Haze is not scene fog, and existing exposure/render settings remain untouched.

Done when an approved contact sheet shows believable morning, daytime, evening, and night in both engines. The same dial angles must mean the same light directions in both.

## 4. Add the small artist interface

- [x] Add a `Sunner` sidebar with Add/Select/Remove, Day angle, derived clock readout, Heading, and Path tilt.
- [x] Bind Day angle to the actual rotation property. Do not create an independently stored clock value.
- [x] Add Dawn/Noon/Dusk/Night positioning buttons that change the same dial and respect Blender's animation workflow.
- [x] Use standard Empty display and Blender rotation tools. Lock unsupported control axes and scale/translation.
- [x] Expose primary brightness/haze controls, with secondary controls collapsed.
- [x] Explain scene World replacement and viewport requirements. Rendered shading, or Material Preview using scene World/lights, is required to see the result.

Done when a user can add the rig, rotate to sunset, redirect the orbit, and restore the previous World without opening the node editor.

## 5. Make animation predictable

- [x] Implement an explicit Animate one day action with start/end frames and linear full-turn rotation.
- [x] Define loop sampling: for an N-frame seamless loop, put the matching endpoint N frames after the first key and render the first N frames, excluding the duplicated endpoint.
- [x] Confirm manual keyframes, scrubbing backwards, multiple turns, and non-sequential frame evaluation.
- [x] Evaluate all controls through native drivers/nodes; avoid frame handlers and required custom driver-namespace functions.
- [x] Do not replace existing animation without an explicit warning/confirmation.

Done when viewport scrubbing and background renders agree, and a saved rig evaluates in a fresh process with the extension and Python auto-run disabled.

## 6. Run focused regression and visual checks

- [x] Add a small Blender integration script covering rig idempotence, expected light directions, opposite moon, horizon fades, and wrap continuity.
- [x] Check noon/midnight direction and expected tilt, plus continuity around dawn/dusk and the full-turn boundary. Use bounded numerical assertions, not fragile exact pixel comparisons.
- [x] Test frame jumps through keyframed dial and brightness controls.
- [x] Test original-World preservation across save/reload, object renaming, and removal. Include an unrelated light and an existing multi-node World.
- [x] Test removal after the user assigns a different World. Leave that World untouched.
- [x] Perform UI undo/redo and extension enable/disable checks.
- [x] Render and inspect a small contact sheet for both engines, with additional near-horizon samples where the fades change fastest.

Done when these affected contracts pass and the contact sheets show no direction mismatch, double-sun shadows, horizon pop, or unintended black daylight sky. Record renderer differences rather than promising parity.

Deterministic integration command:

```bash
blender --background --factory-startup --python-exit-code 1 \
  --python tests/test_cycle.py
```

This command passed all 13 tests on Blender 5.2.1 LTS. Foreground UI checks, both render engines, and clean-profile ZIP installation were checked separately.

## 7. Package and hand over

- [x] Write a short README covering installation, rotation/keyframing, controls, World restoration, supported version, and intentional simplifications.
- [x] Include one small example scene and its preview contact sheet.
- [x] Validate and build from the extension source directory using the documented CLI:

```bash
blender --command extension validate
blender --command extension build
```

- [x] Install the resulting ZIP into a clean Blender profile and repeat the add/rotate/remove smoke test.
- [x] Deliver the ZIP, source, example, and verification notes. Do not publish to an extension marketplace or remote repository without approval.

Done when the ZIP installs cleanly and a new scene can complete the basic workflow without external dependencies.

## Deferred until the core is accepted

- Visible sun/moon discs and moon surface texture.
- Optional stars that fade with daylight.
- Distance fog, clouds, and simple rain moved into the explicitly approved 0.2 scope below.
- Independent lunar orbit or phase.
- Geographic/time/date controls.
- Automatic exposure and light-probe baking.
- Older Blender compatibility.
- Custom orbit gizmo, preset browser, or multiple rigs per scene.

If visible celestial bodies are required in version one, move that item into scope before implementation and test its direct/environment lighting contribution explicitly.

## 8. Approved 0.2 weather extension

- [x] Keep existing 0.1 rigs and light calibration unchanged; weather is opt-in.
- [x] Add bounded height-fading fog, a procedural thin cloud/shadow layer and camera-local instanced rain.
- [x] Add Clear/Misty/Cloudy/Overcast/Rainy presets over native keyframeable controls and FPS-aware wind.
- [x] Provide native EEVEE volume-shadow control without silently changing render settings.
- [x] Verify safe weather removal, whole-rig removal, missing-object cleanup, shared-data protection and camera deletion/rebinding.
- [x] Verify saved weather with the extension and Python auto-run disabled, and attach weather to a rig built from the released 0.1 ZIP.
- [x] Inspect 16 small Cycles/EEVEE weather frames and record render cost and peak process RSS.
- [x] Pass 12 weather tests plus the existing 13 cycle tests, and foreground weather undo/redo/panel capture.
- [x] Validate/package 0.2 ZIP; test installation and repeat updates in isolated profiles while preserving preferences.
- [x] Install and enable the verified release in the normal Blender profile, without modifying scenes or upgrading Blender itself.

Future verified Sunner updates must also update the normal local add-on installation, as explicitly requested by the Captain.
