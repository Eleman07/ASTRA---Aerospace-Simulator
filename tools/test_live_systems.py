"""Numerical and mission regressions for the review build; no network needed."""
import json
import math
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from astra.live_systems import (DEFAULTS, SIGMA, thermal_step, beam_response,
                                radio_budget, eclipse_fraction, validate_config)
from astra.engine import SimulationEngine, EARTH_RADIUS
from astra.engineering import run_engineering_analysis
from astra.mission_route import MissionRoute
from browser_bridge import route_raw

class LiveSystemsTests(unittest.TestCase):
    def test_thermal_implicit_energy_balance(self):
        old, flux, env, dt, capacity, emissivity=300,450000,250,.5,45000,.85
        new=thermal_step(old,flux,env,dt,capacity,emissivity)
        self.assertGreater(new,old)
        self.assertAlmostEqual(capacity*(new-old)/dt,
             flux-emissivity*SIGMA*(new**4-env**4),places=5)

    def test_thermal_equilibrium_and_cooling(self):
        self.assertAlmostEqual(thermal_step(300,0,300,1,45000,.85),300,places=9)
        t=thermal_step(1500,0,3,60,45000,.85)
        self.assertGreater(t,3);self.assertLess(t,1500)

    def test_thermal_refinement(self):
        def run(dt):
            t=300
            for _ in range(round(10/dt)):t=thermal_step(t,1e6,200,dt,45000,.85)
            return t
        a,b,c=run(.2),run(.1),run(.05)
        self.assertLess(abs(b-c),abs(a-b))

    def test_beam_closed_form(self):
        r=beam_response(1000,DEFAULTS)
        self.assertEqual(r['force_N'],1000)
        self.assertAlmostEqual(r['root_moment_N_m'],1000)
        self.assertAlmostEqual(r['stress_Pa'],1e6)
        self.assertAlmostEqual(r['tip_deflection_m'],1/7000)
        self.assertIsNone(beam_response(0,DEFAULTS)['yield_margin'])
        self.assertFalse(beam_response(1e9,DEFAULTS)['within_elastic_limit'])

    def test_radio_inverse_square_and_latency(self):
        a=radio_budget(1000,True,DEFAULTS);b=radio_budget(2000,True,DEFAULTS)
        self.assertAlmostEqual(a['received_power_dBm']-b['received_power_dBm'],20*math.log10(2))
        self.assertAlmostEqual(b['one_way_delay_s'],2*a['one_way_delay_s'])
        hidden=radio_budget(1000,False,DEFAULTS)
        self.assertIsNone(hidden['margin_dB']);self.assertEqual(hidden['status'],'OCCULTED')

    def test_eclipse_geometry(self):
        self.assertEqual(eclipse_fraction([-EARTH_RADIUS-400000,0,0]),1)
        self.assertEqual(eclipse_fraction([EARTH_RADIUS+400000,0,0]),0)
        self.assertEqual(eclipse_fraction([-EARTH_RADIUS,EARTH_RADIUS+1,0]),0)

    def test_parameter_validation(self):
        for payload in ({'bus_load_W':float('nan')},{'panel_efficiency':2},{'battery_capacity_Wh':0},
                        {'initial_soc':True},{'unknown':2},[],{'beam_length_m':-1}):
            with self.subTest(payload=payload),self.assertRaises(ValueError):validate_config(payload)

    def test_live_all_vehicles_and_read_purity(self):
        engine=SimulationEngine()
        for vehicle in ('space','aircraft','drone'):
            with self.subTest(vehicle=vehicle):
                initial=engine.reset(vehicle)
                engine.launch();state=engine.step(2)
                live=state['live_systems']
                self.assertAlmostEqual(live['time_s'],state['time_s'])
                self.assertFalse(live['feeds_flight_dynamics'])
                self.assertEqual(state,engine.state())
                json.dumps(state,allow_nan=False)
                self.assertGreaterEqual(live['thermal']['heat_load_J_m2'],initial['live_systems']['thermal']['heat_load_J_m2'])
                self.assertLess(live['power']['energy_Wh'],initial['live_systems']['power']['energy_Wh'])

    def test_reentry_flux_drives_actual_thermal_observer(self):
        e=SimulationEngine();e.phase='REENTRY'
        e.orbit=[EARTH_RADIUS+50000,0,0,-1500,7000,0]
        old=e.live_systems.temperature_K
        e.live_systems.advance(e,.1,1)
        thermal=e.live_systems.snapshot()['thermal']
        self.assertGreater(thermal['incident_flux_W_m2'],10000)
        self.assertGreater(thermal['temperature_K'],old)

    def test_energy_conservation_and_limits(self):
        engine=SimulationEngine();engine.configure_systems({'battery_capacity_Wh':1,'initial_soc':.1,'bus_load_W':3600})
        engine.launch();state=engine.step(1);p=state['live_systems']['power']
        self.assertEqual(p['energy_Wh'],0)
        self.assertAlmostEqual(.1+p['generated_Wh']-p['consumed_Wh']+p['unserved_Wh']-p['spilled_Wh'],p['energy_Wh'])

    def test_orbital_power_changes_in_shadow(self):
        engine=SimulationEngine();engine.reset('space','orbital');observer=engine.live_systems
        engine.orbit[:3]=[EARTH_RADIUS+400000,0,0];observer.advance(engine,10,10);day=observer.snapshot()['power']
        engine.orbit[:3]=[-EARTH_RADIUS-400000,0,0];observer.advance(engine,10,20);night=observer.snapshot()['power']
        self.assertGreater(day['solar_power_W'],day['load_W']);self.assertEqual(night['solar_power_W'],0)
        self.assertLess(night['energy_Wh'],day['energy_Wh'])

    def test_drone_battery_not_double_integrated(self):
        e=SimulationEngine();e.reset('drone');e.launch();state=e.step(5)
        self.assertEqual(state['live_systems']['power']['energy_Wh'],e.battery_energy_Wh)
        self.assertAlmostEqual(state['live_systems']['power']['soc_pct'],state['battery_pct'])

    def test_split_steps_and_reset(self):
        a,b=SimulationEngine(),SimulationEngine();a.launch();b.launch()
        a.step(2)
        for _ in range(20):b.step(.1)
        sa,sb=a.state()['live_systems'],b.state()['live_systems']
        self.assertAlmostEqual(sa['power']['energy_Wh'],sb['power']['energy_Wh'],places=8)
        self.assertAlmostEqual(sa['thermal']['temperature_K'],sb['thermal']['temperature_K'],places=3)
        self.assertEqual(a.reset('space')['live_systems']['thermal']['heat_load_J_m2'],0)

    def test_configuration_is_atomic_and_guarded(self):
        e=SimulationEngine();before=e.state()
        with self.assertRaises(ValueError):e.configure_systems({'panel_area_m2':-1})
        self.assertEqual(e.state(),before)
        e.launch()
        with self.assertRaises(ValueError):e.configure_systems({'panel_area_m2':10})

    def test_worker_route_configuration(self):
        def request(path,payload):return json.loads(route_raw(json.dumps({'method':'POST','path':path,'payload':payload})))
        self.assertTrue(request('/reset',{'vehicle':'space'})['ok'])
        good=request('/systems/configure',{'bus_load_W':250})
        self.assertTrue(good['ok']);self.assertEqual(good['data']['live_systems']['configuration']['bus_load_W'],250)
        self.assertFalse(request('/systems/configure',{'bus_load_W':-1})['ok'])

class MissionRouteTests(unittest.TestCase):
    def plan(self):return run_engineering_analysis({'analysis':'robotics_route','grid_width':8,'grid_height':8,'cell_size_m':1,'obstacle_fraction':0,'seed':42})
    def test_route_is_local_and_returns_to_origin(self):
        route=MissionRoute(self.plan())
        self.assertEqual(route.outbound[0],[0,0]);self.assertEqual(route.points[-1],[0,0])
        for point in route.points[1:]:route.target(point,[0,0])
        self.assertTrue(route.finished)
    def test_route_guards(self):
        e=SimulationEngine()
        with self.assertRaises(ValueError):e.configure_route(self.plan())
        e.reset('drone');e.launch()
        with self.assertRaises(ValueError):e.configure_route(self.plan())
        with self.assertRaises(ValueError):MissionRoute({'found':False})
        with self.assertRaises(ValueError):MissionRoute({'found':True,'waypoints_m':[[0,0],[501,0]]})
    def test_waypoints_drive_real_gnc_and_land(self):
        e=SimulationEngine();e.reset('drone');e.configure_route(self.plan());e.launch()
        maximum=0
        for _ in range(180):
            s=e.step(1);maximum=max(maximum,math.hypot(*s['position_ned_m'][:2]))
            if s['phase'] in ('LANDED','CRASHED'):break
        self.assertTrue(s['mission_route']['completed'],s['mission_route'])
        self.assertGreater(maximum,5)
        self.assertEqual(s['phase'],'LANDED')
        self.assertLess(math.hypot(*s['position_ned_m'][:2]),1.25)
