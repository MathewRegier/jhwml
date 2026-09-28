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

Webpack module numbers stay inside `core/hw-mod-sdk.js`. If you need a new hook, [ask on Discord](https://discord.gg/XcZePBgDBJ) instead of copying IDs from another mod.

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

---

## Full `web/main.js`

This is the whole script from [`examples/first-hw-mod/web/main.js`](https://github.com/MathewRegier/jhwml/blob/main/examples/first-hw-mod/web/main.js). Paste it into `web/main.js` after you write `mod.json`.

```js
// First HWMod — ride card HUD.
// Tutorial: https://mathewregier.github.io/jhwml/first-mod.html
// Each STEP below is a heading in that page. Read this file top to bottom.

(function () {
  'use strict';

  // STEP 4 — The loader injects hw-mod-sdk.js before this file.
  // If HWMod is missing, the launcher that patched the game is too old.
  var hw = window.HWMod;
  if (!hw) {
    console.warn('[first-hw-mod] window.HWMod is missing. Run a current JHWML launcher, then restart the game.');
    return;
  }

  // STEP 5 — Happy Wheels is a normal web page inside Electron.
  // A DOM overlay is the simplest UI. pointer-events:none so clicks still hit the game.
  var card = document.createElement('div');
  card.id = 'first-hw-mod';
  card.style.cssText = [
    'position:fixed',
    'top:10px',
    'left:10px',
    'z-index:20000',
    'width:196px',
    'pointer-events:none',
    'font:700 12px "Trebuchet MS",Tahoma,sans-serif',
    'color:#f4ead4',
    'background:#1a1208',
    'border:3px solid #111',
    'box-shadow:4px 4px 0 #000',
  ].join(';');
  card.innerHTML =
    '<div style="background:#c41200;color:#fff;padding:5px 8px;letter-spacing:.08em;">RIDE CARD</div>' +
    '<div id="first-hw-mod-body" style="padding:8px;line-height:1.45;"></div>';
  document.documentElement.appendChild(card);
  var body = card.querySelector('#first-hw-mod-body');

  var deaths = 0;
  var phase = 'MENU';

  function setBody(html) {
    body.innerHTML = html;
  }

  function paint(extra) {
    setBody(
      '<div>' + phase + '</div>' +
      '<div>attempt ' + extra.attempt + '</div>' +
      '<div>deaths ' + deaths + '</div>' +
      '<div>' + extra.pos + '</div>' +
      '<div style="margin-top:6px;font-weight:400;opacity:.75;">HWMod ' + hw.version + ' · ' + hw.game + '</div>'
    );
  }

  function cameraLine(character) {
    try {
      var focus = character && character.cameraFocus;
      var point = focus && ((focus.GetWorldCenter && focus.GetWorldCenter()) || (focus.GetPosition && focus.GetPosition()));
      if (point && typeof point.x === 'number') {
        return 'x ' + point.x.toFixed(1) + '  y ' + point.y.toFixed(1);
      }
    } catch (err) {}
    return 'x —  y —';
  }

  function attemptNumber(session) {
    if (session && typeof session.iteration === 'number') return String(session.iteration);
    return '—';
  }

  // STEP 6 — Subscribe to named events. Do not scan webpack yourself.
  hw.on('boot', function () {
    hw.log('first-hw-mod boot', hw.version, hw.game);
    phase = 'BOOT';
    paint({attempt: '—', pos: 'waiting for a session'});
  });

  hw.on('menu', function () {
    phase = 'MENU';
    deaths = 0;
    paint({attempt: '—', pos: 'open a level'});
  });

  hw.on('session', function (session) {
    phase = 'RIDING';
    deaths = 0;
    paint({attempt: attemptNumber(session), pos: cameraLine(hw.character())});
  });

  hw.on('character', function () {
    if (phase === 'MENU') return;
    phase = 'RIDING';
  });

  hw.on('restart', function (session) {
    phase = 'RIDING';
    deaths = 0;
    paint({attempt: attemptNumber(session), pos: cameraLine(hw.character())});
  });

  hw.on('death', function () {
    deaths += 1;
    phase = 'DEAD';
  });

  hw.on('finish', function () {
    phase = 'FINISHED';
  });

  // STEP 7 — tick fires after the game draws a frame.
  // Read bodies here. Do not call world.Step — the game (or Shared Physics) already did.
  hw.on('tick', function (info) {
    var session = info.session || hw.session();
    if (!session || session.isMenu) {
      if (phase !== 'MENU') {
        phase = 'MENU';
        deaths = 0;
      }
      paint({attempt: '—', pos: 'open a level'});
      return;
    }
    var character = info.character || hw.character();
    if (phase !== 'DEAD' && phase !== 'FINISHED') phase = 'RIDING';
    paint({
      attempt: attemptNumber(session),
      pos: cameraLine(character),
    });
  });
})();
```
