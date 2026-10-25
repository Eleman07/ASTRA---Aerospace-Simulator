# ASTRA Flight Systems 1.4.1 — Scope and verification

## What materially changed

- **Real aircraft flight dynamics**: `fixed_wing_coefficients` accepts aircraft Mach and
  changes the attached-flow lift slope (Prandtl–Glauert correction bounded to Mach 0.7).
  The calculation is used in the 6-DoF derivative and exposed in live telemetry.
- **Real aircraft/drone wind physics**: opt-in Monin–Obukhov wind surface layer
  (neutral/stable/unstable) drives air-relative velocity, dynamic pressure and
  flight forces. This can be activated in Engineering Studio using the new
  *ATTIVA VENTO NELLA MISSIONE* button (for AEREO or DRONE), or via POST /reset.
- **Rocket propulsion**: actual pressure-corrected nozzle thrust was already
  integrated; now the same physical mass flow, ambient pressure correction and
  effective specific impulse are reported by the live propulsion telemetry.
  This does not imply turbopump chemistry or a new engine cycle in flight.
- **Engineering Studio**: 18 design solvers, read-only mission-snapshot analyses,
  and explicit provenance/coupling flags. Only the new wind law is the very
  same model used in both the independent analysis and the live plant.
- **Visible version**: 1.4.1 in the HTML header, browser title, API and PWA cache,
  not a CSS pseudo-element claiming a different version.
- **Graphics**: restrained WebGL2 lighting, softer sky exposure/haze, clearer
  Flight Systems theme, better-readable cards and engineering actions.

## What remains modeled at reduced order (not equivalent to certified fidelity)

CFD/RANS aero and experimental coefficient identification, detailed rocket
thermochemistry/turbomachinery, atmosphere site weather assimilation, SPICE
precision ephemerides, nonlinear proximity/docking/contact, full 3D structural
FEA and aeroelasticity, 3D DEM-guided EDL, power electronics/cell aging,
RF fading and coding, and real-perception robotics/SLAM. These require real
hardware/datasets and dedicated validation; we intentionally do not call them
full-fidelity on the basis of these changes.

## API example

POST /api/v1/reset with:

```json
{"vehicle":"aircraft","scenario":"mission","surface_layer_wind":{
  "reference_wind_ned_m_s":[8,0,0],
  "reference_height_m":10,
  "roughness_length_m":0.03,
  "boundary_layer_height_m":100,
  "stability_length_m":null
}}
```

The simulated altitude is clamped to the specified model top for the
horizontal mean wind; Dryden turbulence can still be superimposed.

## Verification executed in this release environment

- `python -m unittest discover -s tools -p 'test_*.py' -v`: **30/30 PASS**
- JavaScript syntax: `node --check` on `app.js`, `engineering-studio.js`,
  `browser-engine-worker.js`, `service-worker.js`: **PASS**
- Local HTTP regression tests: **PASS** (temporary loopback server).
- Visual browser/WebGL smoke test: **NOT VERIFIED**; automated Chromium
  navigation to local addresses returned `ERR_BLOCKED_BY_ADMINISTRATOR`.
- GitHub Pages deploy: **NOT PERFORMED**; requires push from the user's local repo.

Version 1.4.1 is in the literal HTML header, Python package version, both
space/atmosphere telemetry state paths, service worker cache and manifest.
