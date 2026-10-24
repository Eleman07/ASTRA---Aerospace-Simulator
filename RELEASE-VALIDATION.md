# ASTRA 1.0 · Release verification and engineering scope

**Release date:** 2026-10-24

## Scope delivered

- Preserved the existing browser-based 3D spacecraft, aircraft and UAV simulator, its Python standard-library flight engine, Python/MATLAB REST clients, asset catalog, mission recorder, mission scripting, GNC, atmospheric physics and robustness/convergence/FDIR features.
- Added **Engineering Studio**, seven local engineering solvers, a browser laboratory with parameter inputs and result charts, SI result exports, REST endpoints, Python/MATLAB client functions and a working Python example.
- Added an adaptive Dormand–Prince RK5(4) orbital study with J₂, optional COESA76 drag and fixed-direction inertial thrust. Integration respects a minimum dry-mass threshold, terminates on propellant exhaustion and approximates the descending 80 km entry event by root finding in the position interpolant.
- Added standalone FEM cantilever bending, fully implicit finite-volume thermal conduction with surface radiation, nonlinear aircraft attached-flow trim, ideal Laval nozzle flow with a supersonic Mach root, battery/solar eclipse power analysis and radio link-budget estimation.
- Kept all new analyses **isolated** from the live mission. Their assumptions are explicit in returned results and in `ENGINEERING-STUDIO.md`.

## Verification performed in this environment

Environment: Python 3.13.5, pytest 9.0.2 and Node.js 22.16.0 on Linux. All source and distribution JavaScript modules were syntax checked with Node, and core Python modules compiled. Server started successfully using `python -m astra --port 18765`; `/api/v1/status` and `/api/v1/engineering` responded with valid JSON. Example beam calculations returned expected values. Separate direct calls exercised all seven engineering solvers, and a seeded 210-case sweep (30 variations per solver) produced no unexpected exceptions or invalid JSON.

Focused passing regression test groups included:

- `test_engineering_studio.py`, `test_web_build.py`, `test_api_client.py`: 27 tests passed, including closed-form cantilever FEM, energy-conserving two-body orbit, J₂ perturbation, event handling and fuel exhaustion, thermal equilibrium, inverse-square radio loss and API error validation.
- Selected atmosphere, aero, propulsion, RK4, Kalman and LQR regression tests in `test_physics_models.py`: 23 passed.
- Selected multirotor propulsion and specific-force telemetry tests: 12 passed.
- `test_space_rendering_assets.py`, `test_scene_physics_alignment.py`, `test_sensor_based_guidance.py`: 8 passed.
- Seven navigation, turbulence, wind and watchdog suites: 32 passed.
- `test_matlab_client_contract.py`, `test_visual_catalog_assets.py`: 9 passed.

All previous tests included in these passing groups retained their expected behavior. Several exhaustive trajectory, Monte Carlo, convergence and long-mission pytest runs exceeded the execution timeout used in this environment. This does **not** establish that those tests failed, but they were **not fully verified**. Chromium headless also timed out without producing a visual preview in this environment. ASTRA's WebGL appearance and performance on target GPUs or mobile browsers were consequently not independently confirmed here. MATLAB/Simulink execution was not verified with proprietary MATLAB installed.

## Known engineering boundaries / release caveats

**Not a verified bug-free, production-certifiable flight simulator.** There is no scientific basis to promise zero bugs in such a large system after finite testing. The 3D rendering was inherited from the input archive; no comprehensive KSP-like engine rewrite was attempted. Fidelity of vehicle behavior depends on default or user-supplied coefficients; historical planetary trajectories use approximate ephemerides; stand-alone engineering tools are **not coupled** to flight state or real aircraft material geometry. The rendering uses an illustrative terrain model without collision/obstacle physics. See original `README.md`, `ENGINEERING-STUDIO.md`, and `ASSET-CREDITS.md`.

To reproduce the tests after unzipping:

```bash
python -m pytest -q tests/test_engineering_studio.py tests/test_web_build.py tests/test_api_client.py
python -m astra
```

Open <http://127.0.0.1:8765/>. On Windows, use `py -m astra` instead of `python -m astra` if appropriate. Run `python examples/python_engineering_studio.py` in another terminal after the server has started.


## ASTRA 1.1 cockpit / language follow-up (24 October 2026)

- Visual orientation for aircraft and UAV: local NED-to-WebGL attitude transform, pitch and bank signs and animation sample paths were corrected in the preceding 1.1 worktree; test `tests/test_browser_pilot.mjs` covers rotations.
- Input: keyboard and gamepad dead zones, joystick pilot setpoint mapping and manual heading setpoints are covered by corresponding JS/Python tests. Integrated hardware gamepad and live GPU rendering have not been certified.
- Play mode: visible floating joysticks; pilot can select autonomous control or resume manual control without losing cockpit widgets.
- Instrumentation: flight PFD, controllable technical visibility, responsive HUD layout and six primary UI languages. Some specialist prose remains untranslated.
- API PDFs: generated from inspected Python, MATLAB and Simulink methods, checked for readable first and last pages.
- Browser Playwright navigation to the local running server was restricted by the execution environment; DOM/CSS visual smoke tests used an isolated `set_content` page and therefore do not validate actual WebGL assets. No KSP 1/2 visual or functional parity is claimed.


## ASTRA 1.2.2 nebula update
- Replaced the space nebula textures with user-provided reference image variants (1k/2k/4k).
- Stored the original reference under `assets/source/user-nebula-reference.jpg`.
- Bumped service-worker cache to force refresh of space background assets.


## ASTRA 1.2.3 space background rendering fix
- The user-provided nebula is now rendered as a cover-style screen-space space background instead of being treated as a full equirectangular sky map.
- Reduced procedural star overlay intensity to avoid clutter and blur.
- Increased default nebula texture selection to 2k on low tier and 4k on balanced/high tier.
