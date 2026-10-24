"""Altitude-varying mean-wind profiles for atmospheric flight cases."""

from __future__ import annotations

import math
from typing import Any


MAX_PROFILE_KNOTS = 16
MAX_PROFILE_ALTITUDE_M = 84_852.0


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def validate_wind_profile(profile: Any, vehicle: str) -> list[dict[str, Any]] | None:
    """Validate and normalize an altitude/NED-wind table.

    Values are absolute local NED wind velocities, linearly interpolated in
    geometric altitude. The profile is held constant beyond its end knots.
    """
    if profile is None:
        return None
    if vehicle == "space":
        raise ValueError("wind_profile_ned_m_s is available only for aircraft and drones")
    if not isinstance(profile, (list, tuple)) or not 2 <= len(profile) <= MAX_PROFILE_KNOTS:
        raise ValueError(
            f"wind_profile_ned_m_s must contain 2 to {MAX_PROFILE_KNOTS} altitude knots")

    maximum_speed = 16.0 if vehicle == "drone" else 60.0
    normalized: list[dict[str, Any]] = []
    previous_altitude = -math.inf
    for index, knot in enumerate(profile):
        if not isinstance(knot, dict):
            raise ValueError(
                f"wind_profile_ned_m_s[{index}] must be an object with altitude_m and velocity_ned_m_s")
        altitude = _finite_float(knot.get("altitude_m"))
        velocity = knot.get("velocity_ned_m_s")
        if altitude is None or not 0.0 <= altitude <= MAX_PROFILE_ALTITUDE_M:
            raise ValueError(
                f"wind_profile_ned_m_s[{index}].altitude_m must be finite and between 0 and {MAX_PROFILE_ALTITUDE_M:g} m")
        if altitude <= previous_altitude:
            raise ValueError("wind profile altitudes must be strictly increasing")
        if not isinstance(velocity, (list, tuple)) or len(velocity) != 3:
            raise ValueError(
                f"wind_profile_ned_m_s[{index}].velocity_ned_m_s must contain three finite NED velocities")
        vector = [_finite_float(value) for value in velocity]
        if any(value is None for value in vector):
            raise ValueError(
                f"wind_profile_ned_m_s[{index}].velocity_ned_m_s must contain three finite NED velocities")
        vector = [float(value) for value in vector]
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude > maximum_speed:
            raise ValueError(
                f"wind profile magnitude must not exceed {maximum_speed:g} m/s for {vehicle}")
        normalized.append({"altitude_m": float(altitude),
                           "velocity_ned_m_s": vector})
        previous_altitude = float(altitude)
    return normalized


def wind_at_altitude(profile: list[dict[str, Any]], altitude_m: float
                     ) -> tuple[list[float], bool]:
    """Interpolate NED wind and return whether altitude was endpoint-clamped."""
    requested_altitude = float(altitude_m)
    altitude = max(0.0, requested_altitude)
    if altitude <= profile[0]["altitude_m"]:
        return (list(profile[0]["velocity_ned_m_s"]),
                requested_altitude < profile[0]["altitude_m"])
    if altitude >= profile[-1]["altitude_m"]:
        return list(profile[-1]["velocity_ned_m_s"]), altitude > profile[-1]["altitude_m"]
    for lower, upper in zip(profile, profile[1:]):
        if altitude <= upper["altitude_m"]:
            fraction = ((altitude-lower["altitude_m"])/
                        (upper["altitude_m"]-lower["altitude_m"]))
            return ([lower["velocity_ned_m_s"][axis] + fraction *
                     (upper["velocity_ned_m_s"][axis]-
                      lower["velocity_ned_m_s"][axis]) for axis in range(3)], False)
    raise AssertionError("validated wind profile interval was not found")
