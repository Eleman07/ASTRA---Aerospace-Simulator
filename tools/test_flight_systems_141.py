"""ASTRA 1.4.1 physics, version consistency and browser wiring tests.
Run python -m unittest tools.test_flight_systems_141 -v from repo root.
"""
import json
import math
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from astra import __version__
from astra.engine import SimulationEngine
from astra.aerodynamics import fixed_wing_coefficients
from astra.engineering import SOLVERS
from astra.wind import (validate_surface_layer, surface_layer_wind_at_altitude,
                        surface_layer_factor)
from browser_bridge import route_raw

WIND = {'reference_wind_ned_m_s':[8.0,0.0,0.0],
        'reference_height_m':10.0, 'roughness_length_m':0.03,
        'boundary_layer_height_m':100.0}


def api(path, data=None):
    message={'method':'POST' if data is not None else 'GET', 'path':path,
             'payload':data if data is not None else {}}
    decoded=json.loads(route_raw(json.dumps(message)))
    if not decoded['ok']:
        raise AssertionError(decoded.get('error','API failed'))
    return decoded['data']


class FlightSystems141Tests(unittest.TestCase):
    def setUp(self):
        self.sim=SimulationEngine()

    def test_version_visible_is_consistent(self):
        index=(ROOT/'index.html').read_text()
        sw=(ROOT/'service-worker.js').read_text()
        css=(ROOT/'mission-ui-14.css').read_text()
        self.assertEqual(__version__,'1.4.1')
        self.assertEqual(api('/status')['version'],__version__)
        self.assertEqual(self.sim.state()['version'],__version__)
        self.assertIn('<b>FLIGHT SYSTEMS 1.4.1</b>',index)
        self.assertNotIn('VERSION 1.3.1',index)
        self.assertIn('build=291',index)
        self.assertIn('astra-browser-v291',sw)
        self.assertIn('ENGINEERING RELEASE',css)
        self.assertIn('MODELLI PARAMETRICI',index)

    def test_18_studies_persist_and_read_only(self):
        self.assertEqual(len(SOLVERS),18)
        source=(ROOT/'engineering-studio.js').read_text()
        for key in ('wind_shear','aero_envelope','rocket_nozzle_sweep'):
            self.assertIn(key+':{',source)
        self.assertIn("ATTIVA VENTO NELLA MISSIONE",(ROOT/'index.html').read_text())
        self.assertEqual(len(api('/engineering')['solvers']),18)

    def test_neutral_wind_reference_and_endpoints(self):
        settings=validate_surface_layer(WIND,'aircraft')
        wind,limited=surface_layer_wind_at_altitude(settings,10)
        self.assertAlmostEqual(wind[0],8.0,places=11)
        self.assertFalse(limited)
        wind_zero,_=surface_layer_wind_at_altitude(settings,0)
        self.assertEqual(wind_zero,[0,0,0])
        high,limited=surface_layer_wind_at_altitude(settings,1000)
        cap,_=surface_layer_wind_at_altitude(settings,100)
        self.assertTrue(limited)
        self.assertEqual(high,cap)

    def test_neutral_matches_classic_log_law(self):
        f=surface_layer_factor(20,10,.03)
        self.assertAlmostEqual(f,math.log(20/.03)/math.log(10/.03),places=11)
        self.assertGreater(f,1)

    def test_stability_changes_wind_shear(self):
        neutral=surface_layer_factor(20,10,.03)
        stable=surface_layer_factor(20,10,.03,100)
        unstable=surface_layer_factor(20,10,.03,-100)
        self.assertTrue(all(math.isfinite(x) and x>0 for x in (neutral,stable,unstable)))
        self.assertNotAlmostEqual(neutral,stable,places=4)
        self.assertNotAlmostEqual(neutral,unstable,places=4)

    def test_opt_in_surface_wind_changes_real_six_dof_forces(self):
        no_wind=SimulationEngine()
        no_wind.reset('aircraft')
        with_wind=SimulationEngine()
        state=with_wind.reset('aircraft',surface_layer_wind=WIND)
        self.assertEqual(state['environment']['wind_profile_model'],'MONIN_OBUKHOV_SURFACE_LAYER')
        self.assertEqual(state['environment']['surface_layer_wind']['reference_height_m'],10)
        sample=no_wind.flight[:]
        sample[2]=-20.0
        sample[3]=90.0
        a=no_wind._flight_derivative(sample)
        b=with_wind._flight_derivative(sample)
        self.assertGreater(max(abs(x-y) for x,y in zip(a[3:6],b[3:6])),.05)
        self.assertEqual(with_wind.state()['environment']['wind_profile_model'],
                         'MONIN_OBUKHOV_SURFACE_LAYER')

    def test_drone_wind_changes_real_forces(self):
        no=SimulationEngine();no.reset('drone')
        settings=dict(WIND,reference_wind_ned_m_s=[5.,0.,0.])
        yes=SimulationEngine();yes.reset('drone',surface_layer_wind=settings)
        y=no.flight[:]
        y[2]=-20;y[3]=10
        a=no._flight_derivative(y)
        b=yes._flight_derivative(y)
        self.assertTrue(any(abs(u-v)>1e-5 for u,v in zip(a[3:6],b[3:6])))

    def test_wind_invalid_conditions_rejected(self):
        with self.assertRaises(ValueError):
            self.sim.reset('space',surface_layer_wind=WIND)
        with self.assertRaises(ValueError):
            self.sim.reset('aircraft',wind_ned_m_s=[3,0,0],surface_layer_wind=WIND)
        with self.assertRaises(ValueError):
            self.sim.reset('aircraft',surface_layer_wind=dict(WIND,roughness_length_m=-1))
        with self.assertRaises(ValueError):
            self.sim.reset('drone',surface_layer_wind=dict(WIND,reference_wind_ned_m_s=[50,0,0]))

    def test_aircraft_subsonic_compressibility_changes_coefficients(self):
        self.sim.reset('aircraft')
        p=self.sim.aero
        a=fixed_wing_coefficients(p,.08,0,mach=0)
        b=fixed_wing_coefficients(p,.08,0,mach=.45)
        self.assertGreater(b['CL'],a['CL'])
        self.assertGreater(b['compressibility_factor'],1)
        self.assertTrue(b['compressibility_in_model_domain'])
        invalid=fixed_wing_coefficients(p,.08,0,mach=.9)
        self.assertFalse(invalid['compressibility_in_model_domain'])
        with self.assertRaises(ValueError):
            fixed_wing_coefficients(p,.08,0,mach=float('nan'))

    def test_rocket_thrust_telemetry_matches_plant(self):
        st=self.sim.state()
        p=st['propulsion']
        env=st['environment']
        self.assertAlmostEqual(p['net_thrust_N'],self.sim._thrust_at_altitude(st['altitude_m']))
        self.assertAlmostEqual(p['pressure_correction_N'],
                               env['pressure_Pa']*p['nozzle_exit_area_m2'],delta=1e-5)
        self.assertLess(p['effective_isp_s'],self.sim.isp_s)

    def test_snapshot_vs_direct_physics_flag_are_honest(self):
        api('/reset',{'vehicle':'aircraft','surface_layer_wind':WIND})
        direct=api('/engineering/live',{'analysis':'wind_shear'})
        self.assertTrue(direct['mission_context']['coupled_into_flight_dynamics'])
        self.assertIn('stability_length_m',direct)
        offline=api('/engineering/live',{'analysis':'aero_envelope'})
        self.assertFalse(offline['mission_context']['coupled_into_flight_dynamics'])
        self.assertEqual(offline['mission_context']['mode'],'mission_snapshot')


if __name__=='__main__':
    unittest.main(verbosity=2)
