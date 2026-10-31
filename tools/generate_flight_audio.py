"""Deterministic synthetic onboard propulsion loops, generated entirely offline."""
import math
from pathlib import Path
import random
import struct
import wave

ROOT=Path(__file__).resolve().parents[1]

def main():
    target=ROOT/'assets/audio';target.mkdir(exist_ok=True)
    rate=22050;count=rate*2
    for kind in ('rocket','aircraft','drone','rcs'):
        rng=random.Random(kind);samples=[];low=0.
        for i in range(count):
            t=i/rate;noise=rng.uniform(-1,1);low=.94*low+.06*noise
            if kind=='rocket':value=low*1.7+.18*math.sin(math.tau*43*t)+.07*math.sin(math.tau*87*t)
            elif kind=='aircraft':value=.21*math.sin(math.tau*90*t)+.11*math.sin(math.tau*180*t)+.065*math.sin(math.tau*450*t)+low*.45
            elif kind=='drone':value=.15*math.sin(math.tau*220*t)+.09*math.sin(math.tau*440*t)+.06*math.sin(math.tau*663*t)+low*.45
            else:value=noise*.13+low*.25
            samples.append(value)
        # Crossfade the boundary; both the value and its neighborhood join.
        fade=512
        for i in range(fade):
            alpha=i/fade;samples[i]=samples[-fade+i]*(1-alpha)+samples[i]*alpha
        samples=samples[:-fade]
        data=b''.join(struct.pack('<h',int(max(-.9,min(.9,value))*32767)) for value in samples)
        with wave.open(str(target/(kind+'.wav')),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(data)

if __name__=='__main__':main()
