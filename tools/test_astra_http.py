#!/usr/bin/env python3
"""ASTRA HTTP API smoke test. Designed for the original Python server (not GitHub Pages).

Read-only by default. Run with --simulate to reset/launch/step the selected server.
"""
import argparse
import json
import math
import sys

try:
    from astra.client import AstraClient
except ImportError:
    sys.exit(
        "SDK missing. Activate your virtual environment, then install "
        "astra_simulator_client-1.3.0-py3-none-any.whl with: "
        "python -m pip install /path/to/astra_simulator_client-1.3.0-py3-none-any.whl"
    )


def brief(value, limit=550):
    s = json.dumps(value, ensure_ascii=False, indent=2)
    return s if len(s) < limit else s[:limit] + "\n... (truncated)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765",
                        help="Base URL of original ASTRA Python HTTP server")
    parser.add_argument("--simulate", action="store_true",
                        help="WARNING: resets/launches and modifies simulation state")
    parser.add_argument("--steps", type=int, default=20, help="Simulation steps (with --simulate)")
    args = parser.parse_args()
    if "github.io" in args.url.lower():
        sys.exit("GitHub Pages has no HTTP simulation API. Use the in-browser api-test.html instead.")
    sim = AstraClient(args.url, timeout_s=30)
    try:
        print(f"[1/3] Connecting to {args.url}...")
        status = sim.status()
        assert isinstance(status, dict), "Invalid /status response"
        print("PASS /api/v1/status:", brief(status))

        models = sim.models()
        assert isinstance(models, dict), "Invalid /models response"
        print("[2/3] PASS /api/v1/models: top-level keys:", list(models)[:15])

        state = sim.state()
        assert isinstance(state, dict) and "time_s" in state, "Invalid /state response"
        print("[3/3] PASS /api/v1/state:",
              {key: state.get(key) for key in ("vehicle", "phase", "time_s", "altitude_m")})

        if args.simulate:
            print("\nSIMULATION TEST (this modifies server state):")
            before = sim.reset(vehicle="space", scenario="mission")
            sim.launch()
            previous = before["time_s"]
            for i in range(max(1, args.steps)):
                data = sim.step(0.5)
                t = data["time_s"]
                assert math.isfinite(t) and t > previous, f"Time did not advance on step {i + 1}"
                previous = t
            print(f"PASS simulated {max(1, args.steps)} steps. ",
                  f"t={data['time_s']:.2f}s, altitude={data['altitude_m']:.2f}m, ",
                  f"phase={data['phase']}")
        else:
            print("\nRead-only test complete. Add --simulate to test launch and time stepping.")
        print("\nALL TESTS PASSED")
    except (AssertionError, OSError, TimeoutError, ValueError, RuntimeError) as error:
        print("\nTEST FAILED:", error, file=sys.stderr)
        print("Check the original Python server, its URL, and that the SDK is installed in this environment.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
