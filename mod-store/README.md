Public Happy Wheels **mod** library.

The launcher reads **catalog.json** from:
https://raw.githubusercontent.com/MathewRegier/happy-wheels-ghost-relay/main/mod-store/catalog.json

Launcher **self-updates** come from the jhwml repo, not this catalog:
https://raw.githubusercontent.com/MathewRegier/jhwml/main/mod-store/launcher.json

How to make a mod (SDK, `mod.json`, `window.HWMod`): https://mathewregier.github.io/jhwml/

To publish a mod update, bump the version in the mod's mod.json, run `python tools/publish_mod_store.py`, then commit and push relay/mod-store.

To publish a new launcher EXE, bump `tools/launcher_version.py`, build, then run `python tools/publish_launcher.py`. That writes `launcher.json` for jhwml (GitHub Releases) and copies it to this relay folder so existing 0.2.2 EXEs can still find the update.
