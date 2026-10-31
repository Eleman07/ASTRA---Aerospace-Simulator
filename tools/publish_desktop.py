"""Publish tested Windows installer and SDK. Documentation is published separately."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO='Eleman07/ASTRA-Aerospace-Simulator'
TAG='v2.4.0-desktop'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    report=json.loads((ROOT/'dist/desktop-installer.json').read_text())
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    if TAG!='v'+build['version']+'-desktop':raise RuntimeError('Release tag does not match this build')
    routing=json.loads((ROOT/'test-results/input-routing-validation.json').read_text())
    if routing['result']!='PASS' or routing['version']!=build['version']:raise RuntimeError('Input routing unverified')
    for name,value in routing['source_sha256'].items():
        if sha(ROOT/name)!=value:raise RuntimeError('Input sources changed since test: '+name)
    package=json.loads((ROOT/'test-results/desktop-package-validation.json').read_text())
    if any(report.get(k)!='PASS' for k in ('runtime_self_test','installer_test','uninstaller_test')):
        raise RuntimeError('Installer validation incomplete')
    if package.get('frozen_host')!='PASS' or package.get('offline_wheel')!='PASS':
        raise RuntimeError('Packaged host/SDK validation incomplete')
    if package.get('renderer_sha256')!=build['renderer_sha256'] or package.get('sdk_sha256')!=build['sdk_sha256'] or package.get('host_sha256')!=build['executable_sha256']:
        raise RuntimeError('Packaged validation belongs to another build')
    if package.get('camera_api')!='PASS':raise RuntimeError('Camera and PNG capture verification incomplete')
    if package.get('free_flight_api')!='PASS' or package.get('detailed_instruments_api')!='PASS':
        raise RuntimeError('Packaged free flight / instruments SDK not verified')
    if package.get('independent_sdk')!='PASS' or package.get('legacy_module_collision')!='PASS':
        raise RuntimeError('Independent SDK or legacy-shadowing correction unverified')
    gnc=json.loads((ROOT/'test-results/python-gnc-validation.json').read_text())
    if gnc['renderer_sha256']!=build['renderer_sha256'] or gnc['sdk_sha256']!=build['sdk_sha256'] or gnc['closed_loop']!='PASS' or len(gnc.get('live_renderer_fps',[]))<3:
        raise RuntimeError('Live Python GNC verification incomplete')
    for quality in ('high','low'):
        polish=json.loads((ROOT/f'test-results/polish-{quality}.json').read_text())
        if polish['renderer_sha256']!=build['renderer_sha256'] or polish['printing_stand_removed_triangles']!=12 or polish['audio_peak']<=.0001 or not polish['cinematic_reentry'] or not polish['cc0_hdr_flipbooks']:
            raise RuntimeError('Runtime polish verification incomplete: '+quality)
        proof=json.loads((ROOT/f'test-results/native-suite-{quality}.json').read_text())
        if proof.get('renderer_sha256')!=build['renderer_sha256']:
            raise RuntimeError('Graphics validation belongs to another renderer: '+quality)
        if not all(row['loaded'] for row in proof.get('asset_imports',[])):
            raise RuntimeError('GLB import validation incomplete')
        if not proof['cases'][0]['launch_vertical'] or not all(row['launch_vertical'] for row in proof['secondary_models']):
            raise RuntimeError('Rocket launch orientation validation incomplete')
        if len(proof.get('free_flight',[]))!=3 or not all(row['manual'] for row in proof['free_flight']):
            raise RuntimeError('Free flight validation incomplete')
        if len(proof.get('globes',[]))!=2 or not all(row['local_patch_hidden'] for row in proof['globes']):
            raise RuntimeError('Spherical planet validation incomplete')
        if proof.get('detailed_instruments',0)<=12:raise RuntimeError('Expanded flight instruments unverified')
    expected={report['installer']:report['sha256'],report['sdk']:report['sdk_sha256']}
    files=[(ROOT/'dist'/name).resolve() for name in expected]
    for path in files:
        if ROOT not in path.parents or sha(path)!=expected[path.name]:raise RuntimeError('Artifact changed: '+path.name)
    baseline=json.loads((ROOT/'docs/validation/advanced-mission.json').read_text())['source_sha256']
    controlled_orbital_fix={'astra/attitude.py','astra/engine.py'}
    for path,value in baseline.items():
        if not path.startswith('astra/'):continue
        if path in controlled_orbital_fix:
            if path not in build['science_sources'] or sha(ROOT/path)!=build['science_sources'][path]:
                raise RuntimeError('Orbital attitude change is not the tested build: '+path)
        elif sha(ROOT/path)!=value:
            raise RuntimeError('Unreviewed scientific source changed: '+path)
    for path,value in build['science_sources'].items():
        if sha(ROOT/path)!=value:raise RuntimeError('Stale scientific payload: '+path)
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    notes=f'''ASTRA Desktop {build['version']} — Gioca con tre discipline, assetto orbitale manuale e preset grafici, Windows 11 x64 offline.

## Correzione controller

- Gli stick controllano l'assetto e non navigano più l'interfaccia, non cambiano missione e non modificano i campi numerici. Regola di input applicata anche alle finestre secondarie.
- Croce direzionale e frecce della tastiera: navigazione menu. **A conferma, B annulla/chiude il pannello. START avvia/mette in pausa il volo**, X richiama GNC/pausa sicura e Y arma/disarma.
- RT/LT aumentano/riducono la spinta e mantengono il valore al rilascio. Profilo reattivo: sensibilità 1,8, zona morta 0,08, risposta lineare o esponenziale e filtro 0,012 s, regolabili.
- Lettura a ogni frame, invio fino a 60 Hz con solo l'ultimo comando disponibile. I tempi di attesa delle risposte non scartano intervalli di input. Risposte API compatte per il controller.
- Il pad principale non può essere assegnato contemporaneamente come manetta/pedali separati. Corretti gli arrotondamenti dei campi numerici all'apertura del pannello.

Queste correzioni si applicano a spazio, aereo e UAV. Seleziona il pad in CONTROLLER → Primario, lascia gli stick al centro e arma esplicitamente. La disconnessione/perdita di focus ferma il volo libero; nelle missioni torna il GNC. Il movimento resta soggetto a inerzia, spinta e autorità degli attuatori: la sensibilità non elimina la dinamica fisica.

## Assetto orbitale e Gioca

- Il controllo manuale orbitale applica coppia al modello d'assetto condiviso; il riferimento LVLH e la guida di rendezvous sono attivi solo in GNC automatico. Stability Assist mantiene l'assetto inerziale corrente; Prograde/Retrograde, Radiale, Normale, Target e Nodo di manovra sono selezionabili. Il nodo richiede `maneuver_direction_eci`.
- Gioca espone tre attività: Spazio, Aereo e Drone. La campagna contiene 12 operazioni narrative e misurate dalla telemetria: tre ciascuna per Ingegneria, Esplorazione, Pilotaggio e Scienza; la progressione sblocca le operazioni in sequenza.
- Il renderer offre preset Basso/Medio/Alto/Ultra; Medio usa temporal FSR2 a scala 0,67 in Forward+ e Basso passa a OpenGL. Include scattering Rayleigh-Mie stratificato, stelle HDR multi-magnitudine e nebulosa blu. SSR e SDFGI dipendono dal backend e dal preset; SSR non è ray tracing hardware.

## Installazione e Python

Scarica **{report['installer']}** e aggiorna a simulatore chiuso. Motore, renderer, modelli, texture, effetti e audio sono inclusi offline. Non servono browser o Python per usare ASTRA. Il programma principale usa Forward+ Vulkan; Grafica leggera usa OpenGL. L'installer non è firmato digitalmente.

**L'SDK Python {build['sdk']}** conserva gli endpoint scientifici e aggiunge metodi per SAS orbitale e carriera. Scarica `{report['sdk']}` e installalo con:

```powershell
python -m pip install --no-index --upgrade --no-deps .\\{report['sdk']}
```

```python
from astra_sdk import AstraClient
client = AstraClient()
client.pause()
client.reset('space', 'orbital', advanced_models=True)
client.launch()
client.command(mode='python', attitude_target_deg=[10, 5, 0])
state = client.step(0.1)
```

```python
missions = client.game_catalog('space')
client.reset('space', 'orbital', advanced_models=True)
client.orbital_attitude('prograde')
```

`pause()`, `play()`, `step()`, camera, cattura PNG e API v1 conservati. Il clock esterno Python resta esclusivo. `version: 1.5.0` indica il motore scientifico, non la versione desktop o dell'SDK.

## Funzioni conservate e verifica

I 13 modelli scientifici e i 18 solutori restano attivi. Le uniche modifiche ai sorgenti condivisi `astra` correggono il rilascio del servo LVLH in manuale e aggiungono i riferimenti SAS; la dinamica translazionale e i modelli aerospaziali restano invariati. Non dichiariamo parità grafica con Star Citizen né FPS universali.

Test di regressione su input analogici e GUI: gli stick non modificano menu o valori in finestre principali/secondarie, D-pad naviga, A conferma, B chiude e Start avvia una sola volta. Verifiche sull'eseguibile esportato in Forward+ e OpenGL, confronto scientifico esatto su cinque scenari, SDK installato offline, GNC Python reale, camera e PNG. Installer: {report['installed_files_verified']} file verificati per SHA-256 e disinstallazione con dati utente di prova conservati. I test software non sono una certificazione del singolo controller/hardware.

Asset, licenze e modifiche sono documentati nel file ASSET-CREDITS.txt incluso. Il README include tre preview reali e aggiornate e documenta i controlli e le campagne di Gioca.

La release distribuisce installer Windows e wheel Python e punta al commit desktop pubblicato su `main`.

SHA-256:
```
{report['installer']}
{report['sha256']}
{report['sdk']}
{report['sdk_sha256']}
```
'''
    work=ROOT/'build/desktop-installer';work.mkdir(parents=True,exist_ok=True)
    (work/'release-notes.md').write_text(notes,encoding='utf-8')
    if not args.publish:
        print(json.dumps(dict(repository=REPO,tag=TAG,assets=expected),indent=2));return
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
    token=env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')
    if not token:
        credential=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',
            capture_output=True,text=True,env=env,timeout=20,check=True)
        fields=dict(line.split('=',1) for line in credential.stdout.splitlines() if '=' in line)
        token=fields.get('password')
    if not token:raise RuntimeError('GitHub credential unavailable')
    env['GH_TOKEN']=token
    def api(method,path,payload=None,missing_ok=False):
        req=Request('https://api.github.com/repos/'+REPO+'/'+path,method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                     'Content-Type':'application/json','User-Agent':'ASTRA-Desktop-Release'})
        try:
            with urlopen(req,timeout=45) as response:return json.load(response)
        except HTTPError as exc:
            if missing_ok and exc.code==404:return None
            raise RuntimeError('GitHub API '+method+' '+path+' returned '+str(exc.code)) from None
    def gh(*parts):
        result=subprocess.run(['gh',*parts],capture_output=True,env=env,cwd=ROOT,timeout=300)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace').replace(token,'[REDACTED]'))
        return result.stdout
    before=api('GET','git/ref/heads/main')['object']['sha']
    if base!=before:raise RuntimeError('Push the tested desktop commit to main before publishing the release')
    state_path=work/('github-release-state-'+build['version']+'.json')
    state=json.loads(state_path.read_text()) if state_path.exists() else None
    release=api('GET','releases/tags/'+TAG,missing_ok=True)
    if release and (not state or state.get('release_id')!=release['id']):raise RuntimeError('Unowned release exists')
    if not release:
        if api('GET','git/ref/tags/'+TAG,missing_ok=True):raise RuntimeError('Unowned tag exists')
        release=api('POST','releases',dict(tag_name=TAG,target_commitish=base,name='ASTRA Desktop '+build['version']+' — SAS orbitale e Gioca (Windows 11)',
                    body=notes,draft=True,prerelease=False))
        state=dict(repository=REPO,tag=TAG,release_id=release['id'],assets=expected)
        state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    if state['assets']!=expected:raise RuntimeError('Artifacts differ from prepared release')
    if not release['draft']:raise RuntimeError('Release already published; refusing mutation')
    existing={a['name'] for a in release['assets']}
    if not existing.issubset(expected):raise RuntimeError('Unexpected release asset')
    for path in files:
        if path.name not in existing:
            print('Uploading '+path.name,flush=True)
            gh('release','upload',TAG,str(path),'--repo',REPO)
    release=api('GET','releases/'+str(release['id']))
    if {a['name'] for a in release['assets']}!=set(expected):raise RuntimeError('Asset set incomplete')
    for asset in release['assets']:
        path=ROOT/'dist'/asset['name']
        if asset['size']!=path.stat().st_size or asset['state']!='uploaded':raise RuntimeError('Incomplete upload')
        if asset.get('digest'):
            if asset['digest']!='sha256:'+expected[asset['name']]:raise RuntimeError('Server checksum mismatch')
        else:
            data=gh('api','repos/'+REPO+'/releases/assets/'+str(asset['id']),'-H','Accept:application/octet-stream')
            if hashlib.sha256(data).hexdigest()!=expected[asset['name']]:raise RuntimeError('Downloaded checksum mismatch')
    api('PATCH','releases/'+str(release['id']),dict(draft=False,prerelease=False,make_latest='true'))
    verified=api('GET','releases/'+str(release['id']))
    if verified['draft'] or len(verified['assets'])!=2:raise RuntimeError('Publication not confirmed')
    after=api('GET','git/ref/heads/main')['object']['sha']
    receipt=dict(repository=REPO,tag=TAG,release_id=verified['id'],release_url=verified['html_url'],
                 assets=[dict(name=a['name'],url=a['browser_download_url'],sha256=expected[a['name']]) for a in verified['assets']],
                 published=True,prerelease=verified['prerelease'],latest=verified.get('make_latest')=='true',main_before=before,main_after=after,main_unchanged=before==after)
    (ROOT/'dist/desktop-github-release.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
