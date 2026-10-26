"""On-demand Engineering Studio analyses driven by the current ASTRA state.

No solver in this module changes the flight integration. Where flight inputs are
physically applicable they replace design defaults and each source is reported.
Other analyses remain clearly marked as independent engineering studies.
"""
from __future__ import annotations

import math
from typing import Any

from .engineering import SOLVERS, run_engineering_analysis


def _finite(value: Any, low: float | None = None, high: float | None = None):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    if not math.isfinite(value):
        return None
    if low is not None and value < low:
        return None
    if high is not None and value > high:
        return None
    return float(value)


def run_live_study(engine, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute any registered solver using compatible values from flight state.

    Returns a complete provenance record. This is an ON-DEMAND state snapshot,
    not continuous coupling, a certified prediction, or an actuator command.
    """
    if not isinstance(payload, dict):
        raise ValueError("Engineering live request must be a JSON object")
    analysis = payload.get("analysis")
    if analysis not in SOLVERS:
        raise ValueError("Unknown Engineering Studio analysis")
    state = engine.state()
    vehicle = state["vehicle"]
    env = state.get("environment") or {}
    params = state.get("vehicle_parameters") or {}
    design = dict(payload)
    evidence: dict[str, str] = {}
    notes = []

    def seed(key: str, value: Any, evidence_path: str, lo=None, hi=None):
        finite = _finite(value, lo, hi)
        if finite is not None:
            design[key] = finite
            evidence[key] = evidence_path

    altitude = state.get("altitude_m")
    mass = state.get("mass_kg")
    airspeed = state.get("air_relative_speed_m_s")
    if airspeed is None:
        airspeed = state.get("speed_m_s")

    if analysis in {"aircraft_trim", "aero_envelope"} and vehicle == "aircraft":
        seed("mass_kg", mass, "state.mass_kg", 1, 1e7)
        seed("altitude_m", altitude, "state.altitude_m", 0, 20000 if analysis == "aero_envelope" else 85000)
        if analysis == "aircraft_trim":
            seed("airspeed_m_s", airspeed, "state.air_relative_speed_m_s", 0.1, 1000)
            if state.get("model_id") in __import__("astra.engine", fromlist=["MODEL_CATALOG"]).MODEL_CATALOG["aircraft"]:
                design["model_id"] = state["model_id"]
                evidence["model_id"] = "state.model_id"
        else:
            seed("wing_area_m2", params.get("S_m2"), "state.vehicle_parameters.S_m2", 0.1, 2000)
            seed("aspect_ratio", params.get("aspect_ratio"), "state.vehicle_parameters.aspect_ratio", 2, 30)
    elif analysis == "lifting_line" and vehicle == "aircraft":
        seed("airspeed_m_s", airspeed, "state.air_relative_speed_m_s", 1, 350)
        seed("wing_area_m2", params.get("S_m2"), "state.vehicle_parameters.S_m2", .02, 2000)
        aero = state.get("aerodynamics") or {}
        seed("angle_of_attack_deg", aero.get("angle_of_attack_deg"), "state.aerodynamics.angle_of_attack_deg", -12, 14)
    elif analysis == "wind_shear" and vehicle in {"aircraft", "drone"}:
        wind = env.get("wind_ned_m_s")
        if isinstance(wind, (list, tuple)) and len(wind) >= 2:
            components = [_finite(x) for x in wind[:2]]
            if all(x is not None for x in components):
                seed("reference_wind_m_s", math.hypot(*components), "state.environment.wind_ned_m_s", 0, 80)
        if engine.surface_layer_wind is not None:
            layer = engine.surface_layer_wind
            seed("reference_height_m", layer["reference_height_m"],
                 "state.environment.surface_layer_wind.reference_height_m",2,200)
            seed("roughness_length_m", layer["roughness_length_m"],
                 "state.environment.surface_layer_wind.roughness_length_m",0.0001,1)
            if layer["stability_length_m"] is not None:
                design["stability_length_m"] = layer["stability_length_m"]
                evidence["stability_length_m"] = "state.environment.surface_layer_wind.stability_length_m"
            seed("reference_wind_m_s", math.hypot(*layer["reference_wind_ned_m_s"][:2]),
                 "state.environment.surface_layer_wind.reference_wind_ned_m_s",0,80)
            notes.append("This surface layer also drives the live air-relative velocity and aerodynamic forces.")
        else:
            notes.append("Log-law profile is a separate near-surface estimate; enable surface_layer_wind at reset to couple it to flight.")
    elif analysis in {"propulsion", "rocket_nozzle_sweep"} and vehicle == "space":
        if analysis == "propulsion":
            seed("altitude_m", altitude, "state.altitude_m", 0, 1e6)
        else:
            h = _finite(altitude, 0, 1e6)
            if h is not None:
                design["altitudes_m"] = [h, min(h + 5000, 1e6), min(h + 30000, 1e6)]
                evidence["altitudes_m"] = "state.altitude_m"
        notes.append("Chamber thermochemistry and geometry are user-supplied, not measured by ASTRA.")
    elif analysis in {"orbit", "orbit_eclipse_power"} and vehicle == "space":
        if analysis == "orbit":
            seed("initial_altitude_m", altitude, "state.altitude_m", 80001, 1e8)
            seed("mass_kg", mass, "state.mass_kg", 1, 1e7)
            position = state.get("position_eci_m")
            velocity = state.get("velocity_eci_m_s")
            if altitude is not None and altitude > 80000 and isinstance(position, list) and isinstance(velocity, list) and len(position) == len(velocity) == 3:
                design["state_eci"] = position + velocity
                evidence["state_eci"] = "state.position_eci_m + state.velocity_eci_m_s"
        else:
            seed("orbital_altitude_m", altitude, "state.altitude_m", 150000, 1e8)
    elif analysis == "lambert" and vehicle == "space":
        pos = state.get("position_eci_m")
        target = state.get("target_position_eci_m")
        if isinstance(pos, list) and len(pos) == 3 and isinstance(target, list) and len(target) == 3:
            if math.dist(pos, target) > 1000:
                design["position_start_eci_m"] = list(pos)
                design["position_target_eci_m"] = list(target)
                evidence["position_start_eci_m"] = "state.position_eci_m"
                evidence["position_target_eci_m"] = "state.target_position_eci_m"
        notes.append("Lambert trajectory is planning-only; it does not command live burns.")
    elif analysis == "thermal" and vehicle == "space":
        seed("incident_heat_flux_W_m2", env.get("stagnation_point_convective_heat_flux_W_m2"),
             "state.environment.stagnation_point_convective_heat_flux_W_m2", 0, 1e8)
        seed("environment_temperature_K", env.get("temperature_K"), "state.environment.temperature_K", 1, 4000)
        notes.append("Thermal panel analysis does not change vehicle material or flight dynamics.")
    elif analysis == "power" and vehicle == "drone":
        battery = state.get("battery") or {}
        seed("load_W", battery.get("power_draw_W"), "state.battery.power_draw_W", 0, 1e8)
        seed("battery_capacity_Wh", battery.get("capacity_Wh"), "state.battery.capacity_Wh", 0, 1e8)
    elif analysis in {"link", "radio_link"} and vehicle == "space" and state.get("scenario") == "orbital":
        seed("range_m", state.get("range_to_target_m"), "state.range_to_target_m", 1, 1e13)
        notes.append("Range is spacecraft-to-target only; antennas, pointing and RF losses are user assumptions.")

    if not evidence:
        notes.append("No physically transferable live input for this solver/vehicle; evaluated as an independent design study.")

    result = run_engineering_analysis(design)
    result["mission_context"] = {
        "vehicle": vehicle,
        "phase": state.get("phase"),
        "time_s": state.get("time_s"),
        "frame": state.get("frame"),
        "source": "CURRENT_ASTRO_ENGINE_STATE",
        "mode": "mission_snapshot" if evidence else "independent_design_study",
        "inputs_from_telemetry": evidence,
        # This exact wind law participates in the live flight dynamics.
        # Other engineering studies remain read-only, even when the live plant
        # separately models their physical domain (no feedback of study output).
        "coupled_into_flight_dynamics": (analysis == "wind_shear" and
                                         engine.surface_layer_wind is not None and
                                         vehicle in {"aircraft","drone"}),
        "coupling_explanation": "Underlying physical domain contributes to flight dynamics; the on-demand solver does NOT feed its calculated results back into flight.",
        "notes": notes,
    }
    return result
