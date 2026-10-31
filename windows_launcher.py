"""ASTRA offline Windows launcher; also runs from source with standard Python."""
from __future__ import annotations
import argparse
import json
import sys
import webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
import server

# Preserve server.py's external-controller viewer mode. This launcher gives the
# browser ownership of /step so keyboard/touch/controllers advance native Python.
OFFLINE_API = '''
export async function browserApi(path,payload){
 const post=payload!==undefined;
 const response=await fetch('/api/v1'+path,{method:post?'POST':'GET',headers:{'Content-Type':'application/json'},body:post?JSON.stringify(payload):undefined,cache:'no-store'});
 const data=await response.json();if(!response.ok)throw Error(data.error||('HTTP '+response.status));return data;
}
export function browserReady(){return Promise.resolve(true);}
'''


class OfflineHandler(server.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/browser-api.js':
            return self.send_data(OFFLINE_API, 'text/javascript; charset=utf-8')
        return super().do_GET()

    def end_headers(self):
        # The distribution uses only local code/assets. Outgoing fetches, remote
        # images and worker imports cannot become a hidden runtime dependency.
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; "
                         "connect-src 'self'; worker-src 'self'; font-src 'self'; object-src 'none'")
        super().end_headers()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if getattr(sys,'frozen',False):server.ROOT=Path(sys._MEIPASS)
    if args.self_test:
        from browser_bridge import route_raw
        for vehicle in ('aircraft','drone','space'):
            for path,payload in (('/reset',{'vehicle':vehicle}),('/launch',{}),('/step',{'dt_s':.1})):
                reply=json.loads(route_raw(json.dumps({'method':'POST','path':path,'payload':payload})))
                if not reply.get('ok'):raise RuntimeError(reply)
        for vehicle,scenario in (('aircraft','mission'),('drone','mission'),('space','mission'),('space','orbital'),('space','planetary')):
            for path,payload in (('/reset',dict(vehicle=vehicle,scenario=scenario,advanced_models=True)),
                                 ('/launch',{}),('/step',{'dt_s':.1})):
                reply=json.loads(route_raw(json.dumps({'method':'POST','path':path,'payload':payload})))
                if not reply.get('ok'):raise RuntimeError(reply)
            if len(reply['data']['science']['disciplines'])!=13:
                raise RuntimeError('Advanced science modules not bundled')
        for name in ('index.html','app.js','controller-profiles.js','cinematic-renderer.js',
                     'science-ui.js','assets/vehicle-models.json'):
            if not (server.ROOT/name).is_file():raise RuntimeError('Missing bundled asset: '+name)
        print('ASTRA OFFLINE SELF TEST PASS',flush=True)
        return
    try:httpd=ThreadingHTTPServer(('127.0.0.1',args.port),OfflineHandler)
    except OSError as exc:
        print(f'Cannot start ASTRA on port {args.port}: {exc}\nTry ASTRA.exe --port 8766',flush=True)
        return 1
    httpd.daemon_threads=True
    url=f'http://127.0.0.1:{httpd.server_port}'
    print('ASTRA OFFLINE:',url,flush=True)
    print('Native Python physics. No internet or separate Python installation required in the Windows package.',flush=True)
    print('Keep this window open. Close with Ctrl+C. API: '+url+'/api/v1/status',flush=True)
    if not args.no_open:webbrowser.open(url)
    try:httpd.serve_forever()
    except KeyboardInterrupt:pass
    finally:httpd.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
