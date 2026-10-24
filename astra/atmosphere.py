"""U.S. Standard Atmosphere 1976 (COESA76) reference atmosphere.

The lower atmosphere is evaluated from the COESA hydrostatic layer equations.
The thermosphere/exosphere uses tabulated COESA76 values, interpolated in log
pressure and density.  This is a static, moderate-solar-activity reference
profile; it does not model weather, latitude, local time, or daily solar flux.
For variable orbital-drag studies use a time/position-dependent model such as
NRLMSIS instead.

Primary model reference: NOAA/NASA/USAF, U.S. Standard Atmosphere 1976,
NASA-TM-X-74335 / NOAA-S/T-76-1562.
"""

from __future__ import annotations

from bisect import bisect_right
import math

from .constants import G0

SEA_LEVEL_PRESSURE_PA = 101_325.0
R_AIR = 287.05287
GAMMA_AIR = 1.4
R_GEOPOTENTIAL = 6_356_766.0
ATMOSPHERE_MODEL = "COESA76 · static standard day · 0–1000 km"

# Geometric altitude (km), T (K), pressure (Pa), density (kg/m³), sound speed
# (m/s).  Values through 300 km use the 5 km table grid.  The upper-atmosphere
# grid is intentionally coarser because the reference density changes smoothly
# there; the log interpolation preserves positivity over many orders of range.
# Source table: U.S. Standard Atmosphere 1976 (NASA-TM-X-74335).
_COESA76: tuple[tuple[float, float, float, float, float], ...] = (
    (85, 188.893, 4.4568e-1, 8.2195e-6, 275.52),
    (90, 186.867, 1.8435e-1, 3.4400e-6, 274.04),
    (95, 188.418, 7.5775e-2, 1.3873e-6, 275.17),
    (100, 195.081, 3.2012e-2, 5.6044e-7, 280.00),
    (105, 208.835, 1.4423e-2, 2.3325e-7, 289.70),
    (110, 240.000, 7.1493e-3, 9.6734e-8, 310.56),
    (115, 300.000, 4.0037e-3, 4.2794e-8, 347.22),
    (120, 360.000, 2.5366e-3, 2.2199e-8, 380.36),
    (125, 417.231, 1.7360e-3, 1.2918e-8, 409.48),
    (130, 469.268, 1.2503e-3, 8.1494e-9, 434.27),
    (135, 516.589, 9.3569e-4, 5.4647e-9, 455.64),
    (140, 559.627, 7.2029e-4, 3.8313e-9, 474.24),
    (145, 598.776, 5.6690e-4, 2.7805e-9, 490.54),
    (150, 634.392, 4.5422e-4, 2.0752e-9, 504.92),
    (155, 666.799, 3.6929e-4, 1.5848e-9, 517.66),
    (160, 696.290, 3.0394e-4, 1.2336e-9, 528.98),
    (165, 723.132, 2.5277e-4, 9.7526e-10, 539.08),
    (170, 747.566, 2.1210e-4, 7.8155e-10, 548.11),
    (175, 769.811, 1.7936e-4, 6.3382e-10, 556.21),
    (180, 790.066, 1.5272e-4, 5.1940e-10, 563.48),
    (185, 808.511, 1.3081e-4, 4.2952e-10, 570.02),
    (190, 825.312, 1.1265e-4, 3.5807e-10, 575.91),
    (195, 840.616, 9.7489e-5, 3.0064e-10, 581.22),
    (200, 854.559, 8.4736e-5, 2.5407e-10, 586.02),
    (205, 867.264, 7.3943e-5, 2.1596e-10, 590.36),
    (210, 878.842, 6.4757e-5, 1.8456e-10, 594.29),
    (215, 889.395, 5.6902e-5, 1.5849e-10, 597.85),
    (220, 899.014, 5.0150e-5, 1.3671e-10, 601.07),
    (225, 907.785, 4.4321e-5, 1.1839e-10, 604.00),
    (230, 915.782, 3.9270e-5, 1.0290e-10, 606.65),
    (235, 923.075, 3.4879e-5, 8.9757e-11, 609.06),
    (240, 929.726, 3.1051e-5, 7.8550e-11, 611.26),
    (245, 935.794, 2.7701e-5, 6.8954e-11, 613.25),
    (250, 941.330, 2.4762e-5, 6.0706e-11, 615.06),
    (255, 946.381, 2.2176e-5, 5.3587e-11, 616.71),
    (260, 950.991, 1.9894e-5, 4.7420e-11, 618.21),
    (265, 955.198, 1.7875e-5, 4.2058e-11, 619.57),
    (270, 959.039, 1.6084e-5, 3.7382e-11, 620.82),
    (275, 962.545, 1.4494e-5, 3.3294e-11, 621.95),
    (280, 965.746, 1.3078e-5, 2.9710e-11, 622.98),
    (285, 968.670, 1.1815e-5, 2.6560e-11, 623.93),
    (290, 971.340, 1.0686e-5, 2.3783e-11, 624.79),
    (295, 973.779, 9.6760e-6, 2.1331e-11, 625.57),
    (300, 976.008, 8.7704e-6, 1.9159e-11, 626.28),
    (350, 990.057, 3.4446e-6, 7.0011e-12, 630.78),
    (400, 995.825, 1.4518e-6, 2.8028e-12, 632.61),
    (450, 998.225, 6.4452e-7, 1.1843e-12, 633.37),
    (500, 999.236, 3.0235e-7, 5.2148e-13, 633.69),
    (550, 999.667, 1.5137e-7, 2.3832e-13, 633.83),
    (600, 999.853, 8.2130e-8, 1.1367e-13, 633.89),
    (700, 999.970, 3.1908e-8, 3.0698e-14, 633.93),
    (750, 999.986, 2.2595e-8, 1.7900e-14, 633.93),
    (800, 999.994, 1.7036e-8, 1.1358e-14, 633.93),
    (850, 999.997, 1.3403e-8, 7.8223e-15, 633.93),
    (900, 999.999, 1.0873e-8, 5.7587e-15, 633.93),
    (950, 999.999, 9.0013e-9, 4.4525e-15, 633.94),
    (1000, 1000.000, 7.5138e-9, 3.5611e-15, 633.94),
)
_COESA_ALTITUDES_M = tuple(row[0] * 1000.0 for row in _COESA76)

_LAYER_H_M = (0.0, 11_000.0, 20_000.0, 32_000.0, 47_000.0,
              51_000.0, 71_000.0, 84_852.0)
_LAYER_LAPSE_K_M = (-0.0065, 0.0, 0.0010, 0.0028, 0.0, -0.0028, -0.0020)


def _lower_layer_bases() -> tuple[tuple[float, float, float, float], ...]:
    temperature = 288.15
    pressure = 101_325.0
    result: list[tuple[float, float, float, float]] = []
    for i, lapse in enumerate(_LAYER_LAPSE_K_M):
        h_base = _LAYER_H_M[i]
        result.append((h_base, temperature, pressure, lapse))
        delta_h = _LAYER_H_M[i + 1] - h_base
        if lapse == 0.0:
            pressure *= math.exp(-G0 * delta_h / (R_AIR * temperature))
        else:
            next_temperature = temperature + lapse * delta_h
            pressure *= (next_temperature / temperature) ** (-G0 / (lapse * R_AIR))
            temperature = next_temperature
    return tuple(result)


_LOWER_LAYER_BASES = _lower_layer_bases()


def _lower_atmosphere(geometric_altitude_m: float) -> tuple[float, float, float, float]:
    h = geometric_altitude_m
    geopotential_h = R_GEOPOTENTIAL * h / (R_GEOPOTENTIAL + h)
    layer_i = (0 if geopotential_h < 0.0 else
               max(i for i, base in enumerate(_LAYER_H_M[:-1])
                   if base <= geopotential_h))
    h_base, t_base, p_base, lapse = _LOWER_LAYER_BASES[layer_i]
    delta_h = geopotential_h - h_base
    temperature = t_base + lapse * delta_h
    if lapse == 0.0:
        pressure = p_base * math.exp(-G0 * delta_h / (R_AIR * t_base))
    else:
        pressure = p_base * (temperature / t_base) ** (-G0 / (lapse * R_AIR))
    density = pressure / (R_AIR * temperature)
    speed_of_sound = math.sqrt(GAMMA_AIR * R_AIR * temperature)
    return temperature, pressure, density, speed_of_sound


def _upper_atmosphere(geometric_altitude_m: float) -> tuple[float, float, float, float]:
    altitude_km = geometric_altitude_m / 1000.0
    i = min(max(bisect_right(_COESA_ALTITUDES_M, geometric_altitude_m) - 1,
                0), len(_COESA76) - 2)
    low, high = _COESA76[i], _COESA76[i + 1]
    fraction = (altitude_km - low[0]) / (high[0] - low[0])
    temperature = low[1] + fraction * (high[1] - low[1])
    pressure = math.exp(math.log(low[2]) + fraction * (math.log(high[2]) - math.log(low[2])))
    density = math.exp(math.log(low[3]) + fraction * (math.log(high[3]) - math.log(low[3])))
    sound_speed = low[4] + fraction * (high[4] - low[4])
    return temperature, pressure, density, sound_speed


def atmosphere_isa(altitude_m: float) -> dict[str, float | str | bool]:
    """Return a static COESA76 atmosphere state for geometric altitude.

    Lower layers follow the defining hydrostatic equations; the tabulated
    thermosphere/exosphere covers 85–1000 km. ``in_model_domain`` is false when
    the requested altitude falls outside the published -0.5–1000 km interval.
    Above 1000 km the function returns an explicit vacuum instead of silently
    extending the last tabulated density.
    """
    requested_h = float(altitude_m)
    if not math.isfinite(requested_h):
        raise ValueError("altitude_m must be finite")
    h = max(-500.0, min(1_000_000.0, requested_h))
    if h <= 85_000.0:
        temperature, pressure, density, sound_speed = _lower_atmosphere(h)
    else:
        temperature, pressure, density, sound_speed = _upper_atmosphere(h)
    in_model_domain = requested_h <= 1_000_000.0 and requested_h >= -500.0
    if requested_h > 1_000_000.0:
        # The published reference stops at 1,000 km; return an explicit vacuum
        # above it instead of silently extending the last tabulated density.
        pressure = 0.0
        density = 0.0
    return {"temperature_K": temperature, "pressure_Pa": pressure,
            "density_kg_m3": density, "speed_of_sound_m_s": sound_speed,
            "model": ATMOSPHERE_MODEL,
            "in_model_domain": in_model_domain}
