#!/usr/bin/env python3
"""Simple ASTRA rocket throttle feedback demo. Run alongside server.py."""
import argparse
import math
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from astra.client import AstraClient

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8765')
    parser.add_argument('--steps',type=int,default=600)
    args=parser.parse_args()
    sim=AstraClient(args.url)
    print('ASTRA STATUS:',sim.status())
    sim.reset(vehicle='space',scenario='mission')
    sim.launch()
    dt=0.1
    print('GNC active: pressure-feedback throttle; keep local 3D viewer open')
    try:
        for i in range(max(args.steps,1)):
            state=sim.state()
            q=float((state.get('environment') or {}).get('dynamic_pressure_Pa') or 0)
            throttle=max(50.0,min(100.0,75.0+0.002*(25_000.0-q)))
            if not math.isfinite(throttle):raise RuntimeError('Non-finite throttle')
            sim.command(mode='python',throttle_pct=throttle)
            state=sim.step(dt)
            if i%10==0:
                print(f't={state["time_s"]:6.1f}s | alt={state["altitude_m"]:10.1f}m | q={q:9.0f}Pa | throttle={throttle:5.1f}% | {state["phase"]}',flush=True)
            if state['phase'] in {'LANDED','CRASHED','ABORTED'}:break
            time.sleep(dt)
    except KeyboardInterrupt:pass
    print('FINAL:',sim.state()['phase'])

if __name__=='__main__':main()
