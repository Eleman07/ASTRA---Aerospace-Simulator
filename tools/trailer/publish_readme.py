"""Publish only the prepared trailer README using GitHub's optimistic file update."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'build/astra-trailer-4k'
REPO = 'Eleman07/ASTRA-Aerospace-Simulator'


def main():
    before = json.loads((WORK / 'github-before.json').read_text(encoding='utf-8'))
    receipt = json.loads((ROOT / 'test-results/github-trailer-v2.3.2.json').read_text(encoding='utf-8'))
    assert receipt['published'] and receipt['tag'] == before['tag']
    content = (WORK / 'README.github.md').read_bytes()
    assert content.decode('utf-8').count('![') == 3
    expected = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    token = env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')
    if not token:
        result = subprocess.run(['git', 'credential', 'fill'],
            input='protocol=https\nhost=github.com\n\n', capture_output=True, text=True,
            check=True, env=env, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        token = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line).get('password')
    if not token:
        raise RuntimeError('GitHub credential unavailable')

    def api(method, path, payload=None):
        request = Request('https://api.github.com/repos/' + REPO + '/' + path,
            method=method, data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                     'Content-Type': 'application/json', 'User-Agent': 'ASTRA-Trailer-Docs'})
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f'GitHub {method} {path} returned {exc.code}') from None

    current = api('GET', 'contents/README.md')
    if current['sha'] != expected:
        assert current['sha'] == before['readme_sha'], 'README changed concurrently; nothing overwritten'
        update = api('PUT', 'contents/README.md', dict(
            message='docs: add verified 4K ASTRA trailer and credits to Desktop 2.3.2',
            sha=current['sha'], content=base64.b64encode(content).decode('ascii')))
        commit = update['commit']['sha']
    else:
        commit = None
    verified = api('GET', 'contents/README.md')
    assert verified['sha'] == expected and base64.b64decode(verified['content']) == content
    result = dict(repository=REPO, published=True, file='README.md', content_sha=expected,
                  commit_sha=commit, preview_images=3,
                  url='https://github.com/' + REPO + '#trailer-cinematografico')
    (ROOT / 'test-results/github-trailer-readme.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
