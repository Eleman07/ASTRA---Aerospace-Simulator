"""Shared SI physical constants used by ASTRA's simulation and design tools."""

G0 = 9.80665  # standard gravity, m/s²
OMEGA_EARTH = 7.2921150e-5  # Earth sidereal rotation rate, rad/s

# Reference airfield geometry. The runway starts 150 m before the aircraft's
# initial NED origin and extends north; use its midpoint as the nominal aimpoint.
AIRFIELD_RUNWAY_LENGTH_M = 3_000.0
AIRFIELD_RUNWAY_START_OFFSET_M = 150.0
AIRFIELD_RUNWAY_START_N_M = -AIRFIELD_RUNWAY_START_OFFSET_M
AIRFIELD_RUNWAY_END_N_M = (
    AIRFIELD_RUNWAY_START_N_M + AIRFIELD_RUNWAY_LENGTH_M)
AIRFIELD_RUNWAY_AIMPOINT_N_M = (
    AIRFIELD_RUNWAY_START_N_M + AIRFIELD_RUNWAY_LENGTH_M / 2.0)
