# JHWML - Mod Launcher

A desktop installer for friends who do not have Python or Node. It patches Happy Wheels once with a core mod loader and can seed **Jimbob's Multiplayer Mod**. After that, drop a folder into `mods` and restart the game. A Steam update or “Verify files” can remove the loader; run the installer again only then.

Other developers: [docs/index.md](../docs/index.md). Public launcher repo: [github.com/MathewRegier/jhwml](https://github.com/MathewRegier/jhwml).

## Build the .exe

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

The exe is written to:

`dist\JHWML - Mod Launcher.exe`

Send that one file. It is self-contained. The first launch can take a few seconds while it unpacks.

## What friends do

1. Keep Steam and Happy Wheels 1.99 installed. Close the game first.
2. Double-click **JHWML - Mod Launcher**. If install fails on permissions, right-click and run as administrator.
3. Confirm the Steam game folder (browse if it was not found).
4. Check **Jimbob's Multiplayer Mod**.
5. Install, then Play from the launcher or from Steam. Steam should stay running.
6. Later mod updates: replace the folder in `Happy Wheels\mods` and restart the game. You do not need a new launcher.
