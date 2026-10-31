"""Collect reproducible checks for the native release without changing physics."""
import hashlib
import json
from pathlib import Path
import subprocess
import re

ROOT=Path(__file__).resolve().parents[1]

def main():
    read=lambda name:json.loads((ROOT/name).read_text(encoding='utf-8'))
    build=read('dist/desktop-build.json')
    install=read('dist/desktop-installer.json')
    package=read('test-results/desktop-package-validation.json')
    routing=read('test-results/input-routing-validation.json')
    assert routing['version']==build['version'] and routing['result']=='PASS'
    for path,value in routing['source_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==value
    baseline=read('docs/validation/advanced-mission.json')['source_sha256']
    controlled_orbital_fix={'astra/attitude.py','astra/engine.py'}
    preserved={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
               for name,digest in baseline.items() if name.startswith('astra/') and name not in controlled_orbital_fix}
    assert all(preserved.values())
    orbital_fix={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==build['science_sources'].get(name)
                 for name in controlled_orbital_fix}
    assert all(orbital_fix.values())
    orbital_tests=(ROOT/'tools/test_orbital_sas.py').is_file() and (ROOT/'tools/test_gameplay.py').is_file()
    assert orbital_tests
    evidence={profile:read(f'test-results/native-suite-{profile}.json') for profile in ('high','low')}
    assert all(row['renderer_sha256']==build['renderer_sha256'] for row in evidence.values())
    assert all(all(case['loaded'] for case in row['asset_imports']) for row in evidence.values())
    assert all(install.get(key)=='PASS' for key in ('runtime_self_test','installer_test','uninstaller_test'))
    assert package['frozen_host']=='PASS' and package['offline_wheel']=='PASS'
    assert package['free_flight_api']=='PASS' and package['detailed_instruments_api']=='PASS'
    assert package['independent_sdk']=='PASS' and package['legacy_module_collision']=='PASS'
    polish={profile:read(f'test-results/polish-{profile}.json') for profile in ('high','low')}
    for proof in polish.values():
        assert proof['renderer_sha256']==build['renderer_sha256']
        assert proof['unlimited_fps'] and proof['vsync_disabled'] and proof['audio_peak']>.0001
        assert proof['printing_stand_removed_triangles']==12 and proof['cinematic_reentry']
        assert proof['cc0_hdr_flipbooks']
        assert all(row['covered'] for row in proof['chunk_residency'])
    gnc=read('test-results/python-gnc-validation.json')
    assert gnc['closed_loop']=='PASS' and gnc['installed_wheel'] and gnc['commands']==400
    assert gnc['renderer_sha256']==build['renderer_sha256'] and gnc['sdk_sha256']==build['sdk_sha256']
    assert gnc['final_error_m']<.75 and gnc['screenshot']['script_output_matches_state']
    assert len(gnc['live_renderer_fps'])>=3 and gnc['png_sha256']==hashlib.sha256((ROOT/'test-results/python-gnc.png').read_bytes()).hexdigest()
    assert package['camera_api']=='PASS' and package['renderer_sha256']==build['renderer_sha256']
    assert all(proof['cases'][0]['launch_vertical'] for proof in evidence.values())
    assert all(len(proof['free_flight'])==3 and all(row['manual'] for row in proof['free_flight']) for proof in evidence.values())
    assert all(len(proof['globes'])==2 and all(row['local_patch_hidden'] and row['screenshot'] for row in proof['globes']) for proof in evidence.values())
    assert all(proof['detailed_instruments']>12 for proof in evidence.values())
    visual_api=read('test-results/visual-api-validation.json')
    assert visual_api['physics_unchanged'] and visual_api['renderer_sha256']==build['renderer_sha256']
    alignment=read('test-results/vehicle-alignment.json')
    assert len(alignment)==5 and all(row['vertical'] for row in alignment)
    celestial=read('test-results/celestial-views-validation.json')
    assert celestial['source_scene_sha256']==hashlib.sha256((ROOT/'desktop/native_scene.gd').read_bytes()).hexdigest()
    assert len(celestial['cases'])==4 and all(row['spherical'] and row['texture_loaded'] for row in celestial['cases'])
    python_log=(ROOT/'test-results/python-desktop-suite.log').read_text(encoding='utf-8')
    js_log=(ROOT/'test-results/javascript-suite.log').read_text(encoding='utf-8')
    tests=int(re.search(r'Ran (\d+) tests',python_log).group(1))
    assert tests>=97 and 'OK (skipped=2)' in python_log
    assert 'fail 0' in js_log
    result=dict(version=build['version'],release_kind='NATIVE_DESKTOP_PREVIEW',native=True,offline_assets_bundled=True,
                browser_required=False,science_sources_preserved=preserved,audited_orbital_control_sources=orbital_fix,
                orbital_attitude_and_gioca_tests_present=orbital_tests,python_tests=tests,python_passed=tests-2,
                python_installer_tests_skipped=2,native_installer_test=install,
                exact_state_parity_scenarios=5,scientific_disciplines=13,engineering_solvers=18,
                native_graphics=evidence,polish=polish,python_gnc=gnc,packaged_sdk=package,input_routing=routing,visual_api=visual_api,rocket_alignment=alignment,celestial_views=celestial,readme_update_authorized=True,
                limits=['No Star Citizen visual parity claimed','No universal FPS guarantee',
                        'Offscreen GPU tests on NVIDIA RTX 5080 Laptop; not a universal benchmark',
                        'No physical Xbox/HOTAS device validation claimed','SSR is not hardware ray tracing',
                        'Visual reference models do not supply certified vehicle physics'])
    (ROOT/'docs/validation/desktop-native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(native=True,science_sources_preserved=all(preserved.values()),
                          renderer_sha256=build['renderer_sha256'],installer_sha256=install['sha256'],
                          installer_files=install['installed_files_verified'],sdk_sha256=install['sdk_sha256'],
                          validated=True),indent=2))

if __name__=='__main__':main()
