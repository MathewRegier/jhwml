# Make a mod

Put a folder in `Happy Wheels\mods\` after the launcher has patched the game once. Restart Happy Wheels. The loader copies your files and injects your page scripts **before** the stock `dependencies.js`.

**New to this?** Walk through [Your first mod](first-mod.md). Copy [`examples/first-hw-mod`](https://github.com/MathewRegier/jhwml/tree/main/examples/first-hw-mod) and follow the `STEP` comments in `web/main.js`.

Already know the layout? Copy [`examples/hello-hw-mod`](https://github.com/MathewRegier/jhwml/tree/main/examples/hello-hw-mod) and change the `id`.

## Folder

```
Happy Wheels/mods/my-mod/
  mod.json
  web/
    main.js          # names listed in "web" — no slashes
  electron/          # optional
    main.cjs         # electronMain
    bridge.cjs       # electronPreload
  assets/            # optional PNG / atlas overrides
```

`web[]` entries are **basenames only**. Nested files can exist under `web/` (for example `web/characters/`) but they are not auto-loaded. Import them from a top-level script.

## `mod.json`

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | `a-z`, `0-9`, dashes. Runtime allows 63 characters after the first. The public catalog allows 48 total. Folder name is the fallback. |
| `name` | no | Display name, 64 characters |
| `author` | no | 64 characters |
| `description` | no | 240 characters |
| `version` | no | For the launcher catalog. The game loader does not read it. |
| `priority` | no | Default `100`. Lower runs first. |
| `enabled` | no | Default `true`. `false` skips the mod. |
| `web` | no | Page scripts, load order inside this mod |
| `electronMain` | no | Main-process script, relative path |
| `electronPreload` | no | Preload script, relative path |
| `hwmod` | no | Set to `"1"` if you use `window.HWMod`. The loader warns if the SDK file is missing. |

Example:

```json
{
  "id": "hello-hw-mod",
  "name": "Hello HWMod",
  "version": "1.0.0",
  "author": "you",
  "description": "Overlay that uses window.HWMod.",
  "enabled": true,
  "priority": 50,
  "hwmod": "1",
  "web": ["main.js"]
}
```

## Load order

1. `js/hw-mod-sdk.js` — creates `window.HWMod`
2. `js/hw-mod-assets.js` — `HW_MOD_ASSETS` and `HW_MOD_CATALOG`
3. Each enabled mod’s `web[]` scripts, sorted by `priority` then `id`

Wait for `HWMod.on('boot', …)` or `HWMod.on('session', …)` before touching the current level.

## Game hooks

Use [`window.HWMod`](api.md). Do not copy webpack module IDs out of other mods.

## Publishing

Local drop-in is enough to play. To appear in the public launcher catalog, ask Jimbob (Discord **jimbob1111**). Catalog zips still live on the relay repo.
