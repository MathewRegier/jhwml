'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {app, session} = require('electron');
const {gameRoot, loadCatalog} = require('./hw-mod-catalog.js');
const {packIndex, replacementUrl} = require('./asset-map.cjs');
const {buildWebScripts} = require('./boot-list.cjs');

function copyTree(from, to) {
  fs.mkdirSync(to, {recursive: true});
  for (const item of fs.readdirSync(from, {withFileTypes: true})) {
    const src = path.join(from, item.name);
    const dest = path.join(to, item.name);
    if (item.isDirectory()) copyTree(src, dest);
    else if (item.isFile()) fs.copyFileSync(src, dest);
  }
}

function writeCharacterIndex(dir) {
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) return;
  const ids = [];
  for (const item of fs.readdirSync(dir, {withFileTypes: true})) {
    if (!item.isDirectory()) continue;
    if (!/^[a-z0-9][a-z0-9-]*$/i.test(item.name)) continue;
    const json = path.join(dir, item.name, 'character.json');
    if (fs.existsSync(json)) ids.push(item.name);
  }
  ids.sort((a, b) => a.localeCompare(b));
  fs.writeFileSync(path.join(dir, 'index.json'), JSON.stringify({characters: ids}, null, 2));
}

function listAssets(dir) {
  const files = [];
  const walk = (folder, prefix) => {
    for (const item of fs.readdirSync(folder, {withFileTypes: true})) {
      if (item.name === '.gitkeep' || item.name === '.DS_Store') continue;
      const rel = prefix ? `${prefix}/${item.name}` : item.name;
      if (rel.includes('..') || rel.includes('\\')) continue;
      const full = path.join(folder, item.name);
      if (item.isDirectory()) walk(full, rel);
      else if (item.isFile()) files.push(rel.replace(/\\/g, '/'));
    }
  };
  walk(dir, '');
  return files;
}

let assetIndex = new Map();
let assetRedirectInstalled = false;

function installAssetRedirect(packs) {
  assetIndex = packIndex(packs);
  if (assetRedirectInstalled) return;
  const attach = (browserSession) => {
    if (!browserSession || assetRedirectInstalled) return;
    assetRedirectInstalled = true;
    browserSession.webRequest.onBeforeRequest({urls: ['<all_urls>']}, (details, callback) => {
      try {
        const next = replacementUrl(details.url, assetIndex);
        callback(next ? {redirectURL: next} : {});
      } catch {
        callback({});
      }
    });
  };
  try {
    if (session.defaultSession) attach(session.defaultSession);
    else app.whenReady().then(() => attach(session.defaultSession));
  } catch {
    // The page still loads the original game files if the session is unavailable.
  }
}

function syncMods() {
  const root = gameRoot();
  const catalog = loadCatalog(path.join(root, 'mods'));
  const webrootJs = path.join(root, 'resources', 'webroot', 'js');
  const runtime = path.join(root, 'resources', 'mod-runtime');
  fs.mkdirSync(webrootJs, {recursive: true});
  fs.mkdirSync(runtime, {recursive: true});

  const preloadBits = [];
  const mains = [];
  const preloads = [];
  const assetPacks = [];
  for (const mod of catalog) {
    if (mod.electronMain) {
      const file = path.join(mod.dir, mod.electronMain);
      if (fs.existsSync(file)) mains.push(file);
    }
    if (mod.electronPreload) {
      const file = path.join(mod.dir, mod.electronPreload);
      if (fs.existsSync(file)) {
        preloads.push(file);
        preloadBits.push(`try{require(${JSON.stringify(file)});}catch(e){}`);
      }
    }
  }
  fs.writeFileSync(path.join(runtime, 'preload.cjs'), preloadBits.join('\n') || 'void 0;\n', 'utf8');
  function applyPreloads() {
    try {
      const current = session.defaultSession.getPreloads();
      session.defaultSession.setPreloads([...new Set([...current, ...preloads])]);
    } catch {}
  }
  if (app.isReady()) applyPreloads();
  else app.whenReady().then(applyPreloads);
  for (const file of mains) {
    try { require(file); } catch {}
  }

  const webroot = path.join(root, 'resources', 'webroot');
  const assetRoot = path.join(webroot, 'mod-assets');
  fs.rmSync(assetRoot, {recursive: true, force: true});
  fs.mkdirSync(assetRoot, {recursive: true});
  for (const mod of catalog) {
    const dest = path.join(webrootJs, mod.id);
    fs.rmSync(dest, {recursive: true, force: true});
    const web = path.join(mod.dir, 'web');
    if (fs.existsSync(web) && fs.statSync(web).isDirectory()) {
      copyTree(web, dest);
      writeCharacterIndex(path.join(dest, 'characters'));
    }
    const assets = path.join(mod.dir, 'assets');
    if (fs.existsSync(assets) && fs.statSync(assets).isDirectory()) {
      const files = listAssets(assets);
      if (files.length) {
        copyTree(assets, path.join(assetRoot, mod.id));
        copyTree(assets, path.join(dest, 'assets'));
        assetPacks.push({id: mod.id, base: `./mod-assets/${mod.id}/`, files});
      }
    }
  }

  const sdkSrc = path.join(__dirname, 'hw-mod-sdk.js');
  const sdkDest = path.join(webrootJs, 'hw-mod-sdk.js');
  if (fs.existsSync(sdkSrc)) fs.copyFileSync(sdkSrc, sdkDest);
  else if (catalog.some((mod) => mod.hwmod) && !fs.existsSync(sdkDest)) {
    try {
      fs.writeFileSync(path.join(runtime, 'sdk-missing.txt'), 'A mod asked for HWMod but hw-mod-sdk.js was not next to the loader.\n');
    } catch {}
  }

  installAssetRedirect(assetPacks);
  fs.writeFileSync(
    path.join(webrootJs, 'hw-mod-assets.js'),
    `window.HW_MOD_ASSETS=${JSON.stringify(assetPacks)};\nwindow.HW_MOD_CATALOG=${JSON.stringify(catalog.map((mod) => ({id: mod.id, name: mod.name, web: mod.web})))};\n`,
    'utf8',
  );
  try {
    fs.rmSync(path.join(webrootJs, 'hw-asset-override.js'), {force: true});
  } catch {
    // An older page script is unused once the boot list is rewritten below.
  }
  const scripts = buildWebScripts(catalog);
  fs.writeFileSync(
    path.join(webrootJs, 'hw-mod-boot.js'),
    `(function(){${JSON.stringify(scripts)}.forEach(function(src){document.write('<script src="./'+src+'"><\\/script>');});})();\n`,
    'utf8',
  );
  fs.writeFileSync(path.join(runtime, 'mods.json'), JSON.stringify(catalog.map((mod) => ({id: mod.id, name: mod.name, web: mod.web})), null, 2));
  return catalog;
}

syncMods();
module.exports = {syncMods};
