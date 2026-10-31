"""Package the native renderer, scientific runtime and SDK into offline NSIS."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
from build_windows_installer import digest

ROOT=Path(__file__).resolve().parents[1]

def main():
    build=json.loads((ROOT/'dist/desktop-build.json').read_text())
    payload=Path(build['payload']).resolve()
    if ROOT not in payload.parents or not build['native']:raise RuntimeError('Invalid native payload')
    for path,key in [('ASTRA.exe','executable_sha256'),('ASTRA-Renderer.exe','renderer_sha256')]:
        if digest(payload/path)!=build[key]:raise RuntimeError('Stale native payload: '+path)
    for path,value in build['science_sources'].items():
        if digest(ROOT/path)!=value:raise RuntimeError('Science changed since build: '+path)
    subprocess.run([str(payload/'ASTRA.exe'),'--self-test'],check=True,timeout=45)
    work=ROOT/'build/desktop-installer';work.mkdir(parents=True,exist_ok=True)
    files=sorted(path for path in payload.rglob('*') if path.is_file())
    version=build['version']
    manifest={'schema_version':2,'product':'ASTRA Desktop','version':version+'.0',
              'architecture':'windows-x64','offline':True,'browser_required':False,
              'files':[dict(path=p.relative_to(payload).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in files]}
    manifest_path=work/'installation-manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    marker=work/'ASTRA-PACKAGE.txt';marker.write_bytes(b'ASTRA-DESKTOP-2\r\n')
    deletions=[];directories=set()
    for path in files:
        relative=path.relative_to(payload)
        if any(c in str(relative) for c in ('"','$','\r','\n')):raise ValueError('Unsupported filename')
        deletions.append('Delete "$INSTDIR\\'+str(relative)+'"')
        for parent in relative.parents:
            if parent!=Path('.'):directories.add(parent)
    deletions.extend('RMDir "$INSTDIR\\'+str(p)+'"' for p in sorted(directories,key=lambda p:(len(p.parts),str(p)),reverse=True))
    uninstall=work/'uninstall-files.nsh';uninstall.write_text('\n'.join(deletions)+'\n',encoding='utf-8')
    output=ROOT/'dist'/f'ASTRA-Desktop-{version}-Windows-x64-Setup.exe'
    compiler=ROOT/'build/toolchain/nsis-3.13/makensis.exe'
    subprocess.run([str(compiler),'/V2','/DPAYLOAD_DIR='+str(payload),'/DOUTPUT_FILE='+str(output),
        '/DPACKAGE_MARKER='+str(marker),'/DPACKAGE_MANIFEST='+str(manifest_path),
        '/DUNINSTALL_INCLUDE='+str(uninstall),'/DPRODUCT_VERSION='+version+'.0',str(ROOT/'tools/desktop-installer.nsi')],check=True,cwd=ROOT)
    report=dict(version=version,installer=output.name,bytes=output.stat().st_size,sha256=digest(output),
                payload_manifest_sha256=digest(manifest_path),runtime_self_test='PASS',installer_test='NOT_EVALUATED',
                sdk=build['sdk'],sdk_sha256=build['sdk_sha256'])
    (ROOT/'dist/desktop-installer.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
