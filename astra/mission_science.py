"""Advanced science scheduled by the live engine, with explicit coupling contracts."""
from __future__ import annotations
import copy
import math
from .science_models import (Ephemerides, SpectralWind, ModalBeam, EnergyBus, RadioLink,
                             TemporalRequirements, solar_visible_fraction, safe_route,
                             norm, clamp, provenance, G0, RE)
from .nozzle import nozzle_design
from .atmosphere import atmosphere_isa

MODEL_VERSION = 'ASTRA-advanced-1.0'
DEFAULTS = dict(epoch_utc='2026-10-28T00:00:00Z', seed=42,
                turbulence_sigma_m_s=0., turbulence_length_m=120.,
                battery_capacity_Wh=1200., initial_soc=.8, panel_area_m2=4.,
                radio_commands=False, rendezvous_duration_s=900.,
                launch_q_limit_Pa=45000., robot_clearance_m=1.6)


def validate_configuration(payload):
    if not isinstance(payload, dict):
        raise ValueError('Advanced model configuration must be an object')
    if set(payload)-set(DEFAULTS)-{'requirements','beam'}:
        raise ValueError('Unknown advanced model configuration field')
    c = dict(DEFAULTS, **payload)
    if not isinstance(c['radio_commands'], bool):
        raise ValueError('radio_commands must be boolean')
    for k, lo, hi in (('seed',0,2**31-1),('turbulence_sigma_m_s',0,5),
                     ('turbulence_length_m',1,10000),('battery_capacity_Wh',1,1e7),
                     ('initial_soc',0,1),('panel_area_m2',0,1000),
                     ('rendezvous_duration_s',120,7200),('launch_q_limit_Pa',5000,200000),
                     ('robot_clearance_m',.5,4)):
        v = c[k]
        if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not lo<=v<=hi:
            raise ValueError(f'{k} must be a finite number between {lo} and {hi}')
    if int(c['seed']) != c['seed']:
        raise ValueError('seed must be an integer')
    c['seed'] = int(c['seed'])
    return c


class MissionScience:
    def __init__(self, engine, configuration=None):
        self.config = validate_configuration(configuration or {})
        self.ephemerides = Ephemerides(self.config['epoch_utc'])
        self.wind = SpectralWind(self.config['turbulence_sigma_m_s'],
                                 self.config['turbulence_length_m'], self.config['seed'])
        self.beam = ModalBeam(self.config.get('beam'))
        self.bus = EnergyBus(self.config['battery_capacity_Wh'], self.config['initial_soc'])
        self.radio = RadioLink(self.config['seed']+17)
        self.requirements = TemporalRequirements(self.config.get('requirements'))
        self.clock = 0.
        self.control_power_factor = 1.
        self.spool = 0.
        self.nozzle = None
        self.nozzle_cache = {}
        self.alpha_lag = 0.
        self.aero_delta_cl = 0.
        self.trajectory = None
        self.plan_start = engine.t
        self.robot_plan = None
        self.ground = None
        self.records = {}
        self.mass_history = []
        self.power = self.bus.snapshot()
        self._initial_mass = engine.mass_kg
        self.mass_flow_kg_s = None
        if engine.vehicle == 'drone':
            from .mission_route import MissionRoute
            self.robot_plan = safe_route(self.config['seed'],self.config['robot_clearance_m'])
            engine.mission_route = MissionRoute(self.robot_plan)
        if engine.scenario == 'orbital':
            self.trajectory = engine._relative_rtn_state()[:2]
            r,v,axes = engine._relative_rtn_state()
            self.rendezvous_acceleration(engine,r,v,axes,engine.rendezvous_target_rtn_m)
        self.after_step(engine, 0., engine.t)

    def _record(self, key, data, coupling, limits, applicable=True):
        self.records[key] = dict(status='ACTIVE' if applicable else 'NOT_APPLICABLE',
                                 coupling=coupling, values=data, limits=limits,
                                 time_s=self.clock, model_version=MODEL_VERSION)

    def gravity(self, position):
        return self.ephemerides.acceleration(position, self.clock)

    def _engine_point(self, engine, fraction):
        """Infer a reference calorically-perfect engine from catalog vacuum F/Isp/Ae.

        Matching two catalog numbers is calibration, not measured chamber chemistry.
        Frozen gas properties and fixed expansion are deliberately exposed.
        """
        rated = engine.max_thrust_N
        if rated <= 0 or fraction < 1e-4 or engine.isp_s <= 0 or engine.propellant_kg <= 0:
            return dict(ideal_thrust_N=0.,exhaust_mass_flow_kg_s=0.,flow_regime='OFF',
                        chamber_pressure_Pa=0.,mass_continuity_relative_residual=0.)
        key = (rated, engine.isp_s, engine.nozzle_exit_area_m2)
        if key not in self.nozzle_cache:
            exit_area = engine.nozzle_exit_area_m2 or rated/(7e6*1.6)*16
            throat = exit_area/16
            reference = nozzle_design(dict(throat_area_m2=throat,altitude_m=1e6))
            pressure = rated/(reference['thrust_coefficient']*throat)
            gas = 355*(engine.isp_s/reference['ideal_isp_s'])**2
            self.nozzle_cache[key] = dict(throat_area_m2=throat,
                chamber_pressure_Pa=pressure,gas_constant_J_kgK=gas,
                expansion_ratio=16.,specific_heat_ratio=1.22,chamber_temperature_K=3400.)
        params = dict(self.nozzle_cache[key])
        params['chamber_pressure_Pa'] *= fraction
        altitude = clamp(norm(engine.orbit[:3])-RE,0.,1e6)
        ambient = atmosphere_isa(altitude)['pressure_Pa']
        if params['chamber_pressure_Pa'] <= max(ambient,1e4):
            return dict(ideal_thrust_N=0.,exhaust_mass_flow_kg_s=0.,flow_regime='BACK_PRESSURE_CUTOFF',
                        chamber_pressure_Pa=params['chamber_pressure_Pa'],
                        mass_continuity_relative_residual=0.)
        point = nozzle_design(dict(params,altitude_m=altitude))
        point.update(chamber_pressure_Pa=params['chamber_pressure_Pa'],
                     calibrated_gas_constant_J_kgK=params['gas_constant_J_kgK'])
        return point

    def before_step(self, engine, dt, time_s):
        self.clock = time_s+dt/2
        for command in self.radio.receive(time_s):
            engine.set_command(command, _radio_delivery=True, _command_time_s=time_s)
        self.control_power_factor = (1. if (engine.battery_energy_Wh > 0
            if engine.vehicle == 'drone' else self.bus.energy > 1e-9) else 0.)
        for attitude in (engine.spacecraft_attitude, engine.launch_vehicle_attitude):
            if attitude:
                attitude.control_power_factor = self.control_power_factor
        if engine.vehicle == 'space' and engine.scenario not in {'orbital','planetary'}:
            demand = engine.command['throttle_pct']/100
            altitude = max(0,norm(engine.orbit[:3])-RE)
            qbar = .5*atmosphere_isa(altitude)['density_kg_m3']*norm([
                engine.orbit[3]+7.292115e-5*engine.orbit[1],
                engine.orbit[4]-7.292115e-5*engine.orbit[0],engine.orbit[5]])**2
            if engine.command['mode']=='auto' and qbar > .85*self.config['launch_q_limit_Pa']:
                demand *= clamp(self.config['launch_q_limit_Pa']/max(qbar,1), .35, 1)
            tau = .18 if demand>self.spool else .08
            e = math.exp(-dt/tau)
            average = demand+(self.spool-demand)*tau*(1-e)/dt if dt else self.spool
            self.spool = demand+(self.spool-demand)*e
            self.nozzle = self._engine_point(engine,average)
            self.mass_flow_kg_s = self.nozzle['exhaust_mass_flow_kg_s']
            self._update_launch_inertia(engine)
        if engine.vehicle == 'aircraft':
            from .aerodynamics import fixed_wing_coefficients
            air = engine._air_relative_velocity_body(engine.flight)
            speed = max(norm(air), .1)
            alpha = math.atan2(air[2],max(abs(air[0]),.1))
            tau = clamp(4*engine.aero['c_m']/speed,.015,.5)
            self.alpha_lag += (alpha-self.alpha_lag)*(1-math.exp(-dt/tau))
            mach = speed/atmosphere_isa(max(0,-engine.flight[2]))['speed_of_sound_m_s']
            quasi = fixed_wing_coefficients(engine.aero,alpha,0,mach=mach)['CL']
            lagged = fixed_wing_coefficients(engine.aero,self.alpha_lag,0,mach=mach)['CL']
            self.aero_delta_cl = lagged-quasi
        self.clock = time_s

    def thrust_reference(self, engine, altitude):
        if self.nozzle is None or engine.scenario in {'orbital','planetary'}:
            return None
        fraction = engine.command['throttle_pct']/100
        if fraction <= 1e-12:
            return 0.
        # The segment uses one frozen chamber operating point. Ambient pressure
        # variation inside an RK4 segment is small; recompute its pressure term.
        thrust = self.nozzle['ideal_thrust_N']
        if self.nozzle.get('flow_regime') == 'CHOKED_SUPERSONIC':
            thrust += (self.nozzle['ambient_pressure_Pa']-
                       atmosphere_isa(clamp(altitude,0,1e6))['pressure_Pa'])*self.nozzle['exit_area_m2']
        return max(0.,thrust)/fraction

    def _update_launch_inertia(self, engine):
        attitude = engine.launch_vehicle_attitude
        if attitude is None:
            return
        length, radius = attitude.body_length_m, attitude.body_radius_m
        dry, fuel = engine.mass_dry_kg+engine.acs_propellant_kg, engine.propellant_kg
        # Reference shell dry mass plus a shrinking cylindrical tank fill.
        capacity = max(engine.propellant_capacity_kg,1)
        fill = clamp(fuel/capacity,0,1)
        lf, zf, zd = .65*length*fill, .15*length+.325*length*fill, .6*length
        mass = dry+fuel
        cg = (dry*zd+fuel*zf)/max(mass,1)
        transverse = dry*(radius**2/2+length**2/12+(zd-cg)**2)+fuel*(radius**2/4+lf**2/12+(zf-cg)**2)
        axial = dry*radius**2+fuel*radius**2/2
        attitude.inertia_override_kg_m2 = [max(1.,transverse)]*2+[max(1.,axial)]
        attitude.gimbal_to_com_m = max(.1,cg)
        self.launch_mass_properties = dict(center_of_mass_from_engine_m=cg,
            inertia_kg_m2=attitude.inertia_override_kg_m2,
            fuel_fill_fraction=fill, dynamic_pressure_limit_Pa=self.config['launch_q_limit_Pa'])

    def rendezvous_acceleration(self, engine, position, velocity, axes, target):
        from .science_models import differential_gravity
        duration = self.config['rendezvous_duration_s']
        t = clamp(self.clock-self.plan_start,0,duration)
        s = t/duration
        r0,v0 = self.trajectory
        reference=[]; ref_velocity=[]; ref_acc=[]
        for i in range(3):
            a = 3*(target[i]-r0[i])/duration**2-2*v0[i]/duration
            b = -2*(target[i]-r0[i])/duration**3+v0[i]/duration**2
            reference.append(r0[i]+v0[i]*t+a*t*t+b*t**3)
            ref_velocity.append(v0[i]+2*a*t+3*b*t*t)
            ref_acc.append(2*a+6*b*t if t<duration else 0.)
        chief=engine.target_orbit[:3]
        r=norm(chief)
        hvec=[engine.target_orbit[1]*engine.target_orbit[5]-engine.target_orbit[2]*engine.target_orbit[4],
              engine.target_orbit[2]*engine.target_orbit[3]-engine.target_orbit[0]*engine.target_orbit[5],
              engine.target_orbit[0]*engine.target_orbit[4]-engine.target_orbit[1]*engine.target_orbit[3]]
        omega=norm(hvec)/r**2
        omega_dot=-2*sum(chief[i]*engine.target_orbit[i+3] for i in range(3))/r**2*omega
        delta=[sum(position[j]*axes[j][i] for j in range(3)) for i in range(3)]
        chaser=[chief[i]+delta[i] for i in range(3)]
        gc=engine._gravity_eci_acceleration(chief); gd=engine._gravity_eci_acceleration(chaser)
        pc=self.gravity(chief); pd=self.gravity(chaser)
        relative=[sum((gd[i]-gc[i]+pd[i]-pc[i])*axis[i] for i in range(3)) for axis in axes]
        free=[relative[0]+2*omega*velocity[1]+omega**2*position[0]+omega_dot*position[1],
              relative[1]-2*omega*velocity[0]+omega**2*position[1]-omega_dot*position[0],relative[2]]
        acc=[ref_acc[i]-.0008*(position[i]-reference[i])-.055*(velocity[i]-ref_velocity[i])-free[i] for i in range(3)]
        distance=norm(position)
        guard=distance<8
        if guard:
            acc=[.04*position[i]/max(distance,1e-6)-.04*velocity[i] for i in range(3)]
        acc=[v*self.control_power_factor for v in acc]
        self._record('mission-design',dict(duration_s=duration,elapsed_s=t,
            reference_position_rtn_m=reference,reference_velocity_rtn_m_s=ref_velocity,
            tracking_error_m=math.dist(position,reference),
            minimum_energy_cubic=True,finite_burn=True), 'REFERENCE_TO_RCS_GUIDANCE',
            'Unconstrained cubic minimum-control-energy reference, with saturated tracking; no global optimality under actuator limits.')
        self._record('rendezvous',dict(nonlinear_free_acceleration_rtn_m_s2=free,
            commanded_acceleration_rtn_m_s2=acc,keep_out_radius_m=8.,
            safety_escape_active=guard,range_m=distance), 'NONLINEAR_FEEDFORWARD_TO_RCS',
            'Exact central/J2/third-body gravity difference. RTN transport uses osculating two-body frame rate; navigation filter remains CW. No docking/contact model.')
        return acc

    def after_step(self, engine, dt, time_s):
        self.clock=time_s
        space=engine.vehicle=='space'
        landing=engine.scenario=='planetary'
        if landing:
            flight=engine.planetary.state()
            altitude,speed=flight['altitude_m'],flight['speed_m_s']
            qbar=0.;position=None
        elif space:
            position=engine.orbit[:3]
            altitude=norm(position)-RE
            speed=norm(engine.orbit[3:])
            qbar=.5*atmosphere_isa(max(0,altitude))['density_kg_m3']*norm([
                engine.orbit[3]+7.292115e-5*position[1],
                engine.orbit[4]-7.292115e-5*position[0],engine.orbit[5]])**2
        else:
            position=None;altitude=max(0,-engine.flight[2])
            speed=norm(engine._air_relative_velocity_body(engine.flight))
            qbar=.5*atmosphere_isa(altitude)['density_kg_m3']*speed**2
        # Dynamic beam is an operational monitor of an explicit reference member.
        self.beam.advance(dt,qbar*.02)
        structure=self.beam.snapshot()
        self._record('structures',structure,'LIVE_LOAD_TO_MODAL_RESPONSE_AND_REQUIREMENTS',
            'First bending mode of a configured reference cantilever, damping ratio .02. No whole-vehicle aeroelasticity, buckling, shear or material plasticity.')
        self._record('atmosphere',dict(altitude_m=altitude,dynamic_pressure_Pa=qbar,
            temperature_K=atmosphere_isa(max(0,altitude))['temperature_K'],
            gust_ned_m_s=engine._turbulence_gust_ned(engine.flight) if not space else [0,0,0],
            turbulence_sigma_m_s=self.config['turbulence_sigma_m_s']), 'COESA76_AND_FROZEN_SPECTRUM_TO_FORCES',
            'COESA76 plus existing surface-layer wind; finite-band 1D von Karman-shaped gusts for aircraft/UAV. Not a forecast or full 3D turbulence.',not landing)
        sun=self.ephemerides.bodies(time_s)[0][1]
        solar=0.;fraction=1.;incidence=0.
        if space and not landing:
            fraction=solar_visible_fraction(position,sun)
            direction=[sun[i]-position[i] for i in range(3)]
            direction=[v/norm(direction) for v in direction]
            if engine.spacecraft_attitude:
                body=engine.spacecraft_attitude.vector_eci_to_body(direction)
                incidence=abs(body[0]) # two-sided reference panels normal to body X
            else:
                incidence=0.
            if engine.scenario=='orbital' or engine.phase=='ORBIT_COAST':
                solar=1361*self.config['panel_area_m2']*.28*fraction*incidence
        load=180.+10.+120.*engine.command['throttle_pct']/100
        if engine.vehicle=='drone':
            self.power=dict(source='FLIGHT_BATTERY_NO_DUPLICATE_INTEGRATION',
                energy_Wh=engine.battery_energy_Wh,soc_pct=100*engine.battery_energy_Wh/engine.battery_capacity_Wh,
                load_W=engine.battery_power_W,solar_power_W=0.)
        else:
            self.bus.advance(dt,solar,load)
            self.power=dict(self.bus.snapshot(),source='EPS_TO_AVIONICS_AND_ATTITUDE_ACTUATORS',
                load_W=load,solar_power_W=solar,solar_visible_fraction=fraction,panel_incidence_cosine=incidence)
        self._record('power',self.power,'ENERGY_BALANCE_TO_CONTROL_AVAILABILITY',
            'Reference EPS except physical UAV battery. Charge/discharge efficiency .94/.92, two-sided fixed panels; no electrochemical aging or detailed harness.')
        if self.ground is None and position:
            self.ground=[x*RE/norm(position) for x in position]
        if position:
            angle=7.292115e-5*time_s
            x,y,z=self.ground
            ground=[math.cos(angle)*x-math.sin(angle)*y,math.sin(angle)*x+math.cos(angle)*y,z]
            displacement=[position[i]-ground[i] for i in range(3)]
            distance=norm(displacement)
            visible=sum(displacement[i]*ground[i] for i in range(3))>=-1e-5
        else:
            distance=norm(engine.planetary.y[:3]) if landing else norm(engine.flight[:3])
            visible=True
        self.radio.budget(distance,visible,transmit_W=10 if self.control_power_factor else .001)
        self._record('communications',dict(self.radio.last,radio_command_channel=self.config['radio_commands']),
            'PACKET_QUEUE_TO_PYTHON_COMMANDS' if self.config['radio_commands'] else 'LIVE_PACKET_CHANNEL_AVAILABLE',
            'Friis/AWGN coherent uncoded BPSK, 8192-bit packets, serialization and light time. Optional RF Python command channel; no multipath, atmospheric fading or error correcting code.')
        if space and not landing:
            self._record('celestial-mechanics',dict(epoch_utc=self.config['epoch_utc'],
                third_body_acceleration_eci_m_s2=self.gravity(position),
                bodies=[name for name,_,_ in self.ephemerides.bodies(time_s)],
                ephemeris_interpolation_interval_s=60.),'DIFFERENTIAL_GRAVITY_TO_COWELL_PROPAGATION',
                'Prescribed JPL approximate planetary elements and mean lunar Kepler orbit, ecliptic J2000 rotated to equatorial. Not DE/SPICE or mutually integrated solar system.')
        else:
            self._record('celestial-mechanics',{},'INACTIVE_IN_LOCAL_FRAME','Applicable to Earth-orbit missions.',False)
        if self.nozzle:
            self._record('propulsion',dict(self.nozzle,chamber_fraction=self.spool),
                'NOZZLE_FORCE_AND_MASS_FLOW_TO_RK4',
                'Catalog-calibrated frozen perfect gas, fixed expansion 16, analytic first-order chamber response. No reacting chemistry, turbopump transient or viscous separation; shock regime remains ideal 1D.')
        else:
            self._record('propulsion',dict(actual_throttle_pct=engine.command['throttle_pct'],
                model='FINITE_FUEL_RCS' if space else 'PROPELLER_OR_INDIVIDUAL_ROTOR_ACTUATORS'),
                'FORCES_ENERGY_AND_MASS_INTEGRATED','Catalog reference propulsion, no combustion chemistry.')
        self._record('aerodynamics',dict(lift_lag_correction=self.aero_delta_cl,
            lagged_angle_of_attack_rad=self.alpha_lag,dynamic_pressure_Pa=qbar),
            'CONVECTIVE_LIFT_LAG_AND_WAVE_DRAG_TO_6DOF',
            'First-order convective lift lag, nonlinear quasi-steady stall polar, bounded empirical wave drag; generic coefficients, not CFD or identified flutter model.',engine.vehicle=='aircraft')
        if self.robot_plan:
            clearance=min((math.dist(engine.flight[:2],p) for p in self.robot_plan['obstacles_ned_m']),default=1e9)-self.robot_plan['cell_size_m']/math.sqrt(2)
            self._record('robotics',dict(clearance_m=clearance,required_clearance_m=self.config['robot_clearance_m'],
                path=engine.mission_route.snapshot(),plan=self.robot_plan), 'INFLATED_ASTAR_TO_UAV_POSITION_GUIDANCE',
                'Known synthetic 2D obstacles; inflation includes cell radius. Tracking clearance monitored, no SLAM or guarantee under disturbance/emergency return.')
        else:
            self._record('robotics',{},'NOT_APPLICABLE','UAV route autonomy only.',False)
        if not landing and space and engine.scenario!='orbital':
            self._record('launch-systems',dict(getattr(self,'launch_mass_properties',{}),
                stage_index=engine.active_stage_index,propellant_kg=engine.propellant_kg,
                mass_kg=engine.mass_kg,stage_events=copy.deepcopy(engine.stage_events)),
                'FUEL_FILL_CG_AND_INERTIA_TO_TVC_RCS_AND_MAXQ_THROTTLE',
                'Reference dry shell plus shrinking uniform cylindrical propellant tank; no slosh, tank pressure or aerodynamic moment identification.')
        else:
            self._record('launch-systems',{},'NOT_APPLICABLE','Atmospheric launch stages only.',False)
        if landing:
            self._record('planetary-landing',flight,'CLOSED_LOOP_LIVE_6DOF_POWERED_DESCENT',engine.planetary.limits)
        else:
            self._record('planetary-landing',{},'SELECT_LUNAR_DESCENT_MISSION','Live lunar descent available as separate scenario.',False)
        if engine.scenario!='orbital':
            self._record('mission-design',dict(phase=engine.phase,
                next_target=engine.mission_route.snapshot()['target_ned_m'] if engine.mission_route else None),
                'MISSION_PHASE_AND_TARGET_TO_GUIDANCE','Existing launch/air/UAV profiles; cubic finite-burn trajectory planner operates in orbital rendezvous.')
            self._record('rendezvous',{},'SELECT_ORBITAL_MISSION','Orbital rendezvous scenario only.',False)
        quaternion=(engine.planetary.y[6:10] if landing else
            engine.spacecraft_attitude.quaternion_body_to_eci if engine.spacecraft_attitude else
            engine.launch_vehicle_attitude.quaternion_body_to_eci if engine.launch_vehicle_attitude else None)
        self.requirements.evaluate(dict(mass_kg=engine.mass_kg,soc_pct=self.power['soc_pct'],
            root_stress_Pa=structure['root_stress_Pa'],load_factor_g=engine.load_factor_g,
            quaternion_norm_error=abs(norm(quaternion)-1) if quaternion else None,
            landing_speed_m_s=speed if landing and engine.phase in {'LANDED','CRASHED'} else None),time_s)
        self._record('systems-engineering',dict(requirements=self.requirements.snapshot(),
            configuration_sha256=provenance(self.config),seed=self.config['seed']),
            'TEMPORAL_SI_REQUIREMENTS_TO_STICKY_MISSION_EVIDENCE',
            'Sampled interval requirements with sticky failures and coverage; PASS_SO_FAR is not proof between samples or certification.')

    def snapshot(self):
        return dict(enabled=True,version=MODEL_VERSION,time_s=self.clock,
                    configuration=copy.deepcopy(self.config),configuration_sha256=provenance(self.config),
                    disciplines=copy.deepcopy(self.records),implemented_disciplines=13,
                    control_power_available=bool(self.control_power_factor))
