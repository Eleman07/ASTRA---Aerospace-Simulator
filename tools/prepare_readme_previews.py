"""Compress exactly three real release captures for the user-facing README."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build/image-tools'))
from PIL import Image

def main():
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    for name in ['visual-api-validation.json','python-gnc-validation.json']:
        proof=json.loads((ROOT/'test-results'/name).read_text())
        assert proof['renderer_sha256']==build['renderer_sha256']
    pairs=[('modern-nasa-orion-spacecraft.png','desktop-2.4-space.webp'),('README-aircraft.png','desktop-2.4-aircraft.webp'),('python-gnc.png','desktop-2.4-python.webp')]
    rows=[]
    for source,file in pairs:
        original=ROOT/'test-results'/source;target=ROOT/'docs/images'/file
        image=Image.open(original).convert('RGB')
        assert image.size==(1440,900)
        image.save(target,format='WEBP',quality=88,method=6)
        rows.append(dict(source=str(original),path=target.relative_to(ROOT).as_posix(),bytes=target.stat().st_size,
            source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',(ROOT/'README.md').read_text(encoding='utf-8'))
    assert links==[row['path'] for row in rows],links
    report=dict(renderer_sha256=build['renderer_sha256'],images=rows,real_captures=True)
    (ROOT/'test-results/readme-previews.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
