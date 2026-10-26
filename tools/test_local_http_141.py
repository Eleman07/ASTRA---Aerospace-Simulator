"""Local CPython HTTP transport regression tests with a temporary loopback server."""
import json
import pathlib
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server import Handler


class Http141Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.root='http://127.0.0.1:'+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def call(self,path,payload=None):
        req=Request(self.root+path,
            method='POST' if payload is not None else 'GET',
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=3) as response:
            self.assertEqual(response.status,200)
            return json.load(response)

    def test_local_http_version_and_mode(self):
        result=self.call('/api/v1/status')
        self.assertEqual(result['version'],'1.4.1')
        self.assertEqual(result['execution_mode'],'local-http')
        self.assertEqual(result['api'],'local-http')

    def test_local_http_wind_active_and_live_solver(self):
        s=self.call('/api/v1/reset',{
            'vehicle':'aircraft','scenario':'mission',
            'surface_layer_wind':{
                'reference_wind_ned_m_s':[8,0,0],
                'reference_height_m':10,
                'roughness_length_m':.03,
                'boundary_layer_height_m':100,
            }
        })
        self.assertEqual(s['environment']['wind_profile_model'],'MONIN_OBUKHOV_SURFACE_LAYER')
        self.assertEqual(s['version'],'1.4.1')
        analysis=self.call('/api/v1/engineering/live',{'analysis':'wind_shear'})
        self.assertTrue(analysis['mission_context']['coupled_into_flight_dynamics'])
        self.assertEqual(analysis['model'],'MONIN_OBUKHOV_WIND_PROFILE')


if __name__=='__main__':unittest.main()
