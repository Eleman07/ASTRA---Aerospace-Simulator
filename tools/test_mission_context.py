"""ASTRA 1.4 regression + integration checks for mission-bound Engineering Studio.
Run with: python -m unittest discover -s tools -p test_mission_context.py -v
"""
from __future__ import annotations
import json
import math
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2] if pathlib.Path(__file__).resolve().parts[-3] == 'files' else pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from astra.engineering import SOLVERS
from browser_bridge import route_raw


class MissionEngineeringTests(unittest.TestCase):
    @staticmethod
    def request(path, payload=None):
        result = json.loads(route_raw(json.dumps({
            'method': 'POST' if payload is not None else 'GET',
            'path': path,
            'payload': payload if payload is not None else {},
        })))
        if not result['ok']:
            raise AssertionError(f"{path}: {result.get('error')}")
        return result['data']

    def setUp(self):
        self.request('/reset', {'vehicle': 'space', 'scenario': 'mission'})

    def test_every_solver_registered(self):
        self.assertEqual(len(SOLVERS), 18)
        self.assertTrue({'aero_envelope', 'rocket_nozzle_sweep', 'wind_shear'} <= set(SOLVERS))
        result=self.request('/engineering')
        self.assertEqual(len(result['solvers']), 18)

    def test_every_solver_live_route(self):
        for analysis in SOLVERS:
            with self.subTest(analysis=analysis):
                value=self.request('/engineering/live', {'analysis':analysis})
                self.assertEqual(value['analysis'], analysis)
                self.assertIn(value['mission_context']['mode'], ('mission_snapshot', 'independent_design_study'))

    def test_live_study_does_not_change_state(self):
        before=self.request('/state')
        for analysis in ('beam', 'thermal', 'rocket_cycle', 'rocket_nozzle_sweep'):
            self.request('/engineering/live', {'analysis':analysis})
        after=self.request('/state')
        self.assertEqual(before['time_s'], after['time_s'])
        self.assertEqual(before['phase'], after['phase'])
        self.assertEqual(before['mass_kg'], after['mass_kg'])
        self.assertEqual(before['command'], after['command'])

    def test_aircraft_context_seeds_physical_values(self):
        self.request('/reset', {'vehicle':'aircraft', 'scenario':'mission'})
        actual=self.request('/state')
        sample=self.request('/engineering/live', {'analysis':'aero_envelope'})
        context=sample['mission_context']
        self.assertEqual(context['mode'],'mission_snapshot')
        self.assertIn('mass_kg',context['inputs_from_telemetry'])
        self.assertFalse(context['coupled_into_flight_dynamics'])
        self.assertAlmostEqual(sample['stall_speed_estimate_m_s']**2 * actual['environment']['density_kg_m3'] * actual['vehicle_parameters']['S_m2'] * 1.5 / (2 * 9.80665), actual['mass_kg'],delta=1e-5*actual['mass_kg'])

    def test_drone_battery_context(self):
        self.request('/reset', {'vehicle':'drone','scenario':'mission'})
        sample=self.request('/engineering/live', {'analysis':'power'})
        keys=sample['mission_context']['inputs_from_telemetry']
        self.assertIn('battery_capacity_Wh',keys)
        self.assertIn('load_W',keys)

    def test_unsupported_live_coupling_is_honest(self):
        result=self.request('/engineering/live', {'analysis':'robotics_route'})
        self.assertEqual(result['mission_context']['mode'],'independent_design_study')
        self.assertFalse(result['mission_context']['coupled_into_flight_dynamics'])
        self.assertTrue(result['mission_context']['notes'])

    def test_frontend_routes_and_cache(self):
        studio=(ROOT/'engineering-studio.js').read_text()
        ui=(ROOT/'index.html').read_text()
        api=(ROOT/'browser_bridge.py').read_text()
        sw=(ROOT/'service-worker.js').read_text()
        assert ui.count('id="engineeringRunLive"') == 1
        self.assertIn("'/engineering/live'",studio)
        self.assertIn("'/engineering/live'",api)
        self.assertIn('mission-ui-14.css?build=291',ui)
        self.assertIn('astra-browser-v292',sw)
        self.assertIn('aero_envelope:{',studio)
        self.assertIn('rocket_nozzle_sweep:{',studio)
        self.assertIn('wind_shear:{',studio)


if __name__ == '__main__': unittest.main()
