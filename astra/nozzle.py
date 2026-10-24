"""Ideal calorically-perfect-gas converging-diverging rocket nozzle design.

Steady isentropic 1-D equations with bracketed supersonic Mach inversion.
No chemistry, shocks, viscous losses, wall heating or flow separation models.
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
    pstar=chamber_p*(2/(gamma+1))**(gamma/(gamma-1))
    if pstar<=ambient:
        raise ValueError('chamber pressure insufficient for choked isentropic nozzle flow at this altitude')
    mach=_mach_for_ratio(expansion,gamma)
    ratio=(1+ (gamma-1)*mach**2/2)
    pe=chamber_p*ratio**(-gamma/(gamma-1))
    te=chamber_t/ratio
    ve=mach*math.sqrt(gamma*gas*te)
    mdot=throat*chamber_p*math.sqrt(gamma/(gas*chamber_t))*(2/(gamma+1))**((gamma+1)/(2*(gamma-1)))
    area_exit=throat*expansion
    ideal_thrust=mdot*ve+(pe-ambient)*area_exit
    if ambient>=pstar:
        optimal_area_ratio=1.
    else:
        # Pressure-matched expansion maximizes ideal nozzle momentum+pressure thrust.
        matched_mach=math.sqrt(max(1., 2/(gamma-1)*((chamber_p/ambient)**((gamma-1)/gamma)-1))) if ambient>0 else 30.
        optimal_area_ratio=min(200.,_area_ratio(matched_mach,gamma))
    separation_warning=ambient>0 and pe<.4*ambient
    return {'solver':'steady 1-D compressible isentropic nozzle + bracketed supersonic Mach root',
            'exit_mach':mach,'exit_pressure_Pa':pe,'exit_temperature_K':te,
            'exit_velocity_m_s':ve,'exhaust_mass_flow_kg_s':mdot,
            'ideal_thrust_N':ideal_thrust,'ideal_isp_s':ideal_thrust/(mdot*G0),
            'thrust_coefficient':ideal_thrust/(chamber_p*throat),
            'ambient_pressure_Pa':ambient,'exit_area_m2':area_exit,
            'ideal_pressure_matched_expansion_ratio_capped_200':optimal_area_ratio,
            'risk_of_overexpanded_flow_separation':separation_warning,
            'limits':'Steady 1-D frozen perfect gas; no real gas combustion, finite-rate chemistry, boundary-layer losses, shocks, startup transients or flow-separation prediction. If separation risk is flagged, ideal thrust is not reliable.'}
