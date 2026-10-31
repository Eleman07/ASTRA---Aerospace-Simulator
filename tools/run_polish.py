"""Exercise the same internal validation entry point in editor and exported EXE."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--renderer',type=Path,default=ROOT/'build/toolchain/godot/Godot_v4.7.2-stable_win64.exe');parser.add_argument('--quality',default='high');args=parser.parse_args()
    renderer=args.renderer.resolve();output=ROOT/('test-results/polish-'+args.quality);log=Path(str(output)+'.log')
    command=[str(renderer),'--position','-10000,-10000','--resolution','1440x900','--rendering-method','gl_compatibility' if args.quality=='low' else 'forward_plus','--log-file',str(log)]
    if renderer.name.startswith('Godot_'):command+=['--path',str(ROOT/'desktop')]
    assets=renderer.parent/'assets' if (renderer.parent/'assets').is_dir() else ROOT/'assets'
    command+=['--','--assets',str(assets),'--quality',args.quality,'--polish-check',str(output),'--polish-fixtures',str(ROOT/'test-results/polish-fixtures.json')]
    log.write_text('',encoding='utf-8')
    report_path=Path(str(output)+'.json')
    if report_path.exists():report_path.unlink()
    with (ROOT/f'test-results/polish-{args.quality}-stdout.log').open('w',encoding='utf-8') as stream:
        child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+90
            while child.poll() is None:
                if time.monotonic()>deadline:raise TimeoutError('Polish validation timed out')
                text=log.read_text(encoding='utf-8',errors='replace') if log.exists() else ''
                if 'SCRIPT ERROR:' in text or '\nERROR:' in text:raise AssertionError(text[-4000:])
                time.sleep(.1)
            assert child.returncode==0
        finally:
            if child.poll() is None:child.terminate();child.wait(10)
    text=log.read_text(encoding='utf-8');assert 'SCRIPT ERROR:' not in text and '\nERROR:' not in text
    report=json.loads(Path(str(output)+'.json').read_text())
    assert report['unlimited_fps'] and report['vsync_disabled'] and report['audio_peak']>.0001
    expected_scale={'low':.65,'balanced':.67,'high':1.0,'ultra':1.15}[args.quality]
    assert abs(report['resolution_scale']-expected_scale)<1e-6
    if args.quality=='balanced' and report['renderer']=='forward_plus':
        assert report['scaling_3d_mode']==2, 'Balanced Forward+ must use temporal FSR2 upscaling'
    assert report['orion_rectangle_removed'] and report['orbital_exhaust'] and report['launch_exhaust']
    assert all(row['covered'] and row['chunks']<=97 for row in report['chunk_residency'])
    report['renderer_sha256']=hashlib.sha256(renderer.read_bytes()).hexdigest()
    Path(str(output)+'.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
