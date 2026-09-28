"""Copy the public launcher/SDK tree (no game files) to a folder you can push to GitHub.

Example:

    python tools/export_jhwml.py C:\\src\\jhwml

Do not copy Happy Wheels, app.asar, recordings, or the relay.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

FILES = [
    'installer/app.py',
    'installer/build.ps1',
    'installer/README.md',
    'installer/icon.ico',
    'installer/icon.png',
    'core/mod-catalog.cjs',
    'core/mod-loader-main.cjs',
    'core/mod-loader-preload.cjs',
    'core/asset-map.cjs',
    'core/asset-override.js',
    'core/boot-list.cjs',
    'core/hw-mod-sdk.js',
    'tools/packager.py',
    'tools/setup.py',
    'tools/game-manifest.json',
    'tools/mod_store.py',
    'tools/launcher_update.py',
    'tools/launcher_version.py',
    'tools/publish_launcher.py',
    'tools/export_jhwml.py',
    'mod-store/launcher.json',
    'mod-store/README.md',
    'docs/_config.yml',
    'docs/index.md',
    'docs/install-for-players.md',
    'docs/first-mod.md',
    'docs/make-a-mod.md',
    'docs/api.md',
    'docs/electron.md',
    'docs/assets.md',
    'docs/limits.md',
    'examples/first-hw-mod/mod.json',
    'examples/first-hw-mod/README.md',
    'examples/first-hw-mod/web/main.js',
    'examples/hello-hw-mod/mod.json',
    'examples/hello-hw-mod/README.txt',
    'examples/hello-hw-mod/web/main.js',
    'tests/mod-catalog.test.cjs',
    'tests/hw-mod-sdk.test.cjs',
    'tests/boot-list.test.cjs',
    'tests/asset-map.test.cjs',
    'tests/preload-patch.test.cjs',
    'tests/launcher_update_test.py',
]

README = ROOT / 'jhwml' / 'README.md'
GITIGNORE = """node_modules/
__pycache__/
*.pyc
dist/
build/
*.log
mod-store/zips/
"""


def copy_public(dest: pathlib.Path) -> None:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        src = ROOT / rel
        if not src.is_file():
            raise FileNotFoundError(f'Missing {rel}')
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    shutil.copy2(README, dest / 'README.md')
    (dest / '.gitignore').write_text(GITIGNORE, encoding='utf-8')
    (dest / 'package.json').write_text(
        json.dumps(
            {
                'name': 'jhwml',
                'private': True,
                'description': 'Happy Wheels 1.99.2 mod launcher and SDK',
                'scripts': {'test': 'node --test tests/*.test.cjs'},
            },
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )


def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: python tools/export_jhwml.py <destination-folder>')
        sys.exit(2)
    dest = pathlib.Path(sys.argv[1])
    copy_public(dest)
    print('Wrote public JHWML tree to', dest)


if __name__ == '__main__':
    main()
