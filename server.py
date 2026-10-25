#!/usr/bin/env python3
"""Local ASTRA simulation API and shared WebGL viewer. Run python server.py --open."""
import argparse
import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from browser_bridge import route_raw

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock()
BROWSER_API=r'''
export async function browserApi(path,payload){
  const poll=path==='/step';
  const target='/api/v1'+(poll?'/state':path);
  const post=payload!==undefined&&!poll;
  const response=await fetch(target,{method:post?'POST':'GET',headers:{'Content-Type':'application/json'},body:post?JSON.stringify(payload):undefined,cache:'no-store'});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||('HTTP '+response.status));
  return data;
}
export function browserReady(){return Promise.resolve(true)}
// 3D viewer polls the existing Step control, but polling never advances physics.
// The Python GNC script owns simulation time via /api/v1/step.
setInterval(()=>{const step=document.getElementById('step');if(step&&!step.disabled)step.click()},200);
'''
LOCAL_SW=r'''self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.registration.unregister()));'''

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT),**kwargs)
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def send_data(self,data,mime='application/json',status=200):
        if isinstance(data,str):data=data.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.startswith('/api/v1/'):return self.api()
        if path=='/browser-api.js':return self.send_data(BROWSER_API,'text/javascript; charset=utf-8')
        if path=='/service-worker.js':return self.send_data(LOCAL_SW,'text/javascript; charset=utf-8')
        if any(part.startswith('.') for part in path.split('/') if part) or '/__pycache__/' in path:
            return self.send_error(404)
        return super().do_GET()
    def do_POST(self):
        if urlsplit(self.path).path.startswith('/api/v1/'):return self.api()
        return self.send_error(404)
    def api(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>2_000_000:return self.send_data('{"error":"invalid body size"}',status=413)
            payload=json.loads(self.rfile.read(length) or b'{}') if self.command=='POST' else {}
            if not isinstance(payload,dict):raise ValueError('Request body must be a JSON object')
            request={'method':self.command,'path':self.path.removeprefix('/api/v1'),'payload':payload}
            with LOCK: reply=json.loads(route_raw(json.dumps(request)))
            status=200 if reply.get('ok') else 400
            data=reply.get('data') if reply.get('ok') else {'error':reply.get('error','Invalid request')}
            if reply.get('ok') and request['path']=='/status' and isinstance(data,dict):
                data=dict(data,execution_mode='local-http',api='local-http')
            return self.send_data(json.dumps(data,allow_nan=False),status=status)
        except (ValueError,TypeError) as exc:
            return self.send_data(json.dumps({'error':str(exc)}),status=400)
        except Exception as exc:
            return self.send_data(json.dumps({'error':str(exc)}),status=500)
    def log_message(self,fmt,*args):
        if not self.path.startswith('/api/v1/'):
            super().log_message(fmt,*args)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.daemon_threads=True
    url=f'http://127.0.0.1:{args.port}'
    print('ASTRA LOCAL 3D VIEWER:',url,flush=True)
    print('ASTRA PYTHON API:',url+'/api/v1/status',flush=True)
    print('Open viewer and run examples/gnc_demo.py in a second terminal.')
    if args.open:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
