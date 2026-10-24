#!/usr/bin/env python3
"""ASTRA: simple closed-loop rocket thrust control."""

import argparse
import math
import sys
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from astra.client import AstraClient


def clamp(value, low, high):
    return max(low, min(high, value))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8765"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=600
    )
    args = parser.parse_args()

    sim = AstraClient(args.url)

    print("Connecting to ASTRA...")
    print(sim.status())

    print("\nPreparing launch...")
    sim.reset(vehicle="space", scenario="mission")
    sim.launch()

    target_q = 25000.0   # Pa
    kp = 0.002           # proportional thrust gain
    dt = 0.1             # simulation step, seconds

    print("\nGNC active: dynamic-pressure feedback")
    print("Keep the ASTRA 3D viewer open.")
    print("Press Ctrl+C to stop.\n")

    try:
        for i in range(max(1, args.steps)):
            state = sim.state()

            environment = state.get("environment") or {}
            q = float(
                environment.get("dynamic_pressure_Pa", 0.0)
                or 0.0
            )

            # Navigation: read measured dynamic pressure.
            # Guidance: target a safe dynamic pressure.
            # Control: adjust throttle proportionally.
            error = target_q - q

            throttle = clamp(
                75.0 + kp * error,
                50.0,
                100.0
            )

            if not math.isfinite(throttle):
                raise RuntimeError("Invalid throttle value")

            sim.command(
                mode="python",
                throttle_pct=throttle
            )

            state = sim.step(dt)

            if i % 10 == 0:
                print(
                    f"t={state['time_s']:6.1f} s | "
                    f"altitude={state['altitude_m']:10.1f} m | "
                    f"q={q:9.0f} Pa | "
                    f"throttle={throttle:5.1f}% | "
                    f"phase={state['phase']}",
                    flush=True
                )

            if state.get("phase") in (
                "LANDED", "CRASHED", "ABORTED"
            ):
                print("Mission ended:", state["phase"])
                break

            time.sleep(dt)

    except KeyboardInterrupt:
        print("\nGNC stopped.")

    print("Final state:", sim.state()["phase"])


if __name__ == "__main__":
    main()
