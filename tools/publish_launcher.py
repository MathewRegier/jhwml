"""Zip the built launcher EXE and write mod-store/launcher.json.

New EXEs check https://raw.githubusercontent.com/MathewRegier/jhwml/main/mod-store/launcher.json
and download the zip from GitHub Releases.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from launcher_version import EXE_NAME, NAME, VERSION  # noqa: E402

STORE = ROOT / 'mod-store'


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def launcher_payload(name: str, digest: str, file_url: str) -> dict:
    return {
        'id': 'jhwml-mod-launcher',
        'name': NAME,
        'version': VERSION,
        'file': file_url,
        'sha256': digest,
        'notes': 'Mod artwork is applied by the launcher. The old asset script is no longer installed.',
    }


def write_json(path: pathlib.Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'dist' / EXE_NAME
    if not exe.is_file():
        raise SystemExit('Built launcher EXE not found: ' + str(exe))
    name = f'JHWML-Mod-Launcher-{VERSION}.zip'
    release_url = f'https://github.com/MathewRegier/jhwml/releases/download/v{VERSION}/{name}'
    (STORE / 'zips').mkdir(parents=True, exist_ok=True)
    dest = STORE / 'zips' / name
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(exe, EXE_NAME)
    digest = sha256_file(dest)
    payload = launcher_payload(name, digest, release_url)
    write_json(STORE / 'launcher.json', payload)
    print('Wrote', dest)
    print('sha256', digest)
    print('Next: commit mod-store/launcher.json on jhwml, then:')
    print(f'  gh release create v{VERSION} "{dest}" --repo MathewRegier/jhwml --title "JHWML {VERSION}"')


if __name__ == '__main__':
    main()
