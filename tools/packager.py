"""Install mods into the Happy Wheels Steam folder.

The launcher calls install(). That:

  1. Checks you're on Steam 1.99.2-s (hashes in game-manifest.json)
  2. Backs up Happy Wheels.exe + app.asar the first time
  3. Copies selected mods into Happy Wheels\\mods\\
  4. Unpacks the asar, drops in core/ (the loader + SDK), patches
     electron/out/main.js and preload.js
  5. Repacks app.asar and rewrites the SHA256 the EXE bakes in

Steam "Verify integrity of game files" undoes all of this. Run the
launcher again after that.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import struct
import sys
import time

from launcher_version import VERSION

GAME_VERSION = '1.99.2-s'


def strip_inlined_hw_ghost_net(text: str) -> str:
    # Older EXEs pasted the multiplayer hwGhostNet bridge straight into
    # preload.js. The mod ships that itself now, so peel any leftover IIFE
    # out before we append the current hook.
    marker = "exposeInMainWorld('hwGhostNet'"
    alt = 'exposeInMainWorld("hwGhostNet"'
    while marker in text or alt in text:
        idx = text.find(marker)
        if idx < 0:
            idx = text.find(alt)
        start = text.rfind('(() =>', 0, idx)
        if start < 0:
            start = text.rfind('(()=>', 0, idx)
        if start < 0:
            start = idx
        end = text.find('})();', idx)
        if end < 0:
            break
        text = text[:start] + text[end + 5:]
    return text


def patch_game_preload(preload: pathlib.Path, hook: str, transport: str = '') -> None:
    current = strip_inlined_hw_ghost_net(preload.read_text(encoding='utf-8'))
    transport = (transport or '').strip()
    if transport:
        # Optional Steam-invite bridge from jimbobs-multiplayer. Empty string
        # if that mod isn't in the game folder yet.
        current = current.rstrip() + '\n' + transport + '\n'
    hook = hook.strip() + '\n'
    if 'mod-runtime' not in current:
        current = current.rstrip() + '\n' + hook
    if not current.endswith('\n'):
        current += '\n'
    preload.write_text(current, encoding='utf-8')


def patch_live_asar_preload(game: pathlib.Path, transport: str, hook: str) -> str:
    """Write the Steam bridge into the installed asar preload so a sandboxed game window can expose it."""
    packed = game / 'resources' / 'app.asar'
    exe = game / 'Happy Wheels.exe'
    blob = packed.read_bytes()
    files = unpack_asar(blob)
    key = 'electron/out/preload.js'
    if key not in files:
        raise ValueError('Could not find the game preload.')
    current = files[key].decode('utf-8')
    temp = game / 'resources' / '_preload-patch.js'
    temp.write_text(current, encoding='utf-8')
    patch_game_preload(temp, hook, transport)
    updated = temp.read_bytes()
    temp.unlink(missing_ok=True)
    if updated == files[key]:
        return 'already'
    files[key] = updated
    packed_blob = pack_asar({k: v for k, v in files.items() if not k.startswith('node_modules/steamworks.js/')})
    hs = struct.unpack_from('<I', packed_blob, 4)[0]
    header = json.loads(packed_blob[16:16 + struct.unpack_from('<I', packed_blob, 12)[0]])
    old_header = json.loads(blob[16:16 + struct.unpack_from('<I', blob, 12)[0]])
    # steamworks.js lives unpacked next to the asar. Copy the original
    # directory entry so the EXE's integrity check still matches.
    header.setdefault('files', {}).setdefault('node_modules', {'files': {}})['files']['steamworks.js'] = old_header['files']['node_modules']['files']['steamworks.js']
    raw = json.dumps(header, separators=(',', ':')).encode()
    pad = (-len(raw)) % 4
    pickle = struct.pack('<II', 4 + len(raw) + pad, len(raw)) + raw + b'\0' * pad
    new_blob = struct.pack('<II', 4, len(pickle)) + pickle + packed_blob[8 + hs:]
    old_len = struct.unpack_from('<I', blob, 12)[0]
    old_hash = hashlib.sha256(blob[16:16 + old_len]).hexdigest().encode()
    new_hash = hashlib.sha256(raw).hexdigest().encode()
    exe_bytes = exe.read_bytes()
    if exe_bytes.count(old_hash) != 1:
        raise ValueError('The Happy Wheels executable hash did not match this archive.')
    try:
        with exe.open('r+b'):
            pass
    except OSError as error:
        raise ValueError('Close Happy Wheels completely, then try again.') from error
    packed.write_bytes(new_blob)
    try:
        exe.write_bytes(exe_bytes.replace(old_hash, new_hash))
    except OSError:
        packed.write_bytes(blob)  # don't leave a patched asar next to a stock EXE
        raise ValueError('Close Happy Wheels completely, then try again.')
    return 'patched'


def project_root() -> pathlib.Path:
    if getattr(sys, 'frozen', False):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(__file__).resolve().parents[1]


def unpack_asar(blob: bytes) -> dict[str, bytes]:
    # Electron asar layout (little-endian):
    #   [0:8]   pickle size of the header pickle
    #   [8:16]  pickle size of the JSON
    #   [16:]   JSON directory, 4-byte padded, then concatenated file bytes
    # Offsets in the JSON are relative to the start of those file bytes.
    size = struct.unpack_from('<I', blob, 4)[0]
    length = struct.unpack_from('<I', blob, 12)[0]
    header = json.loads(blob[16:16 + length])
    result = {}

    def walk(files, prefix=''):
        for name, item in files.items():
            path = prefix + name
            if 'files' in item:
                walk(item['files'], path + '/')
            elif not item.get('unpacked'):
                start = 8 + size + int(item['offset'])
                result[path] = blob[start:start + item['size']]

    walk(header['files'])
    return result


def pack_asar(files: dict[str, bytes]) -> bytes:
    tree = {'files': {}}
    body = bytearray()
    for name, content in files.items():
        directory = tree['files']
        parts = name.split('/')
        for part in parts[:-1]:
            directory = directory.setdefault(part, {'files': {}})['files']
        block = 4194304  # Electron's default integrity block size
        directory[parts[-1]] = {
            'size': len(content),
            'offset': str(len(body)),
            'integrity': {
                'algorithm': 'SHA256',
                'hash': hashlib.sha256(content).hexdigest(),
                'blockSize': block,
                'blocks': [hashlib.sha256(content[i:i + block]).hexdigest() for i in range(0, len(content), block)],
            },
        }
        body.extend(content)
    header = json.dumps(tree, separators=(',', ':')).encode()
    padding = (-len(header)) % 4
    pickle = struct.pack('<II', 4 + len(header) + padding, len(header)) + header + b'\0' * padding
    return struct.pack('<II', 4, len(pickle)) + pickle + body


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_mods(mods_dir: pathlib.Path) -> list[dict]:
    # Each subfolder with a mod.json is a mod. Missing fields get defaults
    # so old drops still load.
    catalog = []
    if not mods_dir.is_dir():
        return catalog
    for entry in sorted(mods_dir.iterdir()):
        manifest = entry / 'mod.json'
        if not manifest.is_file():
            continue
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['path'] = entry
        data.setdefault('id', entry.name)
        data.setdefault('name', data['id'])
        data.setdefault('description', '')
        data.setdefault('author', '')
        data.setdefault('version', '')
        data.setdefault('priority', 100)
        data.setdefault('web', [])
        data.setdefault('enabled', True)
        catalog.append(data)
    catalog.sort(key=lambda item: (item.get('priority', 100), item['id']))
    return catalog


def find_happy_wheels() -> pathlib.Path | None:
    candidates = []
    steam_roots = []
    if os.name == 'nt':
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    key = winreg.OpenKey(hive, r'SOFTWARE\Valve\Steam')
                    steam_roots.append(pathlib.Path(winreg.QueryValueEx(key, 'SteamPath')[0]))
                except OSError:
                    pass
        except ImportError:
            pass
        steam_roots.extend([
            pathlib.Path(r'C:\Program Files (x86)\Steam'),
            pathlib.Path(r'C:\Program Files\Steam'),
        ])
    seen = set()
    for root in steam_roots:
        root = pathlib.Path(str(root)).expanduser()
        if not root.exists():
            continue
        libraries = [root]
        # Extra libraries live in libraryfolders.vdf ("path" "D:\\SteamLibrary").
        vdf = root / 'steamapps' / 'libraryfolders.vdf'
        if vdf.exists():
            text = vdf.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r'"path"\s*"([^"]+)"', text):
                libraries.append(pathlib.Path(match.group(1).replace('\\\\', '\\')))
        for library in libraries:
            game = library / 'steamapps' / 'common' / 'Happy Wheels'
            key = str(game.resolve()) if game.exists() else ''
            if key and key not in seen and looks_like_game(game):
                seen.add(key)
                candidates.append(game)
    return candidates[0] if candidates else None


def looks_like_game(path: pathlib.Path) -> bool:
    return (path / 'Happy Wheels.exe').is_file() and (path / 'resources' / 'webroot').is_dir()


def _unlock(path: pathlib.Path) -> None:
    # Steam / Explorer sometimes marks files read-only. FILE_ATTRIBUTE_NORMAL (0x80)
    # is the Windows way to clear that before we delete.
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x80)
        except Exception:
            pass


def _unlock_tree(root: pathlib.Path) -> None:
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            _unlock(pathlib.Path(dirpath) / name)
    _unlock(root)


def _rmtree_error(func, path, _exc) -> None:
    _unlock(pathlib.Path(path))
    func(path)


def force_remove(path: pathlib.Path, label: str | None = None) -> None:
    # Retry because Explorer or the still-running game likes to hold a handle
    # for a few hundred ms after you think you closed it.
    path = pathlib.Path(path)
    if not path.exists() and not path.is_symlink():
        return
    name = label or path.name
    _unlock_tree(path)
    last_error = None
    for attempt in range(10):
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
            else:
                kwargs = {'onexc': _rmtree_error} if sys.version_info >= (3, 12) else {'onerror': lambda fn, p, _info: _rmtree_error(fn, p, _info)}
                shutil.rmtree(path, **kwargs)
            if not path.exists():
                return
        except OSError as error:
            last_error = error
        time.sleep(0.12 * (attempt + 1))
    raise ValueError(
        f'Could not delete the old {name} folder. Close Happy Wheels and any File Explorer window looking at the mods folder, then try again.'
    ) from last_error


def replace_tree(source: pathlib.Path, dest: pathlib.Path, label: str | None = None) -> None:
    """Swap dest for a fresh copy of source. Never merge leftover files from the old folder."""
    source = pathlib.Path(source)
    dest = pathlib.Path(dest)
    name = label or dest.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    parked = dest.with_name(dest.name + '.__old__')
    staged = dest.with_name(dest.name + '.__new__')
    force_remove(parked, name)
    force_remove(staged, name)
    if dest.exists() or dest.is_symlink():
        _unlock_tree(dest)
        try:
            dest.rename(parked)
        except OSError:
            force_remove(dest, name)
    if dest.exists():
        raise ValueError(
            f'Windows still has the old {name} folder. Close Happy Wheels and File Explorer, then try again.'
        )
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns('__pycache__'))
    staged.rename(dest)
    if parked.exists():
        force_remove(parked, name)


def write_launcher(game: pathlib.Path) -> None:
    play = game / 'Play Happy Wheels Mods.vbs'
    play.write_text(
        'Set shell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        'root = fso.GetParentFolderName(WScript.ScriptFullName)\n'
        'shell.CurrentDirectory = root\n'
        'shell.Run Chr(34) & root & "\\Happy Wheels.exe" & Chr(34), 1, False\n',
        encoding='utf-8',
    )
    (game / 'mods' / 'README.txt').write_text(
        'Drop a mod folder here. Each mod needs a mod.json file.\n'
        'Restart Happy Wheels to load it. You do not need the launcher again\n'
        'unless a Steam update removes the core loader.\n'
        '\n'
        'Game hooks use window.HWMod. Docs:\n'
        'https://mathewregier.github.io/jhwml/\n',
        encoding='utf-8',
    )


def install(source: pathlib.Path, dest: pathlib.Path | None = None, enabled_ids: list[str] | None = None, progress=None) -> pathlib.Path:
    def note(percent: int, message: str):
        if progress:
            progress(percent, message)

    root = project_root()
    game = pathlib.Path(source).resolve()
    if dest:
        dest_path = pathlib.Path(dest).resolve()
        if dest_path != game and looks_like_game(dest_path):
            game = dest_path
    if not looks_like_game(game):
        raise ValueError('That folder does not look like Happy Wheels.')

    # SHA256 of stock 1.99.2-s files. Frozen EXE looks next to packager.py
    # (copied into the bundle as tools/game-manifest.json).
    manifest_path = root / 'tools' / 'game-manifest.json'
    if not manifest_path.exists():
        manifest_path = root / 'game-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    note(4, 'Checking your Happy Wheels files…')

    exe_backup = game / 'Happy Wheels.exe.original'
    resources = game / 'resources'
    packed = resources / 'app.asar'
    original = resources / 'app.original.asar'
    def asar_is_patched(blob: bytes) -> bool:
        try:
            main = unpack_asar(blob).get('electron/out/main.js', b'').decode('utf-8', errors='ignore')
        except Exception:
            return False
        return 'hw-mod-boot' in main or 'hw-mod-loader' in main

    # Steam replaced app.asar (verify / game update) but our old backup is
    # still sitting there. Snapshot the new stock files before we patch.
    if packed.exists() and original.exists() and packed.read_bytes() != original.read_bytes() and not asar_is_patched(packed.read_bytes()):
        note(3, 'Steam updated Happy Wheels. Replacing the old backup and patching the new files…')
        shutil.copy2(packed, original)
        shutil.copy2(game / 'Happy Wheels.exe', exe_backup)

    exe_is_stock = hashlib.sha256((game / 'Happy Wheels.exe').read_bytes()).hexdigest() == manifest.get('Happy Wheels.exe')
    if not exe_backup.exists() and not exe_is_stock:
        raise ValueError('This copy was already changed. In Steam, use Verify integrity of game files, then run the installer again.')
    already = original.exists() and (exe_backup.exists() or exe_is_stock)

    def read_game(name: str) -> bytes:
        return game.joinpath(*pathlib.PurePosixPath(name).parts).read_bytes()

    # After the first install the EXE + asar hashes won't match stock, by
    # design. Skip those two; everything else still has to be 1.99.2-s.
    skip = {'Happy Wheels.exe', 'resources/app.asar'} if already else set()
    for name, expected in manifest.items():
        if name in skip:
            continue
        try:
            actual = hashlib.sha256(read_game(name)).hexdigest()
        except (OSError, KeyError) as error:
            raise ValueError('Missing original game file: ' + name) from error
        if actual != expected:
            raise ValueError('Unsupported Happy Wheels build: ' + name + '. This pack supports Happy Wheels ' + GAME_VERSION + '. If Steam just updated, open this launcher again so it can update itself, then press Install.')

    probe = game / '.hw-mod-write-test'
    try:
        with (game / 'Happy Wheels.exe').open('r+b'):
            pass
        if packed.exists():
            with packed.open('r+b'):
                pass
        probe.write_text('ok', encoding='utf-8')
        probe.unlink(missing_ok=True)
    except PermissionError as error:
        if probe.exists():
            probe.unlink(missing_ok=True)
        raise ValueError('Close Happy Wheels, then run this installer as Administrator so it can write to the Steam folder.') from error

    if not exe_backup.exists():
        shutil.copy2(game / 'Happy Wheels.exe', exe_backup)
    if packed.exists() and not original.exists():
        shutil.copy2(packed, original)
    if not original.exists():
        raise ValueError('Could not find the game archive to patch.')

    note(18, 'Adding the mods folder…')
    (game / 'mods').mkdir(parents=True, exist_ok=True)

    from mod_store import cache_dir, is_newer
    bundled = root / 'mods'
    chosen: dict[str, dict] = {}
    # Prefer the downloaded cache over anything shipped inside the EXE.
    for folder in (cache_dir() / 'mods', bundled):
        if not folder.is_dir():
            continue
        for mod in load_mods(folder):
            prev = chosen.get(mod['id'])
            if not prev or is_newer(mod.get('version'), prev.get('version')):
                chosen[mod['id']] = mod
    catalog_ids = set(chosen)
    if enabled_ids is not None:
        for mod_id in catalog_ids:
            leftover = game / 'mods' / mod_id
            if mod_id not in enabled_ids and leftover.exists():
                force_remove(leftover, leftover.name)
    for mod in chosen.values():
        if enabled_ids is None or mod['id'] in enabled_ids:
            target = game / 'mods' / mod['id']
            note(22, f'Replacing {mod["name"]} in the mods folder…' if target.exists() else f'Adding {mod["name"]}…')
            replace_tree(mod['path'], target, mod.get('name') or mod['id'])
    installed_mods = load_mods(game / 'mods')
    if enabled_ids is not None:
        # Drop-in folders the catalog doesn't know about stay put.
        installed_mods = [mod for mod in installed_mods if mod['id'] in enabled_ids or mod['id'] not in catalog_ids]

    note(46, 'Preparing the mod loader…')
    app = resources / 'app'
    # Unpack the *stock* asar, not the currently patched one, so a reinstall
    # doesn't stack patches on top of patches.
    for name, data in unpack_asar(original.read_bytes()).items():
        dest_file = app / name
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_bytes(data)

    unpacked_modules = resources / 'app.asar.unpacked' / 'node_modules'
    if unpacked_modules.exists():
        shutil.copytree(unpacked_modules, app / 'node_modules', dirs_exist_ok=True)
    ws_source = root / 'node_modules' / 'ws'
    if not ws_source.exists():
        ws_source = root / 'vendor' / 'ws'
    if ws_source.exists():
        shutil.copytree(ws_source, app / 'node_modules' / 'ws', dirs_exist_ok=True)

    note(62, 'Installing the core mod loader…')
    webroot_js = resources / 'webroot' / 'js'
    webroot_js.mkdir(parents=True, exist_ok=True)
    core_dir = root / 'core'
    if not core_dir.is_dir():
        raise ValueError('Missing core mod loader.')
    out = app / 'electron' / 'out'
    shutil.copyfile(core_dir / 'mod-catalog.cjs', out / 'hw-mod-catalog.js')
    shutil.copyfile(core_dir / 'mod-loader-main.cjs', out / 'hw-mod-loader.js')
    shutil.copyfile(core_dir / 'asset-map.cjs', out / 'asset-map.cjs')
    shutil.copyfile(core_dir / 'boot-list.cjs', out / 'boot-list.cjs')
    shutil.copyfile(core_dir / 'hw-mod-sdk.js', out / 'hw-mod-sdk.js')
    runtime = resources / 'mod-runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(core_dir / 'asset-override.js', runtime / 'asset-override.js')
    # Placeholder. The game's main process rewrites this on boot from the
    # enabled mods' web[] list (see core/boot-list.cjs).
    (webroot_js / 'hw-mod-boot.js').write_text(
        '// Replaced when Happy Wheels starts. Drop a folder into mods and restart the game.\n',
        encoding='utf-8',
    )

    note(78, 'Patching the game loader…')
    entry = out / 'main.js'
    main = entry.read_text(encoding='utf-8')
    before = '<script src="./js/dependencies.js">'
    boot = '<script src="./js/hw-mod-boot.js">'
    if main.count(before) != 1:
        raise ValueError('Unexpected HTML loader; refusing to patch this build.')
    if boot not in main:
        # Inject before the stock webpack bundle so HWMod exists when mods run.
        # The extra escaped slash is how the string actually appears in main.js.
        main = main.replace(before, boot + '<\\/script>' + before)
    if 'require("./hw-mod-loader.js")' not in main:
        main += '\nrequire("./hw-mod-loader.js");\n'
    entry.write_text(main, encoding='utf-8')
    preload = entry.with_name('preload.js')
    hook = (core_dir / 'mod-loader-preload.cjs').read_text(encoding='utf-8')
    transport_path = game / 'mods' / 'jimbobs-multiplayer' / 'electron' / 'transport-preload.cjs'
    if not transport_path.is_file():
        transport_path = root / 'mods' / 'jimbobs-multiplayer' / 'electron' / 'transport-preload.cjs'
    transport = transport_path.read_text(encoding='utf-8') if transport_path.is_file() else ''
    patch_game_preload(preload, hook, transport)

    note(88, 'Updating the Steam game files…')
    files = {p.relative_to(app).as_posix(): p.read_bytes() for p in app.rglob('*') if p.is_file()}
    blob = pack_asar({k: v for k, v in files.items() if not k.startswith('node_modules/steamworks.js/')})
    hs = struct.unpack_from('<I', blob, 4)[0]
    header = json.loads(blob[16:16 + struct.unpack_from('<I', blob, 12)[0]])
    original_blob = original.read_bytes()
    old_header = json.loads(original_blob[16:16 + struct.unpack_from('<I', original_blob, 12)[0]])
    header['files'].setdefault('node_modules', {'files': {}})['files']['steamworks.js'] = old_header['files']['node_modules']['files']['steamworks.js']
    raw = json.dumps(header, separators=(',', ':')).encode()
    pad = (-len(raw)) % 4
    pickle = struct.pack('<II', 4 + len(raw) + pad, len(raw)) + raw + b'\0' * pad
    packed.write_bytes(struct.pack('<II', 4, len(pickle)) + pickle + blob[8 + hs:])
    # Happy Wheels.exe embeds sha256 of the asar JSON header. Swap it or
    # the game opens to a blank window. Always start from the stock backup
    # so we don't chase a hash we wrote last time.
    exe = exe_backup.read_bytes()
    old_length = struct.unpack_from('<I', original_blob, 12)[0]
    old_hash = hashlib.sha256(original_blob[16:16 + old_length]).hexdigest().encode()
    new_hash = hashlib.sha256(raw).hexdigest().encode()
    if exe.count(old_hash) != 1:
        raise ValueError('Unexpected executable integrity resource.')
    (game / 'Happy Wheels.exe').write_bytes(exe.replace(old_hash, new_hash))
    if app.exists():
        shutil.rmtree(app)  # working copy; the game only reads app.asar
    (game / 'install.json').write_text(json.dumps({
        'gameVersion': GAME_VERSION,
        'launcherVersion': VERSION,
        'source': str(game),
        'inPlace': True,
        'dropInMods': True,
        'mods': [mod['id'] for mod in installed_mods],
    }, indent=2), encoding='utf-8')
    write_launcher(game)
    note(100, 'Install finished.')
    return game
