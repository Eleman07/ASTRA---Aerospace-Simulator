# ASTRA Python SDK

**Local HTTP API for aerospace simulation and experimental GNC.**

[Main README](../README.md) ·
[Live Browser Simulator](https://eleman07.github.io/ASTRA---Aerospace-Simulator/) ·
[API Testing Guide](API_TESTING.md)

## 1. Overview

ASTRA provides two execution modes:

| Mode | Execution | External Python SDK |
|---|---|---|
| Browser Edition | Pyodide/WebAssembly in a browser Worker | Not supported |
| Local HTTP Edition | CPython on your computer | Supported |

The local edition runs the ASTRA Python simulation engine
and serves the 3D viewer from the same HTTP server.

The Python SDK connects using HTTP/JSON.

The local API is a development interface intended for
educational experiments, not safety-critical applications.

## 2. Requirements

- Python 3.10 or newer
- A current web browser
- The ASTRA source repository
- No additional Python dependencies

## 3. Start the local simulator

Clone the repository:

```bash
git clone https://github.com/Eleman07/ASTRA---Aerospace-Simulator.git
cd ASTRA---Aerospace-Simulator
```

Launch the local server:

```bash
python server.py --open
```

Open:

http://127.0.0.1:8765

The Python HTTP API is available at:

http://127.0.0.1:8765/api/v1/status

Keep the server terminal running.

## 4. Test the API

In a second terminal, from the repository root:

```bash
curl http://127.0.0.1:8765/api/v1/status
```

Then run:

```bash
python -m tools.test_astra_http --simulate --steps 30
```

The test reads status, models and state, then launches and
integrates the spacecraft simulation.

## 5. Python SDK quick start

The client implementation lives in `astra/client.py`.

Run Python from the repository root:

```python
from astra.client import AstraClient

sim = AstraClient("http://127.0.0.1:8765")

print(sim.status())
print(sim.models())

sim.reset(vehicle="space", scenario="mission")
sim.launch()

for _ in range(20):
    state = sim.step(0.1)
    print(state["time_s"], state["altitude_m"])
```

The SDK has no third-party dependencies.

For projects outside this repository, install or package
the SDK separately, or add the repository root to PYTHONPATH.

## 6. GNC demonstration with live 3D visualization

Start the local server:

```bash
python server.py --open
```

Wait until the 3D viewer loads and select the Space environment.

In a second terminal:

```bash
python examples/gnc_demo.py
```

The demo starts the launch mission and applies a basic
closed-loop throttle controller using dynamic pressure:

q = 0.5 * rho * V^2

The controller aims to reduce excessive dynamic pressure
by adjusting the commanded throttle.

The Python script advances the physical simulation,
while the viewer displays the same simulation state.

Do not start another simulation integration loop while
the GNC demo is running.

This is an educational throttle-control example, not a
validated full six-degree-of-freedom GNC controller.

## 7. Supported API methods

| Python method | HTTP endpoint | Purpose |
|---|---|---|
| `sim.status()` | GET `/api/v1/status` | Version and engine status |
| `sim.models()` | GET `/api/v1/models` | Vehicle model catalog |
| `sim.state()` | GET `/api/v1/state` | Current telemetry |
| `sim.reset(...)` | POST `/api/v1/reset` | Reset mission |
| `sim.launch()` | POST `/api/v1/launch` | Launch mission |
| `sim.command(...)` | POST `/api/v1/command` | Send vehicle commands |
| `sim.step(dt_s)` | POST `/api/v1/step` | Advance physics |
| `sim.stage()` | POST `/api/v1/stage` | Stage separation |
| `sim.engineering(...)` | POST `/api/v1/engineering` | Engineering analysis |
| `sim.inject_fault(...)` | POST `/api/v1/fault` | Fault injection |
| `sim.clear_faults()` | POST `/api/v1/fault/clear` | Clear faults |

See `browser_bridge.py` for the current dispatcher contract.

## 8. Command example

```python
from astra.client import AstraClient

sim = AstraClient()

sim.reset(vehicle="space", scenario="mission")
sim.launch()

sim.command(
    mode="python",
    throttle_pct=85.0
)

for _ in range(100):
    state = sim.step(0.1)

print("Altitude:", state["altitude_m"])
print("Phase:", state["phase"])
```

For externally driven missions, issue commands regularly
to maintain the Python-control watchdog heartbeat.

## 9. Troubleshooting

### Connection refused

The HTTP server is not running or is listening on a
different port. Run `python server.py --open`.

### No module named `astra.__main__`

This repository does not use `python -m astra` to start
the HTTP server. Run `python server.py` instead.

### No module named `browser_bridge`

Run the server from the repository root and verify that
`browser_bridge.py` exists.

### The browser is not moving

Open the local address, not GitHub Pages:

http://127.0.0.1:8765

Wait for the scene to load, then run the Python demo.
Refresh the local viewer if a previous service worker
or cached script is still active.

### GitHub Pages API connection fails

GitHub Pages cannot run the Python HTTP server.
The hosted Browser Edition uses an independent on-device
Pyodide Worker.

### Port already in use

Stop the previous process or start with another port:

```bash
python server.py --port 8877 --open
python examples/gnc_demo.py --url http://127.0.0.1:8877
```

## 10. Security and limitations

The server listens on `127.0.0.1` by default and has
no authentication. Do not expose it to the public Internet.

The browser and Python client share a single simulation
state. Concurrent reset, launch or integration commands
from multiple clients can interrupt a mission.

ASTRA is intended for learning, prototyping and experiments,
not certified flight simulation.
