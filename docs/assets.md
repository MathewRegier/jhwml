# Assets

Put files in `mods/<id>/assets/`. On each launch the loader copies them to:

- `resources/webroot/mod-assets/<id>/`
- `resources/webroot/js/<id>/assets/` (legacy path some mods still read)

The page gets:

```js
window.HW_MOD_ASSETS = [
  {id: 'my-mod', base: './mod-assets/my-mod/', files: ['animate/character9.png']}
];
```

Electron `webRequest` rewrites matching stock `assets-*` URLs to your copies when the file names line up. That is how a PNG overlay can replace a vanilla sheet without editing the asar.

`window.HW_MOD_CATALOG` lists `{id, name, web}` for enabled mods. `HWMod.mods` reads that list.

Do not put Happy Wheels game files inside a mod zip.
