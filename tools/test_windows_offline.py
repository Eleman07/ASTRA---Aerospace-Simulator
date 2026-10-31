import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from windows_launcher import OfflineHandler


class WindowsOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),OfflineHandler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=3)

    def test_native_browser_transport_and_outgoing_network_policy(self):
        with urlopen(self.url+'/browser-api.js') as response:
            source=response.read().decode('utf-8');policy=response.headers['Content-Security-Policy']
        self.assertIn("fetch('/api/v1'+path",source)
        self.assertNotIn('new Worker',source)
        self.assertNotIn('setInterval',source)
        self.assertIn("connect-src 'self'",policy)
        self.assertIn("img-src 'self' blob: data:",policy)

    def test_browser_native_step_advances_without_pyodide(self):
        def post(path,payload):
            request=Request(self.url+'/api/v1'+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urlopen(request) as response:return json.load(response)
        post('/reset',{'vehicle':'drone'});post('/launch',{})
        state=post('/step',{'dt_s':.1})
        self.assertAlmostEqual(state['time_s'],.1)
        self.assertEqual(state['vehicle'],'drone')
