"""Validated reference parts and staged launch-vehicle sizing for ASTRA.

The catalog is an educational ASTRA baseline, not certified flight hardware.
Every assembled parameter is explicit and passed into the physical propagator.
"""

from __future__ import annotations

import math
from typing import Any

from .atmosphere import SEA_LEVEL_PRESSURE_PA
from .constants import G0

CAPSULE_DRY_MASS_KG = 2_800.0
TANK_DRY_MASS_KG = 300.0
TANK_PROPELLANT_KG = 10_000.0
ENGINE_DRY_MASS_KG = 600.0
ENGINE_THRUST_N = 320_000.0
ENGINE_NOZZLE_EXIT_AREA_M2 = 0.32
# Reference high-performance chemical engine vacuum rating. Ambient pressure
# reduces net thrust through the nozzle correction while chamber mass flow is
# derived from this vacuum rating.
ENGINE_ISP_S = 320.0
MIN_LIFTOFF_TWR = 1.1
MAX_STAGES = 4
MAX_TANKS_PER_STAGE = 3
MAX_ENGINES_PER_STAGE = 8
CAPSULE_SECTION_LENGTH_M = 3.4
CAPSULE_REFERENCE_RADIUS_M = 1.8
TANK_SECTION_LENGTH_M = 2.6
ENGINE_SECTION_LENGTH_M = 0.9
TANK_CLUSTER_REFERENCE_RADIUS_M = 1.25
ACS_PROPELLANT_FRACTION = 0.0005


def build_spacecraft_design(payload: object) -> dict[str, Any]:
    """Validate a staged stack and calculate mass, thrust and ideal Δv."""
    if not isinstance(payload, dict):
        raise ValueError("custom_design must be an object")
    allowed = {"name", "tank_count", "engine_count", "stages"}
    if set(payload) - allowed:
        raise ValueError("custom_design accepts name and stage/tank/engine configuration")

    name = payload.get("name", "ASTRA Custom Stack")
    if not isinstance(name, str):
        raise ValueError("design name must be text")
    name = " ".join(name.strip().split())
    if not name or len(name) > 32:
        raise ValueError("design name must contain 1–32 characters")

    if "stages" in payload:
        if "tank_count" in payload or "engine_count" in payload:
            raise ValueError("use either stages or legacy tank_count/engine_count fields")
        raw_stages = payload["stages"]
        if not isinstance(raw_stages, list) or not 1 <= len(raw_stages) <= MAX_STAGES:
            raise ValueError(f"stages must contain between 1 and {MAX_STAGES} stages")
    else:
        raw_stages = [{"tank_count": payload.get("tank_count", 2),
                       "engine_count": payload.get("engine_count", 1)}]

    stages = []
    for index, raw in enumerate(raw_stages, 1):
        if not isinstance(raw, dict) or set(raw) - {"tank_count", "engine_count"}:
            raise ValueError(f"stage {index} must contain only tank_count and engine_count")
        tank_count = raw.get("tank_count", 2)
        engine_count = raw.get("engine_count", 1)
        if (isinstance(tank_count, bool) or not isinstance(tank_count, int)
                or not 1 <= tank_count <= MAX_TANKS_PER_STAGE):
            raise ValueError(f"stage {index} tank_count must be an integer from 1 to {MAX_TANKS_PER_STAGE}")
        if (isinstance(engine_count, bool) or not isinstance(engine_count, int)
                or not 1 <= engine_count <= MAX_ENGINES_PER_STAGE):
            raise ValueError(f"stage {index} engine_count must be an integer from 1 to {MAX_ENGINES_PER_STAGE}")
        stages.append({
            "stage": index,
            "tank_count": tank_count,
            "engine_count": engine_count,
            "reference_length_m": TANK_SECTION_LENGTH_M + ENGINE_SECTION_LENGTH_M,
            "reference_radius_m": TANK_CLUSTER_REFERENCE_RADIUS_M * math.sqrt(tank_count),
            "dry_mass_kg": tank_count*TANK_DRY_MASS_KG + engine_count*ENGINE_DRY_MASS_KG,
            "propellant_capacity_kg": tank_count*TANK_PROPELLANT_KG,
            "thrust_vacuum_N": engine_count*ENGINE_THRUST_N,
            "nozzle_exit_area_m2": engine_count*ENGINE_NOZZLE_EXIT_AREA_M2,
            "isp_vacuum_s": ENGINE_ISP_S,
        })

    tank_count = sum(stage["tank_count"] for stage in stages)
    engine_count = sum(stage["engine_count"] for stage in stages)
    dry_mass = CAPSULE_DRY_MASS_KG + sum(stage["dry_mass_kg"] for stage in stages)
    propellant = sum(stage["propellant_capacity_kg"] for stage in stages)
    acs_propellant = propellant * ACS_PROPELLANT_FRACTION
    wet_mass = dry_mass + propellant + acs_propellant
    reference_body_length_m = (CAPSULE_SECTION_LENGTH_M +
                               sum(stage["reference_length_m"] for stage in stages))
    reference_body_radius_m = max(
        CAPSULE_REFERENCE_RADIUS_M,
        *(stage["reference_radius_m"] for stage in stages))
    thrust = stages[0]["thrust_vacuum_N"]
    sea_level_thrust = stages[0]["engine_count"] * max(
        0.0, ENGINE_THRUST_N - SEA_LEVEL_PRESSURE_PA * ENGINE_NOZZLE_EXIT_AREA_M2)
    stage_twr = []
    mass_at_ignition = wet_mass
    ideal_delta_v = 0.0
    for stage in stages:
        initial_mass = mass_at_ignition
        final_mass = initial_mass - stage["propellant_capacity_kg"]
        stage["wet_mass_at_ignition_kg"] = initial_mass
        stage["mass_after_burn_kg"] = final_mass
        stage["thrust_sea_level_N"] = stage["engine_count"] * max(
            0.0, ENGINE_THRUST_N - SEA_LEVEL_PRESSURE_PA*ENGINE_NOZZLE_EXIT_AREA_M2)
        # The actual ignition altitude depends on the trajectory. Show the
        # sea-level value as a conservative lower bound for every stage.
        stage["twr_at_sea_level"] = stage["thrust_sea_level_N"]/(initial_mass*G0)
        stage_twr.append(stage["twr_at_sea_level"])
        ideal_delta_v += stage["isp_vacuum_s"]*G0*math.log(initial_mass/final_mass)
        mass_at_ignition = final_mass-stage["dry_mass_kg"]
    twr = stage_twr[0]
    if twr < MIN_LIFTOFF_TWR:
        raise ValueError(f"liftoff T/W {twr:.2f} is below the ASTRA mission minimum {MIN_LIFTOFF_TWR:.2f}")
    if any(not math.isfinite(value) or value <= 0.0 for value in stage_twr):
        raise ValueError("each stage must have positive, finite sea-level T/W")
    if not math.isfinite(ideal_delta_v):
        raise ValueError("computed vehicle performance is not finite")

    return {
        "name": name,
        "tank_count": tank_count,
        "engine_count": engine_count,
        "stage_count": len(stages),
        "stages": stages,
        "payload_dry_mass_kg": CAPSULE_DRY_MASS_KG,
        "tank_dry_mass_kg": TANK_DRY_MASS_KG,
        "propellant_per_tank_kg": TANK_PROPELLANT_KG,
        "engine_dry_mass_kg": ENGINE_DRY_MASS_KG,
        "engine_thrust_vacuum_N": ENGINE_THRUST_N,
        "engine_nozzle_exit_area_m2": stages[0]["nozzle_exit_area_m2"],
        "engine_isp_vacuum_s": ENGINE_ISP_S,
        "dry_mass_kg": dry_mass,
        "propellant_capacity_kg": propellant,
        "acs_propellant_capacity_kg": acs_propellant,
        "acs_propellant_fraction": ACS_PROPELLANT_FRACTION,
        "wet_mass_kg": wet_mass,
        "body_length_m": reference_body_length_m,
        "body_radius_m": reference_body_radius_m,
        "geometry_model": "ASTRA_REFERENCE_STACK_GEOMETRY",
        "thrust_vacuum_N": thrust,
        "thrust_sea_level_N": sea_level_thrust,
        "liftoff_twr": twr,
        "stage_twr_at_sea_level": stage_twr,
        "ideal_delta_v_m_s": ideal_delta_v,
    }


def vehicle_parts_catalog() -> dict[str, object]:
    """Return the authoritative reference-part values exposed to the UI/API."""
    return {
        "configuration": {
            "min_stages": 1, "max_stages": MAX_STAGES,
            "min_tanks": 1, "max_tanks": MAX_TANKS_PER_STAGE,
            "min_engines": 1, "max_engines": MAX_ENGINES_PER_STAGE,
            "minimum_liftoff_twr": MIN_LIFTOFF_TWR,
            "standard_gravity_m_s2": G0,
            "acs_propellant_fraction_of_main_propellant": ACS_PROPELLANT_FRACTION,
            "sea_level_pressure_Pa": SEA_LEVEL_PRESSURE_PA,
            "delta_v_model": "stagewise ideal Tsiolkovsky; retains ACS reserve as payload mass; jettisons dry stage mass; excludes ACS impulse, gravity and aerodynamic losses",
        },
        "parts": {
            "capsule": {"dry_mass_kg": CAPSULE_DRY_MASS_KG,
                        "reference_length_m": CAPSULE_SECTION_LENGTH_M,
                        "reference_radius_m": CAPSULE_REFERENCE_RADIUS_M},
            "tank": {"dry_mass_kg": TANK_DRY_MASS_KG,
                     "propellant_capacity_kg": TANK_PROPELLANT_KG,
                     "reference_length_m": TANK_SECTION_LENGTH_M,
                     "cluster_reference_radius_m": TANK_CLUSTER_REFERENCE_RADIUS_M},
            "engine": {"dry_mass_kg": ENGINE_DRY_MASS_KG,
                       "thrust_vacuum_N": ENGINE_THRUST_N,
                       "nozzle_exit_area_m2": ENGINE_NOZZLE_EXIT_AREA_M2,
                       "isp_vacuum_s": ENGINE_ISP_S,
                       "reference_section_length_m": ENGINE_SECTION_LENGTH_M},
            "attitude_control": {
                "acs_propellant_fraction_of_main_propellant": ACS_PROPELLANT_FRACTION,
                "rcs_force_per_axis_N": 24.0,
                "rcs_specific_impulse_s": 220.0,
            },
        },
    }
