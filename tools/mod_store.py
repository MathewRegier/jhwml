"""Download Happy Wheels mods from a public catalog (GitHub raw, R2, etc.)."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import tempfile
import urllib.error
import urllib.request
import zipfile

from launcher_version import USER_AGENT

DEFAULT_CATALOG_URL = os.environ.get(
    'HW_MOD_CATALOG_URL',
    'https://raw.githubusercontent.com/MathewRegier/happy-wheels-ghost-relay/main/mod-store/catalog.json',
)
SAFE_ID = re.compile(r'^[a-z0-9][a-z0-9-]{0,47}$')


def cache_dir() -> pathlib.Path:
    override = os.environ.get('HW_MOD_CACHE')
    root = pathlib.Path(override) if override else pathlib.Path(os.environ.get('LOCALAPPDATA') or pathlib.Path.home() / 'AppData' / 'Local')
    path = root if override else root / 'HappyWheelsModLauncher'
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_version(value: object) -> tuple[int, ...]:
    parts = [int(bit) for bit in re.findall(r'\d+', str(value or '0'))]
    return tuple(parts) if parts else (0,)


def is_newer(remote: object, local: object) -> bool:
    return parse_version(remote) > parse_version(local)


def _read_url(url: str, timeout: int = 20) -> bytes:
    if not url.startswith('https://'):
        raise ValueError('Mod library URLs must use https.')
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def catalog_base(url: str) -> str:
    return url.rsplit('/', 1)[0] + '/'


def fetch_catalog(url: str = DEFAULT_CATALOG_URL) -> dict:
    data = json.loads(_read_url(url).decode('utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('mods'), list):
        raise ValueError('Mod library catalog is invalid.')
    mods = []
    for item in data['mods']:
        if not isinstance(item, dict):
            continue
        mod_id = str(item.get('id') or '')
        if not SAFE_ID.match(mod_id):
            continue
        file_name = str(item.get('file') or item.get('url') or '')
        if not file_name:
            continue
        mods.append({
            'id': mod_id,
            'name': str(item.get('name') or mod_id),
            'version': str(item.get('version') or '0'),
            'author': str(item.get('author') or ''),
            'description': str(item.get('description') or ''),
            'file': file_name,
            'sha256': str(item.get('sha256') or '').lower(),
        })
    data['mods'] = mods
    return data


def _safe_extract(archive: zipfile.ZipFile, dest: pathlib.Path) -> None:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for info in archive.infolist():
        target = (dest / info.filename).resolve()
        if dest != target and dest not in target.parents:
            raise ValueError('Mod zip contained an unsafe path.')
    archive.extractall(dest)


def _normalize_extracted(extracted: pathlib.Path, mod_id: str) -> pathlib.Path:
    if (extracted / 'mod.json').is_file():
        return extracted
    nested = extracted / mod_id
    if (nested / 'mod.json').is_file():
        return nested
    children = [child for child in extracted.iterdir() if child.is_dir() and (child / 'mod.json').is_file()]
    if len(children) == 1:
        return children[0]
    raise ValueError('Downloaded mod is missing mod.json.')


def install_zip(blob: bytes, expected: str, dest: pathlib.Path, mod_id: str) -> pathlib.Path:
    digest = hashlib.sha256(blob).hexdigest()
    if expected and digest != expected:
        raise ValueError('Downloaded mod failed the checksum check.')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        zpath = pathlib.Path(temp) / 'mod.zip'
        zpath.write_bytes(blob)
        unpacked = pathlib.Path(temp) / 'unpacked'
        with zipfile.ZipFile(zpath) as archive:
            _safe_extract(archive, unpacked)
        source = _normalize_extracted(unpacked, mod_id)
        from packager import replace_tree
        replace_tree(source, dest, mod_id)
    return dest


def download_mod(entry: dict, catalog_url: str = DEFAULT_CATALOG_URL, dest: pathlib.Path | None = None) -> pathlib.Path:
    file_name = entry['file']
    url = file_name if file_name.startswith('https://') else catalog_base(catalog_url) + file_name.lstrip('/')
    blob = _read_url(url)
    target = dest or (cache_dir() / 'mods' / entry['id'])
    return install_zip(blob, entry.get('sha256', ''), target, entry['id'])


def _load_available(bundled: pathlib.Path | None) -> dict[str, dict]:
    from packager import load_mods
    local: dict[str, dict] = {}
    if bundled and bundled.is_dir():
        for mod in load_mods(bundled):
            local[mod['id']] = {**mod, 'source': 'bundled'}
    cached_root = cache_dir() / 'mods'
    if cached_root.is_dir():
        for mod in load_mods(cached_root):
            prev = local.get(mod['id'])
            if not prev or is_newer(mod.get('version'), prev.get('version')):
                local[mod['id']] = {**mod, 'source': 'cache'}
    return local


def _installed_mods(installed: pathlib.Path | None) -> dict[str, dict]:
    from packager import load_mods
    if not installed or not installed.is_dir():
        return {}
    return {mod['id']: mod for mod in load_mods(installed)}


def _status_against_game(entry: dict, installed: dict | None) -> tuple[str, str]:
    if not installed:
        return 'new', 'New · v' + str(entry['version'])
    game_version = installed.get('version') or '0'
    if is_newer(entry['version'], game_version):
        return 'update', 'Update v' + str(game_version) + ' → v' + str(entry['version'])
    return 'current', 'Up to date · v' + str(game_version)


def sync_mods(
    catalog_url: str = DEFAULT_CATALOG_URL,
    bundled: pathlib.Path | None = None,
    installed: pathlib.Path | None = None,
    progress=None,
) -> list[dict]:
    def note(message: str) -> None:
        if progress:
            progress(message)

    local = _load_available(bundled)
    game_mods = _installed_mods(installed)

    try:
        catalog = fetch_catalog(catalog_url)
        note('Checked the online mod library.')
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        note('Could not reach the online mod library. Using the copy stored on this computer.')
        result = list(local.values())
        for item in result:
            status, badge = _status_against_game(item, game_mods.get(item['id']))
            if status == 'current':
                item['status'] = 'current'
                item['badge'] = 'Offline · ' + badge
            elif status == 'update':
                item['status'] = 'update'
                item['badge'] = 'Offline · ' + badge
            else:
                item['status'] = 'bundled'
                item['badge'] = 'Offline'
        return result

    for entry in catalog['mods']:
        current = local.get(entry['id'])
        have_version = current.get('version') if current else ''
        need_download = current is None or is_newer(entry['version'], have_version)
        installed_mod = game_mods.get(entry['id'])
        status, badge = _status_against_game(entry, installed_mod)
        if need_download:
            note(('Downloading ' if current else 'Getting new mod ') + entry['name'] + ' v' + entry['version'] + '…')
            try:
                path = download_mod(entry, catalog_url)
                from packager import load_mods
                loaded = next((mod for mod in load_mods(path.parent) if mod['id'] == entry['id']), None)
                local[entry['id']] = {
                    **(loaded or entry),
                    'path': path,
                    'source': 'cloud',
                    'status': status,
                    'badge': badge,
                    'installed_version': installed_mod.get('version') if installed_mod else '',
                }
            except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                note('Could not download ' + entry['name'] + '.')
                if current:
                    current['status'] = status
                    current['badge'] = 'Update failed · ' + badge
                else:
                    local[entry['id']] = {**entry, 'status': 'error', 'badge': 'Download failed'}
        else:
            current['status'] = status
            current['badge'] = badge
            current['name'] = entry.get('name') or current.get('name')
            current['description'] = entry.get('description') or current.get('description')
            current['version'] = entry['version']
            current['installed_version'] = installed_mod.get('version') if installed_mod else ''
    return sorted(local.values(), key=lambda item: (item.get('priority', 100), item['id']))
