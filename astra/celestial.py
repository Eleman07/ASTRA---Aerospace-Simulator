"""Solar-system catalogue and patched-conic transfer planning.

Planet positions use the JPL approximate J2000 Kepler elements (1800–2050).
Satellite paths are circular visualization/design approximations, not a JPL
ephemeris. Lambert solutions seed transfer-window search. The selected
interplanetary arc is differentially corrected and propagated with point-mass
Newtonian gravity from the Sun and eight planets. The Earth–Moon leg remains a
geocentric two-body design approximation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from functools import lru_cache
from typing import Any

AU_M = 149_597_870_700.0
MU_SUN = 1.32712440018e20
MU_EARTH = 3.986004418e14
EARTH_RADIUS = 6_378_137.0
MU_MOON = 4.9048695e12
EARTH_MOON_MU = MU_EARTH+MU_MOON
J2000_JD = 2451545.0
TDB_MINUS_UTC_J2000_S = 64.184

# JPL DE405/LE405 mean elements at 2000-01-01.5 TDB. JPL explicitly warns
# these fitted mean elements describe the orbit's shape/orientation but are
# not an ephemeris. The two-body model uses their phase, shape and plane while
# deriving a dynamically consistent semimajor axis from the period and GM.
MOON_MEAN_ELEMENTS = {
    "semi_major_axis_m": 384_400_000.0,
    "eccentricity": 0.0554,
    "argument_of_periapsis_deg": 318.15,
    "mean_anomaly_j2000_deg": 135.27,
    "inclination_deg": 5.16,
    "ascending_node_deg": 125.08,
    "period_days": 27.321661,
    "epoch_jd_tdb": J2000_JD,
}
MOON_MODEL_SEMI_MAJOR_AXIS_M = (
    EARTH_MOON_MU*(MOON_MEAN_ELEMENTS["period_days"]*86400.0/(2.0*math.pi))**2
)**(1.0/3.0)

# a, e, I, mean longitude L, longitude of perihelion varpi, ascending node Ω;
# plus their rates per Julian century from JPL SSD Table 1 (1800–2050).
PLANETS = {
    "mercury": ("Mercurio", .38709927, .20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593, .00000037, .00001906, -.00594749, 149472.67411175, .16047689, -.12534081, 2.2032e13, 2_439_700., "#b6a38a"),
    "venus": ("Venere", .72333566, .00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255, .00000390, -.00004107, -.00078890, 58517.81538729, .00268329, -.27769418, 3.24859e14, 6_051_800., "#e8bd7a"),
    "earth": ("Terra", 1.00000261, .01671123, -.00001531, 100.46457166, 102.93768193, 0., .00000562, -.00004392, -.01294668, 35999.37244981, .32327364, 0., MU_EARTH, EARTH_RADIUS, "#4b9be8"),
    "mars": ("Marte", 1.52371034, .09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891, .00001847, .00007882, -.00813131, 19140.30268499, .44441088, -.29257343, 4.282837e13, 3_389_500., "#e46d52"),
    "jupiter": ("Giove", 5.20288700, .04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909, -.00011607, -.00013253, -.00183714, 3034.74612775, .21252668, .20469106, 1.26686534e17, 69_911_000., "#d6aa7b"),
    "saturn": ("Saturno", 9.53667594, .05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448, -.00125060, -.00050991, .00193609, 1222.49362201, -.41897216, -.28867794, 3.7931187e16, 58_232_000., "#e9cf91"),
    "uranus": ("Urano", 19.18916464, .04725744, .77263783, 313.23810451, 170.95427630, 74.01692503, -.00196176, -.00004397, -.00242939, 428.48202785, .40805281, .04240589, 5.793939e15, 25_362_000., "#77d9d0"),
    "neptune": ("Nettuno", 30.06992276, .00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574, .00026291, .00005105, .00035372, 218.45945325, -.32241464, -.00508664, 6.836529e15, 24_622_000., "#6689ee"),
}
_PLANET_MUS = tuple(body[13] for body in PLANETS.values())

# id, Italian name, host, mean radius km, orbit radius km, period days,
# approximate host-relative phase at J2000, gravitational parameter m^3/s^2.
MOONS = [
    ("moon", "Luna", "earth", 1737.4, 384400, 27.321661, 134.96, 4.9048695e12),
    ("phobos", "Phobos", "mars", 11.1, 9376, .318910, 0, 7.11e5),
    ("deimos", "Deimos", "mars", 6.2, 23463, 1.262440, 180, 9.6e4),
    ("io", "Io", "jupiter", 1821.6, 421700, 1.769138, 20, 5.959916e12),
    ("europa", "Europa", "jupiter", 1560.8, 671034, 3.551181, 140, 3.202739e12),
    ("ganymede", "Ganimede", "jupiter", 2634.1, 1070412, 7.154553, 255, 9.887819e12),
    ("callisto", "Callisto", "jupiter", 2410.3, 1882709, 16.689018, 70, 7.179289e12),
    ("mimas", "Mimas", "saturn", 198.2, 185539, .942422, 10, 2.5035e9),
    ("enceladus", "Encelado", "saturn", 252.1, 237948, 1.370218, 110, 7.21037e9),
    ("tethys", "Teti", "saturn", 531.1, 294619, 1.887802, 220, 4.1206e10),
    ("dione", "Dione", "saturn", 561.4, 377396, 2.736915, 320, 7.3116e10),
    ("rhea", "Rea", "saturn", 763.8, 527108, 4.518212, 60, 1.5394e11),
    ("titan", "Titano", "saturn", 2574.7, 1221870, 15.945421, 190, 8.978138e12),
    ("iapetus", "Giapeto", "saturn", 734.5, 3560820, 79.3215, 275, 1.2053e11),
    ("miranda", "Miranda", "uranus", 235.8, 129900, 1.413479, 30, 6.4e9),
    ("ariel", "Ariel", "uranus", 578.9, 190900, 2.520379, 145, 8.2e10),
    ("umbriel", "Umbriel", "uranus", 584.7, 266000, 4.144177, 240, 8.5e10),
    ("titania", "Titania", "uranus", 788.9, 436300, 8.705872, 80, 2.269e11),
    ("oberon", "Oberon", "uranus", 761.4, 583500, 13.463239, 200, 2.053e11),
    ("triton", "Tritone", "neptune", 1353.4, 354800, 5.876854, 315, 1.4276e12),
]


def _julian_day(date: datetime) -> float:
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).timestamp() / 86400.0 + 2440587.5


def _parse_date(date_text: str | None) -> datetime:
    date = datetime.fromisoformat(date_text.replace("Z", "+00:00")) if date_text else datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)


@lru_cache(maxsize=131_072)
def _cached_planet_state(body: tuple, jd: float) -> tuple[tuple[float, float, float], float]:
    (_, a0, e0, inc0, L0, varpi0, node0,
     da, de, di, dL, dvarpi, dnode, *_rest) = body
    t = (jd - 2451545.0) / 36525.0
    a = a0 + da*t
    e = e0 + de*t
    inc = math.radians(inc0 + di*t)
    mean = math.radians((L0 + dL*t) - (varpi0 + dvarpi*t))
    omega = math.radians((varpi0 + dvarpi*t) - (node0 + dnode*t))
    node = math.radians(node0 + dnode*t)
    mean = (mean + math.pi) % (2*math.pi) - math.pi
    ecc = mean
    for _ in range(12):
        delta = (ecc - e*math.sin(ecc) - mean) / (1.0 - e*math.cos(ecc))
        ecc -= delta
        if abs(delta) < 1e-13:
            break
    xp = a * (math.cos(ecc)-e)
    yp = a * math.sqrt(1-e*e) * math.sin(ecc)
    x = (math.cos(omega)*math.cos(node)-math.sin(omega)*math.sin(node)*math.cos(inc))*xp + (-math.sin(omega)*math.cos(node)-math.cos(omega)*math.sin(node)*math.cos(inc))*yp
    y = (math.cos(omega)*math.sin(node)+math.sin(omega)*math.cos(node)*math.cos(inc))*xp + (-math.sin(omega)*math.sin(node)+math.cos(omega)*math.cos(node)*math.cos(inc))*yp
    z = math.sin(omega)*math.sin(inc)*xp + math.cos(omega)*math.sin(inc)*yp
    return (x*AU_M, y*AU_M, z*AU_M), a*AU_M


def _planet_state(body: tuple, jd: float) -> tuple[list[float], float]:
    position, semi_major_axis = _cached_planet_state(body, jd)
    return list(position), semi_major_axis


@lru_cache(maxsize=65_536)
def _planet_positions_at_jd(jd: float) -> tuple[tuple[float, float, float], ...]:
    """Share immutable ephemeris batches across RK stages and shooting passes."""
    return tuple(_cached_planet_state(body, jd)[0] for body in PLANETS.values())


def celestial_catalog(date_text: str | None = None) -> dict:
    date = _parse_date(date_text)
    jd = _julian_day(date)
    states = {key: _planet_state(body, jd) for key, body in PLANETS.items()}
    objects = []
    for key, body in PLANETS.items():
        name, a, e, inc, *_ = body
        pos, _ = states[key]
        objects.append({"id": key, "name": name, "class": "planet", "parent_id": "sun",
                        "radius_m": body[14], "mu_m3_s2": body[13], "color": body[15],
                        "semi_major_axis_m": a*AU_M, "eccentricity": e,
                        "inclination_deg": inc, "position_heliocentric_m": pos,
                        "ephemeris_model": "Elementi kepleriani JPL approssimati · J2000 · 1800–2050"})
    objects.insert(0, {"id": "sun", "name": "Sole", "class": "star", "parent_id": None,
                       "radius_m": 695_700_000., "mu_m3_s2": MU_SUN, "color": "#ffe3a1",
                       "semi_major_axis_m": 0., "eccentricity": 0., "inclination_deg": 0.,
                       "position_heliocentric_m": [0., 0., 0.], "ephemeris_model": "origin"})
    for moon_id, name, parent, radius_km, orbit_km, period_days, phase0, moon_mu in MOONS:
        p = states[parent][0]
        if moon_id == "moon":
            rel, _ = _moon_position_velocity(moon_id, date)
            moon_elements_model = (
                "propagazione kepleriana a due corpi dagli elementi medi JPL "
                "DE405/LE405 · approssimazione, non effemeride di precisione"
            )
            orbit_radius_m = MOON_MODEL_SEMI_MAJOR_AXIS_M
            orbit_period_s = MOON_MEAN_ELEMENTS["period_days"]*86400.0
        else:
            # The other satellite paths remain circular visualization models.
            phase = math.radians(phase0 + ((jd-J2000_JD)/period_days*360.0) % 360.0)
            rel = [orbit_km*1000*math.cos(phase),
                   orbit_km*1000*math.sin(phase), 0.0]
            moon_elements_model = "orbita circolare illustrativa · periodo medio"
            orbit_radius_m = orbit_km*1000
            orbit_period_s = period_days*86400
        objects.append({"id": moon_id, "name": name, "class": "moon", "parent_id": parent,
                        "radius_m": radius_km*1000, "mu_m3_s2": moon_mu, "color": "#b4b5c0",
                        "semi_major_axis_m": orbit_radius_m, "period_s": orbit_period_s,
                        **({"reference_mean_semi_major_axis_m":
                            MOON_MEAN_ELEMENTS["semi_major_axis_m"]}
                           if moon_id == "moon" else {}),
                        "position_heliocentric_m": [p[i]+rel[i] for i in range(3)],
                        "position_parent_relative_m": rel,
                        "ephemeris_model": moon_elements_model})
    return {"epoch_utc": date.astimezone(timezone.utc).isoformat(), "julian_date": jd,
            "frame": "mean ecliptic and equinox J2000", "units": "SI",
            "source": ("JPL SSD Approximate Positions of the Planets, Table 1 · "
                       "JPL Planetary Satellite Mean Elements"),
            "moon_element_source": "JPL SSD Planetary Satellite Mean Elements · DE405/LE405 · epoch J2000",
            "validity": ("Planetary element fit valid 1800–2050. The Moon uses a two-body "
                         "Kepler propagation seeded by JPL DE405/LE405 mean elements; "
                         "other moon paths are circular visualization approximations. "
                         "JPL mean elements are not precision ephemerides."),
            "objects": objects}


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: list[float]) -> list[float]:
    magnitude = _norm(a)
    if magnitude <= 0.0 or not math.isfinite(magnitude):
        raise ValueError("cannot form a unit vector from a zero or non-finite state")
    return [value/magnitude for value in a]


def _sphere_of_influence(semi_major_axis_m: float,
                         mu_body: float, mu_parent: float) -> float:
    """Laplace sphere-of-influence radius for a body orbiting its parent."""
    if (semi_major_axis_m <= 0.0 or mu_body <= 0.0 or mu_parent <= 0.0 or
            not all(math.isfinite(value) for value in
                    (semi_major_axis_m, mu_body, mu_parent))):
        raise ValueError("sphere-of-influence inputs must be positive and finite")
    return semi_major_axis_m*(mu_body/mu_parent)**0.4


def _lambert_between_soi_boundaries(
        departure_center_r: list[float], departure_center_v: list[float],
        departure_soi_m: float, arrival_center_r: list[float],
        arrival_center_v: list[float], arrival_soi_m: float,
        transfer_time_s: float, central_mu: float) -> dict[str, Any]:
    """Patch a Lambert arc to outbound and inbound Laplace SOI boundaries.

    Boundary directions depend on the solved excess velocities, so a short
    fixed-point iteration updates both endpoint positions and resolves Lambert.
    The returned transfer remains a central-body two-body arc between SOIs.
    """
    departure_r = list(departure_center_r)
    arrival_r = list(arrival_center_r)
    tolerance_m = max(1.0, max(departure_soi_m, arrival_soi_m)*1e-8)
    for patch_iteration in range(1, 13):
        solution = lambert_universal(departure_r, arrival_r,
                                     transfer_time_s, central_mu)
        departure_v_inf = [solution["departure_velocity_m_s"][i]
                           - departure_center_v[i] for i in range(3)]
        arrival_v_inf = [solution["arrival_velocity_m_s"][i]
                         - arrival_center_v[i] for i in range(3)]
        if _norm(departure_v_inf) <= 1e-9 or _norm(arrival_v_inf) <= 1e-9:
            raise ValueError("Lambert SOI patch has zero hyperbolic excess speed")
        next_departure = [departure_center_r[i]
                          + departure_soi_m*_unit(departure_v_inf)[i]
                          for i in range(3)]
        next_arrival = [arrival_center_r[i]
                        - arrival_soi_m*_unit(arrival_v_inf)[i]
                        for i in range(3)]
        patch_error = max(_norm([next_departure[i]-departure_r[i]
                                 for i in range(3)]),
                          _norm([next_arrival[i]-arrival_r[i]
                                 for i in range(3)]))
        departure_r, arrival_r = next_departure, next_arrival
        if patch_error <= tolerance_m:
            solution = lambert_universal(departure_r, arrival_r,
                                         transfer_time_s, central_mu)
            departure_v_inf = [solution["departure_velocity_m_s"][i]
                               - departure_center_v[i] for i in range(3)]
            arrival_v_inf = [solution["arrival_velocity_m_s"][i]
                             - arrival_center_v[i] for i in range(3)]
            check_departure = [departure_center_r[i]
                               + departure_soi_m*_unit(departure_v_inf)[i]
                               for i in range(3)]
            check_arrival = [arrival_center_r[i]
                             - arrival_soi_m*_unit(arrival_v_inf)[i]
                             for i in range(3)]
            check_error = max(_norm([check_departure[i]-departure_r[i]
                                     for i in range(3)]),
                              _norm([check_arrival[i]-arrival_r[i]
                                     for i in range(3)]))
            if check_error <= tolerance_m*2.0:
                solution.update({
                    "departure_position_m": departure_r,
                    "arrival_position_m": arrival_r,
                    "departure_v_infinity_vector_m_s": departure_v_inf,
                    "arrival_v_infinity_vector_m_s": arrival_v_inf,
                    "departure_soi_radius_m": departure_soi_m,
                    "arrival_soi_radius_m": arrival_soi_m,
                    "soi_patch_iterations": patch_iteration,
                    "soi_patch_residual_m": check_error,
                })
                return solution
    raise ValueError("Lambert sphere-of-influence patch did not converge")


def _stumpff(z: float) -> tuple[float, float]:
    """Return stable Stumpff C(z), S(z) for elliptic/parabolic/hyperbolic cases."""
    if z > 1e-7:
        root = math.sqrt(z)
        return (2.0*math.sin(root/2.0)**2/z,
                (root-math.sin(root))/(root**3))
    if z < -1e-7:
        root = math.sqrt(-z)
        if root > 700.0:
            raise ValueError("hyperbolic universal variable is outside floating-point range")
        return ((math.cosh(root)-1.0)/(-z),
                (math.sinh(root)-root)/(root**3))
    z2 = z*z
    z3 = z2*z
    return (0.5-z/24.0+z2/720.0-z3/40320.0,
            1.0/6.0-z/120.0+z2/5040.0-z3/362880.0)


def lambert_universal(r1_vec: list[float], r2_vec: list[float],
                      transfer_time_s: float, mu: float,
                      prograde: bool = True) -> dict[str, object]:
    """Solve a zero-revolution Lambert boundary-value problem by bisection.

    The independent variable is z = alpha*chi**2 and the monotonic time-of-
    flight residual is bracketed before bisection; no Newton seed is required.
    Returns inertial endpoint velocities and a time residual in seconds.
    """
    if (not math.isfinite(transfer_time_s) or transfer_time_s <= 0.0 or
            not math.isfinite(mu) or mu <= 0.0):
        raise ValueError("transfer time and gravitational parameter must be positive and finite")
    r1 = _norm(r1_vec)
    r2 = _norm(r2_vec)
    if r1 <= 0.0 or r2 <= 0.0:
        raise ValueError("Lambert endpoint radii must be non-zero")
    cosine = max(-1.0, min(1.0, _dot(r1_vec, r2_vec)/(r1*r2)))
    cross_z = _cross(r1_vec, r2_vec)[2]
    sine_magnitude = math.sqrt(max(0.0, 1.0-cosine*cosine))
    sine = sine_magnitude if (cross_z >= 0.0) == prograde else -sine_magnitude
    denominator = 1.0-cosine
    if denominator < 1e-14 or abs(sine) < 1e-14:
        raise ValueError("Lambert geometry is singular for collinear endpoint vectors")
    a_geom = sine*math.sqrt(r1*r2/denominator)
    if abs(a_geom) < 1e-12:
        raise ValueError("Lambert transfer geometry is degenerate")
    sqrt_mu_dt = math.sqrt(mu)*transfer_time_s

    def residual(z: float) -> tuple[float, float]:
        c, s = _stumpff(z)
        if c <= 0.0 or not math.isfinite(c) or not math.isfinite(s):
            return -sqrt_mu_dt, -1.0
        y = r1+r2+a_geom*(z*s-1.0)/math.sqrt(c)
        if y <= 0.0 or not math.isfinite(y):
            return -sqrt_mu_dt, -1.0
        value = (y/c)**1.5*s+a_geom*math.sqrt(y)-sqrt_mu_dt
        if not math.isfinite(value):
            raise ValueError("Lambert time-of-flight residual is not finite")
        return value, y

    f0, _ = residual(0.0)
    if abs(f0) <= sqrt_mu_dt*1e-14:
        low = high = 0.0
    elif f0 > 0.0:
        high = 0.0
        low = -1.0
        f_low, _ = residual(low)
        while f_low >= 0.0 and low > -4096.0:
            low *= 2.0
            f_low, _ = residual(low)
        if f_low >= 0.0:
            raise ValueError("no zero-revolution Lambert solution found in the hyperbolic branch")
    else:
        low = 0.0
        high = 1.0
        f_high, _ = residual(high)
        upper_limit = (2.0*math.pi)**2-1e-7
        while f_high <= 0.0 and high < upper_limit:
            high = min(high*2.0, upper_limit)
            f_high, _ = residual(high)
        if f_high <= 0.0:
            raise ValueError("requested time exceeds the first zero-revolution Lambert branch")

    iterations = 0
    if low != high:
        for iterations in range(1, 121):
            z = 0.5*(low+high)
            f_mid, _ = residual(z)
            if abs(f_mid) <= sqrt_mu_dt*2e-13 or high-low <= 2e-13*max(1.0, abs(z)):
                low = high = z
                break
            if f_mid < 0.0:
                low = z
            else:
                high = z
        else:
            raise ValueError("Lambert bisection did not converge within 120 iterations")
    z = 0.5*(low+high)
    time_residual, y = residual(z)
    c, _ = _stumpff(z)
    f_lagrange = 1.0-y/r1
    g_lagrange = a_geom*math.sqrt(y/mu)
    gdot = 1.0-y/r2
    if abs(g_lagrange) < 1e-14:
        raise ValueError("Lambert Lagrange g coefficient is singular")
    v1 = [(r2_vec[i]-f_lagrange*r1_vec[i])/g_lagrange for i in range(3)]
    v2 = [(gdot*r2_vec[i]-r1_vec[i])/g_lagrange for i in range(3)]
    return {"departure_velocity_m_s": v1, "arrival_velocity_m_s": v2,
            "universal_variable_z": z, "iterations": iterations,
            "time_residual_s": time_residual/math.sqrt(mu),
            "transfer_angle_rad": math.atan2(sine, cosine) % (2.0*math.pi)}


def propagate_kepler_universal(r0_vec: list[float], v0_vec: list[float],
                               elapsed_s: float, mu: float) -> tuple[list[float], list[float]]:
    """Propagate a two-body state with the universal anomaly and f/g functions."""
    if elapsed_s < 0.0 or not math.isfinite(elapsed_s) or mu <= 0.0:
        raise ValueError("elapsed time must be non-negative and mu positive")
    if elapsed_s == 0.0:
        return list(r0_vec), list(v0_vec)
    r0 = _norm(r0_vec)
    v02 = _dot(v0_vec, v0_vec)
    radial_velocity = _dot(r0_vec, v0_vec)/r0
    alpha = 2.0/r0-v02/mu
    sqrt_mu = math.sqrt(mu)
    x = (sqrt_mu*abs(alpha)*elapsed_s if abs(alpha) > 1e-10
         else sqrt_mu*elapsed_s/r0)

    def equation(chi: float) -> tuple[float, float]:
        z = alpha*chi*chi
        c, s = _stumpff(z)
        value = (r0*radial_velocity/sqrt_mu*chi*chi*c
                 +(1.0-alpha*r0)*chi**3*s+r0*chi-sqrt_mu*elapsed_s)
        derivative = (r0*radial_velocity/sqrt_mu*chi*(1.0-z*s)
                      +(1.0-alpha*r0)*chi*chi*c+r0)
        return value, derivative

    low = 0.0
    high = max(1.0, 2.0*abs(x))
    f_high, _ = equation(high)
    for _ in range(80):
        if f_high >= 0.0:
            break
        high *= 2.0
        f_high, _ = equation(high)
    else:
        raise ValueError("could not bracket the universal-variable Kepler root")
    x = min(high, max(low, x))
    converged = False
    for _ in range(120):
        value, derivative = equation(x)
        if abs(value) <= sqrt_mu*elapsed_s*2e-13:
            converged = True
            break
        if value < 0.0:
            low = x
        else:
            high = x
        newton = x-value/derivative if math.isfinite(derivative) and derivative > 1e-14 else math.nan
        x = newton if math.isfinite(newton) and low < newton < high else 0.5*(low+high)
        if high-low <= 2e-13*max(1.0, abs(x)):
            x = 0.5*(low+high)
            converged = True
            break
    if not converged:
        raise ValueError("universal-variable Kepler propagation did not converge")
    z = alpha*x*x
    c, s = _stumpff(z)
    f = 1.0-x*x/r0*c
    g = elapsed_s-x**3/sqrt_mu*s
    r_vec = [f*r0_vec[i]+g*v0_vec[i] for i in range(3)]
    r = _norm(r_vec)
    fdot = sqrt_mu/(r*r0)*(alpha*x**3*s-x)
    gdot = 1.0-x*x/r*c
    v_vec = [fdot*r0_vec[i]+gdot*v0_vec[i] for i in range(3)]
    return r_vec, v_vec


def _planet_position_velocity(planet_id: str, date: datetime) -> tuple[list[float], list[float]]:
    body = PLANETS[planet_id]
    jd = _julian_day(date)
    position, _ = _planet_state(body, jd)
    dt = 30.0
    before, _ = _planet_state(body, jd-dt/86400.0)
    after, _ = _planet_state(body, jd+dt/86400.0)
    velocity = [(after[i]-before[i])/(2.0*dt) for i in range(3)]
    return position, velocity


def _moon_position_velocity(moon_id: str, date: datetime) -> tuple[list[float], list[float]]:
    moon = next((row for row in MOONS if row[0] == moon_id), None)
    if moon is None:
        raise ValueError("unknown moon")
    if moon_id == "moon":
        elements = MOON_MEAN_ELEMENTS
        period_s = elements["period_days"]*86400.0
        mean_motion = 2.0*math.pi/period_s
        # UTC-to-TDB is about 64.184 s at J2000; subsequent leap-second
        # changes are a small timing approximation in this mean-element model.
        elapsed_s = ((_julian_day(date)-elements["epoch_jd_tdb"])*86400.0
                     +TDB_MINUS_UTC_J2000_S)
        mean_anomaly = math.radians(elements["mean_anomaly_j2000_deg"])+mean_motion*elapsed_s
        mean_anomaly = (mean_anomaly+math.pi)%(2.0*math.pi)-math.pi
        eccentricity = elements["eccentricity"]
        eccentric_anomaly = mean_anomaly+eccentricity*math.sin(mean_anomaly)
        for _ in range(16):
            residual = (eccentric_anomaly-eccentricity*math.sin(eccentric_anomaly)
                        -mean_anomaly)
            correction = residual/(1.0-eccentricity*math.cos(eccentric_anomaly))
            eccentric_anomaly -= correction
            if abs(correction) <= 2e-14:
                break
        else:
            raise ValueError("mean lunar Kepler equation did not converge")

        semimajor = MOON_MODEL_SEMI_MAJOR_AXIS_M
        beta = math.sqrt(1.0-eccentricity*eccentricity)
        denominator = 1.0-eccentricity*math.cos(eccentric_anomaly)
        position_pf = [semimajor*(math.cos(eccentric_anomaly)-eccentricity),
                       semimajor*beta*math.sin(eccentric_anomaly)]
        velocity_pf = [-semimajor*mean_motion*math.sin(eccentric_anomaly)/denominator,
                       semimajor*mean_motion*beta*math.cos(eccentric_anomaly)/denominator]

        omega = math.radians(elements["argument_of_periapsis_deg"])
        inclination = math.radians(elements["inclination_deg"])
        node = math.radians(elements["ascending_node_deg"])
        co, so = math.cos(node), math.sin(node)
        cw, sw = math.cos(omega), math.sin(omega)
        ci, si = math.cos(inclination), math.sin(inclination)
        rotation = (
            (co*cw-so*sw*ci, -co*sw-so*cw*ci),
            (so*cw+co*sw*ci, -so*sw+co*cw*ci),
            (sw*si, cw*si),
        )
        position = [rotation[i][0]*position_pf[0]+rotation[i][1]*position_pf[1]
                    for i in range(3)]
        velocity = [rotation[i][0]*velocity_pf[0]+rotation[i][1]*velocity_pf[1]
                    for i in range(3)]
        return position, velocity

    _, _, _, _radius_km, orbit_km, period_days, phase0_deg, _moon_mu = moon
    phase = math.radians(phase0_deg + ((_julian_day(date)-J2000_JD)/period_days*360.0))
    radius = orbit_km*1000.0
    angular_rate = 2.0*math.pi/(period_days*86400.0)
    position = [radius*math.cos(phase), radius*math.sin(phase), 0.0]
    velocity = [-angular_rate*position[1], angular_rate*position[0], 0.0]
    return position, velocity


def _normed_transfer_result(target_id: str, target_name: str, target_class: str,
                            destination_id: str, destination_name: str,
                            departure_date: datetime, arrival_date: datetime,
                            transfer_time_s: float, wait_s: float,
                            departure_delta_v: float, arrival_delta_v: float,
                            departure_v_inf: list[float], arrival_v_inf: list[float],
                            lambert: dict[str, object], trajectory: list[list[float]],
                            method: str, departure_altitude: float,
                            arrival_altitude: float, assumptions: list[str],
                            limitation: str) -> dict:
    return {"target_id": target_id, "target_name": target_name,
            "destination_id": destination_id, "destination_name": destination_name,
            "destination_class": target_class,
            "method": method, "solver": "Lambert a variabili universali · 0 rivoluzioni · bisezione",
            "departure_date_utc": departure_date.isoformat(),
            "arrival_date_utc": arrival_date.isoformat(),
            "departure_parking_altitude_m": departure_altitude,
            "arrival_parking_altitude_m": arrival_altitude,
            "departure_delta_v_m_s": departure_delta_v,
            "departure_vector_delta_v_m_s": lambert.get("departure_vector_delta_v_m_s"),
            "departure_delta_v_model": lambert.get(
                "departure_delta_v_model",
                "stima impulsiva da orbita circolare con orientamento ideale"),
            "arrival_capture_delta_v_m_s": arrival_delta_v,
            "total_delta_v_m_s": departure_delta_v+arrival_delta_v,
            "transfer_time_s": transfer_time_s,
            "transfer_time_days": transfer_time_s/86400.0,
            "next_ideal_window_days": wait_s/86400.0,
            "departure_v_infinity_m_s": (None if departure_v_inf is None
                                          else _norm(departure_v_inf)),
            "arrival_v_infinity_m_s": _norm(arrival_v_inf),
            "departure_c3_m2_s2": (
                lambert["departure_c3_m2_s2"] if "departure_c3_m2_s2" in lambert
                else _dot(departure_v_inf, departure_v_inf)),
            "lambert_iterations": lambert["iterations"],
            "lambert_time_residual_s": lambert["time_residual_s"],
            "transfer_angle_deg": math.degrees(lambert["transfer_angle_rad"]),
            "departure_position_m": lambert["departure_position_m"],
            "departure_position_local_m": lambert.get("departure_position_local_m"),
            "position_frame": lambert.get("position_frame", "eclittica eliocentrica J2000"),
            "departure_velocity_m_s": lambert["departure_velocity_m_s"],
            "velocity_frame": lambert.get("velocity_frame", "eclittica eliocentrica J2000"),
            "arrival_position_m": lambert["arrival_position_m"],
            "arrival_position_local_m": lambert.get("arrival_position_local_m"),
            "arrival_velocity_m_s": lambert["arrival_velocity_m_s"],
            "trajectory_velocity_heliocentric_m_s": lambert.get(
                "trajectory_velocity_heliocentric_m_s"),
            "propagation_model": lambert.get(
                "propagation_model", "conica universale a due corpi · Terra–Luna"),
            "targeting_iterations": lambert.get("targeting_iterations", 0),
            "targeting_position_residual_m": lambert.get(
                "targeting_position_residual_m"),
            "targeting_soi_iterations": lambert.get("soi_targeting_iterations", 0),
            "targeting_soi_boundary_residual_m": lambert.get(
                "soi_boundary_residual_m"),
            "departure_soi_radius_m": lambert.get("departure_soi_radius_m"),
            "arrival_soi_radius_m": lambert.get("arrival_soi_radius_m"),
            "soi_patch_iterations": lambert.get("soi_patch_iterations", 0),
            "soi_patch_residual_m": lambert.get("soi_patch_residual_m", 0.0),
            "trajectory_heliocentric_m": trajectory,
            "assumptions": assumptions,
            "limitation": limitation}


def _search_transfer(synodic_period_s: float, nominal_time_s: float,
                     evaluate: Any) -> dict[str, Any]:
    """Coarse launch-window/time-of-flight search followed by bounded refinement."""
    best: dict[str, Any] | None = None
    tof_min, tof_max = nominal_time_s*0.65, nominal_time_s*1.35

    def consider(wait_s: float, time_s: float) -> None:
        nonlocal best
        if wait_s < 0.0 or wait_s > synodic_period_s or not tof_min <= time_s <= tof_max:
            return
        try:
            candidate = evaluate(wait_s, time_s)
        except (ValueError, OverflowError, ZeroDivisionError):
            return
        if best is None or candidate["total_delta_v_m_s"] < best["total_delta_v_m_s"]:
            candidate["wait_s"] = wait_s
            candidate["transfer_time_s"] = time_s
            best = candidate

    dep_step = synodic_period_s/24.0
    tof_low, tof_high = nominal_time_s*0.65, nominal_time_s*1.35
    tof_step = (tof_high-tof_low)/14.0
    for i in range(25):
        for j in range(15):
            consider(i*dep_step, tof_low+j*tof_step)
    if best is None:
        raise ValueError("no converged Lambert transfer found in the search interval")
    for _ in range(3):
        center_wait, center_tof = best["wait_s"], best["transfer_time_s"]
        for i in range(-2, 3):
            for j in range(-2, 3):
                consider(center_wait+i*dep_step, center_tof+j*tof_step)
        dep_step *= 0.5
        tof_step *= 0.5
    return best


def _trajectory_samples(r0: list[float], v0: list[float], duration: float,
                        mu: float, center_body: str | None = None,
                        departure_date: datetime | None = None) -> list[list[float]]:
    samples = []
    for index in range(49):
        elapsed = duration*index/48.0
        position, _ = propagate_kepler_universal(r0, v0, elapsed, mu)
        if center_body is not None and departure_date is not None:
            center, _ = _planet_position_velocity(center_body,
                                                   departure_date+timedelta(seconds=elapsed))
            position = [position[i]+center[i] for i in range(3)]
        samples.append(position)
    return samples


def _point_mass_acceleration(position: list[float], jd: float,
                             with_gradient: bool = False):
    """Sun-centred Cowell acceleration and optional position Jacobian."""
    x, y, z = position
    radius_squared = x*x+y*y+z*z
    radius = math.sqrt(radius_squared)
    if radius <= 0.0 or not math.isfinite(radius):
        raise ValueError("spacecraft position must be finite and non-zero")
    inverse_cube = 1.0/(radius_squared*radius)
    sun_factor = -MU_SUN*inverse_cube
    ax, ay, az = sun_factor*x, sun_factor*y, sun_factor*z
    if with_gradient:
        sun_factor_5 = 3.0*MU_SUN*inverse_cube/radius_squared
        g00 = sun_factor_5*x*x-MU_SUN*inverse_cube
        g01 = sun_factor_5*x*y
        g02 = sun_factor_5*x*z
        g11 = sun_factor_5*y*y-MU_SUN*inverse_cube
        g12 = sun_factor_5*y*z
        g22 = sun_factor_5*z*z-MU_SUN*inverse_cube
    for body_mu, body_position in zip(_PLANET_MUS, _planet_positions_at_jd(jd)):
        bx, by, bz = body_position
        dx, dy, dz = bx-x, by-y, bz-z
        distance_squared = dx*dx+dy*dy+dz*dz
        distance = math.sqrt(distance_squared)
        body_radius_squared = bx*bx+by*by+bz*bz
        if distance <= 0.0 or body_radius_squared <= 0.0:
            raise ValueError("point-mass ephemeris contains a collision singularity")
        direct = body_mu/(distance_squared*distance)
        indirect = body_mu/(body_radius_squared*math.sqrt(body_radius_squared))
        ax += direct*dx-indirect*bx
        ay += direct*dy-indirect*by
        az += direct*dz-indirect*bz
        if with_gradient:
            inverse_fifth = 3.0*direct/distance_squared
            g00 += inverse_fifth*dx*dx-direct
            g01 += inverse_fifth*dx*dy
            g02 += inverse_fifth*dx*dz
            g11 += inverse_fifth*dy*dy-direct
            g12 += inverse_fifth*dy*dz
            g22 += inverse_fifth*dz*dz-direct
    acceleration = [ax, ay, az]
    if not with_gradient:
        return acceleration
    return acceleration, [[g00, g01, g02], [g01, g11, g12], [g02, g12, g22]]


def _point_mass_derivative(state: list[float], jd: float) -> list[float]:
    with_variational = len(state) == 24
    acceleration, gradient = (_point_mass_acceleration(state[:3], jd, True)
                              if with_variational else
                              (_point_mass_acceleration(state[:3], jd), None))
    derivative = [state[3], state[4], state[5], *acceleration]
    if not with_variational:
        return derivative
    b0,b1,b2,b3,b4,b5,b6,b7,b8 = state[6:15]
    a0,a1,a2,a3,a4,a5,a6,a7,a8 = state[15:24]
    g00,g01,g02 = gradient[0]
    g10,g11,g12 = gradient[1]
    g20,g21,g22 = gradient[2]
    derivative.extend((a0,a1,a2,a3,a4,a5,a6,a7,a8,
                       g00*b0+g01*b3+g02*b6,
                       g00*b1+g01*b4+g02*b7,
                       g00*b2+g01*b5+g02*b8,
                       g10*b0+g11*b3+g12*b6,
                       g10*b1+g11*b4+g12*b7,
                       g10*b2+g11*b5+g12*b8,
                       g20*b0+g21*b3+g22*b6,
                       g20*b1+g21*b4+g22*b7,
                       g20*b2+g21*b5+g22*b8))
    return derivative


def _point_mass_rk4_step(state: list[float], jd: float,
                         step_s: float) -> list[float]:
    """Classical RK4 step; time is measured in seconds from a J2000 date."""
    h_days = step_s/86400.0
    dimensions = len(state)
    k1 = _point_mass_derivative(state, jd)
    k2 = _point_mass_derivative(
        [state[i]+0.5*step_s*k1[i] for i in range(dimensions)], jd+0.5*h_days)
    k3 = _point_mass_derivative(
        [state[i]+0.5*step_s*k2[i] for i in range(dimensions)], jd+0.5*h_days)
    k4 = _point_mass_derivative(
        [state[i]+step_s*k3[i] for i in range(dimensions)], jd+h_days)
    return [state[i]+step_s/6.0*(k1[i]+2.0*k2[i]+2.0*k3[i]+k4[i])
            for i in range(dimensions)]


def _integrate_point_mass(r0: list[float], v0: list[float], duration_s: float,
                          departure: datetime, sample_count: int = 2,
                          max_step_s: float = 86_400.0,
                          with_variational: bool = False
                          ) -> list[list[float]]:
    """Integrate heliocentric states with RK4 and bounded steps near planets.

    The integrator shortens its step within twice any planet's Laplace SOI.
    Returned rows are exact integration states at equally spaced mission times.
    """
    if (duration_s <= 0.0 or sample_count < 2 or max_step_s <= 0.0 or
            not all(math.isfinite(x) for x in (*r0, *v0, duration_s, max_step_s))):
        raise ValueError("point-mass integration requires finite positive inputs")
    epoch_jd = _julian_day(departure)
    boundaries = [duration_s*i/(sample_count-1) for i in range(sample_count)]
    state = [*r0, *v0]
    if with_variational:
        state.extend([0.0]*9)
        state.extend([1.0 if i in (0, 4, 8) else 0.0 for i in range(9)])
    samples = [state[:]]
    elapsed = 0.0
    steps = 0
    proximity = [(body[13], _sphere_of_influence(body[1]*AU_M,
                                                  body[13], MU_SUN)*2.0)
                 for body in PLANETS.values()]
    for target_time in boundaries[1:]:
        while elapsed < target_time-1e-8:
            jd = epoch_jd+elapsed/86400.0
            step = min(max_step_s, target_time-elapsed)
            position = state[:3]
            for body_position, (_, near_radius) in zip(
                    _planet_positions_at_jd(jd), proximity):
                distance = _norm([position[i]-body_position[i] for i in range(3)])
                if distance < near_radius:
                    step = min(step, 7_200.0)
            if step <= 0.0 or not math.isfinite(step):
                raise ValueError("point-mass integrator produced an invalid step")
            state = _point_mass_rk4_step(state, jd, step)
            elapsed += step
            steps += 1
            if steps > 1_000_000 or not all(math.isfinite(x) for x in state):
                raise ValueError("point-mass RK4 propagation failed to remain finite")
        elapsed = target_time
        samples.append(state[:])
    return samples


def _solve_linear_3x3(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve a 3×3 dense system with partial-pivot Gaussian elimination."""
    augmented = [row[:]+[rhs[i]] for i, row in enumerate(matrix)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-15:
            raise ValueError("trajectory targeting Jacobian is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [x/scale for x in augmented[column]]
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [augmented[row][i]-factor*augmented[column][i]
                              for i in range(4)]
    return [augmented[i][3] for i in range(3)]


def _target_point_mass_transfer(r0: list[float], v0: list[float], r_target: list[float],
                                duration_s: float, departure: datetime
                                ) -> dict[str, Any]:
    """Shoot a Sun+planets Cowell arc using its integrated state transition matrix."""
    velocity = v0[:]
    correction_iterations = 0
    endpoint = None
    residual_m = math.inf
    for correction_iterations in range(1, 11):
        states = _integrate_point_mass(r0, velocity, duration_s, departure,
                                       sample_count=97, with_variational=True)
        baseline = states[-1]
        residual = [baseline[i]-r_target[i] for i in range(3)]
        residual_m = _norm(residual)
        endpoint = baseline
        if residual_m <= 100.0:
            break
        # The integrated STM block d(r_final)/d(v_initial) is the exact
        # Jacobian of this discretized Cowell propagation, avoiding extra
        # perturbed trajectory integrations and finite-difference noise.
        jacobian = [baseline[6+row*3:6+(row+1)*3] for row in range(3)]
        correction = _solve_linear_3x3(jacobian, [-value for value in residual])
        correction_norm = _norm(correction)
        if not math.isfinite(correction_norm):
            raise ValueError("trajectory targeting returned a non-finite correction")
        if correction_norm > 5_000.0:
            correction = [value*5_000.0/correction_norm for value in correction]
        velocity = [velocity[i]+correction[i] for i in range(3)]
    else:
        raise ValueError(f"N-body transfer targeting did not converge (residual {residual_m:.3g} m)")

    if endpoint is None or residual_m > 100.0:
        raise ValueError(f"N-body transfer targeting residual exceeds 100 m ({residual_m:.3g} m)")
    residual_m = _norm([endpoint[i]-r_target[i] for i in range(3)])
    if residual_m > 100.0:
        raise ValueError(f"N-body trajectory samples miss arrival boundary by {residual_m:.3g} m")
    return {"departure_velocity_m_s": velocity,
            "arrival_velocity_m_s": endpoint[3:6],
            "trajectory_heliocentric_m": [row[:3] for row in states],
            "trajectory_velocity_heliocentric_m_s": [row[3:6] for row in states],
            "correction_iterations": correction_iterations,
            "terminal_position_residual_m": residual_m}


def _target_patched_point_mass_transfer(
        lambert: dict[str, Any], departure_center: list[float],
        departure_center_velocity: list[float], departure_soi_m: float,
        arrival_center: list[float], arrival_center_velocity: list[float],
        arrival_soi_m: float, duration_s: float, departure: datetime
        ) -> dict[str, Any]:
    """Close both endpoint positions and asymptote directions under Cowell gravity."""
    start = lambert["departure_position_m"][:]
    target = lambert["arrival_position_m"][:]
    velocity = lambert["departure_velocity_m_s"][:]
    tolerance_m = max(10_000.0, max(departure_soi_m, arrival_soi_m)*1e-4)
    for soi_iteration in range(1, 9):
        solution = _target_point_mass_transfer(start, velocity, target,
                                              duration_s, departure)
        departure_v_inf = [solution["departure_velocity_m_s"][i]
                           -departure_center_velocity[i] for i in range(3)]
        arrival_v_inf = [solution["arrival_velocity_m_s"][i]
                         -arrival_center_velocity[i] for i in range(3)]
        next_start = [departure_center[i]+departure_soi_m*_unit(departure_v_inf)[i]
                      for i in range(3)]
        next_target = [arrival_center[i]-arrival_soi_m*_unit(arrival_v_inf)[i]
                       for i in range(3)]
        boundary_residual_m = max(_norm([next_start[i]-start[i] for i in range(3)]),
                                  _norm([next_target[i]-target[i] for i in range(3)]))
        if boundary_residual_m <= tolerance_m:
            solution.update({"departure_position_m": start,
                             "arrival_position_m": target,
                             "soi_targeting_iterations": soi_iteration,
                             "soi_boundary_residual_m": boundary_residual_m})
            return solution
        start, target = next_start, next_target
        velocity = solution["departure_velocity_m_s"]
    raise ValueError(
        f"N-body SOI direction patch did not converge (residual {boundary_residual_m:.3g} m)")


def transfer_plan(target_id: str, date_text: str | None = None) -> dict:
    """Search a Lambert seed and build a targeted transfer design from Earth.

    Departure opportunities and flight times are searched near the circular
    Hohmann duration. The selected planetary trajectory is corrected and
    integrated in the Sun-centred point-mass model. Earth–Moon remains a
    geocentric two-body arc. Parking-orbit departure/capture estimates remain
    impulsive patched conics.
    """
    epoch = _parse_date(date_text)
    catalog = celestial_catalog(epoch.isoformat())
    lookup = {obj["id"]: obj for obj in catalog["objects"]}
    if target_id not in lookup or target_id in {"sun", "earth"}:
        raise ValueError("target must be a celestial destination other than the Sun or Earth")
    target = lookup[target_id]
    earth = lookup["earth"]
    earth_park_r = EARTH_RADIUS+250_000.0
    earth_park_v = math.sqrt(MU_EARTH/earth_park_r)

    if target["class"] == "moon" and target["parent_id"] == "earth":
        moon_id = target_id
        moon_park_r = target["radius_m"]+100_000.0
        moon_park_v = math.sqrt(target["mu_m3_s2"]/moon_park_r)
        period = target["period_s"]
        nominal_a = 0.5*(earth_park_r+target["semi_major_axis_m"])
        nominal_tof = math.pi*math.sqrt(nominal_a**3/MU_EARTH)

        def evaluate(wait_s: float, tof_s: float) -> dict[str, Any]:
            departure = epoch+timedelta(seconds=wait_s)
            arrival = departure+timedelta(seconds=tof_s)
            moon_r, moon_v = _moon_position_velocity(moon_id, arrival)
            r_park = [earth_park_r, 0.0, 0.0]
            v_park = [0.0, earth_park_v, 0.0]
            moon_soi = _sphere_of_influence(
                target["semi_major_axis_m"], target["mu_m3_s2"], MU_EARTH)
            arrival_soi_position = list(moon_r)
            patch_tolerance = max(1.0, moon_soi*1e-8)
            solution = None
            patch_residual = math.inf
            for patch_iteration in range(1, 13):
                solution = lambert_universal(r_park, arrival_soi_position,
                                             tof_s, MU_EARTH)
                arrival_v_inf = [solution["arrival_velocity_m_s"][i]-moon_v[i]
                                 for i in range(3)]
                arrival_vinf = _norm(arrival_v_inf)
                if arrival_vinf <= 1e-9:
                    raise ValueError("lunar Lambert solution has zero arrival excess speed")
                patched_position = [moon_r[i]-moon_soi*arrival_v_inf[i]/arrival_vinf
                                    for i in range(3)]
                patch_residual = _norm([patched_position[i]-arrival_soi_position[i]
                                        for i in range(3)])
                arrival_soi_position = patched_position
                if patch_residual <= patch_tolerance:
                    solution = lambert_universal(r_park, arrival_soi_position,
                                                 tof_s, MU_EARTH)
                    arrival_v_inf = [solution["arrival_velocity_m_s"][i]-moon_v[i]
                                     for i in range(3)]
                    arrival_vinf = _norm(arrival_v_inf)
                    consistency = [moon_r[i]-moon_soi*arrival_v_inf[i]/arrival_vinf
                                   for i in range(3)]
                    patch_residual = _norm([consistency[i]-arrival_soi_position[i]
                                           for i in range(3)])
                    if patch_residual <= patch_tolerance*2.0:
                        break
            else:
                raise ValueError("lunar Lambert sphere-of-influence patch did not converge")
            assert solution is not None
            departure_v = solution["departure_velocity_m_s"]
            arrival_v = solution["arrival_velocity_m_s"]
            departure_dv_vec = [departure_v[i]-v_park[i] for i in range(3)]
            arrival_v_inf = [arrival_v[i]-moon_v[i] for i in range(3)]
            arrival_vinf = _norm(arrival_v_inf)
            arrival_dv = math.sqrt(arrival_vinf**2+2*target["mu_m3_s2"]/moon_park_r)-moon_park_v
            departure_vector_delta_v = _norm(departure_dv_vec)
            # The displayed trajectory starts from this exact fixed LEO state.
            # Use the matching vector impulse in the budget rather than the lower,
            # phase-optimized scalar minimum, which would not produce this arc.
            departure_delta_v = departure_vector_delta_v
            return {"total_delta_v_m_s": departure_delta_v+arrival_dv,
                    "departure_delta_v_m_s": departure_delta_v,
                    "arrival_delta_v_m_s": arrival_dv,
                    "departure_v_inf": None,
                    "arrival_v_inf": arrival_v_inf,
                    "lambert": {**solution, "departure_position_m": r_park,
                                "departure_velocity_m_s": departure_v,
                                "departure_vector_delta_v_m_s": departure_vector_delta_v,
                                "departure_delta_v_model": (
                                    "impulso vettoriale da stato circolare LEO fissato a 250 km; "
                                    "fase e piano orbitali non ottimizzati"),
                                "arrival_position_m": arrival_soi_position,
                                "arrival_velocity_m_s": arrival_v,
                                "departure_soi_radius_m": 0.0,
                                "arrival_soi_radius_m": moon_soi,
                                "soi_patch_iterations": patch_iteration,
                                "soi_patch_residual_m": patch_residual,
                                "position_frame": "eclittica eliocentrica J2000",
                                "velocity_frame": "inerziale geocentrico · eclittica J2000",
                                "departure_c3_m2_s2": None}}

        best = _search_transfer(period, nominal_tof, evaluate)
        departure = epoch+timedelta(seconds=best["wait_s"])
        arrival = departure+timedelta(seconds=best["transfer_time_s"])
        earth_r0, _ = _planet_position_velocity("earth", departure)
        earth_r1, _ = _planet_position_velocity("earth", arrival)
        departure_local = list(best["lambert"]["departure_position_m"])
        arrival_local = list(best["lambert"]["arrival_position_m"])
        trajectory = _trajectory_samples(best["lambert"]["departure_position_m"],
                                         best["lambert"]["departure_velocity_m_s"],
                                         best["transfer_time_s"], MU_EARTH,
                                         "earth", departure)
        best["lambert"]["departure_position_local_m"] = departure_local
        best["lambert"]["arrival_position_local_m"] = arrival_local
        best["lambert"]["departure_position_m"] = [earth_r0[i]+departure_local[i]
                                                    for i in range(3)]
        best["lambert"]["arrival_position_m"] = [earth_r1[i]+arrival_local[i]
                                                  for i in range(3)]
        return _normed_transfer_result(
            target_id, target["name"], "moon", target_id, target["name"],
            departure, arrival, best["transfer_time_s"], best["wait_s"],
            best["departure_delta_v_m_s"], best["arrival_delta_v_m_s"],
            best["departure_v_inf"], best["arrival_v_inf"], best["lambert"], trajectory,
            "Earth–Moon · Lambert two-body to lunar SOI · LEO departure and capture estimate",
            250_000.0, 100_000.0,
            ["Earth-centred Lambert arc from a 250 km parking orbit to the lunar Laplace SOI",
             "capture delta-v estimated for a circular 100 km lunar parking orbit",
             "impulsive departure/capture; no launch ascent or powered surface landing"],
            ("La Luna è propagata con un modello kepleriano a due corpi inizializzato da "
             "elementi medi JPL DE405/LE405 (non è un'effemeride JPL/Horizons). "
             "Sono omesse le perturbazioni solari di terzo corpo, la rotazione terrestre, "
             "la ricerca del piano di partenza, la spinta finita e la discesa sulla superficie."))

    destination = target
    moon_note = ""
    if target["class"] == "moon":
        destination = lookup[target["parent_id"]]
        moon_note = (f"Il trasferimento calcolato arriva al sistema di {destination['name']}; "
                     f"il tratto da {destination['name']} a {target['name']} non è incluso.")
    destination_id = destination["id"]
    target_radius = destination["semi_major_axis_m"]
    earth_radius = earth["semi_major_axis_m"]
    nominal_a = 0.5*(earth_radius+target_radius)
    nominal_tof = math.pi*math.sqrt(nominal_a**3/MU_SUN)
    mean_earth = math.sqrt(MU_SUN/earth_radius**3)
    mean_target = math.sqrt(MU_SUN/target_radius**3)
    synodic = 2.0*math.pi/abs(mean_target-mean_earth)
    target_park_r = destination["radius_m"]+300_000.0
    target_park_v = math.sqrt(destination["mu_m3_s2"]/target_park_r)
    earth_soi = _sphere_of_influence(earth["semi_major_axis_m"], MU_EARTH, MU_SUN)
    destination_soi = _sphere_of_influence(
        destination["semi_major_axis_m"], destination["mu_m3_s2"], MU_SUN)

    def evaluate_planet(wait_s: float, tof_s: float) -> dict[str, Any]:
        departure = epoch+timedelta(seconds=wait_s)
        arrival = departure+timedelta(seconds=tof_s)
        r_earth, v_earth = _planet_position_velocity("earth", departure)
        r_target, v_target = _planet_position_velocity(destination_id, arrival)
        solution = _lambert_between_soi_boundaries(
            r_earth, v_earth, earth_soi, r_target, v_target,
            destination_soi, tof_s, MU_SUN)
        departure_v = solution["departure_velocity_m_s"]
        arrival_v = solution["arrival_velocity_m_s"]
        departure_v_inf = solution["departure_v_infinity_vector_m_s"]
        arrival_v_inf = solution["arrival_v_infinity_vector_m_s"]
        departure_vinf = _norm(departure_v_inf)
        arrival_vinf = _norm(arrival_v_inf)
        departure_dv = math.sqrt(departure_vinf**2+2*MU_EARTH/earth_park_r)-earth_park_v
        arrival_dv = math.sqrt(arrival_vinf**2+2*destination["mu_m3_s2"]/target_park_r)-target_park_v
        return {"total_delta_v_m_s": departure_dv+arrival_dv,
                "departure_delta_v_m_s": departure_dv,
                "arrival_delta_v_m_s": arrival_dv,
                "departure_v_inf": departure_v_inf,
                "arrival_v_inf": arrival_v_inf,
                "lambert": {**solution, "departure_delta_v_model": (
                    "stima impulsiva da orbita circolare LEO con orientamento ideale "
                    "dell'asintoto iperbolico")}}

    best = _search_transfer(synodic, nominal_tof, evaluate_planet)
    departure = epoch+timedelta(seconds=best["wait_s"])
    arrival = departure+timedelta(seconds=best["transfer_time_s"])
    lambert = best["lambert"]
    departure_center, departure_body_velocity = _planet_position_velocity("earth", departure)
    arrival_center, arrival_body_velocity = _planet_position_velocity(destination_id, arrival)
    targeted = _target_patched_point_mass_transfer(
        lambert, departure_center, departure_body_velocity, earth_soi,
        arrival_center, arrival_body_velocity, destination_soi,
        best["transfer_time_s"], departure)
    departure_position = targeted["departure_position_m"]
    arrival_position = targeted["arrival_position_m"]
    departure_velocity = targeted["departure_velocity_m_s"]
    arrival_velocity = targeted["arrival_velocity_m_s"]
    departure_v_inf = [departure_velocity[i]-departure_body_velocity[i]
                       for i in range(3)]
    arrival_v_inf = [arrival_velocity[i]-arrival_body_velocity[i]
                     for i in range(3)]
    departure_vinf = _norm(departure_v_inf)
    arrival_vinf = _norm(arrival_v_inf)
    departure_delta_v = math.sqrt(departure_vinf**2+2.0*MU_EARTH/earth_park_r)-earth_park_v
    arrival_delta_v = (math.sqrt(arrival_vinf**2+
                                 2.0*destination["mu_m3_s2"]/target_park_r)
                       -target_park_v)
    lambert.update({"departure_position_m": departure_position,
                    "arrival_position_m": arrival_position,
                    "departure_velocity_m_s": departure_velocity,
                    "arrival_velocity_m_s": arrival_velocity,
                    "departure_v_infinity_vector_m_s": departure_v_inf,
                    "arrival_v_infinity_vector_m_s": arrival_v_inf,
                    "departure_c3_m2_s2": _dot(departure_v_inf, departure_v_inf),
                    "trajectory_velocity_heliocentric_m_s":
                        targeted["trajectory_velocity_heliocentric_m_s"],
                    "propagation_model": (
                        "Cowell RK4 · gravità puntiforme Sole + 8 pianeti · correzione differenziale"),
                    "targeting_iterations": targeted["correction_iterations"],
                    "targeting_position_residual_m":
                        targeted["terminal_position_residual_m"],
                    "soi_targeting_iterations": targeted["soi_targeting_iterations"],
                    "soi_boundary_residual_m": targeted["soi_boundary_residual_m"]})
    trajectory = targeted["trajectory_heliocentric_m"]
    validity_note = ""
    if arrival.year > 2050:
        validity_note = " L’arrivo è oltre il 2050, fuori dall’intervallo di validità dichiarato degli elementi planetari JPL approssimati."
    limitation = (moon_note or
                  ("L’arco interplanetario usa RK4 Cowell con Sole e otto pianeti come masse puntiformi; "
                   "la velocità iniziale viene corretta per chiudere sulla SOI d’arrivo. "
                   "Gli elementi JPL sono approssimati (1800–2050) e la ricerca della finestra resta una griglia Lambert. "
                   "I budget LEO/cattura sono stime patched-conic impulsive; non sono inclusi lune perturbatrici, "
                   "relatività, corpi minori, manovre finite, TCM, aerobraking o atterraggio."+validity_note))
    return _normed_transfer_result(
        target_id, target["name"], target["class"], destination_id, destination["name"],
        departure, arrival, best["transfer_time_s"], best["wait_s"],
        departure_delta_v, arrival_delta_v,
        departure_v_inf, arrival_v_inf, lambert, trajectory,
        "Lambert seed · Cowell Sun+8 planets · corrected shooting · patched-conic burns",
        250_000.0, 300_000.0,
        ["JPL approximate planetary position/velocity at the selected epochs",
         "Sun plus eight point-mass planets integrated with fourth-order Cowell RK4",
         "initial velocity differentially corrected to the Laplace SOI arrival boundary",
         "Laplace sphere-of-influence radii and circular parking-orbit burn estimates",
         "departure date and time of flight searched near the Hohmann duration"],
        limitation,
    )


def transfer_state(plan: dict[str, Any], elapsed_s: float) -> dict[str, Any]:
    """Return a mission state on the corrected trajectory at elapsed time.

    Planetary states use cubic Hermite interpolation through integrated Cowell
    RK4 samples. Earth–Moon states use universal-variable two-body propagation.
    Neither path models a powered spacecraft or closed-loop GNC.
    """
    try:
        elapsed = float(elapsed_s)
        duration = float(plan["transfer_time_s"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("a transfer plan and finite elapsed_s are required") from exc
    if not math.isfinite(elapsed) or not math.isfinite(duration):
        raise ValueError("elapsed_s and transfer duration must be finite")
    if duration <= 0.0 or elapsed < 0.0 or elapsed > duration:
        raise ValueError("elapsed_s must lie between departure and arrival")

    departure = _parse_date(plan["departure_date_utc"])
    epoch = departure+timedelta(seconds=elapsed)
    if plan.get("target_id") == "moon":
        local_position, local_velocity = propagate_kepler_universal(
            plan["departure_position_local_m"],
            plan["departure_velocity_m_s"], elapsed, MU_EARTH)
        earth_position, earth_velocity = _planet_position_velocity("earth", epoch)
        position_heliocentric = [earth_position[i]+local_position[i] for i in range(3)]
        velocity_heliocentric = [earth_velocity[i]+local_velocity[i] for i in range(3)]
        position_local = local_position
        velocity = local_velocity
        central_body = "earth"
        central_mu = MU_EARTH
        propagator = "universal anomaly · f/g two-body · geocentrico"
    else:
        samples = plan.get("trajectory_heliocentric_m", [])
        velocity_samples = plan.get("trajectory_velocity_heliocentric_m_s", [])
        if len(samples) >= 2 and len(samples) == len(velocity_samples):
            scaled = elapsed/duration*(len(samples)-1)
            index = min(len(samples)-2, int(scaled))
            fraction = min(1.0, max(0.0, scaled-index))
            segment_s = duration/(len(samples)-1)
            u, u2, u3 = fraction, fraction*fraction, fraction*fraction*fraction
            h00, h10 = 2*u3-3*u2+1, u3-2*u2+u
            h01, h11 = -2*u3+3*u2, u3-u2
            position_heliocentric = [
                h00*samples[index][i]+h10*segment_s*velocity_samples[index][i]
                +h01*samples[index+1][i]
                +h11*segment_s*velocity_samples[index+1][i] for i in range(3)]
            dh00, dh10 = 6*u2-6*u, 3*u2-4*u+1
            dh01, dh11 = -dh00, 3*u2-2*u
            velocity_heliocentric = [
                (dh00*samples[index][i]+dh01*samples[index+1][i])/segment_s
                +dh10*velocity_samples[index][i]
                +dh11*velocity_samples[index+1][i] for i in range(3)]
        else:
            position_heliocentric, velocity_heliocentric = propagate_kepler_universal(
                plan["departure_position_m"], plan["departure_velocity_m_s"],
                elapsed, MU_SUN)
        position_local = None
        velocity = velocity_heliocentric
        central_body = "sun"
        central_mu = MU_SUN
        propagator = plan.get("propagation_model", "universal anomaly · f/g two-body")

    return {
        "target_id": plan["target_id"],
        "destination_id": plan["destination_id"],
        "elapsed_s": elapsed,
        "fraction_complete": elapsed/duration,
        "time_to_arrival_s": duration-elapsed,
        "epoch_utc": epoch.isoformat(),
        "position_heliocentric_m": position_heliocentric,
        "position_local_m": position_local,
        "velocity_m_s": velocity,
        "velocity_heliocentric_m_s": velocity_heliocentric,
        "position_frame": plan["position_frame"],
        "velocity_frame": plan["velocity_frame"],
        "central_body": central_body,
        "central_mu_m3_s2": central_mu,
        "propagator": propagator,
    }
