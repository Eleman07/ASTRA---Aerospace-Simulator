"""Deterministic, one-way mission subsystem integration in SI units.

These reduced-order observers evolve at the flight integrator's substep. They
consume the actual trajectory and loads but do not command actuators. Configured
geometry/material/RF values are study assumptions, not vehicle identification.
"""
from __future__ import annotations
import copy
import math
from .constants import OMEGA_EARTH
EARTH_RADIUS = 6378137.0
from .atmosphere import atmosphere_isa

SIGMA = 5.670374419e-8
C = 299792458.0
DEFAULTS = {
    'panel_area_m2': 4.0, 'panel_efficiency': .28,
    'battery_capacity_Wh': 1200.0, 'initial_soc': .8, 'bus_load_W': 180.0,
    'thermal_capacity_J_m2_K': 45000.0, 'emissivity': .85,
    'temperature_limit_K': 1200.0,
    'beam_length_m': 2.0, 'beam_area_m2': 1.0,
    'beam_second_moment_m4': .0001, 'beam_outer_fiber_m': .1,
    'young_modulus_Pa': 70e9, 'yield_stress_Pa': 250e6,
    'frequency_Hz': 2.2e9, 'transmit_power_W': 10.0,
    'antenna_gain_dBi': 12.0, 'receiver_gain_dBi': 24.0,
    'system_loss_dB': 3.0, 'noise_temperature_K': 290.0,
    'bit_rate_bps': 1e6, 'required_ebn0_dB': 9.6,
}
BOUNDS = {
    'panel_area_m2': (0,1000), 'panel_efficiency': (0,1),
    'battery_capacity_Wh': (1,1e7), 'initial_soc': (0,1), 'bus_load_W': (0,1e7),
    'thermal_capacity_J_m2_K': (100,1e8), 'emissivity': (.01,1),
    'temperature_limit_K': (300,5000), 'beam_length_m': (.01,100),
    'beam_area_m2': (.001,10000), 'beam_second_moment_m4': (1e-10,100),
    'beam_outer_fiber_m': (.001,10), 'young_modulus_Pa': (1e6,1e13),
    'yield_stress_Pa': (1e4,1e11), 'frequency_Hz': (1e6,1e12),
    'transmit_power_W': (.001,1e6), 'antenna_gain_dBi': (-30,80),
    'receiver_gain_dBi': (-30,80), 'system_loss_dB': (0,100),
    'noise_temperature_K': (1,1e5), 'bit_rate_bps': (1,1e12),
    'required_ebn0_dB': (-20,50),
}

def validate_config(overrides=None):
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError('systems configuration must be an object')
    config = dict(DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in BOUNDS:
            raise ValueError('Unknown systems parameter: '+key)
        lo, hi = BOUNDS[key]
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'{key} must be finite and between {lo} and {hi}')
        config[key] = float(value)
    return config


def eclipse_fraction(position):
    """Cylindrical Earth umbra, fixed Sun direction +ECI X; 0 or 1."""
    return float(position[0] < 0 and math.hypot(position[1],position[2]) < EARTH_RADIUS)


def thermal_step(temperature, incident_flux, environment_K, dt, capacity, emissivity):
    """Backward Euler radiant balance; bisection solves a monotonic quartic."""
    if dt <= 0:
        return temperature
    source = capacity*temperature/dt + max(0,incident_flux) + emissivity*SIGMA*environment_K**4
    lo, hi = 0., max(temperature,environment_K)+(max(0,incident_flux)*dt/capacity)+1
    for _ in range(48):
        mid=(lo+hi)/2
        if capacity*mid/dt + emissivity*SIGMA*mid**4 > source:
            hi=mid
        else:
            lo=mid
    return (lo+hi)/2


def beam_response(q, config):
    """Uniform pressure on a configured cantilever, Euler–Bernoulli elastic beam."""
    c=config; force=max(0,q)*c['beam_area_m2']; length=c['beam_length_m']
    moment=force*length/2
    stress=moment*c['beam_outer_fiber_m']/c['beam_second_moment_m4']
    return {'pressure_Pa':q, 'force_N':force, 'root_moment_N_m':moment,
            'stress_Pa':stress,
            'tip_deflection_m':force*length**3/(8*c['young_modulus_Pa']*c['beam_second_moment_m4']),
            'yield_margin':c['yield_stress_Pa']/stress-1 if stress>0 else None,
            'within_elastic_limit':stress<=c['yield_stress_Pa'],
            'assumption':'Uniform q on configured reference beam; not whole-vehicle FEM'}


def radio_budget(distance, visible, config):
    c=config; distance=max(1.,distance)
    fspl=20*math.log10(4*math.pi*distance*c['frequency_Hz']/C)
    received=10*math.log10(c['transmit_power_W'])+c['antenna_gain_dBi']+c['receiver_gain_dBi']-c['system_loss_dB']-fspl
    noise=10*math.log10(1.380649e-23*c['noise_temperature_K'])
    ebn0=received-noise-10*math.log10(c['bit_rate_bps'])
    ber=.5*math.erfc(math.sqrt(10**(min(ebn0,80)/10))) if visible else .5
    return {'range_m':distance,'line_of_sight':visible,'free_space_loss_dB':fspl,
            'received_power_dBm':received+30 if visible else None,
            'ebn0_dB':ebn0 if visible else None,
            'margin_dB':ebn0-c['required_ebn0_dB'] if visible else None,
            'bit_error_rate':ber, 'one_way_delay_s':distance/C,
            'status':'OCCULTED' if not visible else 'MARGIN_LOW' if ebn0<c['required_ebn0_dB'] else 'AVAILABLE',
            'assumption':'Ideal BPSK, configured gains; geometric visibility; no fading/coding'}


class LiveSystems:
    def __init__(self, config=None):
        self.config=validate_config(config)
        self.temperature_K=288.15
        self.energy_Wh=self.config['battery_capacity_Wh']*self.config['initial_soc']
        self.generated_Wh=0.
        self.consumed_Wh=0.
        self.spilled_Wh=0.
        self.unserved_Wh=0.
        self.heat_load_J_m2=0.
        self.ground_eci=None
        self._snapshot={}

    def advance(self, engine, dt, time_s):
        c=self.config; space=engine.vehicle=='space'
        if space:
            position=engine.orbit[:3]
            altitude=math.sqrt(sum(x*x for x in position))-EARTH_RADIUS
            relative=[engine.orbit[3]+OMEGA_EARTH*position[1],engine.orbit[4]-OMEGA_EARTH*position[0],engine.orbit[5]]
            speed=math.sqrt(sum(x*x for x in relative))
            flux=engine._space_stagnation_heat_flux_W_m2(engine.orbit)
            if self.ground_eci is None:
                radius=math.sqrt(sum(x*x for x in position))
                self.ground_eci=[x*EARTH_RADIUS/radius for x in position]
            angle=OMEGA_EARTH*time_s; co,si=math.cos(angle),math.sin(angle)
            x,y,z=self.ground_eci; ground=[co*x-si*y,si*x+co*y,z]
            displacement=[position[i]-ground[i] for i in range(3)]
            distance=math.sqrt(sum(x*x for x in displacement))
            visible=sum(displacement[i]*ground[i] for i in range(3))>=-1e-6
            eclipse=eclipse_fraction(position)
            # Panels remain stowed on atmospheric launch/recovery profiles.
            deployed=engine.scenario=='orbital' or engine.phase=='ORBIT_COAST'
            solar=1361*c['panel_area_m2']*c['panel_efficiency']*(1-eclipse) if deployed else 0.
        else:
            altitude=max(0,-engine.flight[2])
            speed=math.sqrt(sum(x*x for x in engine._air_relative_velocity_body(engine.flight)))
            distance=math.sqrt(sum(x*x for x in engine.flight[:3]))
            visible=True; eclipse=0.; solar=0.; flux=0.; deployed=False
        env=atmosphere_isa(altitude)
        q=.5*env['density_kg_m3']*speed*speed
        if not space:
            # Convective recovery heating of the reference panel, no artificial reentry flux.
            recovery=env['temperature_K']+speed*speed/(2*1005.)
            flux=max(0,10*math.sqrt(max(speed,0))*(recovery-self.temperature_K))
        environment_K=env['temperature_K'] if altitude<86000 else 3.
        self.temperature_K=thermal_step(self.temperature_K,flux,environment_K,dt,c['thermal_capacity_J_m2_K'],c['emissivity'])
        self.heat_load_J_m2+=flux*dt
        if engine.vehicle=='drone':
            # Mirror the existing physical battery. Never integrate it twice.
            energy=engine.battery_energy_Wh; capacity=engine.battery_capacity_Wh
            load=engine.battery_power_W; power_source='FLIGHT_BATTERY'
        else:
            load=c['bus_load_W'];capacity=c['battery_capacity_Wh'];power_source='REFERENCE_BUS_OBSERVER'
            self.generated_Wh+=solar*dt/3600; self.consumed_Wh+=load*dt/3600
            raw=self.energy_Wh+(solar-load)*dt/3600
            self.spilled_Wh+=max(0,raw-capacity); self.unserved_Wh+=max(0,-raw)
            self.energy_Wh=min(capacity,max(0,raw));energy=self.energy_Wh
        beam=beam_response(q,c);radio=radio_budget(distance,visible,c)
        self._snapshot={
            'time_s':time_s, 'coupling':'ONE_WAY_LIVE_OBSERVER',
            'feeds_flight_dynamics':False, 'configuration':dict(c),
            'thermal':{'temperature_K':self.temperature_K,'incident_flux_W_m2':flux,
                       'heat_load_J_m2':self.heat_load_J_m2,
                       'limit_K':c['temperature_limit_K'],'within_limit':self.temperature_K<=c['temperature_limit_K'],
                       'model':'Lumped reference panel; implicit radiation balance; no ablation'},
            'structures':beam,
            'power':{'source':power_source,'energy_Wh':energy,'capacity_Wh':capacity,
                     'soc_pct':100*energy/capacity,'solar_power_W':solar,'load_W':load,
                     'eclipse':bool(eclipse),'panels_deployed':deployed,
                     'generated_Wh':self.generated_Wh,'consumed_Wh':self.consumed_Wh,
                     'spilled_Wh':self.spilled_Wh,'unserved_Wh':self.unserved_Wh,
                     'assumption':'Fixed Sun +ECI X, Sun-pointed panel, cylindrical umbra; reference bus except UAV'},
            'communications':radio,
            'checks':{'thermal':'PASS' if self.temperature_K<=c['temperature_limit_K'] else 'FAIL',
                      'structure':'PASS' if beam['within_elastic_limit'] else 'FAIL',
                      'energy':'PASS' if energy>0 else 'FAIL',
                      'radio':'PASS' if radio['status']=='AVAILABLE' else 'FAIL'},
        }

    def snapshot(self):
        return copy.deepcopy(self._snapshot)
