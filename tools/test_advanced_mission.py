"""Analytical checks and live coupling regression for all thirteen disciplines."""
import copy
import json
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from astra.engine import SimulationEngine, EARTH_RADIUS
from astra.science_models import (differential_gravity, Ephemerides, SpectralWind,
    ModalBeam, EnergyBus, RadioLink, TemporalRequirements, safe_route,
    solar_visible_fraction, norm)
from astra.planetary_mission import PlanetaryMission

IDS={'propulsion','aerodynamics','celestial-mechanics','mission-design','rendezvous',
     'structures','atmosphere','power','communications','robotics','launch-systems',
     'planetary-landing','systems-engineering'}


class ScienceAnalyticalTests(unittest.TestCase):
    def test_differential_gravity_cancels_origin_and_matches_radial_tide(self):
        self.assertEqual(differential_gravity([0,0,0],[1e11,0,0],1e20),[0,0,0])
        a=differential_gravity([1e5,0,0],[1e11,0,0],1e20)
        self.assertAlmostEqual(a[0]/(2*1e20*1e5/1e33),1,delta=2e-6)
        self.assertEqual(a[1:], [0,0])

    def test_ephemeris_is_deterministic_continuous_and_earth_centered(self):
        a,b=Ephemerides('2026-10-28T00:00:00Z'),Ephemerides('2026-10-28T00:00:00Z')
        self.assertEqual(a.bodies(59.999),b.bodies(59.999))
        self.assertEqual(len(a.bodies(0)),9)
        self.assertTrue(1.45e11<norm(a.bodies(0)[0][1])<1.53e11)
        self.assertLess(math.dist(a.bodies(60-1e-6)[0][1],a.bodies(60+1e-6)[0][1]),.1)

    def test_modal_frequency_matches_cantilever_analytical_and_energy_ledger(self):
        b=ModalBeam()
        analytical=1.8751040687**2/(2*math.pi*2**2)*math.sqrt(70e9*(.1*.08**3/12)/(2700*.1*.08))
        self.assertAlmostEqual(b.reference['modal']['first_frequency_Hz']/analytical,1,delta=1e-5)
        for _ in range(1000):b.advance(.001,100)
        s=b.snapshot()
        self.assertLess(abs(s['energy_balance_residual_J']),1e-7)
        self.assertGreater(s['dissipated_energy_J'],0)
        self.assertGreater(s['root_stress_Pa'],0)

    def test_modal_free_undamped_energy_is_conserved(self):
        b=ModalBeam();b.damping=0;b.q=.001;b.a=-b.stiffness*b.q/b.mass
        initial=.5*b.stiffness*b.q**2
        for _ in range(1000):b.advance(.003,0)
        energy=.5*(b.mass*b.v**2+b.stiffness*b.q**2)
        self.assertAlmostEqual(energy/initial,1,delta=1e-10)

    def test_eps_energy_including_losses_spill_and_unserved(self):
        b=EnergyBus(1,.5)
        for solar,load in [(500,0),(0,1000),(500,100),(0,1000)]:b.advance(60,solar,load)
        s=b.snapshot()
        self.assertLess(abs(s['balance_residual_Wh']),1e-12)
        self.assertGreater(s['spilled_Wh'],0);self.assertGreater(s['unserved_Wh'],0)
        self.assertGreater(s['conversion_loss_Wh'],0)
        self.assertTrue(0<=s['soc_pct']<=100)

    def test_conical_umbra_day_and_penumbra_are_bounded(self):
        sun=[149597870700.,0,0]
        self.assertEqual(solar_visible_fraction([EARTH_RADIUS+400e3,0,0],sun),1)
        self.assertEqual(solar_visible_fraction([-EARTH_RADIUS-400e3,0,0],sun),0)
        values=[solar_visible_fraction([-7e6,EARTH_RADIUS+d,0],sun) for d in range(-100000,100001,5000)]
        self.assertTrue(any(0<v<1 for v in values))
        self.assertEqual(values,sorted(values))

    def test_radio_inverse_square_pointing_and_packet_delay(self):
        r=RadioLink(42)
        p=r.budget(100)['ebn0_dB'];q=r.budget(1000)['ebn0_dB']
        self.assertAlmostEqual(p-q,20,places=10)
        self.assertAlmostEqual(q-r.budget(1000,pointing_error_deg=25)['ebn0_dB'],12,places=10)
        r.budget(100);self.assertTrue(r.send({'throttle_pct':50},0))
        self.assertEqual(r.receive(.001),[])
        self.assertEqual(r.receive(1),[{'throttle_pct':50}])
        r.budget(100,visible=False);self.assertFalse(r.send({},1))

    def test_frozen_turbulence_is_repeatable_and_finite(self):
        a,b=SpectralWind(1,120,42),SpectralWind(1,120,42)
        self.assertEqual(a.evaluate(1245),b.evaluate(1245))
        self.assertNotEqual(a.evaluate(1245),a.evaluate(0))
        self.assertLess(math.dist(a.evaluate(1245),a.evaluate(1245+1e-6)),1e-5)
        self.assertAlmostEqual(sum(x*x/2 for x in a.amplitudes),1)

    def test_inflated_astar_has_vehicle_clearance_and_deterministic_map(self):
        route=safe_route();self.assertEqual(route,safe_route())
        origin=route['waypoints_m'][0]
        for p in route['waypoints_m']:
            local=[p[i]-origin[i] for i in range(2)]
            clearance=min(math.dist(local,q) for q in route['obstacles_ned_m'])-math.sqrt(2)
            self.assertGreaterEqual(clearance,route['clearance_m'])

    def test_temporal_units_coverage_and_sticky_failure(self):
        req=[dict(id='q',signal='dynamic_pressure_Pa',unit='Pa',low=0,high=100,start_s=2,end_s=4)]
        monitor=TemporalRequirements(req)
        monitor.evaluate({'dynamic_pressure_Pa':300},1)
        self.assertEqual(monitor.snapshot()[0]['evidence']['status'],'NOT_EVALUATED')
        monitor.evaluate({'dynamic_pressure_Pa':30},2)
        monitor.evaluate({'dynamic_pressure_Pa':120},3)
        monitor.evaluate({'dynamic_pressure_Pa':10},4)
        record=monitor.snapshot()[0]['evidence']
        self.assertEqual(record['status'],'FAIL');self.assertEqual(record['first_failure_s'],3)
        self.assertEqual(record['covered_until_s'],4)
        with self.assertRaises(ValueError):TemporalRequirements([dict(req[0],unit='m')])


class AdvancedLiveTests(unittest.TestCase):
    def engine(self,vehicle='space',scenario='mission',**kwargs):
        e=SimulationEngine();e.reset(vehicle,scenario,advanced_models=True,**kwargs);return e

    def test_all_thirteen_have_runtime_contracts_for_each_mission(self):
        for vehicle,scenario in [('space','mission'),('space','orbital'),('space','planetary'),('aircraft','mission'),('drone','mission')]:
            e=self.engine(vehicle,scenario);e.launch();state=e.step(.2)
            science=state['science']
            self.assertEqual(set(science['disciplines']),IDS)
            self.assertEqual(science['time_s'],state['time_s'])
            for model in science['disciplines'].values():
                self.assertTrue(model['coupling']);self.assertTrue(model['limits'])
            json.dumps(state,allow_nan=False)

    def test_state_reads_are_pure_and_config_hash_tracks_assumptions(self):
        e=self.engine();e.launch();e.step(.3)
        a=copy.deepcopy(e.state());self.assertEqual(a,e.state())
        f=self.engine(science_configuration={'seed':43})
        self.assertNotEqual(a['science']['configuration_sha256'],f.state()['science']['configuration_sha256'])

    def test_nozzle_drives_mass_flow_and_transient_thrust(self):
        e=self.engine();e.launch();mass=e.mass_kg
        e.step(.05);s=e.state()['science']['disciplines']['propulsion']['values']
        self.assertGreater(s['ideal_thrust_N'],0)
        self.assertLess(s['ideal_thrust_N'],e.max_thrust_N)
        self.assertAlmostEqual((mass-e.mass_kg)/.05,s['exhaust_mass_flow_kg_s'],delta=.1)
        self.assertLess(s['mass_continuity_relative_residual'],1e-9)
        self.assertGreater(e.launch_vehicle_attitude.gimbal_to_com_m,0)
        self.assertIsNotNone(e.launch_vehicle_attitude.inertia_override_kg_m2)

    def test_third_bodies_act_on_both_propagations(self):
        a=self.engine('space','orbital')
        b=SimulationEngine();b.reset('space','orbital')
        a.command['mode']=b.command['mode']='manual'
        a.step(60);b.step(60)
        self.assertGreater(math.dist(a.orbit[:3],b.orbit[:3]),.001)
        self.assertGreater(math.dist(a.target_orbit[:3],b.target_orbit[:3]),.001)

    def test_eps_depletion_disables_wheel_actuation(self):
        e=self.engine('space','orbital',science_configuration={'initial_soc':0,'panel_area_m2':0})
        e.step(.1)
        self.assertFalse(e.state()['science']['control_power_available'])
        self.assertEqual(e.spacecraft_attitude.control_torque_body_Nm,[0.,0.,0.])

    def test_rf_delivery_changes_actual_control_and_watchdog_recovers_lunar_guidance(self):
        e=self.engine('space','planetary',science_configuration={'radio_commands':True})
        e.launch()
        result=e.set_command(dict(mode='python',throttle_pct=65))
        self.assertTrue(result['radio_command_receipt']['queued'])
        self.assertEqual(e.command['mode'],'auto')
        e.step(.1)
        self.assertEqual(e.command['mode'],'python')
        self.assertEqual(e.command['throttle_pct'],65)
        e.step(3)
        self.assertEqual(e.command['mode'],'auto')
        self.assertEqual(e.external_control['state'],'AUTO_TAKEOVER')

    def test_cubic_nonlinear_guidance_reaches_twenty_meter_hold(self):
        e=self.engine('space','orbital')
        for _ in range(16):e.step(60)
        s=e.state()
        self.assertLess(math.dist(s['relative_position_rtn_m'],[0,-20,0]),3.)
        self.assertLess(s['relative_speed_m_s'],.05)
        self.assertGreater(s['propellant_kg'],0)

    def test_lunar_contact_navigation_and_fuel_conservation(self):
        e=self.engine('space','planetary');e.launch()
        while e.phase not in {'LANDED','CRASHED','ABORTED'} and e.t<150:e.step(5)
        s=e.state()
        self.assertEqual(e.phase,'LANDED');self.assertLess(s['touchdown_speed_m_s'],3)
        self.assertLess(math.hypot(*s['position_enu_m'][:2]),15)
        self.assertAlmostEqual(norm(s['quaternion_body_to_enu']),1,places=12)
        self.assertAlmostEqual(1000-s['mass_kg'],e.planetary.used_propellant,places=8)
        self.assertGreater(s['navigation_estimate']['fixes'],100)
        self.assertLess(math.dist(s['position_enu_m'],s['navigation_estimate']['position_enu_m']),1.)

    def test_planetary_unpowered_freefall_and_finite_fuel(self):
        p=PlanetaryMission();command=dict(mode='manual',throttle_pct=0,roll_deg=0,pitch_deg=0)
        old=p.y[:];p.advance(.01,command)
        self.assertAlmostEqual((p.y[5]-old[5])/.01,-p.gravity(old[2]),delta=1e-6)
        p.y[13]=p.dry+.00001;command['throttle_pct']=100
        p.advance(.02,command)
        self.assertEqual(p.y[13],p.dry)
        self.assertGreaterEqual(p.used_propellant,0)


if __name__=='__main__':unittest.main()
