"""Conform in-engine movies, grade, transition and add music-only soundtrack."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/astra-trailer-4k'
MEDIA=ROOT/'build/trailer-media'
OUT=ROOT/'deliverables/ASTRA-Trailer-4K'
FFMPEG=MEDIA/'ffmpeg.exe'
FFPROBE=MEDIA/'ffprobe.exe'

def probe(path):
    return json.loads(subprocess.check_output([str(FFPROBE),'-v','error','-show_streams','-show_format','-of','json',str(path)]))

def run(name,args):
    log=WORK/(name+'.log')
    with log.open('w',encoding='utf-8') as output:
        result=subprocess.run([str(FFMPEG),'-hide_banner','-y',*args],stdout=output,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError(log.read_text(encoding='utf-8',errors='replace')[-7000:])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--skip-conform',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((WORK/'manifest.json').read_text());music=json.loads((MEDIA/'music-selection.json').read_text())
    encoder=['-c:v','h264_nvenc','-preset','p5','-rc','vbr','-cq','18','-b:v','0']
    test=subprocess.run([str(FFMPEG),'-v','error','-f','lavfi','-i','color=black:s=3840x2160:r=30','-frames:v','2',*encoder,'-f','null','-'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if test.returncode:encoder=['-c:v','libx264','-preset','fast','-crf','18']
    print('ENCODER',encoder,flush=True)
    inputs=[];proof=[]
    for shot in manifest['shots']:
        raw=WORK/(shot['id']+'.avi');target=WORK/(shot['id']+'-conformed.mp4')
        info=probe(raw);v=next(s for s in info['streams'] if s['codec_type']=='video')
        assert (v['width'],v['height'])==(3840,2160)
        total=int(v['nb_frames']);wanted=int(shot['frames']);start=total-wanted
        assert start>=manifest['warmup_frames']-2,(shot['id'],total,wanted)
        if not args.skip_conform or not target.exists():
            run('conform-'+shot['id'],['-i',str(raw),'-an','-vf',f'trim=start_frame={start}:end_frame={total},setpts=PTS-STARTPTS,fps=30,setsar=1,scale=in_range=full:out_range=limited:out_color_matrix=bt709,format=yuv420p',
                *encoder,'-pix_fmt','yuv420p','-movflags','+faststart','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',str(target)])
        p=probe(target);video=next(s for s in p['streams'] if s['codec_type']=='video')
        assert abs(float(video['duration'])-float(shot['duration']))<.04
        inputs+=['-threads','2','-i',str(target)];proof.append(dict(shot=shot['id'],native_size=[v['width'],v['height']],frames=wanted,removed_preroll_frames=start))
        print('CONFORMED',shot['id'],shot['duration'],flush=True)
    graph=[]
    for i in range(len(manifest['shots'])):graph.append(f'[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,format=yuv444p[v{i}]')
    previous='v0';elapsed=manifest['shots'][0]['duration'];transition=manifest['transition']
    styles=['fade','smoothleft','fade','fadeblack','smoothleft','fade']
    for i,shot in enumerate(manifest['shots'][1:],1):
        label='join'+str(i);offset=elapsed-transition
        graph.append(f'[{previous}][v{i}]xfade=transition={styles[i-1]}:duration={transition}:offset={offset}[{label}]')
        previous=label;elapsed+=shot['duration']-transition
    assert abs(elapsed-55)<.001
    graph.append(f'[{previous}]eq=contrast=1.025:saturation=1.035:brightness=-0.004,colorbalance=rs=-0.008:gs=0.003:bs=0.018:rh=0.012:gh=0.006:bh=-0.006,vignette=PI/5.5,noise=alls=1:allf=t+u,fade=t=in:st=0:d=0.65,fade=t=out:st=54.2:d=0.8,format=yuv420p[video]')
    track_index=len(manifest['shots'])
    graph.append(f'[{track_index}:a]atrim=start={music["music_start_s"]}:duration=55,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.8,afade=t=out:st=52.2:d=2.8,loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000[audio]')
    filters=WORK/'edit.ffscript';filters.write_text(';\n'.join(graph),encoding='utf-8')
    master=OUT/'ASTRA_Cinematic_Trailer_4K.mp4'
    run('final-edit',[*inputs,'-i',music['file'],'-filter_complex_threads','4','-filter_complex',filters.read_text(encoding='utf-8'),
        '-map','[video]','-map','[audio]','-t','55',*encoder,'-c:a','aac','-b:a','256k','-ar','48000','-ac','2',
        '-pix_fmt','yuv420p','-r','30','-movflags','+faststart','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
        '-metadata','title=ASTRA | Beyond the Blue','-metadata','artist=Emanuele Magno',
        '-metadata','comment=In-engine footage. Music: Horizons by Scott Buckley, CC BY 4.0. elemanprojects.com',str(master)])
    print('4K MASTER READY',master,flush=True)
    preview=OUT/'ASTRA_Cinematic_Trailer_1080p.mp4'
    run('preview',['-i',str(master),'-vf','scale=1920:1080:flags=lanczos','-c:v','libx264','-preset','fast','-crf','22','-c:a','aac','-b:a','192k','-movflags','+faststart',str(preview)])
    run('poster',['-ss','3.1','-i',str(master),'-frames:v','1','-vf','scale=1920:1080:flags=lanczos',str(OUT/'ASTRA_Trailer_Poster.jpg')])
    credits='''ASTRA — BEYOND THE BLUE | CINEMATIC TRAILER
Created for Emanuele Magno | https://elemanprojects.com

55 seconds | 3840 x 2160 | 16:9 | 30 fps | H.264 + AAC stereo
Native 4K in-engine capture, not upscaled. Movie Maker offline capture of
the ASTRA renderer with states recorded from ASTRA Desktop 2.3.2.
Camera moves, editorial titles, transitions and colour grade added for film.
No simulator sound, microphone recording, voiceover or separate sound effects.

MUSIC — REQUIRED ATTRIBUTION WHEN SHARING
'Horizons' by Scott Buckley — released under CC-BY 4.0.
www.scottbuckley.com.au
https://www.scottbuckley.com.au/library/horizons/
https://creativecommons.org/licenses/by/4.0/
Excerpt edited, faded and loudness-normalised for this trailer.
For YouTube, include this music credit in the video description.

FALCON 9 VISUAL MODEL
Fac-tory-o, Falcon 9 Block 5, CC BY-SA 4.0.
https://commons.wikimedia.org/wiki/File:Falcon_9.stl
https://creativecommons.org/licenses/by-sa/4.0/
ASTRA's assembled/converted mesh uses illustrative materials.
Derived mesh and adapted rendered material retain the original attribution
and share-alike terms. Vehicle models are visual references: flight dynamics
are the ASTRA engineering models, not certified Falcon 9 performance.

AIRCRAFT AND UAV
Innerscene, twin turboprop and quadcopter with flight electronics, CC0 1.0.
https://www.innerscene.com/tools/library/3d-parts/twin-turboprop-aircraft-f8c5fa80
https://www.innerscene.com/tools/library/3d-parts/quadcopter-with-flight-electronics-a25968c1

OTHER VISUAL ASSETS
Earth imagery, sky, terrain, vehicle conversions and VFX retain the credits
listed in ASSET-CREDITS.txt, supplied with this video.
Python scene: 300 real SDK control commands at 30 Hz, target altitude 3 m.
Free-flight scene: actual GIOCA/free mode with manual attitude commands.
'''
    (OUT/'CREDITS.txt').write_text(credits,encoding='utf-8')
    (OUT/'VIDEO-DESCRIPTION.txt').write_text('''ASTRA | Beyond the Blue

Explore spacecraft, fixed-wing aircraft and UAV flight in ASTRA Desktop.
Real in-engine footage, Python SDK control and free-flight mode.
Created by Emanuele Magno.

Explore the portfolio: https://elemanprojects.com

Music: 'Horizons' by Scott Buckley — released under CC-BY 4.0.
www.scottbuckley.com.au
https://www.scottbuckley.com.au/library/horizons/
https://creativecommons.org/licenses/by/4.0/
Music excerpt edited, faded and loudness-normalised.

Falcon 9 visual mesh: Fac-tory-o, CC BY-SA 4.0.
https://commons.wikimedia.org/wiki/File:Falcon_9.stl
https://creativecommons.org/licenses/by-sa/4.0/
Aircraft and UAV: Innerscene, CC0 1.0.
See the accompanying CREDITS.txt and ASSET-CREDITS.txt for full attribution.
''',encoding='utf-8')
    (OUT/'ASSET-CREDITS.txt').write_bytes((ROOT/'ASSET-CREDITS.md').read_bytes())
    (OUT/'recorded_python_controller.py').write_bytes((WORK/'recorded_python_controller.py').read_bytes())
    result=probe(master);v=next(s for s in result['streams'] if s['codec_type']=='video');a=next(s for s in result['streams'] if s['codec_type']=='audio')
    assert (v['width'],v['height'])==(3840,2160) and v['r_frame_rate']=='30/1'
    assert abs(float(result['format']['duration'])-55)<.1 and a['codec_name']=='aac'
    report=dict(duration_s=result['format']['duration'],native_resolution=[3840,2160],aspect_ratio='16:9',fps=30,
        master=str(master),preview=str(preview),master_sha256=hashlib.sha256(master.read_bytes()).hexdigest(),
        music_only=True,music=music,shots=proof,provenance=json.loads((WORK/'provenance.json').read_text()),ffprobe=result)
    (OUT/'VALIDATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('ffprobe','provenance','shots','music')},indent=2))

if __name__=='__main__':main()
