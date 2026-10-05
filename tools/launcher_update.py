"""Download and apply JHWML self-updates without extra windows.

Shipped EXEs poll:

  https://raw.githubusercontent.com/MathewRegier/jhwml/main/mod-store/launcher.json

If the version there is newer we download the zip (GitHub Release), then
hand off to a wscript that waits for this process to die, copies the new
EXE over ours, and relaunches. Windows will not let us overwrite our own
file while we're running.

HW_LAUNCHER_SKIP_UPDATE=1 and HW_LAUNCHER_DRY_RUN=1 are for tests.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
import zipfile

from launcher_version import EXE_NAME, LEGACY_EXE_NAME, NAME, VERSION
from mod_store import _read_url, _safe_extract, cache_dir, catalog_base, is_newer

DEFAULT_LAUNCHER_URL = 'https://raw.githubusercontent.com/MathewRegier/jhwml/main/mod-store/launcher.json'

# Keep the helper wscript off-screen. Old .bat version flashed a console.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008


def launcher_manifest_url(url: str | None = None) -> str:
    return url or os.environ.get('HW_LAUNCHER_UPDATE_URL') or DEFAULT_LAUNCHER_URL


def fetch_launcher_manifest(url: str | None = None) -> dict:
    data = json.loads(_read_url(url or launcher_manifest_url()).decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Launcher update catalog is invalid.')
    version = str(data.get('version') or '')
    file_name = str(data.get('file') or data.get('url') or '')
    if not version or not file_name:
        raise ValueError('Launcher update catalog is missing a version or file.')
    return {
        'version': version,
        'name': str(data.get('name') or NAME),
        'file': file_name,
        'sha256': str(data.get('sha256') or '').lower(),
        'notes': str(data.get('notes') or ''),
    }


def check_for_update(current_version: str = VERSION, catalog_url: str | None = None) -> dict | None:
    if os.environ.get('HW_LAUNCHER_SKIP_UPDATE'):
        return None
    try:
        info = fetch_launcher_manifest(launcher_manifest_url())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return None
    if is_newer(info['version'], current_version):
        return info
    return None


def extract_launcher_exe(blob: bytes, dest: pathlib.Path) -> pathlib.Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        zip_path = pathlib.Path(temp) / 'update.zip'
        zip_path.write_bytes(blob)
        unpacked = pathlib.Path(temp) / 'unpacked'
        with zipfile.ZipFile(zip_path) as archive:
            _safe_extract(archive, unpacked)
        candidates = [path for path in unpacked.rglob('*.exe') if path.is_file()]
        if not candidates:
            raise ValueError('The launcher update zip did not contain an EXE.')
        by_name = {path.name.lower(): path for path in candidates}
        # Prefer the current EXE name; fall back to the 0.1.x filename.
        chosen = by_name.get(EXE_NAME.lower()) or by_name.get(LEGACY_EXE_NAME.lower()) or candidates[0]
        target = dest / EXE_NAME
        target.write_bytes(chosen.read_bytes())
        return target


def download_update(info: dict, catalog_url: str | None = None, dest: pathlib.Path | None = None) -> pathlib.Path:
    file_name = info['file']
    # New manifests use a full GitHub Releases URL. Old ones were a path
    # next to launcher.json.
    url = file_name if file_name.startswith('https://') else catalog_base(launcher_manifest_url()) + file_name.lstrip('/')
    blob = _read_url(url)
    digest = hashlib.sha256(blob).hexdigest()
    if info.get('sha256') and digest != info['sha256']:
        raise ValueError('Downloaded launcher failed the checksum check.')
    folder = dest or (cache_dir() / 'updates' / str(info['version']))
    if folder.exists():
        for stale in folder.glob('*.exe'):
            stale.unlink()
    return extract_launcher_exe(blob, folder)


def write_replace_script(current_exe: pathlib.Path, new_exe: pathlib.Path, pid: int | None = None) -> pathlib.Path:
    # The VBS waits on our PID, copies via a .new staging file, then starts
    # the new EXE. Arguments: source, target, pid, oldpath.
    script = cache_dir() / 'updates' / 'apply-update.vbs'
    script.parent.mkdir(parents=True, exist_ok=True)
    old_bat = script.with_suffix('.bat')
    if old_bat.exists():
        old_bat.unlink()
    script.write_text(
        'Option Explicit\r\n'
        'Dim sh, fso, wmi, procs, source, target, oldpath, pid, folder, staged, backup, env\r\n'
        'Set sh = CreateObject("WScript.Shell")\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        'source = WScript.Arguments(0)\r\n'
        'target = WScript.Arguments(1)\r\n'
        'pid = WScript.Arguments(2)\r\n'
        'oldpath = WScript.Arguments(3)\r\n'
        'folder = fso.GetParentFolderName(target)\r\n'
        'staged = target & ".new"\r\n'
        'backup = target & ".old"\r\n'
        'Do\r\n'
        '  WScript.Sleep 800\r\n'
        '  Set wmi = GetObject("winmgmts:\\\\.\\root\\cimv2")\r\n'
        '  Set procs = wmi.ExecQuery("Select ProcessId From Win32_Process Where ProcessId=" & pid)\r\n'
        '  If procs.Count = 0 Then Exit Do\r\n'
        'Loop\r\n'
        'WScript.Sleep 1200\r\n'
        'On Error Resume Next\r\n'
        'If fso.FileExists(staged) Then fso.DeleteFile staged, True\r\n'
        'If fso.FileExists(backup) Then fso.DeleteFile backup, True\r\n'
        'Err.Clear\r\n'
        'fso.CopyFile source, staged, True\r\n'
        'If Err.Number <> 0 Then WScript.Quit 1\r\n'
        'If fso.GetFile(staged).Size <> fso.GetFile(source).Size Then WScript.Quit 2\r\n'
        'If fso.FileExists(target) Then fso.MoveFile target, backup\r\n'
        'Err.Clear\r\n'
        'fso.MoveFile staged, target\r\n'
        'If Err.Number <> 0 Then\r\n'
        '  Err.Clear\r\n'
        '  fso.CopyFile staged, target, True\r\n'
        'End If\r\n'
        'If Not fso.FileExists(target) Then WScript.Quit 3\r\n'
        'If fso.GetFile(target).Size <> fso.GetFile(source).Size Then WScript.Quit 4\r\n'
        'sh.CurrentDirectory = folder\r\n'
        'Set env = sh.Environment("PROCESS")\r\n'
        'env("PYINSTALLER_RESET_ENVIRONMENT") = "1"\r\n'
        'env.Remove "_PYI_ARCHIVE_FILE"\r\n'
        'env.Remove "_PYI_APPLICATION_HOME_DIR"\r\n'
        'env.Remove "_PYI_PARENT_PROCESS_LEVEL"\r\n'
        'env.Remove "_PYI_SPLASH_IPC"\r\n'
        'sh.Run """" & target & """", 1, False\r\n'
        'If StrComp(oldpath, target, 1) <> 0 And fso.FileExists(oldpath) Then fso.DeleteFile oldpath, True\r\n'
        'If fso.FileExists(backup) Then fso.DeleteFile backup, True\r\n'
        'If fso.FileExists(WScript.ScriptFullName) Then fso.DeleteFile WScript.ScriptFullName, True\r\n',
        encoding='utf-8',
    )
    return script


def _restart_environment() -> dict[str, str]:
    """Drop the running onefile folder so the replacement EXE starts clean."""
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('_PYI_'):
            env.pop(key, None)
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return env


def apply_and_restart(new_exe: pathlib.Path, current_exe: pathlib.Path | None = None) -> pathlib.Path:
    current = pathlib.Path(current_exe or sys.executable)
    new_exe = pathlib.Path(new_exe)
    if not new_exe.is_file():
        raise ValueError('The downloaded launcher EXE is missing.')
    target = current.with_name(EXE_NAME)
    script = write_replace_script(current, new_exe)
    if os.environ.get('HW_LAUNCHER_DRY_RUN'):
        return script  # tests inspect the VBS without spawning wscript
    windir = pathlib.Path(os.environ.get('WINDIR', r'C:\Windows'))
    wscript = windir / 'System32' / 'wscript.exe'
    if not wscript.is_file():
        wscript = windir / 'wscript.exe'
    startup = None
    creationflags = 0
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        creationflags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
    subprocess.Popen(
        [str(wscript), '//B', '//Nologo', str(script), str(new_exe), str(target), str(os.getpid()), str(current)],
        cwd=str(target.parent),
        env=_restart_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startup,
        creationflags=creationflags,
        close_fds=True,
    )
    os._exit(0)  # skip atexit; the VBS is watching this PID
