"""Selected higher-order ASTRA engineering analyses, SI units; dependency-free.

Models include explicit assumptions and reject invalid/underdetermined regimes.
Scientific validation must remain specific to each model; these functions are
not replacements for calibrated flight dynamics, mission navigation or CFD.
"""
from __future__ import annotations
import math

MU_EARTH = 3.986004418e14
R_EARTH = 6378137.0
C_LIGHT = 299792458.0
BOLTZMANN = 1.380649e-23
SOLAR_RADIUS = 695700000.0
AU = 149597870700.0


def scalar(p, key, default, lo, hi):
    raw = p.get(key, default)
    if isinstance(raw, bool):
        raise ValueError(f'{key} must be finite and in [{lo}, {hi}]')
    try: val = float(raw)
    except (ValueError, TypeError) as exc: raise ValueError(f'{key} must be numeric') from exc
    if not math.isfinite(val) or not lo <= val <= hi:
        raise ValueError(f'{key} must be finite and in [{lo}, {hi}]')
    return val


def _vec(p, key, default, maximum):
    raw = p.get(key, default)
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise ValueError(f'{key} must be a three-element vector')
    vals = []
    for a in raw:
        if isinstance(a, bool): raise ValueError(f'{key} must be a finite vector')
        try: x=float(a)
        except (ValueError, TypeError) as exc: raise ValueError(f'{key} must be a finite vector') from exc
        if not math.isfinite(x) or abs(x) > maximum: raise ValueError(f'{key} exceeds allowable magnitude')
        vals.append(x)
    return vals


def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _norm(a): return math.sqrt(_dot(a,a))
def _cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def _unit(v):
    n=_norm(v)
    if n<1e-13: raise ValueError('undefined zero-length direction')
    return [a/n for a in v]


def _solve(a, b):
    a=[list(map(float,row)) for row in a]; b=list(map(float,b)); n=len(b)
    for j in range(n):
        k=max(range(j,n),key=lambda i:abs(a[i][j]))
        if abs(a[k][j]) < 1e-13:raise ValueError('singular aerodynamic system')
        a[j],a[k]=a[k],a[j];b[j],b[k]=b[k],b[j]
        for i in range(j+1,n):
            f=a[i][j]/a[j][j]
            for m in range(j+1,n):a[i][m]-=f*a[j][m]
            b[i]-=f*b[j]
            a[i][j]=0
    x=[0.]*n
    for i in range(n-1,-1,-1):x[i]=(b[i]-sum(a[i][j]*x[j] for j in range(i+1,n)))/a[i][i]
    return x


def lifting_line(p: dict) -> dict:
    """Prandtl lifting-line Fourier collocation with spanwise twist/taper."""
    span=scalar(p,'wingspan_m',12.,.2,200.)
    area=scalar(p,'wing_area_m2',18.,.02,2000.)
    taper=scalar(p,'taper_ratio',.65,.05,1.)
    twist=math.radians(scalar(p,'tip_twist_deg',-2.,-15.,15.))
    alpha=math.radians(scalar(p,'angle_of_attack_deg',5.,-12.,14.))
    zero_lift=math.radians(scalar(p,'zero_lift_angle_deg',-2.,-12.,12.))
    slope=scalar(p,'section_lift_slope_per_rad',2*math.pi,3.,8.)
    rho=scalar(p,'density_kg_m3',1.225,.001,20.)
    speed=scalar(p,'airspeed_m_s',65.,1.,350.)
    panels=int(scalar(p,'spanwise_stations',18,6,32))
    aspect=span**2/area
    root=2*area/(span*(1+taper))
    matrix=[];rhs=[];thetas=[]
    for i in range(1,panels+1):
        theta=i*math.pi/(panels+1)
        chord=root*(1-(1-taper)*abs(math.cos(theta)))
        local=alpha+twist*abs(math.cos(theta))-zero_lift
        matrix.append([math.sin(n*theta)*(4*span/(slope*chord)+n/math.sin(theta)) for n in range(1,panels+1)])
        rhs.append(local)
        thetas.append(theta)
    coeff=_solve(matrix,rhs)
    cl=math.pi*aspect*coeff[0]
    cdi=math.pi*aspect*sum((i+1)*v*v for i,v in enumerate(coeff))
    efficiency=cl*cl/(math.pi*aspect*cdi) if cdi>1e-14 else None
    q=.5*rho*speed**2
    samples=[]
    for theta in thetas:
        pos=.5*span*math.cos(theta)
        chord=root*(1-(1-taper)*abs(math.cos(theta)))
        circulation=2*span*speed*sum(a*math.sin((j+1)*theta) for j,a in enumerate(coeff))
        samples.append({'span_y_m':pos, 'chord_m':chord,'circulation_m2_s':circulation,
                        'lift_per_span_N_m':rho*speed*circulation})
    return {'solver':'Prandtl lifting-line Fourier collocation with taper and geometric washout',
            'lift_coefficient_CL':cl,'induced_drag_coefficient_CDi':cdi,
            'oswald_inviscid_efficiency':efficiency,'aspect_ratio':aspect,
            'lift_N':q*area*cl,'induced_drag_N':q*area*cdi,
            'samples':samples,
            'limits':'Inviscid, incompressible, attached-flow lifting-line model, thin wings, no sideslip. No viscous profile drag, transonic flow, dynamic stall, 3-D CFD or CFD mesh convergence.'}


def _stumpff(z):
    if z>1e-7:
        s=math.sqrt(z)
        return (1-math.cos(s))/z, (s-math.sin(s))/(s*s*s)
    if z< -1e-7:
        s=math.sqrt(-z)
        if s>40: return float('inf'),float('inf')
        return (math.cosh(s)-1)/(-z),(math.sinh(s)-s)/(s*s*s)
    return .5-z/24+z*z/720,1/6-z/120+z*z/5040


def lambert_transfer(p:dict)->dict:
    """Single-revolution universal-variable Lambert boundary value solver."""
    r1=_vec(p,'position_start_eci_m',[7000000.,0.,0.],1e14)
    r2=_vec(p,'position_target_eci_m',[0.,8000000.,0.],1e14)
    duration=scalar(p,'time_of_flight_s',2000.,20.,1e8)
    mu=scalar(p,'gravitational_parameter_m3_s2',MU_EARTH,1e8,1e24)
    branch=p.get('direction','prograde')
    if branch not in ('prograde','retrograde'):raise ValueError('direction must be prograde or retrograde')
    ra,rb=_norm(r1),_norm(r2)
    if min(ra,rb)<1e3:raise ValueError('Lambert positions too close to gravitational center')
    cosine=max(-1.,min(1.,_dot(r1,r2)/(ra*rb)))
    theta=math.acos(cosine)
    if _cross(r1,r2)[2] < 0:theta=2*math.pi-theta
    if branch=='retrograde':theta=2*math.pi-theta
    if abs(math.sin(theta))<1e-7 or abs(1-math.cos(theta))<1e-9:
        raise ValueError('collinear Lambert geometry requires a regularized multi-branch solver')
    A=math.sin(theta)*math.sqrt(ra*rb/(1-math.cos(theta)))
    def tof(z):
        C,S=_stumpff(z)
        if not 0<C<1e200:return None
        y=ra+rb+A*(z*S-1)/math.sqrt(C)
        if y<=0:return None
        x=math.sqrt(y/C)
        return (x**3*S+A*math.sqrt(y))/math.sqrt(mu),y
    # Bracket the zero-revolution root without falling into the multi-rev singularity.
    zhi=(2*math.pi-1e-5)**2
    lo=-100.; valid_lo=None
    for j in range(1800):
        z=lo+(zhi-lo)*j/1799
        f=tof(z)
        if f is None:continue
        if f[0]<=duration:valid_lo=z
        elif valid_lo is not None:
            left,right=valid_lo,z
            for _ in range(95):
                middle=(left+right)*.5
                value=tof(middle)
                if value is None or value[0]<duration:left=middle
                else:right=middle
            z=(left+right)*.5
            _,y=tof(z)
            f=1-y/ra;g=A*math.sqrt(y/mu);gdot=1-y/rb
            if abs(g)<1e-11:raise ValueError('singular Lambert g function')
            v1=[(r2[i]-f*r1[i])/g for i in range(3)]
            v2=[(gdot*r2[i]-r1[i])/g for i in range(3)]
            return {'solver':'Universal-variable zero-revolution Lambert method with Stumpff functions and bisection',
                    'transfer_angle_deg':math.degrees(theta),'departure_velocity_eci_m_s':v1,
                    'arrival_velocity_eci_m_s':v2,
                    'departure_speed_m_s':_norm(v1),'arrival_speed_m_s':_norm(v2),
                    'time_of_flight_s':duration, 'stumpff_z':z, 'semi_latus_rectum_m':_norm(_cross(r1,v1))**2/mu,
                    'limits':'Two-body point mass Lambert single-revolution transfer; excludes J2, third bodies, finite burns, phasing uncertainty, collision checking and multi-revolution branches.'}
    raise ValueError('no Lambert solution bracketed for geometry/time of flight')


def orbit_eclipse_power(p:dict)->dict:
    """Orbit geometry eclipse + incidence and battery energy balance (fixed array)."""
    alt=scalar(p,'orbital_altitude_m',450000.,150000.,1e8)
    inc=math.radians(scalar(p,'inclination_deg',51.6,0.,180.))
    raan=math.radians(scalar(p,'ascending_node_deg',20.,-360.,360.))
    sun_ra=math.radians(scalar(p,'sun_right_ascension_deg',0.,-360.,360.))
    sun_dec=math.radians(scalar(p,'sun_declination_deg',0.,-90.,90.))
    panel_normal=_unit(_vec(p,'panel_normal_eci',[1.,0.,0.],1e5))
    area=scalar(p,'solar_array_area_m2',6.,0.,1e5)
    efficiency=scalar(p,'solar_efficiency',.29,0.,.95)
    load=scalar(p,'bus_load_W',400.,0.,1e8)
    battery=scalar(p,'battery_capacity_Wh',1000.,1.,1e8)
    initial_soc=scalar(p,'initial_soc_fraction',.75,0.,1.)
    eta_charge=scalar(p,'charge_efficiency',.95,.1,1.)
    eta_discharge=scalar(p,'discharge_efficiency',.95,.1,1.)
    samples_per_orbit=int(scalar(p,'samples_per_orbit',360,48,1440))
    orbits=int(scalar(p,'orbits',2,1,20))
    solar_flux=scalar(p,'solar_constant_W_m2',1361.,0.,3000.)
    radius=R_EARTH+alt
    mean_motion=math.sqrt(MU_EARTH/radius**3)
    period=2*math.pi/mean_motion
    sun=[math.cos(sun_dec)*math.cos(sun_ra),math.cos(sun_dec)*math.sin(sun_ra),math.sin(sun_dec)]
    normal=[math.cos(raan),math.sin(raan),0.]
    q=[-math.sin(raan)*math.cos(inc),math.cos(raan)*math.cos(inc),math.sin(inc)]
    energy=initial_soc*battery;unserved=0; eclipse_count=0; generated=0; samples=[]
    dt_h=(period/samples_per_orbit)/3600
    cos_incidence=max(0.,_dot(sun,panel_normal))
    for k in range(samples_per_orbit*orbits):
        phase=(k+.5)*2*math.pi/samples_per_orbit
        r=[radius*(normal[i]*math.cos(phase)+q[i]*math.sin(phase)) for i in range(3)]
        shadow_axis=-_dot(r,sun)
        shadow_radius=R_EARTH-shadow_axis*(SOLAR_RADIUS-R_EARTH)/AU
        rho=math.sqrt(max(0.,radius**2-shadow_axis**2))
        eclipsed=shadow_axis>0 and shadow_radius>0 and rho<shadow_radius
        eclipse_count+=int(eclipsed)
        generation=0. if eclipsed else solar_flux*area*efficiency*cos_incidence
        generated+=generation*dt_h
        net=generation-load
        if net>0: energy=min(battery,energy+net*eta_charge*dt_h)
        else:
            need=-net*dt_h/eta_discharge
            removed=min(energy,need)
            energy-=removed
            unserved+=(need-removed)*eta_discharge
        if k%max(1,samples_per_orbit*orbits//240)==0 or k==samples_per_orbit*orbits-1:
            samples.append({'time_s':(k+1)*period/samples_per_orbit,'soc_fraction':energy/battery,
                            'generated_power_W':generation,'eclipsed':eclipsed})
    return {'solver':'Circular two-body orbital geometry, conical Earth umbra, fixed ECI panel incidence and battery energy integration',
            'orbit_period_s':period,'eclipse_fraction':eclipse_count/(samples_per_orbit*orbits),
            'panel_incidence_cosine':cos_incidence,'generated_energy_Wh':generated,
            'unserved_load_Wh':unserved,'final_soc_fraction':energy/battery,
            'samples':samples,
            'limits':'Circular Earth orbit, fixed solar vector and ECI panel normal during the analysis; conical umbra but no penumbra, reflection, dynamic sun tracking, thermal/electrochemical degradation or multi-bus circuit.'}


def radio_link(p:dict)->dict:
    """Radio link with user-supplied atmospheric attenuation and BER/loss."""
    distance=scalar(p,'range_m',4e5,1.,1e13)
    f=scalar(p,'frequency_Hz',2.2e9,1e5,1e12)
    power=scalar(p,'tx_power_dBm',30.,-100.,100.)
    tx_gain=scalar(p,'tx_gain_dBi',20.,-100.,100.)
    rx_gain=scalar(p,'rx_gain_dBi',30.,-100.,100.)
    antenna_diameter=scalar(p,'antenna_diameter_m',1.2,.01,100.)
    pointing=scalar(p,'pointing_error_deg',.1,0.,180.)
    elevation=scalar(p,'elevation_angle_deg',45.,-90.,90.)
    specific_loss=scalar(p,'specific_atmospheric_attenuation_dB_km',.02,0.,1000.)
    atmospheric_height=scalar(p,'effective_atmosphere_height_km',10.,.01,200.)
    other_loss=scalar(p,'misc_losses_dB',2.,0.,100.)
    noise=scalar(p,'system_noise_temperature_K',350.,1.,100000.)
    bandwidth=scalar(p,'bandwidth_Hz',1e6,1.,1e10)
    rate=scalar(p,'data_rate_bps',100000.,1.,1e10)
    bits=scalar(p,'packet_length_bits',8192.,8.,1e8)
    wavelength=C_LIGHT/f
    beamwidth=70*wavelength/antenna_diameter
    pointing_loss=min(100.,12*(pointing/beamwidth)**2)
    # Atmospheric attenuation is not inferred from weather. It is an input.
    in_view=elevation>0
    slant_path=atmospheric_height/max(math.sin(math.radians(elevation)),.05) if in_view else float('inf')
    atm_loss=specific_loss*slant_path if in_view else float('inf')
    fspl=20*math.log10(4*math.pi*distance/wavelength)
    pr=power+tx_gain+rx_gain-fspl-pointing_loss-other_loss-atm_loss if in_view else None
    pn=10*math.log10(BOLTZMANN*noise*bandwidth)+30
    snr=pr-pn if in_view else None
    ebn0=snr+10*math.log10(bandwidth/rate) if in_view else None
    ber=.5*math.erfc(math.sqrt(10**(ebn0/10))) if in_view and ebn0>-100 else (.5 if in_view else None)
    packet_error= -math.expm1(bits*math.log1p(-ber)) if in_view and ber<1 else (1. if in_view else None)
    return {'solver':'Friis + Gaussian beam pointing + user-provided slant atmospheric loss + coherent BPSK AWGN BER',
            'line_of_sight':in_view,'beamwidth_3db_deg':beamwidth,
            'pointing_loss_dB':pointing_loss,'atmospheric_loss_dB':atm_loss if in_view else None,
            'received_power_dBm':pr,'ebn0_dB':ebn0,'bit_error_probability':ber,
            'packet_error_probability':packet_error,'propagation_latency_s':distance/C_LIGHT,
            'serialization_latency_s':bits/rate,
            'predicted_packet_delivery_probability':1-packet_error if in_view else 0.,
            'limits':'Coherent BPSK in additive white Gaussian noise; user-specified attenuation, ideal synchronization, no coding/interleaving, rain climatology, actual antenna pattern, interference, multipath or atmospheric ray tracing.'}


def rocket_cycle(p:dict)->dict:
    """Open gas-generator-cycle power and propellant-flow accounting.

    Combustion enthalpy/chamber temperature is an input; no equilibrium chemistry.
    The turbine exhaust is assumed dumped, so the effective Isp is conservative.
    """
    from .nozzle import nozzle_design
    chamber=scalar(p,'chamber_pressure_Pa',7e6,1e5,2e8)
    tank=scalar(p,'tank_pressure_Pa',3e5,1e3,1e7)
    injector=scalar(p,'injector_pressure_drop_fraction',.2,0.,.8)
    rho_f=scalar(p,'fuel_density_kg_m3',810.,50.,2500.)
    rho_o=scalar(p,'oxidizer_density_kg_m3',1141.,50.,2500.)
    mixture=scalar(p,'oxidizer_to_fuel_ratio',2.6,.1,20.)
    pump_eff=scalar(p,'pump_efficiency',.72,.1,1.)
    turbine_eff=scalar(p,'turbine_efficiency',.64,.1,1.)
    tin=scalar(p,'turbine_inlet_temperature_K',950.,150.,3000.)
    pin=scalar(p,'turbine_inlet_pressure_Pa',8e6,1e5,2e8)
    pout=scalar(p,'turbine_outlet_pressure_Pa',1.5e5,1e4,2e8)
    cp=scalar(p,'turbine_gas_cp_J_kgK',2100.,100.,20000.)
    gamma=scalar(p,'turbine_gas_gamma',1.25,1.05,1.67)
    if pout>=pin:raise ValueError('turbine inlet pressure must exceed outlet pressure')
    target=chamber*(1+injector)
    delta=max(0.,target-tank)
    nozzle=nozzle_design(p)
    mdot=nozzle['exhaust_mass_flow_kg_s']
    mf=mdot/(1+mixture); mo=mdot-mf
    pump_f=mf*delta/(rho_f*pump_eff)
    pump_o=mo*delta/(rho_o*pump_eff)
    pump_power=pump_f+pump_o
    specific_turbine_work=cp*tin*(1-(pout/pin)**((gamma-1)/gamma))*turbine_eff
    bleed=pump_power/specific_turbine_work
    fraction=bleed/(mdot+bleed)
    if fraction>=.50:
        raise ValueError('turbine mass bleed exceeds 50%; infeasible open-cycle design')
    exhaust_temperature=tin-pump_power/(max(bleed,1e-20)*cp)
    total_flow=mdot+bleed
    return {'solver':'Steady incompressible pump + isentropic turbine gas-generator power balance and nozzle mass-flow accounting',
            'nozzle_thrust_N':nozzle['ideal_thrust_N'],'chamber_mass_flow_kg_s':mdot,
            'fuel_mass_flow_kg_s':mf,'oxidizer_mass_flow_kg_s':mo,
            'pump_pressure_rise_Pa':delta,'fuel_pump_power_W':pump_f,'oxidizer_pump_power_W':pump_o,
            'total_pump_power_W':pump_power,'turbine_specific_work_J_kg':specific_turbine_work,
            'turbine_mass_flow_kg_s':bleed,'turbine_propellant_fraction':fraction,
            'total_propellant_flow_kg_s':total_flow,'estimated_effective_isp_s':nozzle['ideal_thrust_N']/(total_flow*9.80665),
            'power_balance_residual_W':pump_power-bleed*specific_turbine_work,
            'turbine_exit_temperature_K':exhaust_temperature,
            'limits':'Input chamber gas conditions instead of equilibrium combustion. Ideal inlet/nozzle, fixed pump/turbine efficiencies and densities; turbine exhaust dumped without side thrust. No cavitation NPSH, real pump map, turbine blade/thermal stress, combustion instability, transients or cycle certification.'}
