"""Seeded spatial Dryden gust fields for deterministic aircraft/UAV studies.

The implementation synthesizes the canonical one-dimensional Dryden spatial
power spectra as a finite random-phase Fourier series.  The vehicle samples a
frozen field along its path relative to the mean air mass (Taylor frozen-field
assumption).  This keeps turbulence repeatable and independent of the RK4 step
size; it does not model gust gradients, cross-axis spatial coherence, or a
time-evolving weather field.

Spectral forms follow the Dryden equations documented in NASA/TM-2019-220143,
"Verifying Implementation of the Dryden Turbulence Model".
"""

from __future__ import annotations

import math
import random
from typing import Any, Sequence

DRYDEN_MODEL = "DRYDEN_FROZEN_FIELD_SPECTRAL"
NO_TURBULENCE_MODEL = "NONE"
_MODE_COUNT = 48
_K_MIN = 1.0e-3
_K_MAX = 32.0


def _finite_vector(values: Any, name: str, *, minimum: float,
                   maximum: float) -> list[float]:
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError(f"{name} must contain three NED-axis values")
    result: list[float] = []
    for value in values:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not minimum <= value <= maximum):
            raise ValueError(f"{name} values must be finite and between {minimum:g} and {maximum:g}")
        result.append(float(value))
    return result


def validate_turbulence_settings(settings: Any, vehicle: str) -> dict[str, Any]:
    """Validate API turbulence input and return its canonical representation."""
    if settings is None:
        settings = {"model": "none"}
    if not isinstance(settings, dict):
        raise ValueError("turbulence must be an object")
    model = settings.get("model", "none")
    if not isinstance(model, str):
        raise ValueError("turbulence.model must be 'none' or 'dryden'")
    model = model.lower()
    if model == "none":
        unexpected = set(settings)-{"model"}
        if unexpected:
            raise ValueError("turbulence parameters require model='dryden'")
        return {"model": NO_TURBULENCE_MODEL, "seed": None,
                "sigma_ned_m_s": [0.0, 0.0, 0.0],
                "length_ned_m": [None, None, None]}
    if model != "dryden":
        raise ValueError("turbulence.model must be 'none' or 'dryden'")
    if vehicle not in {"aircraft", "drone"}:
        raise ValueError("Dryden turbulence is available only for aircraft and drones")

    seed = settings.get("seed", 20261023)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("turbulence.seed must be an integer between 0 and 4294967295")
    sigma = _finite_vector(settings.get("sigma_uvw_m_s", [1.5, 1.5, 1.0]),
                           "turbulence.sigma_uvw_m_s", minimum=0.0, maximum=30.0)
    lengths = _finite_vector(settings.get("length_uvw_m", [200.0, 200.0, 50.0]),
                             "turbulence.length_uvw_m", minimum=0.1, maximum=100_000.0)
    if vehicle == "drone" and math.sqrt(sum(value*value for value in sigma)) > 16.0:
        raise ValueError("drone turbulence RMS magnitude must not exceed 16 m/s")
    return {"model": DRYDEN_MODEL, "seed": seed,
            "sigma_uvw_m_s": sigma, "length_uvw_m": lengths}


class DrydenTurbulence:
    """Deterministic finite-series realization of the three Dryden gust spectra."""

    def __init__(self, sigma_ned_m_s: Sequence[float],
                 length_ned_m: Sequence[float], seed: int) -> None:
        if len(sigma_ned_m_s) != 3 or len(length_ned_m) != 3:
            raise ValueError("Dryden turbulence requires three RMS values and three length scales")
        self.sigma = tuple(float(value) for value in sigma_ned_m_s)
        self.length = tuple(float(value) for value in length_ned_m)
        self.seed = int(seed)
        rng = random.Random(self.seed)
        edges = [math.exp(math.log(_K_MIN) +
                          (math.log(_K_MAX)-math.log(_K_MIN))*index/_MODE_COUNT)
                 for index in range(_MODE_COUNT+1)]
        self._modes: tuple[tuple[tuple[float, float, float], ...], ...] = tuple(
            self._axis_modes(axis, edges, rng) for axis in range(3))

    def _axis_modes(self, axis: int, edges: Sequence[float],
                    rng: random.Random) -> tuple[tuple[float, float, float], ...]:
        spectrum = _longitudinal_spectrum if axis == 0 else _transverse_spectrum
        bins: list[tuple[float, float]] = []
        for low, high in zip(edges, edges[1:]):
            reduced_wavenumber = math.sqrt(low*high)
            delta = high-low
            bins.append((reduced_wavenumber,
                         spectrum(reduced_wavenumber)*delta))
        normalizer = sum(power for _, power in bins)
        if normalizer <= 0.0:
            return ()
        sigma = self.sigma[axis]
        scale = self.length[axis]
        return tuple((reduced_wavenumber/scale,
                      sigma*math.sqrt(2.0*power/normalizer),
                      rng.uniform(0.0, 2.0*math.pi))
                     for reduced_wavenumber, power in bins)

    def evaluate(self, path_m: float) -> list[float]:
        """Evaluate NED turbulence velocity at distance through the frozen field."""
        if not math.isfinite(path_m):
            raise ValueError("turbulence path distance must be finite")
        return [sum(amplitude*math.cos(wavenumber*path_m+phase)
                    for wavenumber, amplitude, phase in modes)
                for modes in self._modes]


def _longitudinal_spectrum(reduced_wavenumber: float) -> float:
    """Normalized Dryden Φu(k), whose integral from zero to infinity is one."""
    return (2.0/math.pi)/(1.0+reduced_wavenumber*reduced_wavenumber)


def _transverse_spectrum(reduced_wavenumber: float) -> float:
    """Normalized Dryden Φv/Φw(k), whose integral is one."""
    square = reduced_wavenumber*reduced_wavenumber
    return (1.0/math.pi)*(1.0+3.0*square)/(1.0+square)**2

