"""Measure actual input HTTP replies against the frozen host on an isolated port."""
import hashlib
import json
from pathlib import Path
import socket
import statistics
import subprocess
import time
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]

def main():
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    executable=Path(build['payload'])/'ASTRA.exe'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    base=f'http://127.0.0.1:{port}/api/v1'
    host=subprocess.Popen([str(executable),'--serve','--port',str(port),'--smoke',str(ROOT/'test-results/input-latency')],creationflags=subprocess.CREATE_NO_WINDOW)
    def request(path,payload=None):
        data=None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(base+path,data=data,headers={'Content-Type':'application/json'}),timeout=10) as response:
            raw=response.read()
        return json.loads(raw),len(raw)
    try:
        deadline=time.monotonic()+30
        while True:
            try:
                status,_=request('/status')
                if status['process_id']==host.pid:break
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        results={}
        for compact in [False,True]:
            elapsed=[];sizes=[]
            for i in range(65):
                roll=20 if i%2 else -20
                command=dict(throttle_pct=i,roll_deg=roll,pitch_deg=80,yaw_deg=-10)
                start=time.perf_counter()
                reply,size=request('/desktop/pilot',dict(armed=True,neutral_acquired=True,compact=compact,command=command))
                duration=(time.perf_counter()-start)*1000
                actual=reply['command'] if compact else reply['state']['command']
                assert actual['roll_deg']==roll and actual['throttle_pct']==i
                if i>=5:elapsed.append(duration);sizes.append(size)
            ordered=sorted(elapsed)
            results['compact' if compact else 'full']=dict(mean_ms=statistics.mean(elapsed),p95_ms=ordered[int(len(ordered)*.95)-1],mean_bytes=statistics.mean(sizes),samples=len(sizes))
        assert results['compact']['mean_bytes']<results['full']['mean_bytes']/20
        assert request('/state')[0]['time_s']==0
        results.update(version=status['desktop_version'],host_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),scientific_time_unchanged=True,result='PASS')
        (ROOT/'test-results/input-latency.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(results,indent=2))
    finally:
        host.terminate();host.wait(timeout=10)

if __name__=='__main__':main()
