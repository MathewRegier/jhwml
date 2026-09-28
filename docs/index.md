# JHWML

A Windows launcher and **mod framework** for Steam **Happy Wheels 1.99.2**.

Created by Jimbob · Discord **jimbob1111**

You need a legal Steam copy of the game. This project never ships Happy Wheels, `Happy Wheels.exe`, or `app.asar`.

- [Install (players)](install-for-players.md)
- [Your first mod](first-mod.md) — step-by-step HUD with `window.HWMod`
- [Make a mod](make-a-mod.md)
- [`window.HWMod` API](api.md)
- [Electron main and preload](electron.md)
- [Assets](assets.md)
- [Limits](limits.md)

The public source for the launcher and SDK is **[github.com/MathewRegier/jhwml](https://github.com/MathewRegier/jhwml)**. The multiplayer relay and the download catalog stay on [happy-wheels-ghost-relay](https://github.com/MathewRegier/happy-wheels-ghost-relay).

Happy Wheels internals are obfuscated and **locked to Steam 1.99.2**. A game update needs a new launcher. Other mods should use `window.HWMod`, not webpack module numbers.
