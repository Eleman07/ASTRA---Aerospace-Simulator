"""ASTRA additional parameterized engineering analyses.

SI units. Standalone analyses; not coupled to live flight.
No external dependencies.
"""

import math

from .atmosphere import atmosphere_isa

G0 = 9.80665


def numeric(p, key, default, low, high):
    value = p.get(key, default)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(
            f"{key} must be a finite number in [{low}, {high}]"
        )
    return float(value)


def aerodynamic_envelope(p):
    """Finite-wing, subsonic steady-flight performance envelope.

    Uses a Prandtl-Glauert approximation and a finite-wing
    lift-curve correction. Not a transonic or dynamic-stall model.
    """
    mass = numeric(p, "mass_kg", 1250, 1, 1e7)
    area = numeric(p, "wing_area_m2", 16.2, 0.1, 2000)
    aspect = numeric(p, "aspect_ratio", 7.4, 2, 30)
    oswald = numeric(p, "oswald_efficiency", 0.8, 0.3, 1)
    cl_max = numeric(p, "CL_max", 1.5, 0.2, 4)
    cl0 = numeric(p, "CL0", 0.2, -1, 1.5)
    cd0 = numeric(p, "CD0", 0.027, 0.001, 0.3)
    a0 = numeric(p, "lift_slope_2d_per_rad", 2*math.pi, 1, 8)
    altitude = numeric(p, "altitude_m", 2000, -500, 20000)

    speeds = p.get(
        "airspeeds_m_s",
        [35, 45, 55, 70, 90, 110, 140, 170]
    )
    if (
        not isinstance(speeds, list)
        or not 1 <= len(speeds) <= 48
    ):
        raise ValueError("airspeeds_m_s must be a list of 1-48 speeds")

    atmosphere = atmosphere_isa(altitude)
    rho = atmosphere["density_kg_m3"]
    a_sound = atmosphere["speed_of_sound_m_s"]
    k_induced = 1/(math.pi*aspect*oswald)

    rows = []

    for raw_speed in speeds:
        if (
            isinstance(raw_speed, bool)
            or not isinstance(raw_speed, (int, float))
            or not math.isfinite(raw_speed)
            or raw_speed <= 0
        ):
            raise ValueError("Airspeeds must be positive and finite")

        speed = float(raw_speed)
        mach = speed/a_sound

        if mach >= 0.75:
            raise ValueError(
                "Subsonic correction limited to Mach < 0.75"
            )

        beta = math.sqrt(1-mach*mach)

        lift_slope = a0/(
            beta + a0/(math.pi*oswald*aspect)
        )

        q = 0.5*rho*speed*speed
        cl_required = mass*G0/(q*area)
        alpha_required = (cl_required-cl0)/lift_slope
        cd = cd0+k_induced*cl_required**2
        drag = q*area*cd
        stall_limited = cl_required > cl_max

        rows.append({
            "airspeed_m_s": speed,
            "mach": mach,
            "dynamic_pressure_Pa": q,
            "CL_required": cl_required,
            "CD": cd,
            "alpha_required_deg": math.degrees(
                alpha_required
            ),
            "drag_N": drag,
            "thrust_required_N": drag,
            "power_required_W": drag*speed,
            "lift_to_drag": cl_required/cd,
            "within_CL_limit": not stall_limited,
        })

    stall_speed = math.sqrt(
        2*mass*G0/(rho*area*cl_max)
    )

    return {
        "model": "FINITE_WING_SUBSONIC_ENVELOPE",
        "atmosphere": atmosphere,
        "stall_speed_estimate_m_s": stall_speed,
        "induced_drag_factor": k_induced,
        "samples": rows,
        "limitations": [
            "Quasi-steady flight",
            "Subsonic Mach below 0.75",
            "User-supplied CL_max and Oswald efficiency",
            "No dynamic stall or aeroelasticity",
        ],
    }


def _area_mach(mach, gamma):
    return (
        (1/mach)
        * (
            (2/(gamma+1))
            * (1+(gamma-1)*mach*mach/2)
        ) ** ((gamma+1)/(2*(gamma-1)))
    )


def rocket_nozzle_sweep(p):
    """Isentropic choked-flow nozzle performance over altitude."""
    chamber_pressure = numeric(
        p, "chamber_pressure_Pa", 7e6, 1e5, 1e9
    )
    chamber_temp = numeric(
        p, "chamber_temperature_K", 3500, 300, 10000
    )
    gamma = numeric(p, "gamma", 1.22, 1.05, 1.67)
    gas_constant = numeric(
        p, "gas_constant_J_kgK", 355, 100, 2000
    )
    throat_diameter = numeric(
        p, "throat_diameter_m", 0.16, 0.005, 10
    )
    expansion_ratio = numeric(
        p, "expansion_ratio", 12, 1, 2000
    )
    discharge = numeric(
        p, "discharge_coefficient", 0.98, 0.5, 1
    )

    altitude_list = p.get(
        "altitudes_m",
        [0, 10000, 30000, 80000]
    )

    if (
        not isinstance(altitude_list, list)
        or not 1 <= len(altitude_list) <= 40
    ):
        raise ValueError("altitudes_m must contain 1-40 values")

    throat_area = math.pi*throat_diameter**2/4
    exit_area = throat_area*expansion_ratio

    if expansion_ratio == 1:
        exit_mach = 1.0
    else:
        left, right = 1.0, 100.0
        for _ in range(100):
            middle = (left+right)/2
            if _area_mach(middle, gamma) < expansion_ratio:
                left = middle
            else:
                right = middle
        exit_mach = (left+right)/2

    temp_ratio = 1/(
        1+(gamma-1)*exit_mach**2/2
    )

    exit_temp = chamber_temp*temp_ratio
    exit_pressure = (
        chamber_pressure
        * temp_ratio**(gamma/(gamma-1))
    )
    exit_velocity = (
        exit_mach*math.sqrt(
            gamma*gas_constant*exit_temp
        )
    )

    choked_factor = (
        math.sqrt(gamma/gas_constant)
        * (2/(gamma+1))**(
            (gamma+1)/(2*(gamma-1))
        )
    )

    mass_flow = (
        discharge
        * throat_area
        * chamber_pressure
        / math.sqrt(chamber_temp)
        * choked_factor
    )

    rows = []

    for raw_alt in altitude_list:
        if (
            isinstance(raw_alt, bool)
            or not isinstance(raw_alt, (int, float))
            or not math.isfinite(raw_alt)
            or raw_alt < -500
            or raw_alt > 1_000_000
        ):
            raise ValueError(
                "altitudes_m must be between -500 and 1,000,000 m"
            )

        altitude = float(raw_alt)
        ambient_pressure = atmosphere_isa(
            altitude
        )["pressure_Pa"]

        thrust = (
            mass_flow*exit_velocity
            + (exit_pressure-ambient_pressure)*exit_area
        )

        separation_risk = (
            ambient_pressure > 0
            and exit_pressure/ambient_pressure < 0.4
        )

        rows.append({
            "altitude_m": altitude,
            "ambient_pressure_Pa": ambient_pressure,
            "thrust_N": thrust,
            "specific_impulse_s": thrust/(mass_flow*G0),
            "thrust_coefficient": (
                thrust/(chamber_pressure*throat_area)
            ),
            "overexpanded": exit_pressure < ambient_pressure,
            "flow_separation_risk": separation_risk,
        })

    return {
        "model": "ISENTROPIC_CHOKED_NOZZLE",
        "mass_flow_kg_s": mass_flow,
        "exit_mach": exit_mach,
        "exit_pressure_Pa": exit_pressure,
        "exit_temperature_K": exit_temp,
        "exit_velocity_m_s": exit_velocity,
        "samples": rows,
        "limitations": [
            "Specified ideal-gas properties",
            "No combustion chemistry",
            "No shock or separated-flow solution",
            "No engine startup transient",
        ],
    }


def wind_shear(p):
    """Neutral atmospheric surface-layer log-wind profile."""
    reference_speed = numeric(
        p, "reference_wind_m_s", 8, 0, 80
    )
    reference_height = numeric(
        p, "reference_height_m", 10, 2, 200
    )
    roughness = numeric(
        p, "roughness_length_m", 0.03, 0.0001, 1
    )
    direction = numeric(
        p, "direction_toward_deg", 90, -360, 360
    )

    if roughness >= reference_height:
        raise ValueError(
            "Roughness must be below reference height"
        )

    heights = p.get(
        "heights_m",
        [0, 2, 5, 10, 20, 50, 100, 200]
    )
    if not isinstance(heights, list) or not 1 <= len(heights) <= 50:
        raise ValueError("heights_m must contain 1-50 values")

    factor = reference_speed/math.log(
        reference_height/roughness
    )

    direction_rad = math.radians(direction)
    rows = []

    for raw_height in heights:
        if (
            isinstance(raw_height, bool)
            or not isinstance(raw_height, (int, float))
            or not math.isfinite(raw_height)
            or not 0 <= raw_height <= 2000
        ):
            raise ValueError("Invalid wind-profile height")

        height = float(raw_height)

        if height <= roughness:
            speed = 0.0
            gradient = None
        else:
            speed = factor*math.log(height/roughness)
            gradient = factor/height

        rows.append({
            "height_m": height,
            "wind_speed_m_s": speed,
            "north_m_s": speed*math.cos(direction_rad),
            "east_m_s": speed*math.sin(direction_rad),
            "shear_per_s": gradient,
        })

    return {
        "model": "NEUTRAL_LOG_WIND_PROFILE",
        "reference_height_m": reference_height,
        "roughness_length_m": roughness,
        "samples": rows,
        "limitations": [
            "Neutral surface-layer approximation",
            "No atmospheric stability correction",
            "No gusts or terrain-resolved CFD",
            "Not real meteorological observations",
        ],
    }
