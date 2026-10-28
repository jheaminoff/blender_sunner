# Sunner: a simple sun and moon cycle

Status: implemented as Sunner 0.1.0 after the Captain approved this scope. This document retains the original design reasoning; see [README](../README.md) for the shipped behaviour and [verification](verification.md) for evidence.

## Goal

Add a daylight rig, rotate one control to move through the day, and get coordinated light direction, colour, shadows, and sky. Aim for believable outdoor lighting with useful artistic control. Do not simulate dates, geography, or orbital mechanics.

The project directory was empty at discovery. The local executable is `/opt/homebrew/bin/blender`, reporting Blender 5.2.1 LTS. Target 5.2 first, with Cycles and EEVEE. Older-version support is not part of this proposal.

## Research findings

1. Blender already supplies the atmospheric model. Its 5.2 Sky Texture defaults to Multiple Scattering, which models multiple light bounces through the atmosphere. Reuse this rather than implement scattering or distribute HDRIs. [1, 6]
2. A Sun-type light is directional and effectively infinitely distant. Rotating it changes illumination; moving it does not. Both sun and moon should therefore use `SUN` lights, not orbiting point lights. [2]
3. The native Sky Texture sun disc is documented as Cycles-only. EEVEE also has World sun extraction, which can create another directional lighting contribution. For the first version, disable the sky disc and set the owned World's sun extraction threshold to zero. Explicit light objects provide direct sun and moon illumination. This avoids competing direct-light sources. [1, 3]
4. Blender's manual gives illustrative normalized strengths of 1000 W/m² for clear sunlight and 0.001 W/m² for moonlight. A fixed-exposure night will therefore be very dark. A readable night is an artistic adjustment, not a physically accurate intensity ratio. [2]
5. Simple driver expressions support trigonometry, `atan2`, `clamp`, and `smoothstep`, and evaluate with Python script execution disabled. They are a better starting point than a Python callback that edits the scene every frame. Explicit driver variables establish dependencies. [4]
6. EEVEE approximates World lighting through an internal light probe; Cycles handles it differently. Shared controls and a similar look are realistic targets. Pixel-identical results and automatically updating all baked scene probes are not. [3]
7. Existing Sun Position solves geographic location/date/time, which is outside this brief. Physical Atmosphere offers artistic rotation alongside a much larger astronomy and atmosphere toolset. Borrow the direct manipulation, not the feature count. [7, 8]
8. Blender extensions use `blender_manifest.toml` and can be built and validated with Blender's CLI. No external Python dependencies or network access are necessary. [5]

### Local API checks

These facts were checked in a factory-startup, background Blender process without saving a scene:

- Version: `5.2.1 LTS`.
- `ShaderNodeTexSky.sky_type` includes `SINGLE_SCATTERING`, `MULTIPLE_SCATTERING`, `PREETHAM`, and `HOSEK_WILKIE`; its default is `MULTIPLE_SCATTERING`.
- The current property is `aerosol_density`, not the `dust_density` used in older examples. An initial probe using the old name raised `KeyError`; a corrected probe succeeded.
- The node exposes `sun_elevation`, `sun_rotation`, `sun_disc`, `sun_size`, `sun_intensity`, `air_density`, and `ozone_density`.
- `World.sun_threshold` exists and defaults to `10.0`. Zero disables extraction according to the manual.
- Sun lights expose `energy`, `angle`, `normalize`, `use_temperature`, and `temperature`.
- Explicitly setting `World.use_nodes` raised a Blender 6.0 deprecation warning. The new World already exposed a node tree in the successful probe.

These checks establish available API, not visual quality. Render calibration, negative-elevation sky behaviour, azimuth conventions, and animation evaluation still need testing.

## Brainstorm and recommendation

| Approach | Advantage | Cost | Decision |
| --- | --- | --- | --- |
| One light that changes between sun and moon | Few objects | Direction switches become awkward; twilight cannot overlap cleanly | Reject |
| Two directional lights, one orbit, native sky | Simple interaction, soft transitions, existing atmosphere model | Some artistic calibration; simplified full-moon orbit | Recommend |
| HDRI day/night crossfade | Quick attractive static backgrounds | Asset dependencies and baked light directions do not follow arbitrary rotation | Reject for the core |
| Custom atmosphere, weather, astronomical positions | More physical control | Far beyond the requested scope | Defer |

Use two opposing lights under one day dial. The moon is always opposite the sun, a deliberate full-moon approximation. Real moons can be visible in daytime and do not share this fixed daily schedule.

## First-version experience

1. Open the `Sunner` sidebar and choose **Add cycle**. The action creates the rig and assigns a new managed World, explaining that the previous World will be preserved.
2. The selected `Day dial` Empty rotates around its local X axis. Rotate it in the viewport or adjust the same rotation in the sidebar.
3. Midnight is 0°, sunrise 90°, noon 180°, sunset 270°, and midnight again 360°. Display a derived 24-hour clock for orientation, not real civil time.
4. Rotate the parent heading to aim sunrise across the scene. Adjust path tilt to lower the midday sun, without asking for latitude or season.
5. Keyframe the dial normally. An optional **Animate one day** action inserts a linear full turn over a chosen frame interval.
6. **Remove cycle** restores the previous World if the managed World is still assigned, and removes only owned rig data. If the user has assigned another World meanwhile, leave it alone.

Default to late afternoon so the first result shows readable directional shadows and some warmth. Use Blender's ordinary rotate tool before investing in a custom GPU gizmo.

### Compact sidebar

```text
Sunner
  [ Add cycle ]

  Day angle        240°       ~16:00
  [ Dawn ] [ Noon ] [ Dusk ] [ Night ]
  [ Select day dial ]

  Heading          0°
  Path tilt        30°

  Sun brightness   1.0
  Sky brightness   1.0
  Night brightness 1.0
  Haze             1.0

  > Advanced
      Sunset warmth
      Moon tint
      Shadow softness

  [ Animate one day… ]
  [ Remove cycle… ]
```

Values shown are proposed UI multipliers, not calibrated radiometric strengths. Night brightness scales the moon contribution and night sky together. All brightness controls must be animatable.

## Lighting and sky behaviour

- Midday: near-neutral sunlight, blue sky, firm shadows.
- Low sun: progressively warmer sunlight, weaker direct illumination, a warmer horizon.
- Twilight: direct sunlight fades out at the geometric horizon while sky illumination persists, then fades into night. Moon illumination rises smoothly as it clears the opposite horizon.
- Night: dim neutral moonlight, an optional mild cool tint, and a restrained blue-grey World gradient. Avoid making the default moon a saturated blue spotlight.
- Use smooth elevation-based transitions, not clock-based colour presets. Tilting the orbit should change the lighting appropriately.
- Base solar colour on a simple temperature ramp, initially around 5500–6500 K high in the sky and 2500–3500 K near the horizon. These are artistic starting points to calibrate, not an atmospheric transmission solver.
- Start with a Sun angular diameter near 0.53°. Expose a softness multiplier for artistic adjustment. Apply similarly restrained softness to the moon.
- Do not multiply direct light strength by `sin(elevation)` just to darken evening. Surface incidence already changes with direction. Add only the intended atmospheric attenuation and horizon fade.
- Use the native multiple-scattering sky for daylight and the supported twilight range. Test it below the horizon before defining the blend to the night gradient. Roughly -6° to -18° is an initial twilight tuning range, not a promised astronomical model.
- Haze maps to the native aerosol control. It affects the sky, not the depth of objects in the scene. Actual distance fog requires volume or compositing work and is excluded.
- Set calibrated sun/sky gains that work at ordinary scene exposure. Never silently change exposure, view transform, render engine, camera, compositor, or other lights. Warn about extreme existing exposure instead of compensating behind the user's back.
- Include a modest night lift for usability and document that it departs from real moonlight. Do not add automatic exposure in version one.

### Visible celestial bodies

Version one supplies sun/moon illumination and a changing sky, but no visible sun or moon disc. A Blender light object itself does not render as a celestial body. Native sky discs are disabled to keep the initial direct-light setup consistent across engines.

If visible bodies are required for the first release, add a separate scoped task before implementation. A direction-based World-shader disc is worth investigating, but its lighting contribution must not duplicate the explicit lights. Moon texture, phases, eclipses, stars, clouds, and bloom are later additions.

## Proposed implementation

### One authoritative rotation

The day dial's actual, unbounded local X rotation is the cycle state. The sidebar edits that property directly. A clock readout is derived from it. Do not synchronize a separate time-of-day property back and forth with the rotation.

The rig contains a parent for heading/path tilt, a child day dial, and two opposite Sun lights. A collection groups them. Lock unsupported translation/scale and rotation axes in the user-facing controls. Light positions and display lengths are only viewport aids.

For a dial angle `p`, heading `h`, and tilt `t`, the proposed direction towards the sun is:

```text
base = (-sin(t) * cos(p), sin(p), -cos(t) * cos(p))
sun_direction = rotate_about_world_Z(base, h)
moon_direction = -sun_direction
sun_elevation = asin(clamp(sun_direction.z, -1, 1))
```

This corresponds to `Rz(h) * Ry(t) * Rx(p) * (0, 0, -1)`. Keep tilt within a useful non-degenerate range, initially 0–75°. The light emits along local -Z; its orientation must therefore be opposite the direction towards the celestial body. Verify the Sky Texture's azimuth convention against actual shadows rather than guessing an offset. Handle zenith azimuth deterministically, without changing the continuous direction.

Use single-property driver variables for the unbounded Euler angle so multiple revolutions remain usable. Evaluate light direction, colour, energy, and sky from the same control dependencies. Simple native drivers and shader nodes should make playback and background rendering independent of custom frame handlers.

Do not introduce a handler unless the first prototype demonstrates a specific driver limitation. In particular, avoid UI update callbacks as the only animation mechanism.

### World ownership and scene safety

- Create one rig and one owned World per scene. Repeating **Add cycle** selects the existing rig rather than duplicating it.
- Keep the original World untouched and retain a persistent reference sufficient for save/reload and restoration. Account for an original World losing its last scene user.
- Never clear the user's existing World node tree or delete unrelated lights.
- Record ownership with persistent data references/tags, not display names. Renaming objects must not break the rig.
- Store the driving controls on generated Blender data with native custom properties where needed, so existing drivers do not depend on registered Python functions.
- Disabling the extension removes UI and registration, not the user's generated scene. The baked-in rig remains evaluable with the extension disabled; verify this by reopening in a fresh process.
- Use explicit undoable operators for creation, animation, and removal. Broken references should produce a clear message, not silently rebuild over the scene.
- No global scene scans on every frame, background timers, network calls, external assets, or third-party dependencies.

### Small module layout

```text
sunner/
  blender_manifest.toml
  __init__.py       registration
  rig.py            creation, ownership, restoration, removal
  lighting.py       drivers, sky nodes, lighting curves
  operators.py      add/select/presets/animate/remove
  ui.py             sidebar and property presentation
tests/              Blender integration checks
examples/           calibration scene and render references
```

This is a proposed layout, not a demand to create empty modules. Keep code together until it has a reason to separate. Avoid a compatibility layer or extensible preset framework for this first release.

## Approved scope

Defaults approved for the first implementation:

- Blender 5.2 first, tested in both Cycles and EEVEE.
- One managed rig per scene, one dial, two opposing directional lights.
- Native multiple-scattering sky, simple night gradient, readable artistic night.
- No visible celestial discs, stars, weather, geography, dates, seasons, lunar phases, automatic exposure, or automatic light-probe baking in the first release.
- Deliver an installable local extension ZIP. Public release and licensing/maintainer details require confirmation before packaging for distribution.

## Sources

1. [Blender 5.2 Sky Texture](https://docs.blender.org/manual/en/5.2/render/shader_nodes/textures/sky.html).
2. [Blender 5.2 Light Objects](https://docs.blender.org/manual/en/5.2/render/lights/light_object.html).
3. [Blender 5.2 EEVEE World Settings](https://docs.blender.org/manual/en/5.2/render/eevee/world_settings.html).
4. [Blender 5.2 Drivers Panel, including simple expressions](https://docs.blender.org/manual/en/5.2/animation/drivers/drivers_panel.html).
5. [Blender 5.2 How to Create Extensions](https://docs.blender.org/manual/en/5.2/advanced/extensions/getting_started.html).
6. [Marco Pavanello: implementing the multiscattering sky texture](https://marcopavanello.art/blog/2025/09-15/). Author reports integration into Blender 5.0.
7. [Sun Position extension](https://extensions.blender.org/add-ons/sun-position/).
8. [Physical Atmosphere documentation](https://www.physicaladdons.com/physical-atmosphere/documentation/). Used for interaction comparison, not as an implementation dependency.
