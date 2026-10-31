"""Deterministic SI building blocks for the live advanced science path.

No network, NumPy or wall clock dependency. Reference assumptions are explicit;
these models are not vehicle identification or certification data.
"""
from __future__ import annotations
import copy
import hashlib
import heapq
import json
import math
import random
from datetime import datetime, timedelta, timezone

G0 = 9.80665
RE = 6378137.0


def norm(v):
    return math.sqrt(sum(x*x for x in v))


def clamp(x, low, high):
    return max(low, min(high, x))


def differential_gravity(position, body, mu):
    """Third body acceleration in an Earth-centred, translating inertial frame."""
    delta = [body[i]-position[i] for i in range(3)]
    a, b = max(norm(delta), 1.), max(norm(body), 1.)
    return [mu*(delta[i]/a**3-body[i]/b**3) for i in range(3)]


class Ephemerides:
    def __init__(self, epoch):
        from .celestial import _parse_date
        self.epoch = _parse_date(epoch)
        if not 1800 <= self.epoch.year <= 2049:
            raise ValueError('Live ephemerides require an epoch from 1800 through 2049')
        self.cache = {}

    @staticmethod
    def equatorial(v):
        e = math.radians(23.4392911)
        return [v[0], math.cos(e)*v[1]-math.sin(e)*v[2],
                math.sin(e)*v[1]+math.cos(e)*v[2]]

    def _sample(self, second):
        from .celestial import (_julian_day, _planet_state, PLANETS,
                                _moon_position_velocity, MU_SUN, MU_MOON)
        if second not in self.cache:
            date = self.epoch+timedelta(seconds=second)
            jd = _julian_day(date)
            earth = _planet_state(PLANETS['earth'], jd)[0]
            out = [('sun', self.equatorial([-x for x in earth]), MU_SUN),
                   ('moon', self.equatorial(_moon_position_velocity('moon', date)[0]), MU_MOON)]
            for name, data in PLANETS.items():
                if name != 'earth':
                    p = _planet_state(data, jd)[0]
                    out.append((name, self.equatorial([p[i]-earth[i] for i in range(3)]), data[13]))
            self.cache[second] = out
            if len(self.cache) > 6:
                del self.cache[min(self.cache)]
        return self.cache[second]

    def bodies(self, time_s):
        t = math.floor(time_s/60)*60
        a, b = self._sample(t), self._sample(t+60)
        f = (time_s-t)/60
        return [(x[0], [x[1][i]*(1-f)+y[1][i]*f for i in range(3)], x[2])
                for x, y in zip(a, b)]

    def acceleration(self, position, time_s):
        terms = [differential_gravity(position, p, mu) for _, p, mu in self.bodies(time_s)]
        return [sum(v[i] for v in terms) for i in range(3)]


class SpectralWind:
    """Finite-band von Karman-shaped frozen spatial field; expected RMS is sigma.

    The shape (1+(k L)^2)^(-5/6) has a -5/3 high-wavenumber spectrum.
    One dimensional sampling is not a full three dimensional turbulence field.
    """
    def __init__(self, sigma, length, seed, modes=48):
        rng = random.Random(seed)
        ks = [10**(-3+5*i/(modes-1))/length for i in range(modes)]
        weights = [(1+(k*length)**2)**(-5/6)*k for k in ks]
        total = sum(weights)
        self.k = ks
        self.amplitudes = [sigma*math.sqrt(2*w/total) for w in weights]
        self.phases = [[rng.uniform(0, 2*math.pi) for _ in ks] for _ in range(3)]

    def evaluate(self, distance):
        return [sum(a*math.cos(k*distance+p) for a, k, p in
                    zip(self.amplitudes, self.k, phases)) for phases in self.phases]


class ModalBeam:
    """Consistent-mass Hermite FEM first mode, damped Newmark average acceleration."""
    def __init__(self, parameters=None):
        from .engineering import beam_fem
        p = dict(parameters or {})
        p.update(tip_force_N=1., distributed_force_N_m=0.)
        self.reference = beam_fem(p)
        modal = self.reference['modal']
        self.mass = modal['generalized_mass_kg']
        self.stiffness = self.mass*modal['first_eigenvalue_rad2_s2']
        self.damping = 2*.02*math.sqrt(self.stiffness*self.mass)
        self.stress_per_m = modal['root_stress_per_tip_displacement_Pa_m']
        self.q = self.v = self.a = self.force = 0.
        self.work = self.dissipated = 0.

    def advance(self, dt, force):
        if dt <= 0:
            return
        # Initial acceleration must satisfy equilibrium for a free initial condition.
        qp = self.q+dt*self.v+.25*dt*dt*self.a
        vp = self.v+.5*dt*self.a
        a = (force-self.damping*vp-self.stiffness*qp)/(
            self.mass+.5*dt*self.damping+.25*dt*dt*self.stiffness)
        q, v = qp+.25*dt*dt*a, vp+.5*dt*a
        self.work += .5*(self.force+force)*(q-self.q)
        self.dissipated += self.damping*((self.v+v)/2)**2*dt
        self.q, self.v, self.a, self.force = q, v, a, force

    def snapshot(self):
        energy = .5*(self.mass*self.v**2+self.stiffness*self.q**2)
        return dict(tip_displacement_m=self.q, tip_velocity_m_s=self.v,
                    root_stress_Pa=abs(self.q*self.stress_per_m),
                    first_frequency_Hz=self.reference['modal']['first_frequency_Hz'],
                    modal_energy_J=energy, input_work_J=self.work,
                    dissipated_energy_J=self.dissipated,
                    energy_balance_residual_J=self.work-self.dissipated-energy,
                    yield_margin=250e6/max(abs(self.q*self.stress_per_m), 1e-15)-1,
                    model='HERMITE_CONSISTENT_MASS_MODE_1_NEWMARK_BETA_025_GAMMA_05')


def solar_visible_fraction(position, sun):
    """Apparent disk overlap: conical umbra/penumbra; no atmospheric refraction."""
    r = norm(position)
    to_sun = [sun[i]-position[i] for i in range(3)]
    distance = norm(to_sun)
    a = math.asin(clamp(695700000/distance, 0, 1))
    b = math.asin(clamp(RE/max(r, RE), 0, 1))
    d = math.acos(clamp(sum(-position[i]*to_sun[i] for i in range(3))/max(r*distance, 1.), -1, 1))
    if d >= a+b:
        return 1.
    if b >= d+a:
        return 0.
    if a >= d+b:
        return 1-b*b/(a*a)
    x = clamp((d*d+a*a-b*b)/(2*d*a), -1, 1)
    y = clamp((d*d+b*b-a*a)/(2*d*b), -1, 1)
    area = a*a*math.acos(x)+b*b*math.acos(y)-.5*math.sqrt(
        max(0., (-d+a+b)*(d+a-b)*(d-a+b)*(d+a+b)))
    return clamp(1-area/(math.pi*a*a), 0, 1)


class EnergyBus:
    def __init__(self, capacity_Wh=1200., initial_soc=.8):
        self.capacity = capacity_Wh
        self.energy = capacity_Wh*initial_soc
        self.initial = self.energy
        self.generated = self.delivered = self.loss = self.spilled = self.unserved = 0.

    def advance(self, dt, solar_W, load_W):
        generation, demand = solar_W*dt/3600, load_W*dt/3600
        self.generated += generation
        direct = min(generation, demand)
        surplus, deficit = generation-direct, demand-direct
        charge = min(surplus*.94, self.capacity-self.energy)
        discharge = min(deficit/.92, self.energy)
        self.energy += charge-discharge
        self.delivered += direct+discharge*.92
        self.loss += charge*(1/.94-1)+discharge*.08
        self.spilled += surplus-charge/.94
        self.unserved += max(0., deficit-discharge*.92)

    def snapshot(self):
        return dict(energy_Wh=self.energy, soc_pct=100*self.energy/self.capacity,
                    generated_Wh=self.generated, served_load_Wh=self.delivered,
                    conversion_loss_Wh=self.loss, spilled_Wh=self.spilled,
                    unserved_Wh=self.unserved,
                    balance_residual_Wh=self.initial+self.generated-self.delivered-
                    self.loss-self.spilled-self.energy)


class RadioLink:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.queue = []
        self.sequence = self.delivered = self.dropped = 0
        self.last = {}

    def budget(self, distance_m, visible=True, transmit_W=10., pointing_error_deg=0.):
        distance_m = max(distance_m, 1.)
        frequency, rate = 2.2e9, 1e6
        fspl = 20*math.log10(4*math.pi*distance_m*frequency/299792458.)
        pointing_loss = 12*(pointing_error_deg/25.)**2
        received_dBW = 10*math.log10(transmit_W)+12+24-3-fspl-pointing_loss
        ebn0 = received_dBW-10*math.log10(1.380649e-23*290*rate)
        ber = .5*math.erfc(math.sqrt(10**clamp(ebn0/10, -30, 6))) if visible else .5
        packet_success = math.exp(8192*math.log1p(-min(ber, .5))) if visible else 0.
        self.last = dict(distance_m=distance_m, visible=visible, free_space_loss_dB=fspl,
                         pointing_loss_dB=pointing_loss, ebn0_dB=ebn0,
                         margin_dB=ebn0-9.6, bit_error_rate=ber,
                         packet_success_probability=packet_success,
                         one_way_delay_s=distance_m/299792458.+8192/rate,
                         delivered_packets=self.delivered, dropped_packets=self.dropped,
                         queued_packets=len(self.queue))
        return self.last

    def send(self, payload, time_s):
        self.sequence += 1
        if not self.last or self.rng.random() >= self.last['packet_success_probability']:
            self.dropped += 1
            return False
        if len(self.queue) >= 256:
            self.dropped += 1
            return False
        heapq.heappush(self.queue, (time_s+self.last['one_way_delay_s'],
                                    self.sequence, copy.deepcopy(payload)))
        return True

    def receive(self, time_s):
        packets = []
        while self.queue and self.queue[0][0] <= time_s:
            packets.append(heapq.heappop(self.queue)[2])
            self.delivered += 1
        return packets


UNIT_REGISTRY = {'load_factor_g':'g', 'dynamic_pressure_Pa':'Pa',
                 'mass_kg':'kg', 'soc_pct':'%', 'root_stress_Pa':'Pa',
                 'quaternion_norm_error':'1', 'landing_speed_m_s':'m/s'}


class TemporalRequirements:
    def __init__(self, requirements=None):
        self.requirements = copy.deepcopy(requirements or [
            dict(id='finite_mass', signal='mass_kg', unit='kg', low=1., high=1e9),
            dict(id='bus_reserve', signal='soc_pct', unit='%', low=10., high=100.),
            dict(id='reference_beam_elastic', signal='root_stress_Pa', unit='Pa', low=0., high=250e6),
            dict(id='crew_load_envelope', signal='load_factor_g', unit='g', low=0., high=6.),
            dict(id='attitude_normalized', signal='quaternion_norm_error', unit='1', low=0., high=1e-8)])
        if not isinstance(self.requirements, list) or not 1 <= len(self.requirements) <= 40:
            raise ValueError('Provide 1 to 40 temporal requirements')
        ids = set()
        for r in self.requirements:
            if r.get('id') in ids or not isinstance(r.get('id'), str):
                raise ValueError('Requirement identifiers must be unique strings')
            ids.add(r['id'])
            if UNIT_REGISTRY.get(r.get('signal')) != r.get('unit') or r.get('signal') not in UNIT_REGISTRY:
                raise ValueError('Requirement signal and SI unit do not agree')
            for key in ('low', 'high'):
                if not isinstance(r.get(key), (float, int)) or not math.isfinite(r[key]):
                    raise ValueError('Requirement bounds must be finite')
            if r['low'] > r['high']:
                raise ValueError('Requirement lower bound exceeds upper bound')
            r.setdefault('start_s', 0.)
            r.setdefault('end_s', 1e9)
            if not all(isinstance(r[k], (int, float)) and math.isfinite(r[k]) for k in ('start_s','end_s')) or not 0 <= r['start_s'] <= r['end_s']:
                raise ValueError('Invalid temporal coverage window')
        self.records = {r['id']:dict(status='NOT_EVALUATED', samples=0,
                       first_failure_s=None, minimum=None, maximum=None,
                       covered_until_s=None) for r in self.requirements}

    def evaluate(self, values, time_s):
        for r in self.requirements:
            v = values.get(r['signal'])
            if v is None or not r['start_s'] <= time_s <= r['end_s']:
                continue
            rec = self.records[r['id']]
            rec['samples'] += 1
            rec['minimum'] = v if rec['minimum'] is None else min(v, rec['minimum'])
            rec['maximum'] = v if rec['maximum'] is None else max(v, rec['maximum'])
            rec['covered_until_s'] = time_s
            if not math.isfinite(v) or not r['low'] <= v <= r['high']:
                rec['status'] = 'FAIL'
                if rec['first_failure_s'] is None:
                    rec['first_failure_s'] = time_s
            elif rec['status'] != 'FAIL':
                rec['status'] = 'PASS_SO_FAR'

    def snapshot(self):
        return [dict(**r, evidence=copy.deepcopy(self.records[r['id']])) for r in self.requirements]


def safe_route(seed=42, clearance_m=1.6):
    """Inflated 2-D occupancy grid A*, with no diagonal corner cutting."""
    rng = random.Random(seed)
    size, cell = 32, 2.
    start, goal = (2, 2), (29, 29)
    obstacles = {(x, y) for x in range(size) for y in range(size)
                 if rng.random() < .045 and math.dist((x,y), start) > 4
                 and math.dist((x,y), goal) > 4}
    inflation = math.ceil((clearance_m+cell/math.sqrt(2))/cell)
    blocked = {(x+dx,y+dy) for x,y in obstacles
               for dx in range(-inflation,inflation+1)
               for dy in range(-inflation,inflation+1)
               if math.hypot(dx,dy)*cell <= clearance_m+cell/math.sqrt(2)}
    blocked.discard(start); blocked.discard(goal)
    open_list, costs, parent = [(0.,start)], {start:0.}, {}
    while open_list:
        _, p = heapq.heappop(open_list)
        if p == goal:
            break
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            n = p[0]+dx,p[1]+dy
            if not 0 <= n[0] < size or not 0 <= n[1] < size or n in blocked:
                continue
            if dx and dy and ((p[0]+dx,p[1]) in blocked or (p[0],p[1]+dy) in blocked):
                continue
            c = costs[p]+math.hypot(dx,dy)
            if c < costs.get(n, math.inf):
                costs[n], parent[n] = c, p
                heapq.heappush(open_list, (c+math.dist(n,goal),n))
    if goal not in costs:
        raise ValueError('Inflated occupancy grid has no safe route for this seed')
    path, p = [goal], goal
    while p != start:
        p = parent[p]; path.append(p)
    path.reverse()
    return dict(found=True, seed=seed, waypoints_m=[[x*cell,y*cell] for x,y in path],
                obstacles_ned_m=[[(x-start[0])*cell,(y-start[1])*cell] for x,y in sorted(obstacles)],
                clearance_m=clearance_m, cell_size_m=cell,
                model='INFLATED_OCCUPANCY_ASTAR_NO_CORNER_CUTTING')


def provenance(configuration):
    return hashlib.sha256(json.dumps(configuration, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()
