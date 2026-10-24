# ASTRA Engineering Studio · domain-science audit

The existing ASTRA main simulator is a local Python engine with RK4 flight dynamics and an independent WebGL visualization. The Engineering Studio is a set of **seven additional, independently executed, model-based engineering analyses**. It is accessible through the laboratory icon on the left rail or `POST /api/v1/engineering`. Its algorithms DO NOT silently overwrite, tune, or couple to the live mission dynamics. Every solver uses SI units and labels its assumptions. This is educational simulation code, **not** flight-certified analysis or validated high-fidelity CFD/FEM/thermal hardware design.

| Analysis ID | Implemented numerical model | Deliberate limitations |
|---|---|---|
| `orbit` | Adaptive Dormand–Prince embedded RK5(4) Cowell ECI propagation; central Earth, J₂, rotating COESA76 drag, optional constant ECI thrust with mass flow; finite-duration trajectory and local error control | Earth-centered only, no third-body gravity, SRP, actual thrust steering, high-altitude variable atmosphere, attitude, finite fuel tanks or collision with detailed terrain |
| `aircraft_trim` | Bracketed root solve for attached-flow CL at constant speed, angle of bank and density; demand CD from existing fixed-wing polar | Simplified steady-state forces, no propulsion lapse, elevator moments or full 6-DOF trim |
| `propulsion` | 1-D isentropic Laval nozzle, bracketed inversion of supersonic area–Mach relationship, ideal pressure-matched exit-area suggestion | Frozen perfect gas, no shock, chemistry, real exhaust flow or reliable separation model |
| `beam` | Euler–Bernoulli cubic Hermite FEM with consistent point/distributed load vector, pivoted stiffness solve, bending stress and safety factor | 1-D cantilever, linear elastic, rectangular section; no 3-D FEM or vibration modes |
| `thermal` | Transient 1-D implicit finite-volume conduction, nonlinear Newton radiation/convection surface | Homogeneous constant properties and insulated back face; no material ablation or fluid-structure coupling |
| `power` | Orbit-averaged sunlight/eclipse discrete charge balance with battery SoC saturation and charge/discharge efficiencies | Prescribed eclipse fraction, fixed incident angle and load; no electrochemistry or orbital geometry |
| `link` | Friis free-space link, Boltzmann receiver noise, Eb/N₀ margin and Shannon upper bound | No actual modulation, coding, antenna tracking, atmospheric attenuation or packet communication |

## Run the real Python control interface

```bash
python -m astra
```

Open <http://127.0.0.1:8765> in a modern browser. Activate the Engineering Studio icon in the left navigation to run the new analysis tools, or use:

```python
from astra.client import AstraClient
sim = AstraClient()
print(sim.engineering_models())
print(sim.engineering('orbit', initial_altitude_m=400000, duration_s=5400,
                      include_j2=True, include_drag=True))
print(sim.engineering('beam', tip_force_N=-900, elements=24))
print(sim.engineering('thermal', incident_heat_flux_W_m2=20000, duration_s=120))
print(sim.engineering('aircraft_trim', airspeed_m_s=100, altitude_m=1000))
print(sim.engineering('power', solar_array_area_m2=5, battery_capacity_Wh=1400))
print(sim.engineering('link', range_m=400000, frequency_Hz=2.2e9))
print(sim.engineering('propulsion', chamber_pressure_Pa=7e6, expansion_ratio=16))
```

For MATLAB, `sim = astra.AstraClient(); result = sim.engineering("orbit", struct("duration_s", 5400));` after adding `matlab/` to MATLAB's search path. A runnable Python example is in `examples/python_engineering_studio.py`.

## Verification

The new numerical regression checks include beam tip deflection and root reaction against closed-form statics, distributed load against beam theory, two-body orbit closure and energy, sensitivity to J₂ and step tolerance, thermal equilibrium, basic isentropic nozzle response, free-space inverse-square loss, power resource conservation and API error handling. See `tests/test_engineering_studio.py`.

Run the whole regression suite with `python -m pytest -q` if pytest is installed (not required to run ASTRA). A built-in zero-dependency `unittest` runner can run standard-library-compatible tests with `python -m unittest discover -s tests -p 'test_*.py'` (some files rely on pytest imports and may be skipped/fail if it is absent). The new Engineering Studio functions themselves only require the Python standard library.

**Numerical convergence does not establish physical model validity.** Parameter values are reference assumptions, not calibrated aircraft or spacecraft data. None of the analyses is approved for real flight operations, control of physical vehicles, safety-critical use, or structural certification.


## ASTRA 1.2.4: engineering expansion and terrain visibility

Engineering Studio now supports `robotics_route` (deterministic eight-connected A* occupancy-grid planning with no corner cutting) and `planetary_descent` (one-dimensional RK4 variable-mass powered landing with gravity, drag and throttle guidance). Both are independent, parameterized scientific exercises accessed via `POST /api/v1/engineering`; they do **not** steer the active 3-D vehicle. The Engineering Studio Compute action no longer calls `reportValidity()` on a non-form div.

Aircraft rendering uses a 3×3 grid of terrain chunks with eight lower-LOD neighbours surrounding the main tile, plus a longer far clipping range. This improves terrain visibility in flight at altitude. Chunk geometry is approximate with no georeferenced imagery, buildings, collision geometry, or DEM.

ASTRA remains a research/educational prototype. The remaining abbreviated disciplines (thermal, propulsion, aerodynamics, planetary ephemerides, structures, systems engineering, etc.) have declared limits and are **not** magically made full fidelity by this release.


## ASTRA 1.3 advanced analyses

The Engineering Studio exposes six additional independent engineering solvers through
`POST /api/v1/engineering`, with SI units and input validation:

- `planetary_landing_6dof`: nonlinear 6-DoF body-to-world quaternion trajectory,
  torque-limited attitude PD, inertia, thrust and finite fuel in a planetary
  constant local frame. Terrain/contact are not yet geometric 3-D models, and this
  study does not drive the playable mission.
- `rocket_cycle`: open gas-generator turbopump/turbine power balance, propellant bleed,
  and effective ideal nozzle specific impulse. Thermochemistry, startup and
  calibrated turbine/pump maps are **not** provided.
- `lifting_line`: Prandtl finite-wing lifting-line collocation with taper, geometric
  washout and spanwise lift/induced-drag distribution. This is **not CFD**.
- `lambert`: configurable two-body zero-revolution 3D Lambert boundary value solver,
  validated against the standalone two-body Kepler propagator. This is not a
  finite-burn N-body mission trajectory.
- `orbit_eclipse_power`: Earth conical umbra geometry for a circular orbit with
  ECI-fixed array incidence, charging/discharging and battery SOC. No penumbra,
  time-varying sun, attitude coupling or electrochemical network.
- `radio_link`: dish pointing loss, user-provided atmospheric specific attenuation,
  BPSK AWGN bit/packet error estimates, light-time and serialization time.
  No real-time packet loss or propagation through observed weather.

Live requirement checks are separate from the isolated studies:

`POST /api/v1/requirements/verify`

```json
{"requirements":[
  {"id":"ALT-001","field":"altitude_m","operator":">=","value":0,"unit":"m"},
  {"id":"SPD-002","field":"speed_m_s","operator":"<=","value":15000,"unit":"m/s"}
]}
```

The response preserves the field path, measured value, threshold, unit, timestamp,
PASS/FAIL/NOT_EVALUATED classification and tally. This is a snapshot predicate
check, **not** formal V&V or airworthiness certification. Engineering Studio includes
an editable requirement JSON panel connected to the current mission's state.

Some catalogue entries remain `MODELLO SEMPLIFICATO` for good scientific reasons:
validating a physical model requires actual vehicle properties, model coupling,
uncertainty quantification and test data. Labelling an isolated calculation as
fully modelled in the real-time flight engine would be misleading.
