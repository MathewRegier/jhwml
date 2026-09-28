# One-file windowed EXE. Run from anywhere; we cd to the repo root first.
# --noupx: Defender already side-eyes this enough without packing.
# --paths tools so `import packager` works without making tools a package.
# --add-data copies the loader, icons, and (optional) bundled mods into the
# PyInstaller temp extract. `mods` can be empty — the catalog is downloaded
# at runtime. node_modules\ws is for the multiplayer websocket client if
# that mod is selected at install time.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..
python -m pip install --disable-pip-version-check pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile --noupx --name "JHWML - Mod Launcher" `
  --icon installer\icon.ico `
  --paths tools `
  --hidden-import packager `
  --hidden-import mod_store `
  --hidden-import launcher_update `
  --hidden-import launcher_version `
  --add-data "core;core" `
  --add-data "mods;mods" `
  --add-data "tools\game-manifest.json;tools" `
  --add-data "tools\packager.py;tools" `
  --add-data "tools\mod_store.py;tools" `
  --add-data "tools\launcher_update.py;tools" `
  --add-data "tools\launcher_version.py;tools" `
  --add-data "installer\icon.ico;installer" `
  --add-data "installer\icon.png;installer" `
  --add-data "node_modules\ws;node_modules\ws" `
  installer\app.py
Write-Output "Built: $PWD\dist\JHWML - Mod Launcher.exe"
