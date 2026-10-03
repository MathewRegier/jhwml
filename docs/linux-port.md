#!/usr/bin/env python3
"""Linux installer for Happy Wheels 1.99.2.

This script mirrors the Windows JHWML ASAR patching workflow, but skips the
Windows-only EXE hash rewriting and Steam registry detection used on Windows.
It targets the Linux Steam installation layout used by the native port, which
launches from a root folder containing `start.bash` and a `game/` subdirectory.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import struct
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"


def looks_like_game(path: pathlib.Path) -> bool:
    if not path or not path.exists():
        return False
    root_ok = (path / "start.bash").is_file() and (path / "game").is_dir()
    resources_ok = (path / "resources" / "app.asar").is_file() or (path / "game" / "resources" / "app.asar").is_file()
    return root_ok and resources_ok


def find_game_root() -> pathlib.Path | None:
    candidates = []
    home = pathlib.Path.home()
    for base in (
        home / ".steam" / "steam" / "steamapps" / "common",
        home / ".local" / "share" / "Steam" / "steamapps" / "common",
        pathlib.Path("/mnt/games/Steam/steamapps/common"),
        pathlib.Path("/var/lib/steam/steamapps/common"),
        pathlib.Path("/opt/steam/steamapps/common"),
    ):
        if base.exists():
            candidates.append(base)
    seen: set[str] = set()
    for root in candidates:
        for candidate in sorted(root.glob("Happy Wheels")):
            key = str(candidate.resolve())
            if key not in seen and looks_like_game(candidate):
                seen.add(key)
                return candidate
    for root in (home / ".steam" / "steam" / "steamapps" / "common",
                 home / ".local" / "share" / "Steam" / "steamapps" / "common"):
        if root.exists():
            for candidate in sorted(root.glob("*Happy*Wheels*")):
                key = str(candidate.resolve())
                if key not in seen and looks_like_game(candidate):
                    seen.add(key)
                    return candidate
    return None


def resolve_app_asar(game_root: pathlib.Path) -> pathlib.Path:
    candidates = (
        game_root / "resources" / "app.asar",
        game_root / "game" / "resources" / "app.asar",
        game_root / "game" / "app.asar",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Could not find app.asar under {game_root}")


def unpack_asar(blob: bytes) -> dict[str, bytes]:
    size = struct.unpack_from("<I", blob, 4)[0]
    length = struct.unpack_from("<I", blob, 12)[0]
    header = json.loads(blob[16 : 16 + length])
    result: dict[str, bytes] = {}

    def walk(files, prefix=""):
        for name, item in files.items():
            path = prefix + name
            if "files" in item:
                walk(item["files"], path + "/")
            elif not item.get("unpacked"):
                start = 8 + size + int(item["offset"])
                result[path] = blob[start : start + item["size"]]

    walk(header["files"])
    return result


def pack_asar(files: dict[str, bytes]) -> bytes:
    tree = {"files": {}}
    body = bytearray()
    for name, content in files.items():
        directory = tree["files"]
        parts = name.split("/")
        for part in parts[:-1]:
            directory = directory.setdefault(part, {"files": {}})["files"]
        block = 4194304
        directory[parts[-1]] = {
            "size": len(content),
            "offset": str(len(body)),
            "integrity": {
                "algorithm": "SHA256",
                "hash": __import__("hashlib").sha256(content).hexdigest(),
                "blockSize": block,
                "blocks": [__import__("hashlib").sha256(content[i : i + block]).hexdigest() for i in range(0, len(content), block)],
            },
        }
        body.extend(content)
    header = json.dumps(tree, separators=(",", ":")).encode()
    padding = (-len(header)) % 4
    pickle = struct.pack("<II", 4 + len(header) + padding, len(header)) + header + b"\0" * padding
    return struct.pack("<II", 4, len(pickle)) + pickle + bytes(body)


def copy_tree(src: pathlib.Path, dst: pathlib.Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            copy_tree(item, target)
        else:
            shutil.copy2(item, target)


def write_runtime_files(root: pathlib.Path, catalog: list[str]) -> None:
    # Keep the mod runtime layout consistent with the Windows loader.
    runtime_dir = root / "resources" / "mod-runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    preload_file = runtime_dir / "preload.cjs"
    preload_file.write_text("void 0;\n", encoding="utf-8")

    webroot_js = root / "resources" / "webroot" / "js"
    webroot_js.mkdir(parents=True, exist_ok=True)
    (webroot_js / "hw-mod-assets.js").write_text(
        "window.HW_MOD_ASSETS=[];\nwindow.HW_MOD_CATALOG=" + json.dumps(catalog) + ";\n",
        encoding="utf-8",
    )


def patch_asar(app_asar: pathlib.Path) -> None:
    payload = app_asar.read_bytes()
    files = unpack_asar(payload)
    if "electron/out/main.js" not in files:
        raise ValueError(f"{app_asar} does not look like a Happy Wheels Electron app.asar")

    main_path = "electron/out/main.js"
    preload_path = "electron/out/preload.js"
    boot_script = 'window.HWMod = window.HWMod || {};\n'

    main = files[main_path].decode("utf-8", errors="replace")
    preload = files[preload_path].decode("utf-8", errors="replace")

    if "require(\"./hw-mod-loader.js\")" not in main and "require('./hw-mod-loader.js')" not in main:
        main = main + "\nrequire(\"./hw-mod-loader.js\");\n"
    if '<script src="./js/hw-mod-boot.js">' not in main and '<script src="./js/hw-mod-boot.js"><\\/script>' not in main:
        before = '<script src="./js/dependencies.js">'
        if before in main:
            main = main.replace(before, '<script src="./js/hw-mod-boot.js"><\\/script>' + before)

    if "mod-runtime/preload.cjs" not in preload:
        preload = "(() => {\n  try {\n    require(require('path').join(process.resourcesPath, 'mod-runtime', 'preload.cjs'));\n  } catch (e) {}\n})();\n" + preload

    files[main_path] = main.encode("utf-8")
    files[preload_path] = preload.encode("utf-8")

    loader_file = CORE_DIR / "mod-loader-main.cjs"
    if not loader_file.exists():
        raise FileNotFoundError("Missing core/mod-loader-main.cjs in the project root")
    files["electron/out/hw-mod-loader.js"] = loader_file.read_bytes()
    files["electron/out/hw-mod-sdk.js"] = (CORE_DIR / "hw-mod-sdk.js").read_bytes()
    files["electron/out/hw-mod-boot.js"] = b"window.HW_MOD_CATALOG=[];\n"

    # Keep the mod runtime directory in sync with the loader contract.
    files["mod-runtime/preload.cjs"] = b"void 0;\n"
    files["mod-runtime/mods.json"] = b"[]\n"

    patched = pack_asar(files)
    app_asar.write_bytes(patched)


def install_linux(game_root: pathlib.Path | None = None, force: bool = False) -> pathlib.Path:
    if game_root is None:
        game_root = find_game_root()
    if game_root is None:
        raise FileNotFoundError("Could not locate the Happy Wheels Linux game folder.")
    if not looks_like_game(game_root):
        raise ValueError(f"{game_root} does not look like the Linux Happy Wheels install.")

    app_asar = resolve_app_asar(game_root)
    backup = app_asar.with_suffix(app_asar.suffix + ".bak")
    if backup.exists() and not force:
        raise FileExistsError(f"Backup already exists: {backup}. Use --force to overwrite it.")

    # Preserve the stock archive before patching.
    shutil.copy2(app_asar, backup)
    patch_asar(app_asar)

    mods_dir = game_root / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "README.txt").write_text(
        "Drop a mod folder here. Restart the game after installing or updating a mod.\n",
        encoding="utf-8",
    )

    write_runtime_files(game_root, [])
    return game_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch the Linux Happy Wheels app.asar with the JHWML loader")
    parser.add_argument("path", nargs="?", type=pathlib.Path, help="Path to the Happy Wheels installation folder")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing .bak backup")
    args = parser.parse_args()

    try:
        game_root = args.path.resolve() if args.path else find_game_root()
        if game_root is None:
            raise FileNotFoundError("Could not find Happy Wheels.")
        installed = install_linux(game_root, force=args.force)
        print(f"Patched Linux Happy Wheels install at: {installed}")
        print(f"Backup saved at: {resolve_app_asar(installed).with_suffix('.asar.bak')}")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# Notes for future work:
# - Use the same mod catalog code as the Windows launcher once the Linux mod store is added.
# - The current patch is intentionally minimal and only preserves the Electron bootstrap injection path.
# - A follow-up patch can add a Linux launcher UI and mod catalog over the existing repository logic.


""" ,{"content":"# Linux port status

This directory documents the Linux patch path for the native Happy Wheels port.

## What this adds

The repository now includes a minimal Linux patcher at `tools/linux_patch.py` which:

- locates the Steam-native Happy Wheels folder,
- finds `resources/app.asar`,
- patches the Electron bootstrap to inject the JHWML loader,
- writes a backup before patching, and
- creates a `mods/` directory for future drops.

## How to run

```bash
python3 tools/linux_patch.py \
  /home/brenardo/.steam/steam/steamapps/common/Happy\ Wheels
```

Or simply:

```bash
python3 tools/linux_patch.py
```

## Notes

This is intentionally scoped to the Linux-native app architecture: it avoids the
Windows-only EXE integrity rewrite, registry detection, and admin checks used by
`tools/packager.py` on Windows.

The goal is to keep the same Electron bootstrap injection mechanism while
adapting the install logic to the Linux filesystem layout.
"""}]}