"""Inspect the delivered trailer, including full decode and soundtrack provenance."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'build/astra-trailer-4k'
MEDIA = ROOT / 'build/trailer-media'
OUT = ROOT / 'deliverables/ASTRA-Trailer-4K'
FFMPEG = MEDIA / 'ffmpeg.exe'
FFPROBE = MEDIA / 'ffprobe.exe'
sys.path[:0] = [str(ROOT / 'build/trailer-tools'), str(ROOT / 'build/image-tools')]
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def ffmpeg(*args):
    return subprocess.run(
        [str(FFMPEG), '-hide_banner', *map(str, args)],
        capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )


def main():
    master = OUT / 'ASTRA_Cinematic_Trailer_4K.mp4'
    info = json.loads(subprocess.check_output([
        str(FFPROBE), '-v', 'error', '-show_streams', '-show_format',
        '-of', 'json', str(master),
    ]))
    video = [s for s in info['streams'] if s['codec_type'] == 'video']
    audio = [s for s in info['streams'] if s['codec_type'] == 'audio']
    assert len(video) == len(audio) == 1
    assert [video[0]['width'], video[0]['height']] == [3840, 2160]
    assert video[0]['r_frame_rate'] == '30/1' and int(video[0]['nb_frames']) == 1650
    assert audio[0]['channels'] == 2 and audio[0]['sample_rate'] == '48000'
    assert abs(float(info['format']['duration']) - 55) < .05
    decode = ffmpeg('-v', 'error', '-threads', 2, '-i', master, '-f', 'null', '-')
    assert not decode.stderr.strip(), decode.stderr.decode(errors='replace')
    inspection = ffmpeg('-threads', 2, '-i', master, '-an', '-vf',
                        'scale=480:270,blackdetect=d=0.15:pix_th=0.06:pic_th=0.98,freezedetect=n=-60dB:d=1.5',
                        '-f', 'null', '-')
    log = inspection.stderr.decode(errors='replace')
    (WORK / 'quality-inspection.log').write_text(log, encoding='utf-8')
    black = [dict(start=float(a), end=float(b), duration=float(c)) for a, b, c in
             re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)', log)]
    assert all(s['duration'] < 1 for s in black), black
    freeze_starts = [float(t) for t in re.findall(r'freeze_start: ([\d.]+)', log)]
    assert all(t >= 48 for t in freeze_starts), ('Unexpected frozen interval', freeze_starts)

    # The AAC master must correlate with the credited music at the selected offset.
    music = json.loads((MEDIA / 'music-selection.json').read_text())
    def mono(path, seek):
        data = ffmpeg('-v', 'error', '-ss', seek, '-i', path, '-t', 50,
                      '-vn', '-ac', 1, '-ar', 11025, '-f', 'f32le', '-').stdout
        return np.frombuffer(data, dtype='<f4').copy()
    actual = mono(master, 2)
    reference = mono(music['file'], music['music_start_s'] + 2)
    size = min(len(actual), len(reference))
    correlation = float(np.corrcoef(actual[:size], reference[:size])[0, 1])
    assert correlation > .98, ('Soundtrack differs from music source', correlation)

    moments = [1.5, 5.5, 10.5, 16, 20.5, 25.5, 31, 36, 41, 46, 51, 53.5]
    thumb = (640, 360)
    contact = Image.new('RGB', (1920, 4 * 398), '#071018')
    draw = ImageDraw.Draw(contact)
    font = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', 23)
    for i, moment in enumerate(moments):
        target = WORK / f'final-{moment:04.1f}.jpg'
        ffmpeg('-v', 'error', '-y', '-ss', moment, '-i', master, '-frames:v', 1,
               '-vf', 'scale=640:360:flags=lanczos', target)
        x, y = (i % 3) * thumb[0], (i // 3) * 398
        contact.paste(Image.open(target), (x, y))
        draw.text((x + 12, y + 366), f'{moment:04.1f} s', font=font, fill='#b9d9ed')
    contact.save(OUT / 'ASTRA_Trailer_Contact_Sheet.jpg', quality=94)
    report = dict(full_decode_pass=True, frames=1650, duration_s=55,
                  native_size=[3840, 2160], music_correlation=correlation,
                  music_only=True, unexpected_freezes=False, black_intervals=black,
                  intentional_end_card_holds_s=freeze_starts,
                  inspected_frames_s=moments)
    (OUT / 'QUALITY-CHECK.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
