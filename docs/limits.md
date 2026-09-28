# Limits

- **Game version:** Steam Happy Wheels **1.99.2** only. A new game build needs a new launcher.
- **Legal copy:** The launcher patches files you already own. Do not redistribute the game.
- **Obfuscation:** Character classes, Pixi exports, and Box2D live behind minified webpack modules. Those IDs belong in `core/hw-mod-sdk.js`, not in your mod.
- **One tick bus:** Wrap `renderer.render` through `HWMod.on('tick')`. Do not add a second `world.Step`.
- **Physics:** No zero-mass dynamics, no double impulses. If Jimbob's Multiplayer Shared Physics is running, it owns stepping.
- **`web[]`:** Flat filenames only. No `web/lib/foo.js` in the array.
- **Silent Electron errors:** A broken `electronMain` is skipped. Check the main-process console if your bridge never appears.
- **Catalog:** Strangers cannot self-publish yet. [Ask on Discord](https://discord.gg/XcZePBgDBJ). Store ids are at most 48 characters; the runtime allows 63 after the first character.
- **Steam verify:** Restores stock files. Players run the launcher again.
