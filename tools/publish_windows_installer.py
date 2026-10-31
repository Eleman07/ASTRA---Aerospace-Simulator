"""Publish only the verified Windows installer as a GitHub Release asset.

Uses existing Git credentials in memory; never writes or prints credentials.
Source branches, the web deployment and README are not modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO='Eleman07/ASTRA-Aerospace-Simulator'
TAG='v1.5.0-windows'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    report=json.loads((ROOT/'dist'/'windows-installer.json').read_text(encoding='utf-8'))
    if any(report.get(k)!='PASS' for k in ('runtime_self_test','installer_test','uninstaller_test')):
        raise RuntimeError('Installer has not passed all required checks')
    installer=(ROOT/'dist'/report['installer']).resolve()
    if ROOT not in installer.parents:raise RuntimeError('Installer outside workspace')
    digest=hashlib.sha256(installer.read_bytes()).hexdigest()
    if digest!=report['sha256']:raise RuntimeError('Installer changed after verification')
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','diff','--','README.md'],cwd=ROOT):raise RuntimeError('README changed')
    notes=f'''Installer **Windows 11 x64 offline** per ASTRA Flight Systems 1.5.0 (pacchetto 1.5.0.0).

Scarica l'unico allegato **{installer.name}**, eseguilo e avvia ASTRA dal menu Start. Python, motore fisico, modelli 3D e texture sono inclusi: non sono necessari Internet o un'installazione Python separata. L'installazione avviene per l'utente corrente e include la disinstallazione.

Il simulatore si apre nel browser locale su `http://127.0.0.1:8765`. Tieni aperta la finestra del motore durante l'uso.

Novità: le 13 discipline precedentemente parametriche hanno ora un percorso attivo nel motore, con stato, accoppiamenti, telemetria SI, seed e limiti dichiarati. Include propulsione transitoria a ugello Laval, portanza con ritardo, perturbazioni celesti differenziali, pianificazione e guida rendezvous non lineare, risposta dinamica FEM modale, turbolenza spettrale, EPS con penombra, canale radio a pacchetti, A* con ingombro, masse/inerzie di lancio, nuova missione lunare 6-DoF e requisiti temporali.

Grafica: HDR dove supportato, ombre dalla geometria con PCF, bloom, occlusione ambientale da profondità, FXAA e diffusione atmosferica integrata. Le qualità leggere riducono realmente il lavoro GPU. Nuove scena e missione lunari; nuvole e terreno sintetici. Non viene dichiarata equivalenza grafica a Star Citizen o una prestazione FPS su hardware non provato.

I modelli sono riferimenti numerici con ipotesi dichiarate, non modelli certificati di veicoli reali. Il percorso precedente resta selezionabile per confronto. Controller Manager e funzionamento offline restano inclusi. Gli input controller sono stati collaudati con dispositivi simulati; nessuna verifica fisica di Xbox/HOTAS viene dichiarata.

Verifiche: suite di 80 test Python (79 riusciti, un test installer opt-in verificato separatamente), 27 test JavaScript, prove browser offline delle pipeline leggera/alta, discesa lunare e 13 discipline; self-test del motore, integrità di {report['installed_files_verified']} file installati, installazione/disinstallazione e conservazione dei file utente di prova. Il frontend è stato collaudato in Edge con le richieste esterne bloccate.

L'installer non è firmato digitalmente. Questa pubblicazione riguarda solo la distribuzione Windows precompilata: i sorgenti su GitHub e la versione web non sono aggiornati da questo rilascio.

SHA-256:
```
{digest}
```
'''
    work=ROOT/'build'/'installer';work.mkdir(parents=True,exist_ok=True)
    notes_path=work/'release-notes.md';notes_path.write_text(notes,encoding='utf-8')
    if not args.publish:
        print(json.dumps({'repository':REPO,'tag':TAG,'asset':str(installer),'sha256':digest,'notes':str(notes_path)},indent=2))
        return
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
    token=env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')
    if not token:
        credential=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',
                                  capture_output=True,text=True,env=env,timeout=20,check=True)
        fields=dict(line.split('=',1) for line in credential.stdout.splitlines() if '=' in line)
        token=fields.get('password')
    if not token:raise RuntimeError('No authenticated GitHub credential is available')
    env['GH_TOKEN']=token

    def api(method,path,payload=None,missing_ok=False):
        request=Request('https://api.github.com/repos/'+REPO+'/'+path,
                        data=json.dumps(payload).encode('utf-8') if payload is not None else None,
                        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                                 'Content-Type':'application/json','User-Agent':'ASTRA-Windows-Release'},method=method)
        try:
            with urlopen(request,timeout=40) as response:return json.load(response)
        except HTTPError as exc:
            if missing_ok and exc.code==404:return None
            raise RuntimeError('GitHub API '+method+' '+path+' returned '+str(exc.code)) from None

    def gh(*parts):
        result=subprocess.run(['gh',*parts],capture_output=True,env=env,cwd=ROOT,timeout=240)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8',errors='replace').replace(token,'[REDACTED]'))
        return result.stdout

    before=api('GET','git/ref/heads/main')['object']['sha']
    state_path=work/'github-release-state-1.5.0.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else None
    release=api('GET','releases/tags/'+TAG,missing_ok=True)
    if release and (not state or state.get('release_id')!=release['id']):
        raise RuntimeError('Release already exists and was not created by this publication; refusing to overwrite')
    if not release:
        existing_tag=api('GET','git/ref/tags/'+TAG,missing_ok=True)
        if existing_tag:raise RuntimeError('Tag already exists; choose a new release version')
        release=api('POST','releases',{'tag_name':TAG,'target_commitish':base,
                    'name':'ASTRA Flight Systems 1.5.0.0 - Windows 11 offline',
                    'body':notes,'draft':True,'prerelease':False})
        state={'repository':REPO,'tag':TAG,'release_id':release['id'],'sha256':digest}
        state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    if state.get('sha256')!=digest:raise RuntimeError('Installer differs from the prepared release')
    if not release['draft']:raise RuntimeError('Release already published; refusing further mutation')
    if not release['assets']:
        print('Uploading verified Windows installer to draft release...',flush=True)
        gh('release','upload',TAG,str(installer),'--repo',REPO)
    release=api('GET','releases/'+str(release['id']))
    assets=release['assets']
    if len(assets)!=1 or assets[0]['name']!=installer.name:raise RuntimeError('Unexpected release assets')
    asset=assets[0]
    if asset['size']!=installer.stat().st_size or asset['state']!='uploaded':raise RuntimeError('Incomplete asset upload')
    server_digest=asset.get('digest')
    if server_digest:
        if server_digest!='sha256:'+digest:raise RuntimeError('GitHub asset checksum mismatch')
    else:
        download=gh('api','repos/'+REPO+'/releases/assets/'+str(asset['id']),'-H','Accept:application/octet-stream')
        if hashlib.sha256(download).hexdigest()!=digest:raise RuntimeError('Downloaded asset checksum mismatch')
    release=api('PATCH','releases/'+str(release['id']),{'draft':False,'make_latest':'true'})
    verified=api('GET','releases/'+str(release['id']))
    if verified['draft'] or len(verified['assets'])!=1:raise RuntimeError('Release publication not confirmed')
    after=api('GET','git/ref/heads/main')['object']['sha']
    receipt={'repository':REPO,'tag':TAG,'release_id':verified['id'],'release_url':verified['html_url'],
             'asset_url':verified['assets'][0]['browser_download_url'],'asset':installer.name,'sha256':digest,
             'published':True,'main_before':before,'main_after':after,'main_unchanged':before==after}
    (ROOT/'dist'/'windows-github-release.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
