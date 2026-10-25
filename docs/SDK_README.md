# ASTRA Python SDK — Local HTTP API (Engineering 1.4)

[Main README](../README.md) · [API tests](API_TESTING.md) · [Validation and limitations](../RELEASE-VALIDATION.md)

## Architecture

ASTRA on GitHub Pages runs Pyodide inside the browser and **does not provide a public Python HTTP API**. For external Python GNC scripts, run `python server.py --open` from the repository root and connect `AstraClient` to `http://127.0.0.1:8765`.

The local server and the local 3D viewer share the *same* Python simulation instance. The Python client advances time using `step()`, while the viewer reads `state()` without integrating a second simulation.

## Quick start

Open a first terminal in the project folder:

```bash
python server.py --open
```

Open a second terminal, also in the project root:

```bash
python tools/test_astra_http.py --simulate --steps 30
python examples/gnc_demo.py
```

The GNC example controls rocket throttle based on dynamic pressure. It is an educational P-controller, not a flight-certified 6-DoF controller. Do not run the automatic API test and GNC demo simultaneously; both modify mission state.

## Python example

```python
from astra.client import AstraClient

sim = AstraClient('http://127.0.0.1:8765')
print(sim.status())
sim.reset(vehicle='space', scenario='mission')
sim.launch()
for _ in range(30):
    sim.command(mode='python', throttle_pct=85)
    state = sim.step(0.1)
    print(state['time_s'], state['altitude_m'])
```

## Engineering Studio API

18 solvers are registered in the local backend:

```python
print(sim.engineering_solvers())
print(sim.engineering('aero_envelope'))
report = sim.engineering_live('aero_envelope')
print(report['mission_context'])
```

The `engineering_live()` endpoint extracts suitable parameters from the current mission and executes the requested engineering analysis. It reports source fields and applicability. **It does not force-couple all independent solvers into flight dynamics**. In particular FEM, radio links, thermal design, EDL studies and trajectory design remain engineering analyses unless a separately validated physical coupling is implemented.

## Available methods

`status()`, `models()`, `state()`, `reset()`, `launch()`, `command()`, `step()`, `stage()`, `engineering()`, `engineering_live()`, `engineering_solvers()`, `vehicle_parts()`, `inject_fault()`, `clear_faults()`.

## Troubleshooting

- `Connection refused`: Start `python server.py` and keep its terminal open.
- `No module named browser_bridge`: Run from the directory containing `server.py` and `browser_bridge.py`.
- `No module named tools`: Execute tests from the repository root, not `~`.
- `No module named astra.__main__`: This project uses `python server.py`, not `python -m astra`.
- No vehicle movement: Open the **local** viewer at `http://127.0.0.1:8765`, then run the GNC demo in the second terminal. Avoid pressing Reset during externally controlled flight.
- Port busy: `python server.py --port 8877 --open` and `python examples/gnc_demo.py --url http://127.0.0.1:8877`.

The development server binds `127.0.0.1` and has no authentication. Do not expose it to the public Internet. Models are intended for engineering education, not safety-critical deployment.
