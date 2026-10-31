"""Run native renderer offscreen with the unchanged Python physics host."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_runtime import DesktopRuntime,make_handler

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--renderer',type=Path,default=ROOT/'build/toolchain/godot/Godot_v4.7.2-stable_win64.exe')
    p.add_argument('--pck',type=Path)
    p.add_argument('--quality',default='high')
    args=p.parse_args()
    output=ROOT/'test-results'/('native-suite-'+args.quality)
    output.parent.mkdir(exist_ok=True)
    for suffix in ('.log','.json'):
        old=Path(str(output)+suffix)
        if old.exists():old.unlink()
    runtime=DesktopRuntime()
    runtime.visuals.update({'quality':args.quality,
        'resolution_scale':{'low':.65,'balanced':.67,'high':1.0,'ultra':1.15}[args.quality]})
    runtime.start()
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(runtime))
    server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    command=[str(args.renderer.resolve()),'--position','-10000,-10000','--resolution','1440x900',
             '--rendering-method','gl_compatibility' if args.quality=='low' else 'forward_plus',
             '--log-file',str(output)+'.log']
    if args.pck:command+=['--main-pack',str(args.pck.resolve())]
    elif args.renderer.name.startswith('Godot_'):command+=['--path',str(ROOT/'desktop')]
    assets=args.renderer.parent/'assets' if (args.renderer.parent/'assets').is_dir() else ROOT/'assets'
    command+=['--','--api',f'http://127.0.0.1:{server.server_port}','--assets',str(assets.resolve()),
              '--quality',args.quality,'--smoke-suite',str(output)]
    try:
        subprocess.run(command,cwd=ROOT,check=True,timeout=180,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        log=Path(str(output)+'.log').read_text(encoding='utf-8',errors='replace')
        if 'SCRIPT ERROR:' in log or '\nERROR:' in log:raise AssertionError(log[-12000:])
        report=json.loads(Path(str(output)+'.json').read_text())
        assert len(report['cases'])==5 and report['solvers']==18
        assert abs(report['resolution_scale']-{'low':.65,'balanced':.67,'high':1.0,'ultra':1.15}[args.quality])<1e-6
        assert all(case['screenshot'] and case['loaded'] and case['disciplines']==13 and case['time_s']>0 for case in report['cases'])
        assert report['procedural_vehicles'] is False
        assert report['cases'][0]['launch_vertical'],report['cases'][0]
        assert len(report['secondary_models'])==3 and all(row['loaded'] for row in report['secondary_models'])
        assert all(row['launch_vertical'] for row in report['secondary_models'])
        assert next(row for row in report['secondary_models'] if row['model_id']=='merlo-h6')['rotor_pivots']==6
        assert len(report['asset_imports'])==3 and all(row['loaded'] and row['screenshot'] for row in report['asset_imports'])
        assert len(report['free_flight'])==3 and all(row['manual'] for row in report['free_flight'])
        assert len(report['globes'])==2 and all(row['local_patch_hidden'] and row['screenshot'] for row in report['globes'])
        assert report['detailed_instruments']>12
        report['renderer_executable']=str(args.renderer.resolve())
        report['renderer_sha256']=hashlib.sha256(args.renderer.read_bytes()).hexdigest()
        Path(str(output)+'.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        server.shutdown();server.server_close();runtime.close();thread.join(3)

if __name__=='__main__':main()
