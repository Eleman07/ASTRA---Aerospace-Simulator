# ASTRA 1.3 — model-readiness matrix

**Interpretation:** The user requested unsimplified scientific models, not new labels. An algorithm is not automatically a high-fidelity *vehicle* model. We distinguish mathematical sophistication from accurate, calibrated, integrated simulation. Every module below is available locally; new solvers are stand-alone unless marked live.

| Domain | Implemented in ASTRA 1.3 | Still needed before claiming high-fidelity full mission simulation |
| --- | --- | --- |
| Propulsion | Ideal choked nozzle + new open gas-generator turbopump/turbine energetic and propellant-flow balance; engine thrust and fuel in the mission | Equilibrium/finite-rate combustion, temperature-dependent gas chemistry, performance maps and engine thermal/stability dynamics coupled to flight |
| Aerodynamics and stability | 6-DoF aerodynamic coefficients, trim solver and new lifting-line Fourier method computing spanwise circulation, lift and induced drag | Calibrated stability derivatives, dynamic stall, Navier–Stokes/RANS CFD with turbulence closures, mesh/grid-convergence and aeroelastic coupling |
| Planet/moon ephemerides | JPL fitted mean planetary elements (1800–2050) and Moon Kepler approximation; Sun+8 planet Cowell transfer trajectory | JPL SPICE kernel datasets, time scales/frames, all moons, perturbations, ephemeris accuracy tests |
| Mission trajectory design | Lambert-seeded planetary transfer with differential correction and Cowell Sun+8 planets; new configurable 3D Lambert BVP analysis | Mission-wide finite-burn targeting, optimized multi-arc trajectory with constraints, coupled launch/re-entry/landing |
| Rendezvous/proximity | CW/RTN control and RCS; synthetic relative navigation telemetry | Nonlinear 6-DoF proximity guidance, independent sensor models, collision/keepout constraints, docking contact, Monte Carlo validation |
| Structures and loads | Hermite Euler–Bernoulli 1D FEM with loads, stress and margins; live q and load-factor telemetry | Calibrated 3D structural FEM (shell/solid), buckling, modal and forced vibration, fatigue, damage, transient CFD loading |
| Atmosphere, weather and turbulence | COESA76, altitude-dependent mean wind, seedable Dryden spectral turbulence | Validated site-specific weather reanalysis/forecast ingestion and uncertainty, spatial turbulence, precipitation and icing physics |
| Electrical and energy | Battery and power budget in missions; new circular-orbit Earth conical umbra, incidence and SOC model | Coupled solar pointing, penumbra, power-electronics bus network, cell chemistry, temperature and aging models |
| Communication and links | Standard Friis/thermal/Shannon budget plus new antenna pointing error, user-specified atmospheric attenuation, BPSK BER/packet loss and latency | Actual RF channel/coding/modulation, Earth geography, radio network/scheduling, weather-dependent attenuation, live packet-link effects |
| Robotics and autonomy | Mission UAV GNC, offline A* planner with obstacle grid | SLAM with physically generated measurements, mapping uncertainty, 3D occupancy, path tracking, hazard avoidance on live flight |
| Launch vehicles and staging | Stageable vehicle mass/thrust, ideal delta-v, orbit launch-return scenario, GNC | Validated engine cycle/propellant dynamics, slosh/flex, vibroacoustics, optimal ascent constraints and verified stage separation physics |
| Planetary descent and landing | Existing 1D descent plus new nonlinear rigid-body 6-DoF quaternion RK4 study (3D position/velocity, body rates, torques, mass, guidance) | Coupled playable planetary mission, body ephemerides, DEM terrain/contact, sensors, plume-surface interaction and validated hazard-receding-horizon guidance |
| Requirements, systems and verification | **Live integration**: new predicate-based requirement checks against the actual ASTRA state, with field source, timestamp, PASS/FAIL/NOT_EVALUATED; existing Monte Carlo and convergence studies | Requirements database, versioning, requirements-to-tests traceability, continuous temporal specifications, calibrated uncertainties and certification |

## What changed in this release

Six new computational studies (`planetary_landing_6dof`, `rocket_cycle`, `lifting_line`, `lambert`, `orbit_eclipse_power`, `radio_link`) extend the nine existing Engineering Studio solvers. The mission state is now also consumed by `POST /api/v1/requirements/verify`.

These enhancements are **not** a claim of complete full-fidelity CFD, chemistry, structural mechanics, advanced EDL, independent SLAM or an aerospace-certified digital twin. The existing 6-DoF flight stack, previous graphics, Python/MATLAB APIs and vehicle catalog are preserved. The 1.3 improvement is measured by actual code paths and numerical tests rather than relabeling the earlier `MODELLO SEMPLIFICATO` statuses as `COMPLETO`.
