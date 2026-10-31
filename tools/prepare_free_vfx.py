"""Prepare the CC0 Unity Labs flipbooks without changing pixel data.

The original 2016 EXR headers declare 55 channel-list bytes but contain four
channels (73 bytes). Correct that header length for strict EXR readers.
"""
import hashlib
import json
from pathlib import Path
import struct
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    target=ROOT/'assets/vfx';rows=[]
    for name,file in [('WispySmoke01','smoke-8x8.exr'),('Flame02','flame-16x4.exr')]:
        archive=ROOT/'build/vfx-source'/(name+'.zip')
        with zipfile.ZipFile(archive) as z:original=z.read(next(n for n in z.namelist() if n.endswith('.exr')))
        data=bytearray(original)
        assert data[8:24]==b'channels\x00chlist\x00'
        declared=struct.unpack_from('<I',data,24)[0]
        end=28;channels=[]
        while data[end]:
            terminator=data.index(0,end);channels.append(bytes(data[end:terminator]).decode())
            end=terminator+17
        actual=end+1-28
        assert channels==['A','B','G','R'] and actual==73
        struct.pack_into('<I',data,24,actual)
        (target/file).write_bytes(data)
        rows.append(dict(asset=name,author='Unity Labs Paris / Thomas ICHE',license='CC0 1.0',
            source='https://unity.com/blog/engine-platform/free-vfx-image-sequences-flipbooks',
            download=f'https://unity3d.com/files/labs/downloads/vfx/assets01/{name}/{name}-flipbooks.zip',
            zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(original).hexdigest(),
            file=file,runtime_sha256=hashlib.sha256(data).hexdigest(),
            processing=f'Corrected EXR chlist byte count {declared} to {actual}; pixel data and channel order unchanged'))
    (target/'sources.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
