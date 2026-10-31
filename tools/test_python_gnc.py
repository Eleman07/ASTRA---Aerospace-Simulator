"""Closed-loop navigation/guidance/control through the installed wheel and EXE."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

CODE='''from astra_sdk import AstraClient

client = AstraClient()
client.pause()
state = client.reset("drone", advanced_models=True)
client.launch()
target_m = 3.0
fps_samples = []

for _ in range(400):
    nav = state["navigation_estimate"]
    error = target_m - nav["altitude_m"]
    acceleration = 3.0 * error - 2.8 * nav["vertical_speed_m_s"]
    max_thrust = state["vehicle_parameters"]["max_thrust_N"]
    throttle = state["mass_kg"] * (9.80665 + acceleration)
    throttle = max(0, min(100, throttle / max_thrust * 100))
    client.command(mode="python", throttle_pct=throttle,
                   roll_deg=0, pitch_deg=0, yaw_deg=0)
    state = client.step(0.02)
    if _ % 50 == 0:
        fps_samples.append(client.renderer_status().get("fps", 0))
'''

def main():
    build=json.loads((ROOT/'dist/desktop-build.json').read_text());payload=Path(build['payload'])
    target=ROOT/'test-results/desktop-sdk-gnc'
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--disable-pip-version-check','--upgrade','--target',str(target),str(ROOT/'dist'/build['sdk'])],check=True)
    sys.path.insert(0,str(target));from astra_sdk import AstraClient,CLIENT_VERSION
    assert Path(AstraClient.client_info()['client_module']).is_relative_to(target)
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    output=ROOT/'test-results/python-gnc';data=ROOT/'test-results/python-gnc-data.json'
    if data.exists():data.unlink()
    validation=ROOT/'test-results/python-gnc-validation.json'
    if validation.exists():validation.unlink()
    for suffix in ('.png','.json'):
        old=Path(str(output)+suffix)
        if old.exists():old.unlink()
    host=subprocess.Popen([str(payload/'ASTRA.exe'),'--serve','--port',str(port),'--quality','high','--smoke',str(output)],creationflags=subprocess.CREATE_NO_WINDOW)
    renderer=None
    try:
        client=AstraClient(f'http://127.0.0.1:{port}')
        deadline=time.monotonic()+30
        while True:
            try:
                if client.status().get('process_id')==host.pid:break
            except (ConnectionError,RuntimeError):pass
            if time.monotonic()>deadline:raise TimeoutError('Frozen GNC API unavailable')
            time.sleep(.1)
        log=ROOT/'test-results/python-gnc-renderer.log'
        command=[str(payload/'ASTRA-Renderer.exe'),'--position','-10000,-10000','--resolution','1440x900','--rendering-method','forward_plus','--log-file',str(log),'--','--api',client.base_url,'--assets',str(payload/'assets'),'--quality','high','--python-proof',str(output),'--python-proof-data',str(data)]
        renderer=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+45
        while not client.renderer_status()['connected']:
            if renderer.poll() is not None:raise RuntimeError('GNC renderer exited early')
            if time.monotonic()>deadline:raise TimeoutError('GNC renderer startup')
            time.sleep(.1)
        namespace={}
        # Execute exactly the controller displayed in the native preview.
        source=CODE.replace('client = AstraClient()', 'client = AstraClient('+repr(client.base_url)+')')
        start=time.perf_counter();exec(compile(source,'ASTRA_GNC_controller.py','exec'),namespace)
        elapsed=time.perf_counter()-start;state=namespace['state']
        error=abs(state['altitude_m']-3.)
        assert state['phase'] not in ('CRASHED','ABORTED','LANDED') and error<.75
        assert state['command']['mode']=='python' and abs(state['time_s']-8.)<1e-6
        assert client.snapshot()['desktop']['clock_owner']=='external'
        before=client.state();time.sleep(.1);assert client.state()==before
        summary=f"400 comandi / 8,00 s simulati\nTarget quota: 3,000 m\nQuota effettiva: {state['altitude_m']:.3f} m\nErrore finale: {error:.3f} m\nControllo PYTHON · clock EXTERNAL\n13 discipline nel motore"
        client.set_camera(azimuth_deg=55,elevation_deg=18,distance_m=3.)
        view=client.set_view(cinematic_effects=False,audio_enabled=False)
        # A view-revision acknowledgement proves the renderer consumed an
        # atomic snapshot taken after the final external physics step.
        deadline=time.monotonic()+30
        while client.renderer_status().get('view_revision')!=view['revision']:
            if time.monotonic()>deadline:raise TimeoutError('Final GNC snapshot not presented')
            time.sleep(.1)
        data.write_text(json.dumps(dict(code=source,summary=summary,final=state,client_version=CLIENT_VERSION)),encoding='utf-8')
        assert renderer.wait(timeout=75)==0
        text=log.read_text(encoding='utf-8');assert 'SCRIPT ERROR:' not in text and '\nERROR:' not in text,text[-4000:]
        screenshot=json.loads(Path(str(output)+'.json').read_text())
        assert Path(str(output)+'.png').is_file()
        assert screenshot['script_output_matches_state'] and client.state()==before
        live_fps=[value for value in namespace['fps_samples'] if value>0]
        assert len(live_fps)>=3
        report=dict(version=CLIENT_VERSION,installed_wheel=True,closed_loop='PASS',commands=400,simulated_seconds=state['time_s'],wall_seconds=elapsed,target_altitude_m=3.,actual_altitude_m=state['altitude_m'],final_error_m=error,clock_owner='external',live_renderer_fps=live_fps,screenshot=screenshot,png_sha256=hashlib.sha256(Path(str(output)+'.png').read_bytes()).hexdigest(),
            renderer_sha256=build['renderer_sha256'],host_sha256=build['executable_sha256'],sdk_sha256=build['sdk_sha256'])
        (ROOT/'test-results/python-gnc-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        if renderer is not None and renderer.poll() is None:renderer.terminate();renderer.wait(10)
        host.terminate();host.wait(10)

if __name__=='__main__':main()
