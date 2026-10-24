"""First-order propulsion models for ASTRA's atmospheric vehicles.

The hover/climb model applies actuator-disk momentum theory, then adds rotor
profile, motor, avionics, and airframe drag losses. It is suitable for mission
energy estimates, not rotor or motor design certification.
The fixed-wing propeller model is an axial actuator disk with finite shaft
power, sea-level static thrust calibration, altitude power lapse and fuel
consumption from brake-specific fuel consumption. It is an engineering-level
model, not a blade-element design tool or a measured engine map.
"""

from __future__ import annotations

import math


SEA_LEVEL_DENSITY_KG_M3 = 1.225


def fixed_wing_propulsion(*, static_thrust_N: float, airspeed_m_s: float,
                          air_density_kg_m3: float, total_disk_area_m2: float,
                          propeller_efficiency: float,
                          power_lapse_exponent: float,
                          specific_fuel_consumption_kg_per_kWh: float,
                          engine_power_fraction: float) -> dict[str, float | str]:
    """Estimate fixed-wing propeller thrust and fuel flow from shaft power.

    ``static_thrust_N`` is a sea-level, static reference used with total disk
    area to infer rated shaft power through actuator-disk momentum theory.
    For forward axial speed ``V``, induced velocity solves
    ``P_useful = 2 rho A vi (V + vi)^2`` and thrust is
    ``2 rho A vi (V + vi)``. Engine shaft power lapses with density ratio to
    ``power_lapse_exponent`` and is multiplied by the integrated spool state.
    Fuel flow uses brake-specific fuel consumption in kg/kWh.
    """
    values = (static_thrust_N, airspeed_m_s, air_density_kg_m3,
              total_disk_area_m2, propeller_efficiency, power_lapse_exponent,
              specific_fuel_consumption_kg_per_kWh, engine_power_fraction)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("fixed-wing propulsion inputs must be finite")
    if static_thrust_N <= 0.0 or airspeed_m_s < 0.0 or air_density_kg_m3 < 0.0:
        raise ValueError("thrust must be positive; speed and density cannot be negative")
    if total_disk_area_m2 <= 0.0:
        raise ValueError("total propeller disk area must be positive")
    if not 0.0 < propeller_efficiency <= 1.0:
        raise ValueError("propeller efficiency must be in (0, 1]")
    if power_lapse_exponent < 0.0:
        raise ValueError("power lapse exponent cannot be negative")
    if specific_fuel_consumption_kg_per_kWh < 0.0:
        raise ValueError("specific fuel consumption cannot be negative")
    if not 0.0 <= engine_power_fraction <= 1.0:
        raise ValueError("engine power fraction must be between zero and one")

    sea_level_induced_velocity = math.sqrt(
        static_thrust_N/(2.0*SEA_LEVEL_DENSITY_KG_M3*total_disk_area_m2))
    rated_shaft_power = (static_thrust_N*sea_level_induced_velocity/
                         propeller_efficiency)
    density_ratio = air_density_kg_m3/SEA_LEVEL_DENSITY_KG_M3
    power_lapse = density_ratio**power_lapse_exponent if density_ratio > 0.0 else 0.0
    shaft_power = rated_shaft_power*power_lapse*engine_power_fraction
    useful_power = shaft_power*propeller_efficiency

    if useful_power == 0.0 or air_density_kg_m3 == 0.0:
        induced_velocity = 0.0
        thrust = 0.0
    else:
        momentum_scale = 2.0*air_density_kg_m3*total_disk_area_m2
        # The zero-airspeed solution is the exact cube root. It is also a
        # robust upper bound for Newton iteration at forward speed.
        induced_velocity = (useful_power/momentum_scale)**(1.0/3.0)
        speed = airspeed_m_s
        for _ in range(16):
            convective_speed = speed+induced_velocity
            residual = momentum_scale*induced_velocity*convective_speed**2-useful_power
            if abs(residual) <= max(useful_power*1e-12, 1e-12):
                break
            slope = momentum_scale*convective_speed*(speed+3.0*induced_velocity)
            candidate = induced_velocity-residual/slope
            if candidate <= 0.0 or not math.isfinite(candidate):
                candidate = induced_velocity*0.5
            if abs(candidate-induced_velocity) <= max(induced_velocity*1e-12, 1e-12):
                induced_velocity = candidate
                break
            induced_velocity = candidate
        thrust = momentum_scale*induced_velocity*(speed+induced_velocity)

    fuel_flow = (specific_fuel_consumption_kg_per_kWh*shaft_power/
                 3_600_000.0)
    return {
        "model": "AXIAL_ACTUATOR_DISK_POWER_LAPSE",
        "thrust_N": thrust,
        "induced_velocity_m_s": induced_velocity,
        "shaft_power_W": shaft_power,
        "rated_shaft_power_W": rated_shaft_power,
        "power_lapse_factor": power_lapse,
        "air_density_ratio": density_ratio,
        "fuel_flow_kg_s": fuel_flow,
    }


def fixed_wing_power_fraction_for_thrust(*, required_thrust_N: float,
                                         static_thrust_N: float,
                                         airspeed_m_s: float,
                                         air_density_kg_m3: float,
                                         total_disk_area_m2: float,
                                         propeller_efficiency: float,
                                         power_lapse_exponent: float,
                                         specific_fuel_consumption_kg_per_kWh: float
                                         ) -> float:
    """Invert the axial actuator-disk model for the engine power fraction.

    The requested thrust is converted to induced velocity and shaft power
    using the same momentum theory as :func:`fixed_wing_propulsion`; this
    avoids treating thrust as linear in power, which it is not for a propeller.
    The result is clipped to the available full-power envelope.
    """
    if (isinstance(required_thrust_N, bool) or
            not isinstance(required_thrust_N, (int, float)) or
            not math.isfinite(required_thrust_N) or required_thrust_N < 0.0):
        raise ValueError("required_thrust_N must be finite and non-negative")
    maximum = fixed_wing_propulsion(
        static_thrust_N=static_thrust_N,
        airspeed_m_s=airspeed_m_s,
        air_density_kg_m3=air_density_kg_m3,
        total_disk_area_m2=total_disk_area_m2,
        propeller_efficiency=propeller_efficiency,
        power_lapse_exponent=power_lapse_exponent,
        specific_fuel_consumption_kg_per_kWh=(
            specific_fuel_consumption_kg_per_kWh),
        engine_power_fraction=1.0,
    )
    if required_thrust_N <= 0.0:
        return 0.0
    maximum_thrust = float(maximum["thrust_N"])
    full_power = float(maximum["shaft_power_W"])
    if maximum_thrust <= 0.0 or full_power <= 0.0 or air_density_kg_m3 <= 0.0:
        return 1.0
    if required_thrust_N >= maximum_thrust:
        return 1.0

    momentum_scale = 2.0*air_density_kg_m3*total_disk_area_m2
    induced_velocity = 0.5*(math.sqrt(
        airspeed_m_s**2 + 4.0*required_thrust_N/momentum_scale)-airspeed_m_s)
    useful_power = (momentum_scale*induced_velocity*
                    (airspeed_m_s+induced_velocity)**2)
    required_shaft_power = useful_power/propeller_efficiency
    return max(0.0, min(1.0, required_shaft_power/full_power))


def multirotor_power(thrust_N: float, max_thrust_N: float,
                     air_density_kg_m3: float, total_disk_area_m2: float,
                     figure_of_merit: float, motor_efficiency: float,
                     profile_power_max_W: float, avionics_power_W: float,
                     climb_rate_m_s: float = 0.0,
                     parasitic_power_W: float = 0.0) -> dict[str, float]:
    """Estimate electrical power and induced flow for a multirotor.

    ``climb_rate_m_s`` is positive upward. The ideal actuator-disk induced
    velocity solves ``T = 2 rho A vi (vi + Vc)``. The result then accounts for
    figure of merit, motor efficiency, a profile-power curve proportional to
    thrust fraction to the 3/2 power, avionics draw, and supplied airframe drag.
    """
    values = (thrust_N, max_thrust_N, air_density_kg_m3, total_disk_area_m2,
              figure_of_merit, motor_efficiency, profile_power_max_W,
              avionics_power_W, climb_rate_m_s, parasitic_power_W)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("multirotor power inputs must be finite")
    if max_thrust_N <= 0.0 or not 0.0 <= thrust_N <= max_thrust_N:
        raise ValueError("thrust must be between zero and a positive maximum")
    if air_density_kg_m3 <= 0.0 or total_disk_area_m2 <= 0.0:
        raise ValueError("air density and total rotor-disk area must be positive")
    if not 0.0 < figure_of_merit <= 1.0:
        raise ValueError("figure_of_merit must be in (0, 1]")
    if not 0.0 < motor_efficiency <= 1.0:
        raise ValueError("motor_efficiency must be in (0, 1]")
    if profile_power_max_W < 0.0 or avionics_power_W < 0.0 or parasitic_power_W < 0.0:
        raise ValueError("loss and avionics power values cannot be negative")

    if thrust_N == 0.0:
        induced_velocity = 0.0
        induced_power = 0.0
        profile_power = 0.0
    else:
        root = math.sqrt(climb_rate_m_s**2 +
                         2.0*thrust_N/(air_density_kg_m3*total_disk_area_m2))
        induced_velocity = 0.5*(root-climb_rate_m_s)
        induced_power = max(0.0, thrust_N*(induced_velocity+climb_rate_m_s))
        thrust_fraction = thrust_N/max_thrust_N
        profile_power = profile_power_max_W*thrust_fraction**1.5

    rotor_shaft_power = induced_power/figure_of_merit+profile_power
    electrical_power = (rotor_shaft_power/motor_efficiency+
                        avionics_power_W+parasitic_power_W)
    return {
        "induced_velocity_m_s": induced_velocity,
        "induced_power_W": induced_power,
        "rotor_profile_power_W": profile_power,
        "rotor_shaft_power_W": rotor_shaft_power,
        "parasitic_power_W": parasitic_power_W,
        "avionics_power_W": avionics_power_W,
        "electrical_power_W": electrical_power,
    }
