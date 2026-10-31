"""Build a portable offline Windows directory and ZIP using installed PyInstaller.

Build dependencies: Windows, Python >=3.10, PyInstaller. Runtime: Windows x64
and a WebGL2-capable browser. No downloads are performed by this script.
"""
from pathlib import Path
import hashlib
import json
import platform
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    if sys.platform!='win32':raise SystemExit('Build on Windows for a native Windows executable')
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--console',
          '--name','ASTRA','--distpath',str(ROOT/'dist'/'native-1.5.0'),
          '--workpath',str(ROOT/'build'/'windows'),'--specpath',str(ROOT/'build'),
          '--collect-submodules','astra']
    files=sorted({*ROOT.glob('*.js'),*ROOT.glob('*.css'),*ROOT.glob('*.html'),
                  ROOT/'manifest.json',ROOT/'icon.svg',ROOT/'browser-python-files.json'})
    for path in files:args+=['--add-data',f'{path};.']
    args+=['--add-data',f'{ROOT/"assets"};assets',str(ROOT/'windows_launcher.py')]
    subprocess.run(args,cwd=ROOT,check=True)
    native=ROOT/'dist'/'native-1.5.0'/'ASTRA'
    target=ROOT/'dist'/'ASTRA-Windows-1.5.0'
    # Versioned delivery path keeps an older running package untouched.
    shutil.copytree(native,target,dirs_exist_ok=True)
    subprocess.run([str(target/'ASTRA.exe'),'--self-test'],check=True,cwd=ROOT)
    (target/'AVVIO-OFFLINE.txt').write_text(
        'ASTRA Flight Systems - Windows offline\n\n'
        'Estrarre tutta la cartella ZIP. Avviare ASTRA.exe.\n'
        'Tenere aperta la finestra del motore; Ctrl+C per chiudere.\n'
        'Il browser apre http://127.0.0.1:8765. Nessuna installazione Python richiesta.\n'
        'Serve un browser con WebGL2, per esempio Microsoft Edge su Windows 11.\n'
        'Per una porta occupata: ASTRA.exe --port 8766\n'
        'I profili controller sono salvati nel browser, separati per porta/origine.\n'
        'Nel pannello MODELLI: percorso avanzato, 13 discipline, seed e limiti.\n'
        'Profilo SPAZIO > Discesa lunare per la nuova missione 6-DoF.\n'
        'GRAFICA > HIGH o ULTRA abilita ombre, HDR, bloom e occlusione ambientale.\n'
        'La qualita grafica e migliorata, senza equivalenza dichiarata a Star Citizen.\n'
        'Hardware fisico non verificato. Il pacchetto non e firmato digitalmente.\n',encoding='utf-8')
    shutil.copy2(ROOT/'docs'/'ADVANCED_MODELS.md',target/'MODELLI-AVANZATI.txt')
    archive=Path(shutil.make_archive(str(ROOT/'dist'/'ASTRA-Windows-Offline'),'zip',root_dir=ROOT/'dist',base_dir='ASTRA-Windows-1.5.0'))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    report={'platform':platform.platform(),'python':sys.version,'archive':archive.name,
            'bytes':archive.stat().st_size,'sha256':digest,'self_test':'PASS'}
    (ROOT/'dist'/'windows-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
