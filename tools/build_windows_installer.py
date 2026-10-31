"""Package an already verified ASTRA-Windows payload as one offline NSIS installer.

Usage: python tools/build_windows_installer.py --compiler <path-to-makensis.exe>
No source commits or uploads are performed by this script.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.5.0.0'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',required=True,type=Path)
    args=parser.parse_args()
    if sys.platform!='win32':raise SystemExit('Build this installer on Windows')
    payload=(ROOT/'dist'/'ASTRA-Windows-1.5.0').resolve()
    if ROOT not in payload.parents or not (payload/'ASTRA.exe').is_file():
        raise SystemExit('Build and verify the Windows payload first')
    subprocess.run([str(payload/'ASTRA.exe'),'--self-test'],check=True,cwd=ROOT)
    # Refuse a stale frontend so the binary release contains the current local work.
    for source in [*ROOT.glob('*.js'),*ROOT.glob('*.css'),*ROOT.glob('*.html')]:
        if digest(source)!=digest(payload/'_internal'/source.name):
            raise SystemExit('Payload needs rebuilding: '+source.name)
    work=ROOT/'build'/'installer';work.mkdir(parents=True,exist_ok=True)
    files=sorted(path for path in payload.rglob('*') if path.is_file())
    manifest={'schema_version':1,'product':'ASTRA Flight Systems','version':VERSION,
              'architecture':'windows-x64','offline':True,'files':[
                  {'path':path.relative_to(payload).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path)} for path in files]}
    manifest_path=work/'installation-manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    marker=work/'ASTRA-PACKAGE.txt';marker.write_bytes(b'ASTRA-WINDOWS-1\r\n')
    deletions=[];directories=set()
    for path in files:
        relative=path.relative_to(payload)
        if any(c in str(relative) for c in ('"','$','\r','\n')):raise ValueError('Unsupported payload filename')
        deletions.append('Delete "$INSTDIR\\'+str(relative)+'"')
        for parent in relative.parents:
            if parent!=Path('.'):directories.add(parent)
    deletions.extend('RMDir "$INSTDIR\\'+str(p)+'"' for p in sorted(directories,key=lambda p:(len(p.parts),str(p)),reverse=True))
    uninstall=work/'uninstall-files.nsh';uninstall.write_text('\n'.join(deletions)+'\n',encoding='utf-8')
    output=ROOT/'dist'/f'ASTRA-Flight-Systems-{VERSION}-Windows-x64-Setup.exe'
    command=[str(args.compiler.resolve()),'/V2',
             '/DPAYLOAD_DIR='+str(payload),'/DOUTPUT_FILE='+str(output),
             '/DPACKAGE_MARKER='+str(marker),'/DPACKAGE_MANIFEST='+str(manifest_path),
             '/DUNINSTALL_INCLUDE='+str(uninstall),str(ROOT/'tools'/'windows-installer.nsi')]
    subprocess.run(command,check=True,cwd=ROOT)
    report={'version':VERSION,'installer':output.name,'bytes':output.stat().st_size,
            'sha256':digest(output),'payload_manifest_sha256':digest(manifest_path),
            'runtime_self_test':'PASS','installer_test':'NOT_EVALUATED'}
    (ROOT/'dist'/'windows-installer.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
