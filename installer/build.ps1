$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..
python -c "import os, shutil, pathlib; src=pathlib.Path('mods'); dest=pathlib.Path(os.environ['TEMP'])/'jhwml-public-mods'; shutil.rmtree(dest, ignore_errors=True); dest.mkdir(parents=True); skip={'jimbobs-builder','jimbobs-level-cloner'};
[shutil.copytree(p, dest/p.name) if p.is_dir() else shutil.copy2(p, dest/p.name) for p in src.iterdir() if p.name not in skip and not p.name.startswith('.')]
print(dest)"
python -m pip install --disable-pip-version-check pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile --noupx --name "JHWML - Mod Launcher" `
  --icon installer\icon.ico `
  --paths tools `
  --hidden-import packager `
  --hidden-import mod_store `
  --hidden-import launcher_update `
  --hidden-import launcher_version `
  --add-data "core;core" `
  --add-data "$env:TEMP\jhwml-public-mods;mods" `
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
