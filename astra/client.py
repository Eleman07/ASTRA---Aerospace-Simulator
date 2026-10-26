"""ASTRA Python HTTP SDK. Supports original and Engineering 1.4 API."""
import json
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

class AstraClient:
    def __init__(self,base_url='http://127.0.0.1:8765',timeout_s=30):
        self.base_url=base_url.rstrip('/')
        self.timeout_s=timeout_s
        if 'github.io' in self.base_url.lower():
            raise ValueError('GitHub Pages runs a browser-local Pyodide engine, not an HTTP API')
    def _request(self,endpoint,payload=None):
        data=None if payload is None else json.dumps(payload,allow_nan=False).encode()
        req=Request(self.base_url+endpoint,data=data,method='POST' if data is not None else 'GET',headers={'Content-Type':'application/json','Accept':'application/json'})
        try:
            with urlopen(req,timeout=self.timeout_s) as response:return json.load(response)
        except HTTPError as err:
            raise RuntimeError(f'ASTRA HTTP {err.code}: {err.read().decode("utf-8",errors="replace")}') from err
        except URLError as err:
            raise ConnectionError(f'ASTRA server unavailable at {self.base_url}. Run python server.py --open first.') from err
    def status(self):return self._request('/api/v1/status')
    def models(self):return self._request('/api/v1/models')
    def state(self):return self._request('/api/v1/state')
    def reset(self,vehicle='space',scenario='mission',**kwargs):
        return self._request('/api/v1/reset',{'vehicle':vehicle,'scenario':scenario,**kwargs})
    def launch(self):return self._request('/api/v1/launch',{})
    def step(self,dt_s=0.1):return self._request('/api/v1/step',{'dt_s':dt_s})
    def command(self,**kwargs):return self._request('/api/v1/command',kwargs)
    def stage(self):return self._request('/api/v1/stage',{})
    def engineering(self,analysis,**kwargs):return self._request('/api/v1/engineering',{'analysis':analysis,**kwargs})
    def engineering_live(self,analysis,**kwargs):return self._request('/api/v1/engineering/live',{'analysis':analysis,**kwargs})
    def engineering_solvers(self):return self._request('/api/v1/engineering')
    def vehicle_parts(self):return self._request('/api/v1/vehicle-parts')
    def inject_fault(self,**kwargs):return self._request('/api/v1/fault',kwargs)
    def clear_faults(self):return self._request('/api/v1/fault/clear',{})
    def close(self):pass
