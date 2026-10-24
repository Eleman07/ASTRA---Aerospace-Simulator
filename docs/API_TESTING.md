# ASTRA API — Complete Testing Guide

> **Choose the correct API first.** ASTRA Browser on GitHub Pages hosts a WebGL frontend and a Pyodide engine in a **Web Worker**; it has **no public HTTP simulation endpoint**. The Python `AstraClient` wheel talks to the **original ASTRA Python HTTP server**, not to GitHub Pages.

![Browser-local API architecture](images/browser-api-architecture.png)

## A. Test the live browser API (GitHub Pages)

### A1. Start with diagnostics

1. Open [ASTRA diagnostics](https://eleman07.github.io/ASTRA---Aerospace-Simulator/diagnostics.html).
2. Select **Verify files and engine startup** (*Verifica file e avvio motore*).
3. A passing run displays `PYODIDE READY` and identifies the Python runtime version.
4. If startup fails, read the exact error and open [GitHub Actions](https://github.com/Eleman07/ASTRA---Aerospace-Simulator/actions). Try **Clear old ASTRA cache** if an older service worker was installed.

### A2. Run automatic API checks without writing code

After adding this documentation kit to the repository and waiting for the GitHub Pages deployment to succeed, open:

**[Browser API Test Console](https://eleman07.github.io/ASTRA---Aerospace-Simulator/api-test.html)**

Click:

1. **Test status / models / state**: asserts the engine identifies itself as `browser-pyodide`, loads the model catalog, and returns a numeric mission clock.
2. **Run rocket launch API test**: creates a **new, isolated** suborbital rocket simulation, calls `/reset` and `/launch`, then propagates 30 × 0.5 s using `/step`.
3. **Download JSON report**: saves the tests and telemetry from the isolated page.

**Expected:** `PASS · READ API` and `PASS · ROCKET SIMULATION`, with `time_s` increasing and telemetry samples returned. A successful HTTP 200 from the page itself is *not* proof that the physics engine works; the Python worker must finish these checks.

> The test page creates its own Web Worker. It does **not** synchronize with or animate a second ASTRA tab. To see a rocket move, start the mission in the main simulator UI.

### A3. Test manually from the browser console (optional)

Open [ASTRA](https://eleman07.github.io/ASTRA---Aerospace-Simulator/), press **F12 → Console**, and run:

```javascript
const { browserApi, browserReady } = await import('./browser-api.js');
await browserReady();
const status = await browserApi('/status');
const models = await browserApi('/models');
const state = await browserApi('/state');
console.log(status, Object.keys(models), state);
```

This uses the local Worker module, which `app.js` also imports. **Do not paste unknown code into a browser console.** To avoid disturbing the main simulation, prefer the dedicated `api-test.html` page.

### Browser-local routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/status` | Engine version and mode (`browser-pyodide`) |
| GET | `/state` | Current state/telemetry |
| GET | `/models` | Vehicle model catalog |
| POST | `/reset` | Create/reset local mission |
| POST | `/launch` | Start mission |
| POST | `/step` | Advance physics by `dt_s` |
| POST | `/command` | Send GNC / manual commands |
| GET/POST | `/engineering` | List/run engineering analyses |

Internally, these routes are messages handled by `browser_bridge.py`; **they are not network URLs**. `curl https://eleman07.github.io/ASTRA---Aerospace-Simulator/api/v1/status` will not contact the physics engine.

## B. Test the original Python HTTP API with the SDK

**Requirements:** Ubuntu/Windows/macOS, Python 3.10+, the **original ASTRA 1.3 package (including `astra/server.py` and `astra/__main__.py`)**, and the downloadable SDK wheel.

### B1. Start the original server

Terminal **A**, from the extracted **original full ASTRA** project root (not the static Browser Edition):

```bash
python3 -m astra --host 127.0.0.1 --port 8765
```

Keep the terminal running. Then in Terminal **B**:

```bash
curl http://127.0.0.1:8765/api/v1/status
```

A JSON object with the ASTRA version and capabilities is expected.

### B2. Install the SDK into a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Ubuntu/macOS
python -m pip install ./downloads/astra_simulator_client-1.3.0-py3-none-any.whl
python -c 'from astra.client import AstraClient; print("SDK import OK")'
```

On Windows use `.venv\Scripts\activate` in Command Prompt or `.venv\Scripts\Activate.ps1` in PowerShell. Change the wheel path to the folder where you downloaded it.

### B3. Run the automated Python test

From your checkout containing `tools/test_astra_http.py`:

```bash
python tools/test_astra_http.py --url http://127.0.0.1:8765
```

This read-only test calls `/status`, `/models`, `/state`. Expected final line: `ALL TESTS PASSED`.

To **reset the running simulation** and check the rocket launch and time stepping:

```bash
python tools/test_astra_http.py --url http://127.0.0.1:8765 --simulate --steps 30
```

Expected: numeric altitude and time, increasing `time_s`, and `ALL TESTS PASSED`.

### B4. Minimal SDK example

```python
from astra.client import AstraClient

sim = AstraClient('http://127.0.0.1:8765')
print(sim.status())
print(sim.models().keys())

sim.reset(vehicle='space', scenario='mission')
sim.launch()
for _ in range(20):
    state = sim.step(0.5)
    print(state['time_s'], state['altitude_m'])
```

**Important:** This is a command-and-control API, not an HTTP video stream. The HTTP server state can be shared by multiple clients. The existing ASTRA 1.3 server does not provide per-user authenticated sessions; never expose it openly to the public Internet without hardening.

## C. Common errors

| Symptom | Likely cause | Fix |
|---|---|---|
| `NetworkError ... importScripts()` | Stale pre-1.3.3 Worker or Pyodide mismatch | Deploy the ES-module Worker and clear service worker caches |
| `PYODIDE FAILED` | Missing or blocked Pyodide WASM assets | Check diagnostics and GitHub Actions deploy log |
| Browser launch fails, GitHub Actions green | Browser runtime not verified by build | Run `api-test.html`, inspect exception |
| `AstraClient` cannot connect to `github.io` | Browser Edition has no HTTP API | Use in-browser API test, or launch original Python server |
| `ModuleNotFoundError: No module named 'astra'` | SDK installed in a different interpreter | Select `.venv` in VS Code and install with `python -m pip` |
| `Connection refused` on `127.0.0.1:8765` | Original Python HTTP server is not running | Start `python3 -m astra` from original full package |
| Page loads but WebGL is blank | GPU/browser drivers/WebGL or visual assets | Update browser and driver; inspect DevTools Console |

## D. Safety and evidence

- A valid response proves the corresponding path was executed; it does **not** validate engineering accuracy.
- Keep solver assumptions, units, initial conditions, and limitations with any technical result.
- For precision claims, run numerical convergence and validation against appropriate reference cases.
