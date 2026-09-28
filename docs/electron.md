# Electron main and preload

Optional `mod.json` fields:

```json
{
  "electronMain": "electron/main.cjs",
  "electronPreload": "electron/preload.cjs"
}
```

Paths are relative to the mod folder. `..` and absolute paths are rejected.

## Main (`electronMain`)

Runs in the Happy Wheels **main process** when the game starts. Errors are swallowed so one mod cannot block the rest. Register IPC handlers here.

The page URL is `https://totaljerkface.com/__hw_app__/`. Check `event.senderFrame.url` (or `event.sender.getURL()`) before handling a call.

## Preload (`electronPreload`)

Loaded through the core `mod-runtime/preload.cjs` chain. Use `contextBridge.exposeInMainWorld` for a **unique** name. Do not reuse `hwGhostNet`, `hwGhostSteam`, or `hwCharacterCreator`.

```js
const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('myModBridge', {
  ping: () => ipcRenderer.invoke('my-mod:ping'),
});
```

`contextBridge` freezes the name. A second `exposeInMainWorld` with the same key throws.

The official game preload is sandboxed. Nested `require` of files outside the asar often fails there. Keep your preload small and next to the mod folder; the loader `require`s it from disk.
