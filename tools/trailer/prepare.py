"""Record genuine ASTRA desktop/SDK states and stage an isolated movie project."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/astra-trailer-4k'
PROJECT=WORK/'project'
FPS=30

PYTHON_CODE='''from astra_sdk import AstraClient

client = AstraClient()
client.pause()
state = client.reset("drone", advanced_models=True)
client.launch()

target_m = 3.0
dt_s = 1 / 30
samples = []

for frame in range(300):
    nav = state["navigation_estimate"]
    error = target_m - nav["altitude_m"]
    accel = 3.0*error - 2.8*nav["vertical_speed_m_s"]
    thrust = state["vehicle_parameters"]["max_thrust_N"]
    throttle = state["mass_kg"]*(9.80665+accel)
    throttle = max(0, min(100, 100*throttle/thrust))
    client.command(mode="python", throttle_pct=throttle,
                   roll_deg=0, pitch_deg=0, yaw_deg=0)
    state = client.step(dt_s)
    samples.append(client.snapshot())
'''

def write(path,data):
    path.write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False),encoding='utf-8')

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    payload=Path(build['payload'])
    assert build['version']=='2.3.2'
    assert hashlib.sha256((payload/'ASTRA.exe').read_bytes()).hexdigest()==build['executable_sha256']
    sys.path.insert(0,str(ROOT/'test-results/desktop-sdk-installed'))
    from astra_sdk import AstraClient,CLIENT_VERSION
    assert 'desktop-sdk-installed' in AstraClient.client_info()['client_module']
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    url=f'http://127.0.0.1:{port}'
    host=subprocess.Popen([str(payload/'ASTRA.exe'),'--serve','--port',str(port),'--smoke',str(WORK/'isolated-host')],
        cwd=payload,creationflags=subprocess.CREATE_NO_WINDOW)
    client=AstraClient(url,timeout_s=180)
    deadline=time.monotonic()+40
    while True:
        try:
            if client.status()['process_id']==host.pid:break
        except (ConnectionError,RuntimeError):pass
        if time.monotonic()>deadline:raise TimeoutError('isolated ASTRA host')
        time.sleep(.2)
    models=client.models()
    shots=[]
    def warm(seconds):
        for i in range(0,seconds,5):client.step(min(5,seconds-i))
    def record(name,seconds,control=None):
        frames=[]
        for i in range(round(seconds*FPS)):
            if control:client.command(**control(i/FPS))
            state=client.step(1/FPS)
            if state['phase'] in ('CRASHED','ABORTED','LANDED'):raise RuntimeError((name,i,state['phase']))
            frames.append(client.snapshot())
        print(name,'recorded',len(frames),'frames; altitude',round(frames[0]['state']['altitude_m'],2),'->',round(frames[-1]['state']['altitude_m'],2),flush=True)
        return frames
    def shot(name,frames,**kwargs):
        path=WORK/(name+'.json');write(path,frames)
        shots.append(dict(id=name,path=str(path),duration=len(frames)/FPS,frames=len(frames),**kwargs))
    try:
        client.reset('space','mission',model_id='dardo-lifting-body',advanced_models=True)
        client.launch();warm(180)
        space=record('Falcon9_space_master',13)
        assert min(row['state']['altitude_m'] for row in space)>100000
        common=dict(asset='space-x-crew-dragon',exposure=.84,fov=43)
        shot('01_orbit',space[:240],camera=[64,13,36,90,7,31],title='A S T R A',subtitle='ENGINEER THE NEXT FRONTIER',**common)
        shot('02_detail',space[240:],camera=[172,5,27,190,3,23],title='PRECISION IN MOTION',subtitle='FALCON 9  /  SPACEFLIGHT',**common)
        client.reset('aircraft',advanced_models=True);client.launch();warm(145)
        plane=record('Aircraft_flight',10,lambda t:dict(mode='manual',throttle_pct=87,roll_deg=18*math.sin(math.pi*t/10),pitch_deg=5,yaw_deg=85))
        shot('03_aircraft',plane,asset='auto',exposure=.82,fov=42,camera=[136,12,29,110,9,25],title='OWN THE ATMOSPHERE',subtitle='FIXED-WING FLIGHT  /  PHYSICS-DRIVEN AERODYNAMICS')
        client.reset('drone',advanced_models=True);client.launch();warm(30)
        drone=record('Drone_flight',8)
        shot('04_drone',drone,asset='auto',exposure=.86,fov=42,camera=[44,18,2.3,85,13,1.95],title='CONTROL EVERY AXIS',subtitle='UAV OPERATIONS  /  SIX-DEGREE-OF-FREEDOM DYNAMICS')
        os.environ['ASTRA_API_URL']=url
        namespace={};exec(compile(PYTHON_CODE,'recorded_python_controller.py','exec'),namespace)
        py=namespace['samples'];state=namespace['state']
        assert len(py)==300 and state['command']['mode']=='python'
        assert abs(state['time_s']-10)<1e-6 and abs(state['altitude_m']-3)<.5
        shot('05_python',py,asset='auto',exposure=.86,fov=42,camera=[55,14,2.8,67,12,2.6],title='CODE THE FLIGHT',subtitle='PYTHON API  /  CLOSED-LOOP CONTROL',python=True)
        (WORK/'recorded_python_controller.py').write_text(PYTHON_CODE,encoding='utf-8')
        print('Python SDK loop:',CLIENT_VERSION,'300 real commands; final altitude',state['altitude_m'],flush=True)
        client.free_flight('aircraft',advanced_models=True)
        client.command(mode='manual',throttle_pct=100,pitch_deg=0,roll_deg=0,yaw_deg=0)
        client.play();client.acquire_clock('external');warm(90)
        free=record('Free_flight',10,lambda t:dict(mode='manual',throttle_pct=90,roll_deg=22*math.sin(math.pi*t/10),pitch_deg=6,yaw_deg=0))
        assert all(s['desktop']['play_mode']=='free' and s['state']['command']['mode']=='manual' for s in free)
        shot('06_freeflight',free,asset='auto',exposure=.82,fov=43,camera=[145,14,29,123,10,26],title='YOUR FLIGHT. YOUR RULES.',subtitle='FREE FLIGHT  /  SPACE  ·  AIRCRAFT  ·  UAV',native_ui=True)
        shot('07_portfolio',space[-210:],camera=[226,8,43,242,5,48],title='EXPLORE THE NEXT FRONTIER',subtitle='elemanprojects.com',outro=True,**common)
        provenance=dict(host_sha256=build['executable_sha256'],renderer_sha256=build['renderer_sha256'],
            sdk_sha256=build['sdk_sha256'],client_info=AstraClient.client_info(),desktop_version=build['version'],
            actual_sdk_commands=300,python_final_altitude_m=state['altitude_m'],python_target_m=3,
            actual_simulator_state=True,frame_source='isolated frozen ASTRA Desktop HTTP API',
            actual_game_mode='free',no_microphone_recording=True,simulator_audio_in_final=False)
        write(WORK/'provenance.json',provenance)
    finally:
        host.terminate();host.wait(timeout=10)
    shutil.copytree(ROOT/'desktop',PROJECT,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.godot'))
    fonts=PROJECT/'fonts';fonts.mkdir(exist_ok=True)
    for name in ['bahnschrift.ttf','consola.ttf','arialbd.ttf']:shutil.copy2(Path('C:/Windows/Fonts')/name,fonts/name)
    shutil.copy2(Path(__file__).with_name('capture.gd'),PROJECT/'trailer_capture.gd')
    config=(PROJECT/'project.godot').read_text(encoding='utf-8')
    config=config.replace('run/main_scene="res://main.tscn"','run/main_scene="res://trailer_capture.tscn"')
    config=config.replace('viewport_width=1440','viewport_width=3840').replace('viewport_height=900','viewport_height=2160')
    config=config.replace('window_width_override=1440','window_width_override=1920').replace('window_height_override=900','window_height_override=1080')
    config=config.replace('window/stretch/mode="canvas_items"','window/stretch/mode="viewport"')
    config+='\n[editor]\nmovie_writer/mjpeg_quality=0.90\nmovie_writer/fps=30\n'
    (PROJECT/'project.godot').write_text(config,encoding='utf-8')
    (PROJECT/'trailer_capture.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://trailer_capture.gd" id="1"]\n[node name="TrailerCapture" type="Node"]\nscript = ExtResource("1")\n',encoding='utf-8')
    manifest=dict(fps=FPS,width=3840,height=2160,warmup_frames=64,transition=.5,
        target_duration=55,asset_root=str(payload/'assets'),models=models,python_code=PYTHON_CODE,
        music_title='Horizons',music_artist='Scott Buckley',music_license='CC BY 4.0',portfolio='https://elemanprojects.com',shots=shots)
    write(WORK/'manifest.json',manifest)
    print('PREPARATION COMPLETE',WORK,flush=True)

if __name__=='__main__':main()
