# Your first mod

This page builds a small **ride card** HUD with `window.HWMod`. The finished files live in [`examples/first-hw-mod`](https://github.com/MathewRegier/jhwml/tree/main/examples/first-hw-mod). You can copy that folder, or type it yourself as you read.

You need a legal Steam copy of Happy Wheels **1.99.2** and the JHWML launcher.

## What you will make

A red stamp in the top-left of the game:

- **MENU** on the main screen
- **RIDING** after you start a level
- **DEAD** / **FINISHED** when those happen
- attempt number, death count, and camera position

It never steps physics and never uses webpack module numbers. That is the point of the SDK.

---

## STEP 1 — Patch the game once

Close Happy Wheels. Run **JHWML - Mod Launcher** and install. That injects the loader and `js/hw-mod-sdk.js`.

A Steam **Verify integrity of game files** removes the loader. Run the launcher again after that.

You do not rebuild the launcher to try a mod.

## STEP 2 — Make a folder

Create:

```
Happy Wheels/mods/first-hw-mod/
  mod.json
  web/
    main.js
```

The folder name should match the `id` you put in `mod.json`. Drop the folder in `mods` after the launcher has patched the game at least once.

## STEP 3 — Write `mod.json`

```json
{
  "id": "first-hw-mod",
  "name": "First HWMod",
  "version": "1.0.0",
  "author": "you",
  "description": "Ride card HUD that teaches window.HWMod.",
  "enabled": true,
  "priority": 40,
  "hwmod": "1",
  "web": ["main.js"]
}
```

| Field | Why it is here |
| --- | --- |
| `id` | Unique. Lowercase letters, numbers, dashes. Two mods cannot share one. |
| `web` | Page scripts, **basenames only** — write `main.js`, not `web/main.js`. |
| `hwmod` | `"1"` means you use `window.HWMod`. The loader warns if the SDK file is missing. |
| `priority` | Lower runs first. Default is `100`. |
| `enabled` | `false` skips the mod without deleting it. |

No Electron files are required for a HUD.

## STEP 4 — Grab `window.HWMod`

The loader runs scripts in this order:

1. `js/hw-mod-sdk.js` → creates `window.HWMod`
2. `js/hw-mod-assets.js`
3. Each mod’s `web[]` list

So `main.js` can read `HWMod` on the first line. Still check it:

```js
var hw = window.HWMod;
if (!hw) {
  console.warn('[first-hw-mod] window.HWMod is missing. Run a current JHWML launcher.');
  return;
}
```

Open the game with DevTools if you want: that warning means the installed launcher is older than the SDK.

## STEP 5 — Draw a HUD

Happy Wheels is a web page. `document.createElement` is enough. Set `pointer-events: none` so the overlay does not eat clicks.

See `web/main.js` in the example for the stamp layout. Keep UI on the DOM. Do not inject Pixi objects unless you know you need them.

## STEP 6 — Listen to events

```js
hw.on('boot', function () { /* webpack require is up */ });
hw.on('menu', function () { /* main menu / no playable session */ });
hw.on('session', function (session) { /* a real level with a world */ });
hw.on('character', function (character) { /* rider exists or was replaced */ });
hw.on('tick', function (info) { /* after the game draws a frame */ });
hw.on('restart', function (session) { /* iteration went backwards */ });
hw.on('death', function (character) { /* character.dead became true */ });
hw.on('finish', function (session) { /* replayData.completed became true */ });
```

Wait for `boot` or `session` before you assume a level exists. On `menu`, clear per-level state (this example resets the death count).

## STEP 7 — Read the rider on `tick`

`tick` payload is `{ session, character, world }`. You can also call the getters:

```js
hw.session()     // currentSession, or null
hw.character()   // session.character, or null
hw.world()       // session.m_world, or null
```

The example reads `session.iteration` and `character.cameraFocus.GetWorldCenter()` (Box2D meters). Wrap native calls in `try/catch`. Those objects disappear on death and menu.

**Do not** call `world.Step`. The game already stepped. If Jimbob's Multiplayer Shared Physics is on, it owns stepping too.

## STEP 8 — Count deaths, do not fake physics

```js
hw.on('death', function () {
  deaths += 1;
});
hw.on('restart', function () {
  deaths = 0;
});
```

Rules that keep mods from fighting:

- No second `world.Step`
- No zero-mass dynamic bodies
- No double impulses
- Prefer reading on `tick`, or one force if you must push

Webpack module numbers stay inside `core/hw-mod-sdk.js`. If you need a new hook, ask on Discord instead of copying IDs from another mod.

## STEP 9 — Restart the game

Close Happy Wheels fully (not just the level). Launch it from Steam.

You should see **RIDE CARD** immediately. Open any level: it should switch to **RIDING**, then **DEAD** when you explode.

If nothing appears:

1. Folder path is `Happy Wheels\mods\first-hw-mod\mod.json` (not `mods\mods\...`).
2. `id` matches the folder name.
3. You ran a launcher that includes the SDK, then fully restarted the game.
4. Console has `[first-hw-mod]` or `[HWMod]` logs.

## STEP 10 — Make it yours

1. Copy the folder.
2. Change `id` (and the folder name) to something unique, like `my-ride-card`.
3. Change the `#first-hw-mod` element id in `main.js` so two copies do not clash.
4. Add your own `tick` logic.

Full API: [`window.HWMod`](api.md). Folder contract: [Make a mod](make-a-mod.md). Limits: [Limits](limits.md).
