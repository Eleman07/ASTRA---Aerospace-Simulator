"""Deterministic RK4 step-refinement studies on isolated ASTRA missions."""

from __future__ import annotations

import math
from typing import Any

from .engine import SimulationEngine
from .wind import validate_wind_profile


_TERMINAL_PHASES = {"LANDED", "CRASHED", "ABORTED"}
_TOLERANCES = {
    "position_m": 1.0,
    "velocity_m_s": 0.02,
    "altitude_m": 1.0,
    "attitude_deg": 0.1,
    "resource_remaining_pct": 0.05,
    "phase_transition_time_s": 0.1,
    "peak_dynamic_pressure_relative_pct": 0.1,
}
_MAX_ESTIMATED_STEPS = 250_000


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _euler321_quaternion(angles_deg: list[float]) -> list[float]:
    roll, pitch, yaw = (math.radians(value) * 0.5 for value in angles_deg)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy,
            cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy]


def _attitude_quaternion(engine: SimulationEngine, state: dict[str, Any]) -> list[float] | None:
    quaternion = state.get("attitude_quaternion_body_to_eci")
    if isinstance(quaternion, list) and len(quaternion) == 4:
        return [float(value) for value in quaternion]
    attitude = state.get("attitude_deg")
    if isinstance(attitude, list) and len(attitude) == 3:
        return _euler321_quaternion([float(value) for value in attitude])
    return None


def _case_state(engine: SimulationEngine) -> dict[str, Any]:
    state = engine.state()
    if engine.vehicle == "space":
        position = list(engine.orbit[:3])
        velocity = list(engine.orbit[3:6])
        frame = "ECI"
    else:
        position = list(engine.flight[:3])
        velocity = engine._ned_velocity(engine.flight)
        frame = "NED"
    return {
        "time_s": state["time_s"],
        "phase": state["phase"],
        "model_id": state["model_id"],
        "fault": state["fault"],
        "frame": frame,
        "position_m": position,
        "velocity_m_s": velocity,
        "altitude_m": state["altitude_m"],
        "attitude_quaternion": _attitude_quaternion(engine, state),
        "resource_remaining_pct": state.get("battery_pct", state.get("propellant_pct")),
        "peak_dynamic_pressure_Pa": state["mission_metrics"]["max_dynamic_pressure_Pa"],
    }


def _attitude_error_deg(a: list[float] | None, b: list[float] | None) -> float | None:
    if a is None or b is None:
        return None
    dot = min(1.0, abs(sum(x*y for x, y in zip(a, b))))
    return math.degrees(2.0 * math.acos(dot))


def _differences(coarse: dict[str, Any], fine: dict[str, Any]) -> dict[str, float | None]:
    coarse_q = abs(coarse["peak_dynamic_pressure_Pa"])
    fine_q = abs(fine["peak_dynamic_pressure_Pa"])
    peak_q_delta = abs(coarse_q - fine_q)
    return {
        "position_m": _norm([a-b for a, b in zip(coarse["position_m"], fine["position_m"])]),
        "velocity_m_s": _norm([a-b for a, b in zip(coarse["velocity_m_s"], fine["velocity_m_s"])]),
        "altitude_m": abs(coarse["altitude_m"] - fine["altitude_m"]),
        "attitude_deg": _attitude_error_deg(coarse["attitude_quaternion"], fine["attitude_quaternion"]),
        "resource_remaining_pct": (
            abs(coarse["resource_remaining_pct"] - fine["resource_remaining_pct"])
            if coarse["resource_remaining_pct"] is not None and
            fine["resource_remaining_pct"] is not None else None),
        "peak_dynamic_pressure_Pa": peak_q_delta,
        # Relative change remains meaningful across rocket, aircraft and UAV
        # loads; the floor avoids division by a near-zero dynamic pressure.
        "peak_dynamic_pressure_relative_pct": (
            100.0 * peak_q_delta / max(coarse_q, fine_q, 1.0)),
    }


def run_convergence_study(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare identical, isolated mission runs while halving the RK4 step."""
    vehicle = payload.get("vehicle", "space")
    scenario = payload.get("scenario", "mission")
    model_id = payload.get("model_id")
    custom_design = payload.get("custom_design")
    baseline_wind = payload.get("baseline_wind_ned_m_s", [0.0, 0.0, 0.0])
    baseline_wind_profile = validate_wind_profile(
        payload.get("baseline_wind_profile_ned_m_s"), vehicle)
    baseline_turbulence = payload.get("baseline_turbulence")
    if vehicle not in {"space", "aircraft", "drone"}:
        raise ValueError("vehicle must be space, aircraft or drone")
    if scenario not in {"mission", "leo-return", "orbital"}:
        raise ValueError("scenario must be mission, leo-return or orbital")
    if scenario != "mission" and vehicle != "space":
        raise ValueError("leo-return and orbital studies are available only for spacecraft")

    step_ceiling = (0.5 if scenario == "orbital" else
                    0.02 if vehicle == "drone" else
                    0.05 if vehicle == "aircraft" or scenario in {"mission", "leo-return"}
                    else 0.5)
    default_base = step_ceiling
    default_horizon = {"space": 120.0 if scenario != "orbital" else 600.0,
                       "aircraft": 30.0, "drone": 20.0}[vehicle]
    horizon = payload.get("horizon_s", default_horizon)
    base_step = payload.get("base_step_s", default_base)
    levels = payload.get("levels", 4)
    if (isinstance(horizon, bool) or not isinstance(horizon, (int, float)) or
            not math.isfinite(horizon) or not 1.0 <= horizon <= 600.0):
        raise ValueError("horizon_s must be finite and between 1 and 600 seconds")
    if (isinstance(base_step, bool) or not isinstance(base_step, (int, float)) or
            not math.isfinite(base_step) or not 0.001 <= base_step <= step_ceiling):
        raise ValueError(f"base_step_s must be between 0.001 and {step_ceiling:g} seconds for this case")
    if isinstance(levels, bool) or not isinstance(levels, int) or levels not in {3, 4, 5, 6}:
        raise ValueError("levels must be 3, 4, 5 or 6")
    estimated_steps = sum(math.ceil(float(horizon)/(float(base_step)/(2**index)))
                          for index in range(levels))
    if estimated_steps > _MAX_ESTIMATED_STEPS:
        raise ValueError(
            f"study exceeds the {_MAX_ESTIMATED_STEPS}-step compute budget; "
            "increase base_step_s, shorten horizon_s or select 3 levels")
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

    tolerances = dict(_TOLERANCES)
    supplied_tolerances = payload.get("tolerances", {})
    if not isinstance(supplied_tolerances, dict):
        raise ValueError("tolerances must be an object of positive finite limits")
    unknown_tolerances = set(supplied_tolerances)-set(_TOLERANCES)
    if unknown_tolerances:
        raise ValueError(f"unknown convergence tolerances: {sorted(unknown_tolerances)}")
    maximum_tolerances = {"position_m": 1.0e6, "velocity_m_s": 1.0e3,
                          "altitude_m": 1.0e6, "attitude_deg": 180.0,
                          "resource_remaining_pct": 100.0,
                          "phase_transition_time_s": 600.0,
                          "peak_dynamic_pressure_relative_pct": 1000.0}
    for key, value in supplied_tolerances.items():
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) or value <= 0.0 or
                value > maximum_tolerances[key]):
            raise ValueError(
                f"tolerances.{key} must be positive and no greater than "
                f"{maximum_tolerances[key]:g}")
        tolerances[key] = float(value)

    requested_horizon = float(horizon)
    step_sizes = [float(base_step)/(2**index) for index in range(levels)]
    cases: list[dict[str, Any]] = []
    for step_size in step_sizes:
        engine = SimulationEngine()
        engine.reset(vehicle, scenario, model_id, custom_design,
                     [float(value) for value in baseline_wind],
                     baseline_turbulence, baseline_wind_profile)
        engine.integration_step_cap_s = step_size
        engine.guidance_update_period_s = (
            0.5 if scenario == "orbital" else
            0.02 if vehicle == "drone" else
            0.05)
        if scenario != "orbital":
            engine.launch()
        last_phase = engine.phase
        phase_transitions: list[dict[str, Any]] = []
        while engine.t < requested_horizon - 1e-10 and engine.phase not in _TERMINAL_PHASES:
            engine.step(min(1.0, requested_horizon-engine.t))
            if engine.phase != last_phase:
                phase_transitions.append({
                    "phase": engine.phase,
                    "time_s": engine.t-engine.phase_time_s,
                })
                last_phase = engine.phase
        case = _case_state(engine)
        finite_values = [case["time_s"], case["altitude_m"],
                         *case["position_m"], *case["velocity_m_s"],
                         case["peak_dynamic_pressure_Pa"]]
        if case["attitude_quaternion"] is not None:
            finite_values.extend(case["attitude_quaternion"])
        if case["resource_remaining_pct"] is not None:
            finite_values.append(case["resource_remaining_pct"])
        if any(not math.isfinite(value) for value in finite_values):
            case["fault"] = case["fault"] or "NON_FINITE_STATE"
        cases.append({"step_s": step_size,
                      "phase_transitions": phase_transitions, **case})

    adjacent = []
    for index in range(len(cases)-1):
        coarse, fine = cases[index], cases[index+1]
        sequence_a = [item["phase"] for item in coarse["phase_transitions"]]
        sequence_b = [item["phase"] for item in fine["phase_transitions"]]
        differences = _differences(coarse, fine)
        differences["phase_transition_time_s"] = (
            max((abs(a["time_s"]-b["time_s"])
                 for a, b in zip(coarse["phase_transitions"], fine["phase_transitions"])),
                default=0.0)
            if sequence_a == sequence_b else None)
        adjacent.append(differences)
    reference_sequence = [item["phase"] for item in cases[0]["phase_transitions"]]
    all_phases_match = all(
        [item["phase"] for item in case["phase_transitions"]] == reference_sequence and
        case["phase"] == cases[0]["phase"] for case in cases)
    all_reach_horizon = all(case["time_s"] >= requested_horizon-1e-7 for case in cases)
    all_finite = all(case["fault"] is None for case in cases)
    latest = adjacent[-1]
    previous = adjacent[-2] if len(adjacent) > 1 else adjacent[-1]
    refinement_improves = all(
        latest[key] is not None and previous[key] is not None and
        latest[key] <= previous[key] * 1.05
        for key in ("position_m", "velocity_m_s", "altitude_m",
                    "phase_transition_time_s",
                    "peak_dynamic_pressure_relative_pct"))
    within_tolerance = all(
        latest[key] is None or latest[key] <= tolerances[key]
        for key in tolerances)
    if not all_finite:
        status = "NON_FINITE_STATE"
    elif (not all_phases_match or
          any(item["phase_transition_time_s"] is None for item in adjacent)):
        status = "INCONCLUSIVE_PHASE_CHANGE"
    elif not all_reach_horizon:
        status = "TERMINAL_BEFORE_HORIZON"
    elif within_tolerance:
        status = "CONVERGED_WITHIN_TOLERANCE"
    elif refinement_improves:
        status = "REFINEMENT_IMPROVES"
    else:
        status = "NOT_CONVERGED"

    observed_order: dict[str, float | None] = {}
    if len(adjacent) >= 2:
        for key in ("position_m", "velocity_m_s", "altitude_m", "attitude_deg",
                    "phase_transition_time_s", "peak_dynamic_pressure_Pa"):
            coarse_delta, fine_delta = adjacent[-2][key], adjacent[-1][key]
            observed_order[key] = (
                math.log2(coarse_delta/fine_delta)
                if coarse_delta is not None and fine_delta is not None and
                coarse_delta > 0.0 and fine_delta > 0.0 else None)
    return {
        "schema": "ASTRA-RK4-CONVERGENCE-2",
        "vehicle": vehicle,
        "scenario": scenario,
        "model_id": cases[-1].get("model_id", model_id),
        "status": status,
        "integrator": "classical fixed-step RK4",
        "control_update_period_s": (
            0.5 if scenario == "orbital" else 0.02 if vehicle == "drone" else 0.05),
        "attitude_control_update_period_s": (
            0.05 if vehicle == "space" and scenario != "orbital" else None),
        "control_update_model": (
            "guidance uses fixed-period zero-order hold across refinements; "
            "powered launch attitude is sampled at 20 Hz independently of RK4"),
        "requested_horizon_s": requested_horizon,
        "actual_horizon_s": [case["time_s"] for case in cases],
        "step_sizes_s": step_sizes,
        "levels": levels,
        "frame": cases[-1]["frame"],
        "baseline_wind_ned_m_s": [float(value) for value in baseline_wind],
        "baseline_wind_profile_ned_m_s": baseline_wind_profile,
        "baseline_turbulence": baseline_turbulence,
        "tolerances": tolerances,
        "refinement_improves": refinement_improves,
        "observed_order": observed_order,
        "runs": cases,
        "adjacent_differences": adjacent,
        "interpretation": (
            "Questo studio confronta soltanto l’errore numerico del profilo selezionato "
            "a un orizzonte fissato. Il quarto ordine teorico di RK4 vale per dinamiche "
            "regolari; controllori campionati e transizioni ibride possono ridurre "
            "l’ordine osservato. Non dimostra la validità fisica dei modelli, la "
            "convergenza di ogni scenario o la sicurezza di un veicolo reale."),
    }
