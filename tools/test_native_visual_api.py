"""Exercise actual Python camera/model/capture requests against a native window."""
import argparse
import json
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_runtime import DesktopRuntime,make_handler
from astra.client import AstraClient

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--renderer',type=Path,default=ROOT/'build/toolchain/godot/Godot_v4.7.2-stable_win64.exe');args=parser.parse_args()
    runtime=DesktopRuntime()
    runtime.visuals.update({'quality':'high','resolution_scale':1.0})
    runtime.start()
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(runtime));server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    log=ROOT/'test-results/visual-api-native.log'
    command=[str(args.renderer.resolve()),'--position','-10000,-10000','--resolution','1440x900','--rendering-method','forward_plus','--log-file',str(log)]
    if args.renderer.name.startswith('Godot_'):command+=['--path',str(ROOT/'desktop')]
    assets=args.renderer.parent/'assets' if (args.renderer.parent/'assets').is_dir() else ROOT/'assets'
    url=f'http://127.0.0.1:{server.server_port}'
    command+=['--','--api',url,'--assets',str(assets.resolve()),'--quality','high']
    process=subprocess.Popen(command,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
    client=AstraClient(url);shots=[]
    try:
        deadline=time.monotonic()+60
        while not client.renderer_status()['connected']:
            if time.monotonic()>deadline:raise TimeoutError('Native renderer not ready')
            time.sleep(.1)
        client.pause();client.reset('space','orbital',advanced_models=True);client.launch();client.step(.2)
        before=client.state()
        for model in ['nasa-orion-spacecraft','space-x-crew-dragon']:
            view=client.set_view(model=model,show_ui=False,azimuth_deg=55,elevation_deg=18,distance_m=13,exposure=.8)
            deadline=time.monotonic()+30
            while True:
                report=client.renderer_status()
                if report.get('view_revision')==view['revision'] and report.get('asset_id')==model and report.get('asset_loaded'):break
                if time.monotonic()>deadline:raise TimeoutError('Native asset selection not applied: '+str(report))
                time.sleep(.1)
            shot=client.capture(ROOT/'test-results'/('modern-'+model+'.png'),overwrite=True)
            data=Path(shot['path']).read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n'
            assert struct.unpack_from('>II',data,16)==(1440,900)
            assert client.state()==before
            shots.append(dict(model=model,capture=shot,render=report))
        client.reset('aircraft',advanced_models=True);client.launch()
        client.command(mode='manual',throttle_pct=100,roll_deg=0,pitch_deg=0,yaw_deg=0)
        air=client.step(60)
        if air['altitude_m']<5:air=client.step(30)
        assert air['phase'] not in ('CRASHED','ABORTED') and air['altitude_m']>1
        view=client.set_view(model='auto',show_ui=False,exposure=1.,azimuth_deg=55,elevation_deg=10,distance_m=17)
        deadline=time.monotonic()+30
        while True:
            render=client.renderer_status()
            if render.get('view_revision')==view['revision'] and render.get('asset_id')=='innerscene-twin-turboprop':break
            if time.monotonic()>deadline:raise TimeoutError('Aircraft preview not ready')
            time.sleep(.1)
        time.sleep(.7)
        aircraft=client.capture(ROOT/'test-results/README-aircraft.png',overwrite=True)
        assert client.state()==air
        result=dict(version=client.status()['desktop_version'],camera_api='PASS',png_capture='PASS',physics_unchanged=True,shots=shots,aircraft_preview=dict(capture=aircraft,altitude_m=air['altitude_m'],time_s=air['time_s']),
                    renderer_sha256=hashlib.sha256(args.renderer.read_bytes()).hexdigest())
        (ROOT/'test-results/visual-api-validation.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    finally:
        process.terminate();process.wait(timeout=15);server.shutdown();server.server_close();runtime.close()
    text=log.read_text(encoding='utf-8',errors='replace')
    assert 'SCRIPT ERROR:' not in text and '\nERROR:' not in text,text[-10000:]

if __name__=='__main__':main()
