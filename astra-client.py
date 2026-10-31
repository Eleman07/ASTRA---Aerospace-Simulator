#!/usr/bin/env python3
"""Connect a Python guidance loop to ASTRA Desktop; never starts a second engine."""
import argparse
from astra_sdk import AstraClient

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default=None,help='API URL; otherwise discover the active desktop instance')
    parser.add_argument('--exe',help='Explicitly start ASTRA Desktop.exe before connecting')
    parser.add_argument('--scenario',default='orbital',choices=['mission','orbital','planetary'])
    parser.add_argument('--duration',type=float,default=10)
    args=parser.parse_args()
    client=AstraClient.launch_desktop(args.exe) if args.exe else AstraClient(args.url)
    print(client.status())
    client.pause()
    client.reset('space',args.scenario,advanced_models=True)
    client.launch()
    # The desktop renders the same engine state. GNC remains automatic here.
    for _ in range(max(0,int(args.duration/.1))):
        state=client.step(.1)
        print(f"t={state['time_s']:.1f} s  h={state['altitude_m']:.1f} m  phase={state['phase']}")
        if state['phase'] in {'LANDED','CRASHED','ABORTED'}:break
    print('Simulation paused under external clock. Use client.play() to resume desktop time.')

if __name__=='__main__':main()
