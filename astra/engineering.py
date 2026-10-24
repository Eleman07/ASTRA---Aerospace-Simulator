"""Isolated ASTRA Engineering Studio solvers, using SI units throughout.

These are educational, parameterized analyses, not high-fidelity vehicle models.
They do not silently alter the live flight simulation. The JSON API exposes all
assumptions and computational limits and performs strict input validation.
"""
from __future__ import annotations

import math
from typing import Callable

from .atmosphere import atmosphere_isa
from .aerodynamics import fixed_wing_coefficients
from .engine import EARTH_RADIUS, EARTH_J2, MU_EARTH, MODEL_CATALOG
from .constants import G0, OMEGA_EARTH
from .nozzle import nozzle_design


def number(p: dict, key: str, default: float, low: float, high: float,
           *, inclusive_low: bool = False) -> float:
    raw = p.get(key, default)
    if isinstance(raw, bool):
        raise ValueError(f'{key} must be a finite number')
    try:
        value = float(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{key} must be a finite number') from exc
    if not math.isfinite(value) or value > high or (value < low if inclusive_low else value <= low):
        raise ValueError(f'{key} must be in {"[" if inclusive_low else "("}{low}, {high}]')
    return value


def integer(p: dict, key: str, default: int, low: int, high: int) -> int:
    raw = p.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, int) or not low <= raw <= high:
        raise ValueError(f'{key} must be an integer in [{low}, {high}]')
    return raw


def vector(p: dict, key: str, default: list[float], limit: float) -> list[float]:
    raw = p.get(key, default)
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise ValueError(f'{key} must be a three-element SI vector')
    result = []
    for i in range(3):
        try:
            v = float(raw[i])
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{key} contains a non-numeric component') from exc
        if isinstance(raw[i], bool) or not math.isfinite(v) or abs(v) > limit:
            raise ValueError(f'{key} components must be finite and <= {limit} in magnitude')
        result.append(v)
    return result


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Dense linear solve with scaled partial pivoting (small FEM systems)."""
    n = len(b)
    a = [list(row) for row in a]
    b = list(b)
    for k in range(n):
        j = max(range(k, n), key=lambda i: abs(a[i][k]))
        if abs(a[j][k]) < 1e-16:
            raise ValueError('singular engineering matrix; check geometry and constraints')
        a[k], a[j] = a[j], a[k]
        b[k], b[j] = b[j], b[k]
        pivot = a[k][k]
        for i in range(k + 1, n):
            f = a[i][k] / pivot
            a[i][k] = 0.0
            for j2 in range(k + 1, n):
                a[i][j2] -= f*a[k][j2]
            b[i] -= f*b[k]
    x = [0.0]*n
    for i in range(n - 1, -1, -1):
        x[i] = (b[i] - sum(a[i][j]*x[j] for j in range(i + 1, n)))/a[i][i]
    return x


def beam_fem(p: dict) -> dict:
    """Euler-Bernoulli Hermite FEM cantilever with distributed and tip loads.

    Uses consistent nodal load vectors and direct stiffness assembly; flexural
    shear deformation and geometric/material nonlinearity are not included.
    """
    length = number(p, 'length_m', 2, 0, 100)
    young = number(p, 'young_modulus_Pa', 70e9, 1e5, 1e13)
    width = number(p, 'width_m', .1, 0, 10)
    height = number(p, 'height_m', .08, 0, 10)
    tip = number(p, 'tip_force_N', -1000, -1e8, 1e8, inclusive_low=True)
    uniform = number(p, 'distributed_force_N_m', -200, -1e7, 1e7, inclusive_low=True)
    yield_strength = number(p, 'yield_strength_Pa', 250e6, 1e3, 1e12)
    elements = integer(p, 'elements', 16, 2, 64)
    dx = length / elements
    inertia = width*height**3/12
    ndof = 2*(elements + 1)
    k = [[0.0]*ndof for _ in range(ndof)]
    f = [0.0]*ndof
    shape = ((12, 6*dx, -12, 6*dx),
             (6*dx, 4*dx*dx, -6*dx, 2*dx*dx),
             (-12, -6*dx, 12, -6*dx),
             (6*dx, 2*dx*dx, -6*dx, 4*dx*dx))
    for e in range(elements):
        indexes = [2*e, 2*e+1, 2*e+2, 2*e+3]
        for r in range(4):
            f[indexes[r]] += uniform*dx*(dx/12 if r in (1, 3) else .5)*(1 if r != 3 else -1)
            for c in range(4):
                k[indexes[r]][indexes[c]] += young*inertia/dx**3*shape[r][c]
    f[-2] += tip
    displacement = [0.0, 0.0] + _solve([row[2:] for row in k[2:]], f[2:])
    # End curvature of the Hermite interpolants, not a stress-smoothed FEM fit.
    max_moment = 0.0
    for e in range(elements):
        w1, theta1, w2, theta2 = displacement[2*e:2*e+4]
        for t in (0., 1.):
            curvature = ((-6+12*t)*w1 + (6-12*t)*w2)/dx**2 + ((-4+6*t)*theta1+(-2+6*t)*theta2)/dx
            max_moment = max(max_moment, abs(young*inertia*curvature))
    stress = max_moment*height/(2*inertia)
    return {'solver': 'Euler-Bernoulli cubic Hermite finite elements + pivoted Gaussian elimination',
            'frame': 'cantilever root at x=0; loads in transverse positive y',
            'elements': elements, 'second_moment_m4': inertia,
            'tip_deflection_m': displacement[-2], 'tip_rotation_rad': displacement[-1],
            'root_reaction_force_N': sum(k[0][j]*displacement[j] for j in range(ndof))-f[0],
            'root_reaction_moment_N_m': sum(k[1][j]*displacement[j] for j in range(ndof))-f[1],
            'max_abs_bending_moment_N_m': max_moment,
            'max_abs_bending_stress_Pa': stress,
            'yield_safety_factor': yield_strength/stress if stress else None,
            'samples': [{'x_m': i*dx, 'deflection_m': displacement[2*i],
                         'rotation_rad': displacement[2*i+1]} for i in range(elements+1)],
            'limits': 'Linear-elastic small-deflection beam, rectangular uniform section, perfectly fixed root; not 3-D FEM or structural certification.'}


def thermal_fvm(p: dict) -> dict:
    """Transient 1-D implicit finite volumes; Newton-linearized radiation.

    The slab is insulated on its back surface. An imposed surface heat flux
    enters the front face, which simultaneously radiates and convects.
    """
    thickness = number(p, 'thickness_m', .05, .00001, 2)
    conductivity = number(p, 'conductivity_W_mK', 1.1, .0001, 1000)
    density = number(p, 'density_kg_m3', 1600, 0, 25000)
    heat_capacity = number(p, 'heat_capacity_J_kgK', 1000, 0, 10000)
    emissivity = number(p, 'emissivity', .8, 0, 1, inclusive_low=True)
    convection = number(p, 'convection_W_m2K', 10, 0, 10000, inclusive_low=True)
    heat_flux = number(p, 'incident_heat_flux_W_m2', 20000, 0, 1e8, inclusive_low=True)
    env_t = number(p, 'environment_temperature_K', 290, 1, 4000)
    initial = number(p, 'initial_temperature_K', 290, 1, 4000)
    duration = number(p, 'duration_s', 120, 0, 86400)
    cells = integer(p, 'cells', 12, 2, 64)
    steps = integer(p, 'steps', 120, 1, 2000)
    dx = thickness/cells
    dt = duration/steps
    cap = density*heat_capacity*dx/dt
    cond = conductivity/dx
    temp = [initial]*cells
    sigma = 5.670374419e-8
    samples = [{'time_s': 0., 'front_temperature_K': initial, 'back_temperature_K': initial}]
    max_seen = initial
    for s in range(steps):
        before = list(temp)
        for iteration in range(16):
            residual = [0.0]*cells
            jac = [[0.0]*cells for _ in range(cells)]
            for i in range(cells):
                residual[i] = cap*(temp[i]-before[i]);jac[i][i] = cap
                if i:
                    residual[i] += cond*(temp[i]-temp[i-1]);jac[i][i] += cond;jac[i][i-1] -= cond
                if i < cells-1:
                    residual[i] += cond*(temp[i]-temp[i+1]);jac[i][i] += cond;jac[i][i+1] -= cond
            front = max(1.0,temp[0])
            residual[0] += emissivity*sigma*(front**4-env_t**4) + convection*(front-env_t)-heat_flux
            jac[0][0] += 4*emissivity*sigma*front**3+convection
            correction = _solve(jac, [-r for r in residual])
            factor = 1.0
            if min(t+v for t, v in zip(temp,correction)) < 1.:
                factor = min(1., .5*min((t-1)/(-v) for t,v in zip(temp,correction) if v < 0))
            temp = [t+factor*v for t,v in zip(temp,correction)]
            if max(abs(factor*v) for v in correction) < 1e-8:
                break
        else:
            raise ValueError('thermal nonlinear solver failed to converge for selected inputs')
        max_seen = max(max_seen, max(temp))
        if (s+1) % max(1,steps//100) == 0 or s == steps-1:
            samples.append({'time_s': dt*(s+1), 'front_temperature_K': temp[0], 'back_temperature_K': temp[-1]})
    return {'solver': 'fully implicit finite-volume transient conduction with Newton surface radiation',
            'surface': 'incident heat flux and radiative/convective cooling at x=0; insulated back',
            'maximum_temperature_K': max_seen,
            'thermal_diffusivity_m2_s': conductivity/(density*heat_capacity),
            'final_profile_K': temp,
            'spatial_grid_m': [(i+.5)*dx for i in range(cells)],
            'samples': samples,
            'limits': 'Constant isotropic material properties, no ablation, phase change, heat-flux variation, contact resistance, or radiation transport; educational 1-D analysis.'}


def link_budget(p: dict) -> dict:
    """Friis link with receiver noise power and Eb/N0 capacity assessment."""
    distance = number(p,'range_m',4e5,0,1e13)
    freq = number(p,'frequency_Hz',2.2e9,1e3,1e12)
    tx_dbm = number(p,'tx_power_dBm',30,-100,100,inclusive_low=True)
    tx_gain = number(p,'tx_gain_dBi',15,-100,100,inclusive_low=True)
    rx_gain = number(p,'rx_gain_dBi',20,-100,100,inclusive_low=True)
    system_loss = number(p,'misc_losses_dB',3,0,100,inclusive_low=True)
    temperature = number(p,'noise_temperature_K',500,1,100000)
    bandwidth = number(p,'bandwidth_Hz',1e6,1,1e10)
    data_rate = number(p,'data_rate_bps',100000,1,1e11)
    min_ebn0 = number(p,'required_ebn0_dB',7,-10,40,inclusive_low=True)
    c = 299792458.
    fspl = 20*math.log10(4*math.pi*distance*freq/c)
    received_dbm = tx_dbm+tx_gain+rx_gain-fspl-system_loss
    noise_dbm = 10*math.log10(1.380649e-23*temperature*bandwidth)+30
    cn_db = received_dbm-noise_dbm
    ebn0 = cn_db+10*math.log10(bandwidth/data_rate)
    snr_lin = 10**(cn_db/10)
    shannon = bandwidth*math.log2(1+snr_lin)
    rate_limit = bandwidth*10**((cn_db-min_ebn0)/10)
    return {'solver':'Friis free-space equation + Boltzmann noise + Shannon-Hartley',
            'free_space_path_loss_dB':fspl, 'received_power_dBm':received_dbm,
            'noise_power_dBm':noise_dbm, 'carrier_to_noise_dB':cn_db,
            'ebn0_dB':ebn0,'link_margin_dB':ebn0-min_ebn0,
            'shannon_capacity_bps':shannon,'max_rate_at_required_ebn0_bps':rate_limit,
            'passes_link_budget':ebn0>=min_ebn0 and data_rate<=shannon,
            'limits':'Free-space line of sight, fixed antenna pointing and G/T, thermal noise only; excludes atmospheric absorption, fading, coding implementation losses and weather.'}


def aircraft_trim(p: dict) -> dict:
    """Safeguarded bisection for pre-stall straight-and-level aircraft trim."""
    model_id = p.get('model_id','aquila-x4')
    if not isinstance(model_id,str) or model_id not in MODEL_CATALOG['aircraft']:
        raise ValueError('unknown aircraft model_id')
    model = MODEL_CATALOG['aircraft'][model_id]
    aero = model['aero']
    speed = number(p,'airspeed_m_s',95,0.1,1000)
    altitude = number(p,'altitude_m',1000,0,85000,inclusive_low=True)
    mass = number(p,'mass_kg',model['dry_kg']+model.get('fuel_start_kg',0),1,1e7)
    bank_deg = number(p,'bank_deg',0,-70,70,inclusive_low=True)
    rho = atmosphere_isa(altitude)['density_kg_m3']
    pressure = .5*rho*speed**2
    lift_target = mass*G0/math.cos(math.radians(bank_deg))
    cl_target = lift_target/(pressure*aero['S_m2'])
    stall = float(aero.get('alpha_stall_rad',math.radians(15)))
    low = -stall
    high = stall
    def cl(alpha):return float(fixed_wing_coefficients(aero,alpha,0)['CL'])
    if not cl(low) <= cl_target <= cl(high):
        return {'solver':'bracketed lift equilibrium in the attached-flow polar',
                'feasible':False,'required_CL':cl_target,
                'available_CL_range':[cl(low),cl(high)],
                'minimum_speed_at_CLmax_m_s':math.sqrt(2*lift_target/(rho*aero['S_m2']*max(0.01,cl(high)))),
                'model_id':model_id,
                'limits':'No pre-stall steady trim available under the supplied assumptions.'}
    for _ in range(60):
        middle = (low+high)/2
        if cl(middle) < cl_target: low = middle
        else: high=middle
    alpha = (low+high)/2
    coefficients = fixed_wing_coefficients(aero,alpha,0)
    drag = pressure*aero['S_m2']*coefficients['CD']
    max_thrust = float(model['thrust_N'])
    return {'solver':'bracketed nonlinear level-flight trim / pre-stall aerodynamic polar',
            'feasible':drag<=max_thrust,
            'model_id':model_id,'reference_density_kg_m3':rho,
            'dynamic_pressure_Pa':pressure,'required_CL':cl_target,
            'angle_of_attack_deg':math.degrees(alpha), 'stall_margin_deg':coefficients['stall_margin_deg'],
            'drag_N':drag,'required_throttle_pct_static_estimate':100*drag/max_thrust,
            'lift_N':lift_target,'load_factor':1/math.cos(math.radians(bank_deg)),
            'limits':'Steady coordinated flight: ignores thrust lapse, propeller inflow, moments/elevator trim, unsteady effects, Reynolds/Mach and maneuver transients. Throttle uses catalog static thrust, not the flight propulsion solver.'}


def electrical_power(p: dict) -> dict:
    """Deterministic orbit-cycle spacecraft solar/battery sizing sweep."""
    period = number(p,'orbit_period_s',5400,60,200000)
    eclipse = number(p,'eclipse_fraction',.35,0, .95,inclusive_low=True)
    array_area = number(p,'solar_array_area_m2',4,0,1e5,inclusive_low=True)
    efficiency = number(p,'solar_efficiency',.28,0,.95,inclusive_low=True)
    solar_flux = number(p,'solar_irradiance_W_m2',1361,0,5000,inclusive_low=True)
    incidence = number(p,'incidence_angle_deg',0,0,90,inclusive_low=True)
    load = number(p,'load_W',450,0,1e8,inclusive_low=True)
    capacity = number(p,'battery_capacity_Wh',800,0,1e8,inclusive_low=True)
    soc = number(p,'initial_soc_fraction',.8,0,1,inclusive_low=True)
    charge_eff = number(p,'charge_efficiency',.94,0,1)
    discharge_eff = number(p,'discharge_efficiency',.95,0,1)
    cycles = integer(p,'cycles',3,1,20)
    steps = integer(p,'samples_per_orbit',120,12,720)
    sun_power = solar_flux*array_area*efficiency*max(0,math.cos(math.radians(incidence)))
    initial_energy = soc*capacity
    energy = initial_energy
    min_energy = energy
    max_energy = energy
    unserved_Wh = 0.
    curtailed_Wh = 0.
    samples=[]
    dt_h = period/steps/3600
    for i in range(cycles*steps):
        phase = (i%steps+.5)/steps
        # Simplified contiguous eclipse interval; no attitude/orbital geometry.
        sun = 0. if phase < eclipse else sun_power
        diff = sun-load
        if diff >= 0:
            charged = min(max(0,capacity-energy),diff*dt_h*charge_eff)
            energy += charged
            curtailed_Wh += diff*dt_h-charged/charge_eff
        else:
            demand = -diff*dt_h/discharge_eff
            delivered = min(energy,demand)
            energy-=delivered
            unserved_Wh += max(0,demand-delivered)*discharge_eff
        min_energy=min(min_energy,energy)
        max_energy=max(max_energy,energy)
        if i%max(1,cycles*steps//180)==0 or i==cycles*steps-1:
            samples.append({'time_s':(i+1)*period/steps,'soc_fraction':energy/capacity if capacity else 0,
                            'generated_power_W':sun})
    return {'solver':'discrete orbit-eclipse power balance with charge/discharge efficiencies and SOC saturation',
            'sunlit_power_W':sun_power,'periodic_average_generation_W':sun_power*(1-eclipse),
            'load_W':load,'minimum_soc_fraction':min_energy/capacity if capacity else 0,
            'final_soc_fraction':energy/capacity if capacity else 0,
            'unserved_load_Wh':unserved_Wh,'curtailed_generation_Wh':curtailed_Wh,
            'energy_neutral_orbit':max(0.,sun_power-load)*(1-eclipse)*charge_eff >= load*eclipse/discharge_eff,
            'samples':samples,
            'limits':'Constant irradiance, fixed incidence, prescribed eclipse duration; no penumbra, solar degradation, battery voltage, temperature, power electronics or actual eclipse geometry.'}


def _orbital_acc(t: float, y: list[float], *, j2: bool, drag: bool,
                 area:float, cd:float, thrust:list[float],isp:float) -> list[float]:
    x,yy,z,vx,vy,vz,mass=y
    r2=x*x+yy*yy+z*z
    r=math.sqrt(r2)
    if r < EARTH_RADIUS*.96:
        raise ValueError('orbital propagation state is inside the Earth')
    f= -MU_EARTH/(r2*r)
    ax,ay,az=f*x,f*yy,f*z
    if j2:
        factor=1.5*EARTH_J2*MU_EARTH*EARTH_RADIUS**2/r**5
        zscale=5*z*z/r2
        ax+=factor*x*(zscale-1)
        ay+=factor*yy*(zscale-1)
        az+=factor*z*(zscale-3)
    if drag and area>0:
        # atmosphere fixed to rotating planet; static COESA76 is not space weather
        rho=float(atmosphere_isa(max(0,r-EARTH_RADIUS))['density_kg_m3'])
        vr=[vx+OMEGA_EARTH*yy,vy-OMEGA_EARTH*x,vz]
        vmag=math.sqrt(sum(a*a for a in vr))
        damp=-.5*rho*cd*area*vmag/mass
        ax+=damp*vr[0];ay+=damp*vr[1];az+=damp*vr[2]
    tmag=math.sqrt(sum(a*a for a in thrust))
    ax+=thrust[0]/mass;ay+=thrust[1]/mass;az+=thrust[2]/mass
    return [vx,vy,vz,ax,ay,az,-tmag/(isp*G0) if tmag else 0]

# Dormand-Prince RK 5(4); the coefficients are the exact published tableau.
_DOPRI_A=((),(1/5,), (3/40,9/40), (44/45,-56/15,32/9),
          (19372/6561,-25360/2187,64448/6561,-212/729),
          (9017/3168,-355/33,46732/5247,49/176,-5103/18656),
          (35/384,0,500/1113,125/192,-2187/6784,11/84))
_DOPRI_C=(0,1/5,3/10,4/5,8/9,1,1)
_DOPRI_B5=(35/384,0,500/1113,125/192,-2187/6784,11/84,0)
_DOPRI_B4=(5179/57600,0,7571/16695,393/640,-92097/339200,187/2100,1/40)


def orbital_propagation(p: dict) -> dict:
    """Adaptive Cowell IVP with embedded fifth/fourth order error estimator."""
    alt = number(p,'initial_altitude_m',400000,80000,1e8)
    v_circ=math.sqrt(MU_EARTH/(EARTH_RADIUS+alt))
    default=[EARTH_RADIUS+alt,0,0,0,v_circ,0]
    supplied=p.get('state_eci')
    if supplied is None:
        pos_vel=default
    else:
        if not isinstance(supplied,(list,tuple)) or len(supplied)!=6:
            raise ValueError('state_eci must contain six position/velocity SI components')
        pos_vel=[]
        for i,v in enumerate(supplied):
            try: vv=float(v)
            except (ValueError,TypeError) as exc: raise ValueError('invalid state_eci') from exc
            if isinstance(v,bool) or not math.isfinite(vv) or abs(vv)>1e10:
                raise ValueError('state_eci must contain finite physical components')
            pos_vel.append(vv)
    if math.sqrt(sum(x*x for x in pos_vel[:3])) <= EARTH_RADIUS+80000:
        raise ValueError('initial state must be above 80 km')
    duration=number(p,'duration_s',5400,0,604800)
    mass=number(p,'mass_kg',500,0,1e7)
    dry_mass=number(p,'dry_mass_kg',mass*.5,0,mass,inclusive_low=True)
    area=number(p,'drag_area_m2',0,0,100000,inclusive_low=True)
    cd=number(p,'drag_coefficient',2.2,0,5,inclusive_low=True)
    isp=number(p,'isp_s',300,1,20000)
    thrust=vector(p,'thrust_eci_N',[0.,0.,0.],1e6)
    use_j2=p.get('include_j2',True)
    use_drag=p.get('include_drag',True)
    if not isinstance(use_j2,bool) or not isinstance(use_drag,bool):
        raise ValueError('include_j2 and include_drag must be boolean')
    rtol=number(p,'relative_tolerance',1e-8,1e-12,1e-3)
    max_step=number(p,'maximum_step_s',120,.01,3600)
    initial_h=min(10.,max_step,duration)
    h=initial_h
    t=0.
    y=pos_vel+[mass]
    fuel_mass_flow=math.sqrt(sum(v*v for v in thrust))/(isp*G0)
    accepted=0
    rejected=0
    samples=[]
    max_alt=0.
    min_alt=float('inf')
    initial_energy=sum(v*v for v in y[3:6])*.5-MU_EARTH/math.sqrt(sum(x*x for x in y[:3]))
    stop='duration_reached'
    def sample():
        nonlocal min_alt,max_alt
        r=math.sqrt(sum(v*v for v in y[:3]))
        altitude=r-EARTH_RADIUS
        min_alt=min(min_alt,altitude);max_alt=max(max_alt,altitude)
        return {'time_s':t,'position_eci_m':y[:3].copy(),'velocity_eci_m_s':y[3:6].copy(),
                'altitude_m':altitude,'mass_kg':y[6]}
    samples.append(sample())
    next_sample=duration/150
    min_dt=1e-7
    for _ in range(200000):
        if t>=duration-1e-9:
            break
        if accepted>=12000 or rejected>=10000:
            stop='step_budget_exceeded'
            break
        h=min(h,max_step,duration-t)
        if fuel_mass_flow:
            remaining_fuel_time=(y[6]-dry_mass)/fuel_mass_flow
            if remaining_fuel_time<=1e-8:
                stop='propellant_exhausted';break
            h=min(h,remaining_fuel_time)
        old_y=y.copy()
        old_t=t
        f=lambda ti,yi:_orbital_acc(ti,yi,j2=use_j2,drag=use_drag,area=area,cd=cd,thrust=thrust,isp=isp)
        k=[]
        for stage in range(7):
            v=[y[j]+h*sum(a*k[s][j] for s,a in enumerate(_DOPRI_A[stage])) for j in range(7)]
            k.append(f(t+h*_DOPRI_C[stage],v))
        candidate=[y[j]+h*sum(_DOPRI_B5[s]*k[s][j] for s in range(7)) for j in range(7)]
        err=[h*sum((_DOPRI_B5[s]-_DOPRI_B4[s])*k[s][j] for s in range(7)) for j in range(7)]
        # Dimensionally appropriate absolute errors for ECI (m, m/s, kg).
        scales=[max(1e-2,rtol*max(abs(y[j]),abs(candidate[j]),1)) for j in range(3)] + [max(1e-5,rtol*max(abs(y[j]),abs(candidate[j]),1)) for j in range(3,6)] + [max(1e-6,rtol*max(abs(y[6]),abs(candidate[6]),1))]
        norm=math.sqrt(sum((err[j]/scales[j])**2 for j in range(7))/7)
        if not math.isfinite(norm):raise ValueError('non-finite orbital integration error')
        if norm<=1.:
            t+=h;y=candidate;accepted+=1
            current_radius=math.sqrt(sum(v*v for v in y[:3]))
            current_altitude=current_radius-EARTH_RADIUS
            if current_radius<=EARTH_RADIUS+80000:
                # Event locate the 80 km crossing to avoid displaying a buried
                # Earth state. The linear-in-state interpolation is an event
                # approximation, not an RK dense-output interpolant.
                low,high=0.,1.
                for _ in range(50):
                    middle=(low+high)/2
                    rmid=math.sqrt(sum((old_y[j]+middle*(candidate[j]-old_y[j]))**2 for j in range(3)))
                    if rmid>EARTH_RADIUS+80000:low=middle
                    else:high=middle
                fraction=(low+high)/2
                y=[old_y[j]+fraction*(candidate[j]-old_y[j]) for j in range(7)]
                t=old_t+fraction*h
                min_alt=min(min_alt,80000.)
                stop='atmospheric_entry_80km'
                samples.append(sample());break
            min_alt=min(min_alt,current_altitude)
            max_alt=max(max_alt,current_altitude)
            if fuel_mass_flow and y[6]<=dry_mass+1e-8:
                y[6]=dry_mass
                stop='propellant_exhausted'
                samples.append(sample());break
            if t>=next_sample-1e-9 or t>=duration-1e-9:
                samples.append(sample());next_sample=t+duration/150
        else:
            rejected+=1
        h*= min(5., max(.2, .9*max(norm,1e-15)**(-.2)))
        if h < min_dt:
            raise ValueError('adaptive orbit integrator minimum step reached')
    else:
        stop='iteration_budget_exceeded'
    final_energy=sum(v*v for v in y[3:6])*.5-MU_EARTH/math.sqrt(sum(v*v for v in y[:3]))
    return {'solver':'Dormand-Prince embedded RK5(4) adaptive Cowell propagation',
            'frame':'ECI Earth-centered inertial; SI units',
            'model':{'earth_J2':use_j2,'COESA76_rotating_atmosphere_drag':use_drag,
                     'constant_inertial_thrust':thrust,'fixed_drag_area_m2':area,'drag_coefficient':cd,
                     'isp_s':isp,'dry_mass_kg':dry_mass,'relative_tolerance':rtol},
            'accepted_steps':accepted,'rejected_steps':rejected,'termination':stop,
            'final_mass_kg':y[6],'propellant_consumed_kg':mass-y[6],
            'elapsed_s':t,'minimum_altitude_m':min_alt,'maximum_altitude_m':max_alt,
            'specific_kepler_energy_initial_J_kg':initial_energy,
            'specific_kepler_energy_final_J_kg':final_energy,
            'specific_kepler_energy_relative_change':(final_energy-initial_energy)/abs(initial_energy) if initial_energy else None,
            'samples':samples,
            'limits':'Earth-fixed COESA76 density and zonal J2 only; no lunisolar gravity, time-varying space weather, SRP, maneuvers or attitude coupling. Energy conserved only for unperturbed two-body case; surface entry ends at an interpolated 80 km crossing; thrust stops at specified dry mass.'}



def robotic_route_plan(p: dict) -> dict:
    """Educational deterministic occupancy-grid A* with corner-cut prevention.

    The obstacle map is synthetic and not a perception/SLAM map. This solver
    provides an independent executable path planning demonstration, not flight GNC.
    """
    import heapq
    import random
    width=integer(p,'grid_width',36,8,96)
    height=integer(p,'grid_height',28,8,96)
    density=number(p,'obstacle_fraction',.15,0,.45,inclusive_low=True)
    cell_size=number(p,'cell_size_m',2.,.05,100)
    seed=integer(p,'seed',42,0,2**31-1)
    origin=(1,1); destination=(width-2,height-2)
    rng=random.Random(seed)
    obstacles={(x,y) for y in range(1,height-1) for x in range(1,width-1)
               if rng.random()<density}
    for center in (origin,destination):
        for dx in range(-1,2):
            for dy in range(-1,2):obstacles.discard((center[0]+dx,center[1]+dy))
    # Weighted Euclidean edge distance is admissible under Euclidean heuristic.
    frontier=[(math.dist(origin,destination),0.,origin)]
    costs={origin:0.}; parent={}; expanded=0; visited=set()
    moves=tuple((dx,dy) for dx in (-1,0,1) for dy in (-1,0,1) if (dx,dy)!=(0,0))
    while frontier:
        _,d,here=heapq.heappop(frontier)
        if here in visited:continue
        visited.add(here);expanded+=1
        if here==destination:break
        for dx,dy in moves:
            other=(here[0]+dx,here[1]+dy)
            if not 0<=other[0]<width or not 0<=other[1]<height or other in obstacles:continue
            if dx and dy and ((here[0]+dx,here[1]) in obstacles or (here[0],here[1]+dy) in obstacles):continue
            nd=d+math.hypot(dx,dy)
            if nd>=costs.get(other,float('inf'))-1e-12:continue
            costs[other]=nd;parent[other]=here
            heapq.heappush(frontier,(nd+math.dist(other,destination),nd,other))
    found=destination in costs and destination in visited
    cells=[]
    if found:
        node=destination;cells.append(node)
        while node!=origin:node=parent[node];cells.append(node)
        cells.reverse()
    return {'solver':'A* 8-connected occupancy grid (Euclidean admissible heuristic)',
            'found':found,'grid_size_cells':[width,height], 'seed':seed,
            'cell_size_m':cell_size,'obstacle_fraction_requested':density,
            'obstacle_cells':len(obstacles),'expanded_nodes':expanded,
            'path_length_m':costs[destination]*cell_size if found else None,
            'waypoints_m':[[x*cell_size,y*cell_size] for x,y in cells],
            'obstacles':[[x,y] for x,y in sorted(obstacles)],
            'limits':'2-D static synthetic occupancy grid only. No sensing, SLAM, 3-D obstacles, vehicle dynamics, collision volumes, or connection to live UAV simulation.'}


def planetary_descent(p: dict) -> dict:
    """Independent powered vertical landing: variable mass + gravity + drag.

    Uses a conservative speed target decreasing with remaining stopping distance.
    A fixed-step RK4 propagates height, vertical velocity and vehicle mass.
    The burn guidance is a simplified feedback law and not optimal control.
    """
    g=number(p,'surface_gravity_m_s2',1.62,.01,30)
    radius=number(p,'body_radius_m',1737400,1000,1e8)
    h=number(p,'initial_altitude_m',1200,1,1e6)
    v=number(p,'initial_vertical_speed_m_s',-35,-10000,10000,inclusive_low=True)
    mass=number(p,'initial_mass_kg',1000,10,1e7)
    dry=number(p,'dry_mass_kg',650,1,1e7)
    thrust=number(p,'maximum_thrust_N',14500,1,1e9)
    isp=number(p,'isp_s',310,20,10000)
    area=number(p,'drag_area_m2',5,0,1000,inclusive_low=True)
    cd=number(p,'drag_coefficient',1.1,.05,5)
    rho=number(p,'surface_density_kg_m3',0,0,15,inclusive_low=True)
    scale=number(p,'density_scale_height_m',10500,1,1e7)
    duration=number(p,'maximum_duration_s',240,1,3600)
    dt=number(p,'step_s',.08,.005,.5)
    if dry>=mass:raise ValueError('dry_mass_kg must be smaller than initial_mass_kg')
    gravity=lambda z:g*(radius/(radius+max(z,0)))**2
    # Earth/Mars can use a simple exponential atmosphere. Airless bodies set rho=0.
    def dragacc(z,vel,m):
        dens=rho*math.exp(-max(z,0)/scale)
        return -.5*dens*cd*area*vel*abs(vel)/m
    def throttle(z,vel,m):
        current_g=gravity(z)
        available=thrust/m-current_g
        if available<=.01:return 1.
        # The target vertical speed is limited by braking distance; near ground aim for -1.0 m/s.
        speed_target=-min(25.,math.sqrt(max(0.,2.*max(available*.32,.1)*max(z-6,0))))
        speed_target=min(-.8,speed_target)
        desired=current_g+2.4*(speed_target-vel)-dragacc(z,vel,m)
        return max(0.,min(1.,desired*m/thrust))
    def deriv(y,u):
        z,vel,m=y
        force=u*thrust if m>dry+1e-9 else 0.
        return [vel,force/m-gravity(z)+dragacc(z,vel,m),-force/(isp*G0)]
    t=0.;samples=[];peak_q=0.;fuel_used=0.;landed=False;crashed=False;status='duration_exceeded'
    def record():
        return {'time_s':round(t,4),'altitude_m':max(0,h),'vertical_speed_m_s':v,
                'mass_kg':mass,'throttle_fraction':throttle(h,v,mass) if mass>dry else 0.}
    samples.append(record());next_sample=duration/120
    for _ in range(min(720000,int(math.ceil(duration/dt))+1)):
        if t>=duration-1e-10:break
        step=min(dt,duration-t)
        u=throttle(h,v,mass) if mass>dry else 0.
        if mass<=dry+1e-9:u=0.
        if u>0:step=min(step,(mass-dry)*isp*G0/(u*thrust))
        if step<1e-11:mass=dry;continue
        y0=[h,v,mass]
        k1=deriv(y0,u)
        k2=deriv([y0[i]+.5*step*k1[i] for i in range(3)],u)
        k3=deriv([y0[i]+.5*step*k2[i] for i in range(3)],u)
        k4=deriv([y0[i]+step*k3[i] for i in range(3)],u)
        candidate=[y0[i]+step*(k1[i]+2*k2[i]+2*k3[i]+k4[i])/6 for i in range(3)]
        if not all(math.isfinite(a) for a in candidate):raise ValueError('nonfinite descent integration result')
        if candidate[0]<=0:
            frac=max(0.,min(1.,h/max(h-candidate[0],1e-12)))
            v=v+frac*(candidate[1]-v);t+=frac*step
            mass=max(dry,mass+frac*(candidate[2]-mass));h=0.
            landed=True;crashed=abs(v)>3.;status='hard_impact' if crashed else 'soft_landing'
            samples.append(record());break
        h,v,mass=candidate[0],candidate[1],max(dry,candidate[2]);t+=step
        dens=rho*math.exp(-h/scale);peak_q=max(peak_q,.5*dens*v*v)
        if t+1e-8>=next_sample:
            samples.append(record());next_sample+=duration/120
    if samples[-1]['time_s']<t-1e-5:samples.append(record())
    return {'solver':'Vertical variable-mass RK4 powered descent with throttle feedback',
            'landing_status':status,'landed':landed,'soft_landing':landed and not crashed,
            'touchdown_speed_m_s':abs(v) if landed else None,'elapsed_s':t,
            'final_altitude_m':h,'final_mass_kg':mass,
            'propellant_consumed_kg':number(p,'initial_mass_kg',1000,10,1e7)-mass,
            'maximum_dynamic_pressure_Pa':peak_q,'samples':samples,
            'limits':'One-dimensional vertical descent. Gravity inverse-square, exponential atmosphere, constant Isp/thrust/Cd; no 6-DoF, terrain, thrust-vector control, horizontal navigation, wind, hazard avoidance or coupling to live missions.'}

from .advanced import lifting_line, lambert_transfer, orbit_eclipse_power, radio_link, rocket_cycle
from .planetary_6dof import planetary_landing_6dof

SOLVERS={'planetary_landing_6dof':planetary_landing_6dof,'rocket_cycle':rocket_cycle,'lifting_line':lifting_line,'lambert':lambert_transfer,
         'orbit_eclipse_power':orbit_eclipse_power,'radio_link':radio_link,
         'propulsion':nozzle_design,'beam':beam_fem,'thermal':thermal_fvm,'link':link_budget,
         'aircraft_trim':aircraft_trim,'power':electrical_power,'orbit':orbital_propagation,
         'robotics_route':robotic_route_plan,'planetary_descent':planetary_descent}


def run_engineering_analysis(payload:dict) -> dict:
    if not isinstance(payload,dict):raise ValueError('analysis request must be a JSON object')
    kind=payload.get('analysis')
    if not isinstance(kind,str) or kind not in SOLVERS:
        raise ValueError('analysis must be one of: '+', '.join(SOLVERS))
    result=SOLVERS[kind](payload)
    return {'analysis':kind, 'units':'SI', **result}
