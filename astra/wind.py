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


# Physics-consistent surface-layer shear, opt-in via /reset.
# Monin-Obukhov similarity, Businger-Dyer integrated momentum functions.
# Apply only inside the declared surface-layer domain (maximum 200 m).
def _psi_m(zeta: float) -> float:
    if zeta >= 0.0:
        return -5.0 * zeta
    x = (1.0 - 16.0 * zeta) ** 0.25
    return (2.0 * math.log((1.0 + x)/2.0)
            + math.log((1.0 + x*x)/2.0)
            - 2.0 * math.atan(x) + math.pi/2.0)


def surface_layer_factor(height_m: float, reference_height_m: float,
                         roughness_length_m: float,
                         stability_length_m: float | None = None) -> float:
    """Wind magnitude ratio U(z)/U(zref) in a Monin-Obukhov layer.

    Uses the log-law with Businger-Dyer correction. Only suitable for an
    approximately stationary, horizontally homogeneous surface layer.
    """
    z = max(0.0, float(height_m))
    zref = float(reference_height_m)
    z0 = float(roughness_length_m)
    if not (0.0 < z0 < zref) or not math.isfinite(z):
        raise ValueError('Invalid surface-layer height/roughness')
    if z <= z0:
        return 0.0
    def log_profile(height):
        val = math.log(height / z0)
        if stability_length_m is not None:
            L = float(stability_length_m)
            if not math.isfinite(L) or abs(L) < 5.0:
                raise ValueError('stability_length_m must have |L| >= 5 m')
            val -= _psi_m(height/L) - _psi_m(z0/L)
        return val
    denom = log_profile(zref)
    if denom <= 0.0:
        raise ValueError('Invalid Monin-Obukhov reference layer')
    return max(0.0, log_profile(z) / denom)


def validate_surface_layer(config: Any, vehicle: str) -> dict[str, Any] | None:
    """Validate opt-in surface wind profile for atmospheric vehicles."""
    if config is None:
        return None
    if vehicle not in ('aircraft','drone'):
        raise ValueError('surface_layer_wind is only available for aircraft/drone')
    if not isinstance(config, dict):
        raise ValueError('surface_layer_wind must be an object')
    allowed = {'reference_wind_ned_m_s','reference_height_m',
               'roughness_length_m','boundary_layer_height_m','stability_length_m'}
    if set(config) - allowed:
        raise ValueError('Unknown surface_layer_wind parameter')
    v = config.get('reference_wind_ned_m_s', [8.0,0.0,0.0])
    if not isinstance(v, (tuple,list)) or len(v) != 3:
        raise ValueError('reference_wind_ned_m_s needs three numbers')
    vv = [_finite_float(x) for x in v]
    if any(x is None for x in vv) or abs(vv[2])>1e-12:
        raise ValueError('surface layer requires finite horizontal reference wind')
    ref = _finite_float(config.get('reference_height_m',10.0))
    rough = _finite_float(config.get('roughness_length_m',0.03))
    top = _finite_float(config.get('boundary_layer_height_m',100.0))
    if ref is None or rough is None or top is None or not (0.0001 <= rough <= 1.0 and
          2.0 <= ref <= 100.0 and ref <= top <= 200.0 and rough < ref):
        raise ValueError('Surface layer requires z0 0.0001..1m and 2<=zref<=top<=200m')
    stability = config.get('stability_length_m')
    if stability is not None:
        stability = _finite_float(stability)
        if stability is None or abs(stability) < 5.0:
            raise ValueError('stability_length_m needs finite |L| >= 5 m')
    limit = 16.0 if vehicle == 'drone' else 60.0
    max_magnitude = math.hypot(vv[0],vv[1])*surface_layer_factor(top,ref,rough,stability)
    if max_magnitude > limit + 1e-8:
        raise ValueError(f'Surface-layer wind at {top:g}m exceeds {vehicle} limit {limit:g}m/s')
    return {'reference_wind_ned_m_s':[float(x) for x in vv],
            'reference_height_m':ref, 'roughness_length_m':rough,
            'boundary_layer_height_m':top,'stability_length_m':stability}


def surface_layer_wind_at_altitude(config: dict[str, Any],
                                   altitude_m: float) -> tuple[list[float],bool]:
    """Return NED mean wind and whether the surface-layer cap was reached."""
    top = config['boundary_layer_height_m']
    altitude = max(0.0,float(altitude_m))
    clipped = altitude > top
    factor = surface_layer_factor(min(altitude,top),
                                  config['reference_height_m'],
                                  config['roughness_length_m'],
                                  config.get('stability_length_m'))
    return [factor*v for v in config['reference_wind_ned_m_s']], clipped
