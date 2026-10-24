"""Reproducible Monte Carlo campaigns for bounded ASTRA reference models."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import random
from typing import Any

from .engine import SimulationEngine
from .wind import validate_wind_profile


def _bounded_normal(rng: random.Random, sigma: float) -> float:
    """Draw a normal perturbation truncated to a documented three-sigma range."""
    return max(-3.0 * sigma, min(3.0 * sigma, rng.gauss(0.0, sigma)))


def _bounded_wind_vector(vector: list[float], maximum_speed: float) -> list[float]:
    """Project wind into the speed envelope without rounding beyond its edge."""
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= maximum_speed:
        return vector
    # Eight machine epsilons leave room for the three scaled components and
    # their norm to round, while changing a 60 m/s limit by < 1.1e-13 m/s.
    interior_speed = maximum_speed * (1.0 - 8.0 * math.ulp(1.0))
    # Normalize by the largest component first so even finite, very large
    # API inputs cannot overflow the norm or collapse to a calm-wind vector.
    largest_component = max(abs(value) for value in vector)
    direction = [value / largest_component for value in vector]
    scale = interior_speed / math.sqrt(sum(value * value for value in direction))
    return [value * scale for value in direction]


def _apply_perturbations(engine: SimulationEngine, values: dict[str, float]) -> None:
    mass = values["mass_factor"]
    thrust = values["thrust_factor"]
    drag = values["drag_factor"]
    if engine.vehicle == "space":
        engine.mass_dry_kg *= mass
        engine.mass_kg = (engine.mass_dry_kg + engine.propellant_kg +
                          engine.acs_propellant_kg)
        for stage in engine.stage_specs:
            stage["dry_mass_kg"] *= mass
            stage["thrust_vacuum_N"] *= thrust
        engine._activate_stage()
        for key in ("Cd", "aeroshell_Cd", "drogue_Cd", "parachute_Cd"):
            engine.launch_vehicle[key] *= drag
        return

    if engine.vehicle == "aircraft":
        engine.mass_dry_kg *= mass
        engine.mass_kg = engine.mass_dry_kg + engine.propellant_kg
        engine.flight[-2] = engine.mass_kg
        engine.max_thrust_N *= thrust
        engine.aero["CL0"] *= values["lift_factor"]
        engine.aero["CLalpha_rad"] *= values["lift_factor"]
        engine.aero["CD0"] *= drag
        engine.aero["induced_drag_k"] *= drag
        return

    engine.mass_kg *= mass
    engine.mass_dry_kg *= mass
    engine.flight[-2] = engine.mass_kg
    engine.max_thrust_N *= thrust
    engine.drone["max_thrust_N"] *= thrust
    engine.drone["reference_mass_kg"] = engine.mass_kg
    for key in ("Ixx_kgm2", "Iyy_kgm2", "Izz_kgm2"):
        engine.drone[key] *= mass
    engine.battery_capacity_Wh *= values["battery_factor"]
    engine.battery_energy_Wh *= values["battery_factor"]
    engine.drone["battery_capacity_Wh"] = engine.battery_capacity_Wh
    engine.drone["body_drag_area_m2"] *= drag


def _wilson_interval(successes: int, count: int) -> list[float]:
    if not count:
        return [0.0, 1.0]
    z = 1.959963984540054
    p = successes / count
    denominator = 1.0 + z * z / count
    center = (p + z * z / (2.0 * count)) / denominator
    half_width = (z * math.sqrt(p * (1.0 - p) / count +
                                z * z / (4.0 * count * count)) / denominator)
    return [max(0.0, center - half_width), min(1.0, center + half_width)]


def _percentiles(values: list[float]) -> dict[str, float] | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None

    def at(fraction: float) -> float:
        location = (len(finite) - 1) * fraction
        low = math.floor(location)
        high = math.ceil(location)
        return finite[low] + (finite[high] - finite[low]) * (location - low)

    return {"p05": at(0.05), "p50": at(0.5), "p95": at(0.95),
            "minimum": finite[0], "maximum": finite[-1]}


def run_robustness_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    """Run a reproducible bounded uncertainty ensemble without touching the live engine."""
    vehicle = payload.get("vehicle", "space")
    model_id = payload.get("model_id")
    scenario = payload.get("scenario", "mission")
    count = payload.get("samples", 8)
    seed = payload.get("seed", 20261023)
    custom_design = payload.get("custom_design")
    baseline_wind = payload.get("baseline_wind_ned_m_s", [0.0, 0.0, 0.0])
    baseline_wind_profile = validate_wind_profile(
        payload.get("baseline_wind_profile_ned_m_s"), vehicle)
    baseline_turbulence = payload.get("baseline_turbulence")
    if vehicle not in {"space", "aircraft", "drone"}:
        raise ValueError("vehicle must be space, aircraft or drone")
    if scenario not in {"mission", "leo-return"}:
        raise ValueError("Monte Carlo supports launch/recovery missions, not orbital rendezvous")
    if scenario == "leo-return" and (vehicle != "space" or not isinstance(custom_design, dict)):
        raise ValueError("leo-return Monte Carlo requires the selected custom spacecraft stack")
    sample_limit = 4 if scenario == "leo-return" else 24
    if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= sample_limit:
        raise ValueError(f"samples must be an integer from 2 to {sample_limit} for this profile")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer from 0 to 4294967295")
    if custom_design is not None and (vehicle != "space" or scenario not in {"mission", "leo-return"}):
        raise ValueError("custom_design is available only for spacecraft launch missions")
    if (not isinstance(baseline_wind, list) or len(baseline_wind) != 3 or
            any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) for value in baseline_wind)):
        raise ValueError("baseline_wind_ned_m_s must contain three finite values")
    if vehicle == "space" and any(float(value) != 0.0 for value in baseline_wind):
        raise ValueError("baseline wind is available only for aircraft and drones")
    if baseline_wind_profile is not None and any(
            float(value) != 0.0 for value in baseline_wind):
        raise ValueError(
            "baseline_wind_profile_ned_m_s replaces baseline_wind_ned_m_s")

    # One-sigma spreads are explicit engineering study assumptions, not measured
    # catalog tolerances. Samples are truncated at three sigma for bounded runs.
    sigmas = {"mass_fraction_1sigma": 0.015,
              "thrust_fraction_1sigma": 0.02,
              "drag_fraction_1sigma": 0.12,
              "lift_fraction_1sigma": 0.03 if vehicle == "aircraft" else 0.0,
              "battery_fraction_1sigma": 0.06 if vehicle == "drone" else 0.0,
              "horizontal_wind_m_s_1sigma": 0.0 if vehicle == "space" else
              (1.5 if vehicle == "drone" else 2.5)}
    rng = random.Random(seed)
    horizon_s = {"space": 14_000.0 if scenario == "leo-return" else 4_000.0,
                 "aircraft": 1_200.0, "drone": 240.0}[vehicle]
    runs = []
    for sample_id in range(count):
        mass_delta = _bounded_normal(rng, sigmas["mass_fraction_1sigma"])
        thrust_delta = _bounded_normal(rng, sigmas["thrust_fraction_1sigma"])
        drag_delta = _bounded_normal(rng, sigmas["drag_fraction_1sigma"])
        values = {
            "mass_factor": 1.0 + mass_delta,
            "thrust_factor": 1.0 + thrust_delta,
            "drag_factor": 1.0 + drag_delta,
            "lift_factor": 1.0 + _bounded_normal(rng, sigmas["lift_fraction_1sigma"]),
            "battery_factor": 1.0 + _bounded_normal(rng, sigmas["battery_fraction_1sigma"]),
            "wind_north_m_s": _bounded_normal(rng, sigmas["horizontal_wind_m_s_1sigma"]),
            "wind_east_m_s": _bounded_normal(rng, sigmas["horizontal_wind_m_s_1sigma"]),
        }
        wind = None
        sample_wind_profile = None
        if vehicle != "space":
            maximum_wind = 16.0 if vehicle == "drone" else 60.0
            if baseline_wind_profile is not None:
                sample_wind_profile = []
                for knot in baseline_wind_profile:
                    vector = [knot["velocity_ned_m_s"][0] + values["wind_north_m_s"],
                              knot["velocity_ned_m_s"][1] + values["wind_east_m_s"],
                              knot["velocity_ned_m_s"][2]]
                    vector = _bounded_wind_vector(vector, maximum_wind)
                    sample_wind_profile.append({
                        "altitude_m": knot["altitude_m"],
                        "velocity_ned_m_s": vector})
                wind = [0.0, 0.0, 0.0]
            else:
                wind = [float(baseline_wind[0]) + values["wind_north_m_s"],
                        float(baseline_wind[1]) + values["wind_east_m_s"],
                        float(baseline_wind[2])]
                wind = _bounded_wind_vector(wind, maximum_wind)
                values["wind_north_m_s"], values["wind_east_m_s"] = wind[:2]
        engine = SimulationEngine()
        engine.reset(vehicle, scenario, model_id, custom_design, wind,
                     baseline_turbulence, sample_wind_profile)
        _apply_perturbations(engine, values)
        engine.launch()
        terminal = {"LANDED", "CRASHED", "ABORTED"}
        while engine.t < horizon_s and engine.phase not in terminal:
            engine.step(min(1.0, horizon_s - engine.t))
        state = engine.state()
        metrics = state["mission_metrics"]
        orbital = state.get("orbital_elements") or {}
        battery = state.get("battery") or {}
        runs.append({
            "sample": sample_id + 1,
            "seed": seed,
            "perturbations": values,
            "wind_profile_ned_m_s": sample_wind_profile,
            "phase": state["phase"],
            "completed": state["phase"] == "LANDED",
            "time_s": state["time_s"],
            "altitude_m": state["altitude_m"],
            "speed_m_s": state["speed_m_s"],
            "max_dynamic_pressure_Pa": metrics["max_dynamic_pressure_Pa"],
            "max_load_factor_g": metrics["max_load_factor_g"],
            "max_stagnation_point_convective_heat_flux_W_m2":
                metrics["max_stagnation_point_convective_heat_flux_W_m2"],
            "touchdown_speed_m_s": metrics["touchdown_speed_m_s"],
            "resource_remaining_pct": state.get("battery_pct", state.get("propellant_pct")),
            "orbit_type": orbital.get("orbit_type"),
        })

    metric_names = ("time_s", "altitude_m", "speed_m_s", "max_dynamic_pressure_Pa",
                    "max_load_factor_g", "max_stagnation_point_convective_heat_flux_W_m2",
                    "touchdown_speed_m_s", "resource_remaining_pct")
    summary = {name: _percentiles([run[name] for run in runs if run[name] is not None])
               for name in metric_names}
    successes = sum(run["completed"] for run in runs)
    return {
        "schema": "ASTRA-ROBUSTNESS-CAMPAIGN-1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "vehicle": vehicle,
        "model_id": model_id,
        "scenario": scenario,
        "integrator": "fixed-step RK4; ASTRA internal step limits",
        "time_step_s": 1.0,
        "maximum_simulated_time_s": horizon_s,
        "samples_requested": count,
        "samples_completed": len(runs),
        "seed": seed,
        "uncertainty_model": {
            "distribution": "truncated normal, independent inputs, bounded at ±3σ",
            "interpretation": "analyst-selected study assumptions; not measured vehicle tolerances",
            "wind_envelope_policy": (
                "Realized wind above the vehicle speed envelope is radially "
                "projected into it, scaling all NED components. For profiles "
                "this projection is applied separately at each altitude knot; "
                "wind perturbations describe the common horizontal offset "
                "before projection, and each realized profile is exported. "
                "For uniform wind, reported wind perturbations are the final "
                "north/east velocities after projection."),
            "one_sigma": sigmas,
            "outcome_confidence_interval": "95% Wilson interval for the observed completion fraction",
        },
        "baseline_wind_ned_m_s": list(baseline_wind),
        "baseline_wind_profile_ned_m_s": baseline_wind_profile,
        "baseline_turbulence": baseline_turbulence,
        "completion_fraction": successes / len(runs),
        "completion_fraction_wilson_95": _wilson_interval(successes, len(runs)),
        "summary": summary,
        "runs": runs,
    }
