"""Additional parametric aerospace design analyses with declared assumptions.

These analyses are educational and do not automatically alter the flight plant.
"""
from __future__ import annotations
import math
from .atmosphere import atmosphere_isa
from .wind import surface_layer_factor

G0 = 9.80665

def _num(p, name, default, low, high):
    val=p.get(name,default)
    if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or not low<=val<=high:
        raise ValueError(f"{name} must lie in [{low}, {high}]")
    return float(val)

def _values(p,key,default,lo,hi):
    vals=p.get(key,default)
    if not isinstance(vals,list) or not 1<=len(vals)<=48:
        raise ValueError(f"{key} requires 1-48 values")
    for v in vals:
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:
            raise ValueError(f"{key}: invalid value")
    return [float(v) for v in vals]

def aerodynamic_envelope(p):
    mass=_num(p,'mass_kg',1250,1,1e7);area=_num(p,'wing_area_m2',16.2,.1,2000)
    ar=_num(p,'aspect_ratio',7.4,2,30);e=_num(p,'oswald_efficiency',.8,.3,1)
    clmax=_num(p,'CL_max',1.5,.2,4);cd0=_num(p,'CD0',.027,.001,.3)
    cl0=_num(p,'CL0',.2,-1,1.5);a0=_num(p,'lift_slope_2d_per_rad',2*math.pi,1,8)
    altitude=_num(p,'altitude_m',2000,-500,20000)
    atm=atmosphere_isa(altitude);rho=atm['density_kg_m3'];a=atm['speed_of_sound_m_s']
    factor=1/(math.pi*ar*e)
    speeds=_values(p,'airspeeds_m_s',[35,45,55,70,90,110,140,170],.1,500)
    samples=[]
    for v in speeds:
        mach=v/a
        if mach>=.75:raise ValueError('Subsonic approximation requires Mach < .75')
        lift_slope=a0/(math.sqrt(1-mach*mach)+a0/(math.pi*ar*e))
        q=.5*rho*v*v;cl=mass*G0/(q*area);cd=cd0+factor*cl*cl
        samples.append({'airspeed_m_s':v,'mach':mach,'dynamic_pressure_Pa':q,
                        'CL_required':cl,'CD':cd,'alpha_required_deg':math.degrees((cl-cl0)/lift_slope),
                        'drag_N':q*area*cd,'thrust_required_N':q*area*cd,
                        'power_required_W':q*area*cd*v,'lift_to_drag':cl/cd,
                        'within_CL_limit':cl<=clmax})
    return {'solver':'Finite-wing subsonic flight envelope','model':'FINITE_WING_SUBSONIC_ENVELOPE',
            'stall_speed_estimate_m_s':math.sqrt(2*mass*G0/(rho*area*clmax)),
            'induced_drag_factor':factor,'samples':samples,
            'limitations':['Quasi-steady model','Mach < .75','No dynamic stall or CFD']}

def _a_over_at(M,gamma):
    return (1/M)*((2/(gamma+1))*(1+(gamma-1)*M*M/2))**((gamma+1)/(2*(gamma-1)))

def rocket_nozzle_sweep(p):
    pc=_num(p,'chamber_pressure_Pa',7e6,1e5,1e9);t=_num(p,'chamber_temperature_K',3500,300,10000)
    gamma=_num(p,'gamma',1.22,1.05,1.67);r=_num(p,'gas_constant_J_kgK',355,100,2000)
    throat=_num(p,'throat_diameter_m',.16,.005,10);ratio=_num(p,'expansion_ratio',12,1,2000)
    cd=_num(p,'discharge_coefficient',.98,.5,1)
    area=math.pi*throat*throat/4;exit_area=ratio*area
    if ratio==1:M=1.
    else:
        lo,hi=1.,100.
        for _ in range(100):
            mid=(lo+hi)/2
            if _a_over_at(mid,gamma)<ratio:lo=mid
            else:hi=mid
        M=(lo+hi)/2
    temp_ratio=1/(1+(gamma-1)*M*M/2)
    te=t*temp_ratio;pe=pc*temp_ratio**(gamma/(gamma-1))
    ve=M*math.sqrt(gamma*r*te)
    mdot=cd*area*pc/math.sqrt(t)*math.sqrt(gamma/r)*(2/(gamma+1))**((gamma+1)/(2*(gamma-1)))
    samples=[]
    for h in _values(p,'altitudes_m',[0,10000,30000,80000],-500,1e6):
        pa=atmosphere_isa(h)['pressure_Pa'];thrust=mdot*ve+(pe-pa)*exit_area
        samples.append({'altitude_m':h,'ambient_pressure_Pa':pa,'thrust_N':thrust,
                        'specific_impulse_s':thrust/(mdot*G0),
                        'thrust_coefficient':thrust/(pc*area),
                        'overexpanded':pe<pa,'flow_separation_risk':pa>0 and pe/pa<.4})
    return {'solver':'Isentropic choked nozzle sweep','model':'ISENTROPIC_CHOKED_NOZZLE',
            'mass_flow_kg_s':mdot,'exit_mach':M,'exit_pressure_Pa':pe,
            'exit_temperature_K':te,'exit_velocity_m_s':ve,'samples':samples,
            'limitations':['Isentropic ideal gas','No shocks, separated flow or combustion chemistry']}

def wind_shear(p):
    """Parameterized Monin-Obukhov log wind profile (SI units)."""
    speed=_num(p,'reference_wind_m_s',8,0,80)
    ref=_num(p,'reference_height_m',10,2,200)
    z0=_num(p,'roughness_length_m',.03,.0001,1)
    direction=_num(p,'direction_toward_deg',90,-360,360)
    stability=p.get('stability_length_m')
    if stability is not None:
        stability=_num(p,'stability_length_m',-100,-100000,100000)
        if abs(stability)<5.0:raise ValueError('Stability length requires |L|>=5m')
    if ref<=z0:raise ValueError('reference height must exceed roughness')
    rad=math.radians(direction);samples=[]
    for h in _values(p,'heights_m',[0,2,5,10,20,50,100,200],0,2000):
        ratio=surface_layer_factor(h,ref,z0,stability)
        v=speed*ratio
        if h>z0:
            dh=max(.001,h*1e-4)
            left=max(z0*1.001,h-dh);right=h+dh
            gradient=speed*(surface_layer_factor(right,ref,z0,stability)-
                            surface_layer_factor(left,ref,z0,stability))/(right-left)
        else:
            gradient=None
        samples.append({'height_m':h,'wind_speed_m_s':v,
                        'north_m_s':v*math.cos(rad),'east_m_s':v*math.sin(rad),
                        'shear_per_s':gradient,
                        'within_surface_layer_domain':h<=200})
    return {'solver':'Monin-Obukhov surface layer wind',
            'model':'MONIN_OBUKHOV_WIND_PROFILE',
            'reference_height_m':ref,'roughness_length_m':z0,
            'stability_length_m':stability,'samples':samples,
            'limitations':['Surface-layer theory, not meteorological forecast',
                           'Profile above 200m is extrapolated in this standalone study',
                           'No time-dependent weather, gusts, terrain or CFD']}
