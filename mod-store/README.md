Launcher self-updates for JHWML.

Shipped EXEs read **launcher.json** from:
https://raw.githubusercontent.com/MathewRegier/jhwml/main/mod-store/launcher.json

The zip URL in that file should be a **GitHub Release** on this repo.

How to make a mod (SDK, `mod.json`, `window.HWMod`): https://mathewregier.github.io/jhwml/

To publish a new launcher EXE, bump `tools/launcher_version.py`, build, then run `python tools/publish_launcher.py`. Commit `launcher.json` and create a GitHub Release.

Help: https://discord.gg/XcZePBgDBJ
