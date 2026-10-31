"""Native API parity, clock arbitration and SDK integration, no GPU required."""
import copy
import json
import math
from pathlib import Path
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from astra.client import AstraClient
from astra.engine import SimulationEngine
from desktop_runtime import DesktopRuntime,make_handler,visual_frame


class DesktopRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime=DesktopRuntime();self.runtime.start()
    def tearDown(self):self.runtime.close()

    def test_medium_graphics_preset_keeps_its_render_scale(self):
        view=self.runtime.dispatch('/desktop/view')
        self.assertEqual(view['settings']['quality'],'balanced')
        self.assertEqual(view['settings']['resolution_scale'],.67)

    def test_scientific_algorithms_have_identical_results(self):
        for vehicle,scenario in [('space','mission'),('space','orbital'),('space','planetary'),('aircraft','mission'),('drone','mission')]:
            reference=SimulationEngine()
            reference.reset(vehicle,scenario,advanced_models=True)
            self.runtime.dispatch('/reset',dict(vehicle=vehicle,scenario=scenario,advanced_models=True),'POST')
            reference.launch();self.runtime.dispatch('/launch',{},'POST')
            expected=reference.step(.4)
            actual=self.runtime.dispatch('/step',dict(dt_s=.4),'POST')
            self.assertEqual(actual,expected)
            if vehicle=='space' and scenario=='mission':
                launch_axis=self.runtime.dispatch('/desktop/snapshot')['visual']['vehicle_basis'][1]
                self.assertGreater(launch_axis[1],.999)

    def test_external_step_never_combines_with_desktop_clock(self):
        self.runtime.dispatch('/reset',dict(vehicle='drone',advanced_models=True),'POST')
        self.runtime.dispatch('/launch',{},'POST')
        self.runtime.dispatch('/desktop/clock',dict(owner='external'),'POST')
        for _ in range(10):self.runtime.dispatch('/step',dict(dt_s=.1),'POST')
        before=self.runtime.dispatch('/state')
        time.sleep(.06)
        self.assertEqual(before,self.runtime.dispatch('/state'))
        self.assertAlmostEqual(before['time_s'],1)
        self.assertEqual(self.runtime.clock_owner,'external')
        self.runtime.dispatch('/command',dict(mode='python',throttle_pct=50),'POST')
        before=self.runtime.dispatch('/state')
        with self.assertRaises(ValueError):
            self.runtime.dispatch('/desktop/pilot',dict(armed=True,neutral_acquired=True,command=dict(throttle_pct=10)),'POST')
        time.sleep(.04)
        self.assertEqual(self.runtime.dispatch('/state'),before)
        self.assertFalse(self.runtime.controller_armed)

    def test_automatic_clock_pauses_and_has_finite_steps(self):
        self.runtime.dispatch('/reset',dict(vehicle='drone',advanced_models=True),'POST')
        self.runtime.dispatch('/desktop/play',{},'POST');time.sleep(.07)
        self.runtime.dispatch('/desktop/pause',{},'POST')
        before=self.runtime.dispatch('/state')
        self.assertGreater(before['time_s'],0)
        time.sleep(.04)
        self.assertEqual(before,self.runtime.dispatch('/state'))
        self.assertLess(before['time_s'],1)

    def test_snapshot_reads_are_pure_and_preserve_units(self):
        snap=self.runtime.dispatch('/desktop/snapshot')
        other=self.runtime.dispatch('/desktop/snapshot')
        self.assertEqual(snap,other)
        self.assertEqual(len(snap['state']['science']['disciplines']),13)
        basis=snap['visual']['vehicle_basis']
        for vector in basis:self.assertAlmostEqual(sum(v*v for v in vector),1,places=8)
        json.dumps(snap,allow_nan=False)

    def test_arming_and_input_loss_return_to_gnc(self):
        with self.assertRaises(ValueError):self.runtime.dispatch('/desktop/pilot',dict(armed=True,command={}), 'POST')
        self.runtime.dispatch('/desktop/pilot',dict(armed=True,neutral_acquired=True,command=dict(throttle_pct=55)), 'POST')
        self.assertEqual(self.runtime.engine.command['mode'],'manual')
        with self.runtime.lock:self.runtime.last_pilot_wall=time.monotonic()-1
        time.sleep(.05)
        self.assertFalse(self.runtime.controller_armed)
        self.assertEqual(self.runtime.engine.command['mode'],'auto')

    def test_compact_pilot_reply_applies_same_command_without_building_visual_snapshot(self):
        from unittest.mock import patch
        command=dict(throttle_pct=73,roll_deg=15,pitch_deg=90,yaw_deg=-12)
        with patch.object(self.runtime,'_snapshot',side_effect=AssertionError('input must not generate full telemetry')):
            reply=self.runtime.dispatch('/desktop/pilot',dict(armed=True,neutral_acquired=True,compact=True,command=command),'POST')
        self.assertTrue(reply['controller_armed']);self.assertEqual(reply['clock_owner'],'desktop')
        self.assertEqual(reply['command'],self.runtime.engine.command)
        self.assertEqual(reply['command']['pitch_deg'],90)
        self.assertEqual(reply['command']['mode'],'manual')
        self.assertEqual(self.runtime.engine.t,0)
        reply['command']['throttle_pct']=0
        self.assertEqual(self.runtime.engine.command['throttle_pct'],73)
        # Full response remains available to existing API clients.
        full=self.runtime.dispatch('/desktop/pilot',dict(armed=True,command=command),'POST')
        self.assertEqual(full['state']['command']['throttle_pct'],73)

    def test_invalid_inputs_do_not_advance_or_create_nan(self):
        before=self.runtime.engine.t
        for value in [float('nan'),float('inf'),-1,61]:
            with self.assertRaises(ValueError):self.runtime.dispatch('/step',dict(dt_s=value),'POST')
        self.assertEqual(before,self.runtime.engine.t)
        with self.assertRaises(ValueError):self.runtime.dispatch('/desktop/speed',dict(speed=float('nan')),'POST')

    def test_all_eighteen_solvers_and_celestial_api_survive(self):
        solvers=self.runtime.dispatch('/engineering')
        self.assertEqual(len(solvers['solvers']),18)
        result=self.runtime.dispatch('/engineering',dict(analysis='beam'),'POST')
        self.assertGreater(result['modal']['first_frequency_Hz'],0)
        celestial=self.runtime.dispatch('/celestial?date=2026-10-28T00%3A00%3A00Z')
        self.assertGreater(len(celestial['objects']),8)

    def test_recording_does_not_influence_physics(self):
        self.runtime.dispatch('/reset',dict(vehicle='drone'),'POST')
        self.runtime.dispatch('/launch',{},'POST')
        self.runtime.dispatch('/step',dict(dt_s=.4),'POST')
        before=self.runtime.dispatch('/state')
        recording=self.runtime.dispatch('/desktop/recording')
        self.assertGreater(len(recording['samples']),0)
        self.assertEqual(self.runtime.dispatch('/state'),before)
        self.assertEqual(recording['units'],'SI')

    def test_presentation_and_asset_selection_never_change_physics(self):
        before=self.runtime.dispatch('/state')
        catalogue=self.runtime.dispatch('/desktop/assets')
        ids={m['id'] for m in catalogue['models']}
        self.assertTrue(set(catalogue['defaults'].values()).issubset(ids))
        self.assertNotIn('nasa-apollo-lm',ids)
        reply=self.runtime.dispatch('/desktop/view',dict(model='space-x-crew-dragon',azimuth_deg=70,distance_m=18,show_ui=False),'POST')
        self.assertEqual(reply['settings']['model'],'space-x-crew-dragon')
        self.assertEqual(self.runtime.dispatch('/state'),before)

    def test_invalid_view_updates_are_atomic_and_capture_requires_explicit_path(self):
        before=self.runtime.dispatch('/desktop/view')
        for payload in [dict(exposure=float('nan')),dict(model='homemade'),dict(resolution_scale=.01),dict(show_ui=1)]:
            with self.assertRaises(ValueError):self.runtime.dispatch('/desktop/view',payload,'POST')
            self.assertEqual(self.runtime.dispatch('/desktop/view'),before)
        with self.assertRaises(ValueError):self.runtime.dispatch('/desktop/capture',dict(path='relative.png'),'POST')

    def test_free_flight_uses_same_physics_without_automatic_mission_guidance(self):
        for vehicle,scenario in [('space','mission'),('space','orbital'),('space','planetary'),('aircraft','mission'),('drone','mission')]:
            snap=self.runtime.dispatch('/desktop/free',dict(vehicle=vehicle,scenario=scenario,advanced_models=True),'POST')
            self.assertEqual(snap['desktop']['play_mode'],'free');self.assertFalse(snap['desktop']['running'])
            self.assertEqual(snap['state']['command']['mode'],'manual')
            if vehicle=='space' and scenario=='mission':
                with self.runtime.lock:
                    self.runtime.dispatch('/desktop/play',{},'POST')
                    waiting=self.runtime._step(.2);self.runtime.running=False
                self.assertFalse(waiting['mission_started']);self.assertEqual(waiting['time_s'],0)
                self.runtime.dispatch('/command',dict(throttle_pct=100,pitch_deg=90,mode='manual'),'POST')
                snap=self.runtime.dispatch('/desktop/snapshot')
            reference=SimulationEngine();reference.reset(vehicle,scenario,advanced_models=True)
            command=copy.deepcopy(snap['state']['command']);reference.launch();reference.set_command(command)
            # Native vertical pitch support already exists in the adapter.
            reference.command.update(command)
            with self.runtime.lock:
                self.runtime.dispatch('/desktop/play',{},'POST');self.runtime.running=False
            self.assertEqual(reference.step(.2),self.runtime.dispatch('/step',dict(dt_s=.2),'POST'))
            with self.runtime.lock:self.runtime._disarm('TEST')
            self.assertFalse(self.runtime.running);self.assertEqual(self.runtime.engine.command['mode'],'manual')
        self.runtime.dispatch('/reset',dict(vehicle='drone'),'POST')
        self.assertEqual(self.runtime.play_mode,'mission')

    def test_detailed_instruments_are_read_only_and_distinguish_units_and_frames(self):
        for vehicle,scenario in [('space','orbital'),('space','planetary'),('aircraft','mission'),('drone','mission')]:
            self.runtime.dispatch('/reset',dict(vehicle=vehicle,scenario=scenario),'POST')
            before=self.runtime.dispatch('/state')
            sections=self.runtime.dispatch('/desktop/flight-details')
            self.assertEqual(before,self.runtime.dispatch('/state'));self.assertEqual(len(sections),6)
            pos=next(s for s in sections if s['id']=='position')
            self.assertIn('ECI' if scenario=='orbital' else 'ENU' if scenario=='planetary' else 'NED',pos['note'])
            first=pos['rows'][0];self.assertEqual(first['unit'],'m')
            self.assertEqual(first['value'],before['position_eci_m' if scenario=='orbital' else 'position_enu_m' if scenario=='planetary' else 'position_ned_m'][0])
            json.dumps(sections,allow_nan=False)
        before=self.runtime.dispatch('/state')
        self.runtime.dispatch('/desktop/view',dict(distance_m=25_000_000),'POST')
        self.assertEqual(before,self.runtime.dispatch('/state'))


class NativeSDKTests(unittest.TestCase):
    def setUp(self):
        self.runtime=DesktopRuntime();self.runtime.start()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.runtime))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=AstraClient('http://127.0.0.1:'+str(self.server.server_port))
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.runtime.close();self.thread.join(3)
    def test_sdk_controls_same_native_engine(self):
        status=self.client.status()
        self.assertEqual(status['execution_mode'],'desktop-native')
        self.assertFalse(status['browser_required'])
        self.client.pause();self.client.reset('space','orbital',advanced_models=True)
        self.client.launch();self.client.command(mode='python',attitude_target_deg=[10,5,0])
        state=self.client.step(.2)
        self.assertEqual(state,self.client.snapshot()['state'])
        self.assertEqual(self.client.snapshot()['desktop']['clock_owner'],'external')
        self.assertEqual(len(self.client.engineering_solvers()['solvers']),18)
        self.assertTrue(self.client.recording()['samples'])
    def test_legacy_methods_remain_available(self):
        self.assertTrue(self.client.models());self.assertTrue(self.client.vehicle_parts())
        self.assertEqual(self.client.engineering('beam')['analysis'],'beam')
        self.assertGreater(len(self.client.celestial('2026-10-28T00:00:00Z')['objects']),8)

    def test_independent_sdk_reports_its_actual_module_and_desktop_methods(self):
        from astra_sdk import AstraClient as IndependentClient,CLIENT_VERSION
        self.assertIs(IndependentClient,AstraClient)
        client=IndependentClient(self.client.base_url)
        self.assertTrue(callable(client.pause));self.assertTrue(callable(client.play))
        self.assertTrue(callable(client.step));self.assertTrue(callable(client.free_flight))
        info=client.status()
        self.assertEqual(info['client_version'],CLIENT_VERSION)
        self.assertIn('astra_sdk',info['client_module'])
        self.assertIn('desktop_version',info)
        client.pause()

    def test_sdk_camera_and_telemetry_are_pure_reads_of_scientific_state(self):
        before=self.client.state()
        self.client.set_camera(70,15,12)
        self.assertEqual(self.client.view()['settings']['distance_m'],12)
        self.assertGreater(len(self.client.visual_models()['models']),5)
        self.assertFalse(self.client.renderer_status()['connected'])
        self.assertEqual(list(self.client.telemetry(samples=2,interval_s=.001)),[before,before])

    def test_sdk_exposes_gioca_catalog_and_orbital_sas(self):
        catalog=self.client.game_catalog('space')
        self.assertEqual(len(catalog['space']),6)
        self.client.reset('space','orbital',advanced_models=True)
        result=self.client.orbital_attitude('prograde')
        self.assertEqual(result['command']['attitude_sas_mode'],'prograde')
        self.assertFalse(self.client.game_state()['game']['active'])


if __name__=='__main__':unittest.main()
