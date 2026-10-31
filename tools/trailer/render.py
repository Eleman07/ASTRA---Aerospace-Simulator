"""Capture native 3840x2160 ASTRA footage using Godot Movie Maker."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/astra-trailer-4k'
GODOT=ROOT/'build/toolchain/godot/Godot_v4.7.2-stable_win64_console.exe'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview',action='store_true');parser.add_argument('--shot',action='append');args=parser.parse_args()
    project=WORK/'project';shutil.copy2(Path(__file__).with_name('capture.gd'),project/'trailer_capture.gd')
    manifest=json.loads((WORK/'manifest.json').read_text())
    env=dict(os.environ)
    for key,relative in [('APPDATA','user-data'),('TEMP','temp'),('TMP','temp')]:
        path=WORK/relative;path.mkdir(exist_ok=True);env[key]=str(path)
    with (WORK/'import.log').open('w',encoding='utf-8') as log:
        subprocess.run([str(GODOT),'--headless','--editor','--path',str(project),'--import','--quit'],check=True,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90)
    for shot in manifest['shots']:
        if args.shot and shot['id'] not in args.shot:continue
        name=shot['id'];logpath=WORK/(name+('-preview.log' if args.preview else '-movie.log'))
        command=[str(GODOT),'--path',str(project),'--position','-10000,-10000','--resolution','1920x1080',
            '--rendering-method','forward_plus','--disable-vsync','--audio-driver','Dummy','--log-file',str(logpath)]
        if not args.preview:command+=['--write-movie',str(WORK/(name+'.avi')),'--fixed-fps',str(manifest['fps'])]
        command+=['--','--work',str(WORK),'--shot',name]
        if args.preview:command+=['--preview']
        print('CAPTURING',name,'PREVIEW' if args.preview else 'NATIVE 4K',flush=True)
        with (WORK/(name+'-stdout.log')).open('w',encoding='utf-8') as output:
            subprocess.run(command,check=True,cwd=project,env=env,stdout=output,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,timeout=600)
        log=logpath.read_text(encoding='utf-8',errors='replace')
        if 'SCRIPT ERROR:' in log or '\nERROR:' in log:raise AssertionError(log[-7000:])
        proof=json.loads((WORK/(name+('-preview.json' if args.preview else '-capture.json'))).read_text())
        assert proof['native_size']==[3840,2160] and proof['asset_loaded']
        print('CAPTURE PASS',name,proof['native_size'],proof['asset'],flush=True)

if __name__=='__main__':main()
