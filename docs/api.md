# `window.HWMod`

Stable page API for Steam Happy Wheels **1.99.2-s**. The SDK is injected before every mod script.

Walkthrough: [Your first mod](first-mod.md). Working files: [`examples/first-hw-mod`](https://github.com/MathewRegier/jhwml/tree/main/examples/first-hw-mod).

```js
HWMod.version          // SDK version string, currently '1.0.0'
HWMod.game             // '1.99.2-s'
HWMod.mods             // [{id, name, web}, ...] from the loader
HWMod.on(event, fn)    // boot, session, menu, character, tick, restart, death, finish
HWMod.off(event, fn)
HWMod.session()        // currentSession or null
HWMod.character()      // session.character or null
HWMod.world()          // session.m_world or null
HWMod.controller()     // {happyWheels, sessionController} or null
HWMod.pixi()           // {Container, Sprite, Texture, Graphics, TextureCache, raw} or null
HWMod.wrap(obj, name, fn)
HWMod.log(...)
```

`fn` for `wrap` is `function (original, args) { return original.apply(this, args); }`.

## Events

| Event | When |
| --- | --- |
| `boot` | Webpack `require` and the Pixi renderer are up |
| `session` | A playable session with `m_world` or `containerSprite` (not menu / editor test) |
| `menu` | The current session is the menu or missing |
| `character` | `session.character` is set or replaced |
| `tick` | After the game renderer draws a frame. **Do not call `world.Step`.** |
| `restart` | `session.iteration` went backwards |
| `death` | `character.dead` became true |
| `finish` | `replayData.completed` became true |

```js
HWMod.on('session', function (session) {
  HWMod.log('playing', session);
});

HWMod.on('tick', function (info) {
  var world = info.world;
  if (!world) return;
  // Read bodies. Do not step the world.
});
```

## Physics

One tick bus. Shared Physics (Jimbob's Multiplayer) already owns `run30fps` / `Step` when that mod is on.

- Do not call `m_world.Step`
- Do not create zero-mass dynamic bodies
- Do not apply the same impulse twice
- Prefer reading bodies or applying a force on `tick`

## What stays inside the SDK

Numeric webpack IDs, minified Pixi export names, and the `Tmu*` chunk inject. If you need a new hook, [ask on Discord](https://discord.gg/XcZePBgDBJ) rather than copying IDs from `ghost.js`.
