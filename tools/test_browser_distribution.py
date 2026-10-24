"""Offline-compatible Python bridge and static manifest smoke tests."""
import importlib, json, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import browser_bridge

class BrowserTests(unittest.TestCase):
    def query(self,path,payload=None):
        obj=json.loads(browser_bridge.route_raw(json.dumps({'path':path,'payload':payload or {},'method':'POST' if payload is not None else 'GET'})))
        self.assertTrue(obj['ok'],obj)
        return obj['data']
    def test_manifest_sources(self):
        paths=json.loads((ROOT/'browser-python-files.json').read_text())
        self.assertTrue(paths)
        for name in paths:self.assertTrue((ROOT/name).is_file(),name)
    def test_status(self):
        self.assertEqual(self.query('/status')['execution_mode'],'browser-pyodide')
    def test_core_physics(self):
        s=self.query('/reset',{'vehicle':'space','scenario':'mission'})
        self.assertEqual(s['vehicle'],'space')
        self.query('/launch',{})
        for _ in range(7):s=self.query('/step',{'dt_s':0.1})
        self.assertGreater(s['time_s'],0)
        self.assertGreater(s['altitude_m'],0)
    def test_models(self):
        self.assertIn('space',self.query('/models'))
    def test_engineering(self):
        self.assertIn('solvers',self.query('/engineering'))
    def test_engineering_execution(self):
        result=self.query('/engineering',{'analysis':'beam'})
        self.assertEqual(result['analysis'],'beam')
    def test_aircraft_and_drone(self):
        for kind in ('aircraft','drone'):
            snapshot=self.query('/reset',{'vehicle':kind,'scenario':'mission'})
            self.assertEqual(snapshot['vehicle'],kind)
            self.assertGreaterEqual(snapshot['altitude_m'],0)
    def test_requirements_live(self):
        snapshot=self.query('/requirements/verify',{'requirements':[{'id':'R-TIME','field':'time_s','operator':'>=','value':0,'unit':'s'}]})
        self.assertTrue(snapshot['verified'])
    def test_reject_bad(self):
        ans=json.loads(browser_bridge.route_raw(json.dumps({'path':'/invalid'})))
        self.assertFalse(ans['ok'])
if __name__=='__main__':unittest.main(verbosity=2)
