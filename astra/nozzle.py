"""Ideal calorically-perfect-gas converging-diverging rocket nozzle design.

Steady 1-D perfect-gas equations with subsonic/supersonic Mach inversion
and an internal normal-shock branch. No chemistry or viscous separation model.
"""
from __future__ import annotations

import math

from .atmosphere import atmosphere_isa
from .constants import G0


def _positive(payload, key, default, low, high):
    raw=payload.get(key,default)
    if isinstance(raw,bool):raise ValueError(f'{key} must be numeric')
    try:v=float(raw)
    except (ValueError,TypeError) as exc:raise ValueError(f'{key} must be numeric') from exc
    if not math.isfinite(v) or not low<=v<=high:
        raise ValueError(f'{key} must be between {low} and {high}')
    return v


def _area_ratio(mach, gamma):
    return ((2/(gamma+1)*(1+(gamma-1)*mach*mach/2))**((gamma+1)/(2*(gamma-1)))/mach)


def _mach_for_ratio(ratio, gamma):
    if ratio<=1:return 1.
    lo,hi=1.,30.
    if _area_ratio(hi,gamma)<ratio:raise ValueError('expansion ratio beyond solver range')
    for _ in range(90):
        mid=.5*(lo+hi)
        if _area_ratio(mid,gamma)<ratio:lo=mid
        else:hi=mid
    return .5*(lo+hi)


def _subsonic_mach(ratio, gamma):
    if ratio < 1.0-1e-10:
        raise ValueError('area/Astar must be at least one')
    if ratio <= 1.0:
        return 1.0
    lo, hi = 1e-12, 1.0
    for _ in range(90):
        mid = (lo+hi)/2
        if _area_ratio(mid, gamma) > ratio:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def _shock_exit(shock_area_ratio, expansion, gamma, chamber_p):
    """Return exit Mach, exit p, downstream total p for a shock at As/At."""
    m1 = _mach_for_ratio(shock_area_ratio, gamma)
    m2 = math.sqrt((1+(gamma-1)*m1*m1/2)/(gamma*m1*m1-(gamma-1)/2))
    total_ratio = (((gamma+1)*m1*m1/((gamma-1)*m1*m1+2))**(gamma/(gamma-1))
                   *((gamma+1)/(2*gamma*m1*m1-(gamma-1)))**(1/(gamma-1)))
    total_p = chamber_p*total_ratio
    exit_mach = _subsonic_mach(expansion/shock_area_ratio*_area_ratio(m2,gamma),gamma)
    pe = total_p*(1+(gamma-1)*exit_mach**2/2)**(-gamma/(gamma-1))
    return exit_mach, pe, total_p


def nozzle_design(payload:dict) -> dict:
    gamma=_positive(payload,'specific_heat_ratio',1.22,1.05,1.67)
    gas=_positive(payload,'gas_constant_J_kgK',355.,50,2000)
    chamber_p=_positive(payload,'chamber_pressure_Pa',7e6,1e4,2e8)
    chamber_t=_positive(payload,'chamber_temperature_K',3400,100,10000)
    throat=_positive(payload,'throat_area_m2',.03,1e-7,100)
    expansion=_positive(payload,'expansion_ratio',16,1,200)
    altitude=_positive(payload,'altitude_m',0,0,1000000)
    # COESA76 is defined only through 1000 km.
    ambient=float(atmosphere_isa(altitude)['pressure_Pa'])
    if ambient >= chamber_p:
        raise ValueError('chamber total pressure must exceed ambient; reverse flow is not modeled')
    pstar=chamber_p*(2/(gamma+1))**(gamma/(gamma-1))
    mach=_mach_for_ratio(expansion,gamma)
    critical_exit=chamber_p*(1+(gamma-1)*_subsonic_mach(expansion,gamma)**2/2)**(-gamma/(gamma-1))
    shock_exit_pressure=_shock_exit(expansion,expansion,gamma,chamber_p)[1]
    regime='CHOKED_SUPERSONIC';shock_area=None;exit_total_p=chamber_p;throat_mach=1.
    if ambient > critical_exit:
        regime='UNCHOKED_SUBSONIC'
        mach=math.sqrt(2/(gamma-1)*((chamber_p/ambient)**((gamma-1)/gamma)-1))
        throat_mach=_subsonic_mach(_area_ratio(mach,gamma)/expansion,gamma)
    elif ambient > shock_exit_pressure:
        regime='CHOKED_INTERNAL_NORMAL_SHOCK'
        lo,hi=1.,expansion
        for _ in range(90):
            mid=(lo+hi)/2
            if _shock_exit(mid,expansion,gamma,chamber_p)[1]>ambient:lo=mid
            else:hi=mid
        shock_area=(lo+hi)/2
        mach,_,exit_total_p=_shock_exit(shock_area,expansion,gamma,chamber_p)
    ratio=(1+ (gamma-1)*mach**2/2)
    pe=exit_total_p*ratio**(-gamma/(gamma-1))
    te=chamber_t/ratio
    ve=mach*math.sqrt(gamma*gas*te)
    mdot=throat*chamber_p*math.sqrt(gamma/(gas*chamber_t))*(2/(gamma+1))**((gamma+1)/(2*(gamma-1)))
    if regime=='UNCHOKED_SUBSONIC':
        mdot*=throat_mach*(1+(gamma-1)*throat_mach**2/2)**(-(gamma+1)/(2*(gamma-1)))/(2/(gamma+1))**((gamma+1)/(2*(gamma-1)))
    area_exit=throat*expansion
    ideal_thrust=mdot*ve+(pe-ambient)*area_exit
    if ambient>=pstar:
        optimal_area_ratio=1.
    else:
        # Pressure-matched expansion maximizes ideal nozzle momentum+pressure thrust.
        matched_mach=math.sqrt(max(1., 2/(gamma-1)*((chamber_p/ambient)**((gamma-1)/gamma)-1))) if ambient>0 else 30.
        optimal_area_ratio=min(200.,_area_ratio(matched_mach,gamma))
    separation_warning=ambient>0 and (pe<.4*ambient or regime=='CHOKED_INTERNAL_NORMAL_SHOCK')
    continuity_flow=pe/(gas*te)*ve*area_exit
    return {'solver':'steady 1-D perfect-gas Laval nozzle with bracketed Mach roots and internal normal shock',
            'flow_regime':regime,'throat_mach':throat_mach,
            'shock_area_over_throat_area':shock_area,
            'exit_total_pressure_Pa':exit_total_p,
            'critical_back_pressure_Pa':critical_exit,
            'mass_continuity_relative_residual':abs(continuity_flow-mdot)/max(mdot,1e-30),
            'exit_mach':mach,'exit_pressure_Pa':pe,'exit_temperature_K':te,
            'exit_velocity_m_s':ve,'exhaust_mass_flow_kg_s':mdot,
            'ideal_thrust_N':ideal_thrust,'ideal_isp_s':ideal_thrust/(mdot*G0),
            'thrust_coefficient':ideal_thrust/(chamber_p*throat),
            'ambient_pressure_Pa':ambient,'exit_area_m2':area_exit,
            'ideal_pressure_matched_expansion_ratio_capped_200':optimal_area_ratio,
            'risk_of_overexpanded_flow_separation':separation_warning,
            'limits':'Steady 1-D calorically perfect gas; inviscid internal normal shock where required by back pressure. No combustion chemistry, boundary layers, oblique shock train, startup or viscous flow separation. Flagged shock/separation thrust is an ideal 1-D reference, not engine performance data.'}
