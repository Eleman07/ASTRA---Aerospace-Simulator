"""Opt-in integration test for the built installer, isolated to the workspace.

python tools/test_windows_installer.py
Does not create desktop/Start menu links or change the uninstall registry.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]


class InstallerArtifactTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='win32' and __name__=='__main__',
                         'opt-in built-installer integration test; run this file directly')
    def test_install_runtime_and_uninstall_preserving_user_files(self):
        report_path=ROOT/'dist'/'desktop-installer.json'
        report=json.loads(report_path.read_text(encoding='utf-8'))
        installer=(ROOT/'dist'/report['installer']).resolve()
        self.assertIn(ROOT,installer.parents)
        self.assertEqual(hashlib.sha256(installer.read_bytes()).hexdigest(),report['sha256'])
        tests=ROOT/'test-results';tests.mkdir(exist_ok=True)
        target=(tests/('native-installer-smoke-'+str(time.time_ns()))).resolve()
        self.assertIn(tests.resolve(),target.parents)
        self.assertFalse(target.exists())
        subprocess.run([str(installer),'/S','/NOINTEGRATION','/D='+str(target)],
                       check=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        manifest=json.loads((target/'installation-manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['files']:
            installed=(target/entry['path']).resolve()
            self.assertIn(target,installed.parents)
            self.assertEqual(hashlib.sha256(installed.read_bytes()).hexdigest(),entry['sha256'],entry['path'])
        result=subprocess.run([str(target/'ASTRA.exe'),'--self-test'],check=True,
                              capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0)  # Windowed exe has no console stdout
        sentinel=target/'keep-user-file.txt';sentinel.write_text('user data must survive uninstall',encoding='utf-8')
        uninstaller=target/'Uninstall.exe'
        subprocess.run([str(uninstaller),'/S'],check=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline and (uninstaller.exists() or (target/'ASTRA.exe').exists()):
            time.sleep(.1)
        self.assertFalse((target/'ASTRA.exe').exists())
        self.assertFalse(uninstaller.exists())
        self.assertEqual(sentinel.read_text(encoding='utf-8'),'user data must survive uninstall')
        self.assertEqual(list(target.iterdir()),[sentinel])
        report.update(installer_test='PASS',installed_files_verified=len(manifest['files']),
                      uninstaller_test='PASS',user_files_preserved=True)
        report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))


if __name__=='__main__':unittest.main(verbosity=2)
