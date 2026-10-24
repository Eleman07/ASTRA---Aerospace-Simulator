"""Compact quasi-steady fixed-wing aerodynamic coefficient model."""

from __future__ import annotations

import math
from typing import Any


def fixed_wing_coefficients(aero: dict[str, Any], alpha_rad: float,
                            beta_rad: float) -> dict[str, float | bool]:
    """Return lift, drag and side-force coefficients for a smoothed stall polar.

    The attached-flow lift curve is linear. Beyond the configured stall angle it
    blends smoothly into a decaying post-stall lift curve while a quadratic
    separated-flow drag term is added. This is a low-order engineering model;
    it does not represent dynamic stall, hysteresis, or Reynolds/Mach effects.
    """
    if not math.isfinite(alpha_rad) or not math.isfinite(beta_rad):
        raise ValueError("angles of attack and sideslip must be finite")

    alpha_stall = float(aero.get("alpha_stall_rad", math.radians(15.0)))
    transition = float(aero.get("stall_transition_rad", math.radians(4.0)))
    decay = float(aero.get("post_stall_decay_rad", math.radians(20.0)))
    if alpha_stall <= 0.0 or transition <= 0.0 or decay <= 0.0:
        raise ValueError("stall angles and transition widths must be positive")

    cl0 = float(aero["CL0"])
    cl_alpha = float(aero["CLalpha_rad"])
    alpha_abs = abs(alpha_rad)
    excess = max(0.0, alpha_abs - alpha_stall)
    linear_cl = cl0 + cl_alpha * alpha_rad
    if excess == 0.0:
        cl = linear_cl
    else:
        sign = 1.0 if alpha_rad >= 0.0 else -1.0
        cl_at_stall = cl0 + cl_alpha * sign * alpha_stall
        post_stall_cl = float(aero.get("CL_post_stall", 0.55)) * sign
        post_stall_cl += (cl_at_stall - post_stall_cl) * math.exp(-excess / decay)
        blend_fraction = min(1.0, excess / transition)
        blend = blend_fraction * blend_fraction * (3.0 - 2.0 * blend_fraction)
        cl = (1.0 - blend) * linear_cl + blend * post_stall_cl

    beta_drag = float(aero.get("CD_beta", 0.12))
    stall_drag = float(aero.get("CD_stall_per_rad2", 4.5)) * excess * excess
    cd = (float(aero["CD0"]) + float(aero["induced_drag_k"]) * cl * cl
          + beta_drag * beta_rad * beta_rad + stall_drag)
    cy = float(aero["CYbeta_rad"]) * beta_rad
    return {"CL": cl, "CD": cd, "CY": cy,
            "stall_margin_rad": alpha_stall - alpha_abs,
            "stall_margin_deg": math.degrees(alpha_stall - alpha_abs),
            "stall_state": alpha_abs > alpha_stall}


def fixed_wing_moment_coefficients(
        aero: dict[str, Any], alpha_rad: float, beta_rad: float,
        body_rates_rad_s: list[float] | tuple[float, float, float],
        airspeed_m_s: float,
        control_deflections_rad: list[float] | tuple[float, float, float]
        ) -> dict[str, float]:
    """Return low-order roll, pitch and yaw moment coefficients.

    The model uses conventional body axes (x forward, y right, z down) and
    normalized p-hat/q-hat/r-hat rates. Control derivatives are the moment
    coefficient change at the catalogued maximum surface deflection. Catalog
    values are generic reference assumptions, not identified aircraft data.
    Missing derivatives retain the earlier roll/yaw/rate model; static pitch
    stability is opt-in through ``Cm_alpha_per_rad``.
    """
    rates = tuple(float(value) for value in body_rates_rad_s)
    deflections = tuple(float(value) for value in control_deflections_rad)
    values = (alpha_rad, beta_rad, airspeed_m_s, *rates, *deflections)
    if (len(rates) != 3 or len(deflections) != 3
            or not all(math.isfinite(float(value)) for value in values)):
        raise ValueError("fixed-wing moment inputs must be finite three-axis values")
    if airspeed_m_s < 0.1:
        raise ValueError("fixed-wing moment model requires airspeed above 0.1 m/s")

    span_m, chord_m = float(aero["b_m"]), float(aero["c_m"])
    if span_m <= 0.0 or chord_m <= 0.0:
        raise ValueError("fixed-wing span and chord must be positive")
    p_hat = rates[0] * span_m / (2.0 * airspeed_m_s)
    q_hat = rates[1] * chord_m / (2.0 * airspeed_m_s)
    r_hat = rates[2] * span_m / (2.0 * airspeed_m_s)
    names = ("aileron", "elevator", "rudder")
    limits = tuple(float(aero[f"{name}_max_deflection_rad"]) for name in names)
    if any(limit <= 0.0 for limit in limits):
        raise ValueError("fixed-wing control surface limits must be positive")
    controls = tuple(max(-1.0, min(1.0, value/limit))
                     for value, limit in zip(deflections, limits))

    cl = (float(aero.get("Cl_beta_per_rad", -0.12))*beta_rad
          + float(aero.get("Cl_p", -0.5))*p_hat
          + float(aero.get("Cl_delta_a_at_max_deflection", 0.08))*controls[0])
    cm = (float(aero.get("Cm0", 0.0))
          + float(aero.get("Cm_alpha_per_rad", 0.0))*alpha_rad
          + float(aero.get("Cm_q", -12.0))*q_hat
          + float(aero.get("Cm_delta_e_at_max_deflection", 1.05))*controls[1])
    cn = (float(aero.get("Cn_beta_per_rad", 0.16))*beta_rad
          + float(aero.get("Cn_r", -0.22))*r_hat
          + float(aero.get("Cn_delta_r_at_max_deflection", 0.07))*controls[2])
    if not all(math.isfinite(value) for value in (cl, cm, cn)):
        raise ValueError("fixed-wing moment coefficients must be finite")
    return {"Cl": cl, "Cm": cm, "Cn": cn,
            "p_hat": p_hat, "q_hat": q_hat, "r_hat": r_hat,
            "aileron_normalized": controls[0],
            "elevator_normalized": controls[1],
            "rudder_normalized": controls[2]}
