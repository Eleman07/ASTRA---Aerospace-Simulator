"""Add the verified trailer to the existing desktop release without replacing binaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'build/astra-trailer-4k'
OUT = ROOT / 'deliverables/ASTRA-Trailer-4K'
REPO = 'Eleman07/ASTRA-Aerospace-Simulator'


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    before = json.loads((WORK / 'github-before.json').read_text(encoding='utf-8'))
    validation = json.loads((OUT / 'VALIDATION.json').read_text(encoding='utf-8'))
    quality = json.loads((OUT / 'QUALITY-CHECK.json').read_text(encoding='utf-8'))
    assert before['repository'] == REPO and before['tag'] == 'v2.3.2-desktop'
    assert quality['full_decode_pass'] and quality['music_only'] and not quality['unexpected_freezes']
    assert quality['frames'] == 1650 and quality['native_size'] == [3840, 2160]
    assert quality['music_correlation'] > .99
    master = OUT / 'ASTRA_Cinematic_Trailer_4K.mp4'
    assert sha(master) == validation['master_sha256']
    credits = OUT / 'ASTRA-Trailer-Credits.txt'
    credits.write_text((OUT / 'CREDITS.txt').read_text(encoding='utf-8') +
                      '\n\n===== FULL ASTRA ASSET ATTRIBUTIONS =====\n\n' +
                      (OUT / 'ASSET-CREDITS.txt').read_text(encoding='utf-8') +
                      '\n\n===== SUGGESTED VIDEO DESCRIPTION =====\n\n' +
                      (OUT / 'VIDEO-DESCRIPTION.txt').read_text(encoding='utf-8'), encoding='utf-8')
    files = [master, OUT / 'ASTRA_Cinematic_Trailer_1080p.mp4', credits]
    expected = {p.name: dict(sha256=sha(p), size=p.stat().st_size) for p in files}
    tag = before['tag']
    base = f'https://github.com/{REPO}/releases/download/{tag}/'
    section = f'''## Trailer cinematografico

**ASTRA | Beyond the Blue** — 55 secondi, 3840×2160 nativi, 16:9, 30 fps.
Scene nel motore ASTRA: Falcon 9 nello spazio, aereo e UAV in volo, controllo
tramite SDK Python realmente eseguito e modalità GIOCA. Titoli inglesi,
movimenti di camera, transizioni e color grading. Audio: solo musica.
Finale con il portfolio https://elemanprojects.com.

- [Trailer 4K]({base}{files[0].name})
- [Trailer 1080p]({base}{files[1].name})
- [Crediti completi: musica e asset]({base}{credits.name})

Musica: 'Horizons' di Scott Buckley — released under CC-BY 4.0.
[scottbuckley.com.au](https://www.scottbuckley.com.au/library/horizons/)
· [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Estratto montato con dissolvenze e normalizzazione del volume.
I crediti completi dei modelli e delle immagini sono allegati.

Il trailer è materiale dimostrativo: applicazione e SDK mantengono le
versioni Desktop 2.3.2 e SDK 2.3.0 già pubblicate.

'''
    notes = before['release_body']
    if '## Trailer cinematografico' not in notes:
        intro, rest = notes.split('\n\n', 1)
        notes = intro + '\n\n' + section + rest
    notes = notes.replace('La release distribuisce solo installer Windows e wheel Python.',
                          'La release distribuisce installer Windows, wheel Python e trailer dimostrativo con crediti.')
    (WORK / 'release-notes-with-trailer.md').write_text(notes, encoding='utf-8')
    plan = dict(repository=REPO, tag=tag, release_id=before['release_id'], assets=expected,
                existing_installer_and_sdk_preserved=True)
    if not args.publish:
        print(json.dumps(plan, indent=2), flush=True)
        return

    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    token = env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')
    if not token:
        result = subprocess.run(['git', 'credential', 'fill'],
            input='protocol=https\nhost=github.com\n\n', capture_output=True, text=True,
            env=env, check=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        token = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line).get('password')
    if not token:
        raise RuntimeError('GitHub credential unavailable')
    env['GH_TOKEN'] = token

    def api(method, path, payload=None):
        request = Request('https://api.github.com/repos/' + REPO + '/' + path,
            method=method, data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                     'Content-Type': 'application/json', 'User-Agent': 'ASTRA-Trailer-Publisher'})
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f'GitHub {method} {path} returned {exc.code}') from None

    def check_original(release):
        assert release['id'] == before['release_id'] and release['tag_name'] == tag
        assert not release['draft'] and not release.get('immutable')
        by_name = {a['name']: a for a in release['assets']}
        for old in before['release_assets']:
            now = by_name[old['name']]
            assert all(now[k] == old[k] for k in ['id', 'size', 'digest'])

    release = api('GET', 'releases/tags/' + tag)
    check_original(release)
    if release['body'] not in (before['release_body'], notes):
        raise RuntimeError('Release notes changed concurrently; nothing overwritten')
    existing = {a['name']: a for a in release['assets']}
    for path in files:
        if path.name in existing:
            assert existing[path.name]['digest'] == 'sha256:' + expected[path.name]['sha256']
            continue
        print('UPLOADING', path.name, flush=True)
        result = subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo', REPO],
            capture_output=True, env=env, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace').replace(token, '[REDACTED]'))
    release = api('GET', 'releases/tags/' + tag)
    check_original(release)
    media = {a['name']: a for a in release['assets'] if a['name'] in expected}
    assert set(media) == set(expected)
    for name, asset in media.items():
        assert asset['state'] == 'uploaded' and asset['size'] == expected[name]['size']
        assert asset['digest'] == 'sha256:' + expected[name]['sha256']
    if release['body'] != notes:
        api('PATCH', 'releases/' + str(release['id']), dict(body=notes))
    verified = api('GET', 'releases/tags/' + tag)
    check_original(verified)
    assert verified['body'] == notes and verified['prerelease'] == release['prerelease']
    receipt = dict(**plan, published=True, release_url=verified['html_url'],
                   assets_verified=[dict(name=a['name'], url=a['browser_download_url'],
                                         sha256=expected[a['name']]['sha256']) for a in media.values()])
    (ROOT / 'test-results/github-trailer-v2.3.2.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
