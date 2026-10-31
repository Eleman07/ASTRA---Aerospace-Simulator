"""Update the desktop tutorial while retaining the existing three real previews."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO='Eleman07/ASTRA-Aerospace-Simulator'
FILES=['README.md']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    preview=json.loads((ROOT/'test-results/readme-previews.json').read_text())
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    assert len(preview['images'])==3
    for row in preview['images']:assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256']
    contents={name:(ROOT/name).read_bytes() for name in FILES}
    if not args.publish:print(json.dumps(dict(repository=REPO,files=FILES),indent=2));return
    receipt=json.loads((ROOT/'dist/desktop-github-release.json').read_text())
    assert receipt['tag']=='v'+build['version']+'-desktop' and receipt['published']
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
    token=env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')
    if not token:
        result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=env,check=True,timeout=20)
        token=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line).get('password')
    if not token:raise RuntimeError('GitHub credential unavailable')
    def api(method,path,payload=None):
        request=Request('https://api.github.com/repos/'+REPO+'/'+path,method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'ASTRA-Docs-Publisher'})
        with urlopen(request,timeout=60) as response:return json.load(response)
    assert not api('GET','releases/tags/'+receipt['tag'])['draft']
    before=api('GET','git/ref/heads/main')['object']['sha']
    base_tree=api('GET','git/commits/'+before)['tree']['sha']
    entries=[]
    for name,data in contents.items():
        blob=api('POST','git/blobs',dict(content=base64.b64encode(data).decode(),encoding='base64'))
        expected=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        assert blob['sha']==expected
        entries.append(dict(path=name,mode='100644',type='blob',sha=blob['sha']))
    tree=api('POST','git/trees',dict(base_tree=base_tree,tree=entries))
    commit=api('POST','git/commits',dict(message='docs: update Desktop '+build['version']+' downloads and controller/menu mapping',tree=tree['sha'],parents=[before]))
    comparison=api('GET','compare/'+before+'...'+commit['sha'])
    changed={row['filename'] for row in comparison['files']}
    assert changed==set(FILES),changed
    if api('GET','git/ref/heads/main')['object']['sha']!=before:raise RuntimeError('main changed concurrently; documentation commit was not applied')
    api('PATCH','git/refs/heads/main',dict(sha=commit['sha'],force=False))
    assert api('GET','git/ref/heads/main')['object']['sha']==commit['sha']
    verified=api('GET','contents/README.md?ref='+commit['sha'])
    assert base64.b64decode(verified['content'])==contents['README.md']
    proof=dict(repository=REPO,commit_sha=commit['sha'],url='https://github.com/'+REPO+'#readme',
        files=FILES,preview_images=3,only_authorized_files_changed=True,parent_sha=before,published=True)
    (ROOT/('test-results/github-readme-'+build['version']+'.json')).write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof,indent=2))

if __name__=='__main__':main()
