# First HWMod

A small **ride card** overlay. It is the worked example for the SDK tutorial.

**Walk through it here:** [https://mathewregier.github.io/jhwml/first-mod.html](https://mathewregier.github.io/jhwml/first-mod.html)

## Try it

1. Run **JHWML - Mod Launcher** once so the game has the loader and `window.HWMod`.
2. Close Happy Wheels.
3. Copy this whole folder to:

   `Steam\steamapps\common\Happy Wheels\mods\first-hw-mod\`

4. Launch Happy Wheels from Steam. A red ride card appears in the top-left.
5. Open a level. The card switches from MENU to RIDING, then DEAD / FINISHED as you play.

Then open `web/main.js`. Every `STEP` comment matches a heading in the tutorial.

When you make your own mod, change the `id` in `mod.json` and rename the folder to match. Two mods cannot share an `id`.
