'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

const tools = path.join(__dirname, '..', 'tools');
const hook = fs.readFileSync(path.join(__dirname, '..', 'core', 'mod-loader-preload.cjs'), 'utf8');

function python(code) {
  const result = spawnSync('python', ['-c', code], {encoding: 'utf8', cwd: tools});
  if (result.status !== 0) throw Error(result.stderr || result.stdout || 'python failed');
  return result.stdout;
}

test('packager strips a baked hwGhostNet bridge and keeps a single mod-runtime hook', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hw-preload-'));
  const preload = path.join(dir, 'preload.js');
  const baked = `(()=>{"use strict";const e=require("electron");e.contextBridge.exposeInMainWorld("hwNative",{})})();\n(() => {\n  const {contextBridge,ipcRenderer}=require('electron');\n  contextBridge.exposeInMainWorld('hwGhostNet',{\n    connect:url=>ipcRenderer.invoke('ghost:connect',url)\n  });\n})();\n`;
  fs.writeFileSync(preload, baked);
  const hookPath = path.join(dir, 'hook.cjs');
  fs.writeFileSync(hookPath, hook);
  python(`from packager import patch_game_preload
from pathlib import Path
patch_game_preload(Path(${JSON.stringify(preload)}), Path(${JSON.stringify(hookPath)}).read_text(encoding='utf-8'))
print(Path(${JSON.stringify(preload)}).read_text(encoding='utf-8'))`);
  const out = fs.readFileSync(preload, 'utf8');
  assert.equal(out.includes('hwGhostNet'), false);
  assert.equal(out.includes('hwNative'), true);
  assert.equal(out.includes('mod-runtime'), true);
  assert.equal(out.split('mod-runtime').length - 1, 1);
});

test('packager inlines the current Steam bridge into the game preload', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hw-preload-'));
  const preload = path.join(dir, 'preload.js');
  fs.writeFileSync(preload, `(()=>{"use strict";const e=require("electron");e.contextBridge.exposeInMainWorld("hwNative",{})})();\n`);
  const hookPath = path.join(dir, 'hook.cjs');
  fs.writeFileSync(hookPath, hook);
  const transport = fs.readFileSync(path.join(__dirname, '..', 'mods', 'jimbobs-multiplayer', 'electron', 'transport-preload.cjs'), 'utf8');
  python(`from packager import patch_game_preload
from pathlib import Path
transport = Path(${JSON.stringify(path.join(__dirname, '..', 'mods', 'jimbobs-multiplayer', 'electron', 'transport-preload.cjs'))}).read_text(encoding='utf-8')
patch_game_preload(Path(${JSON.stringify(preload)}), Path(${JSON.stringify(hookPath)}).read_text(encoding='utf-8'), transport)
print(Path(${JSON.stringify(preload)}).read_text(encoding='utf-8'))`);
  const out = fs.readFileSync(preload, 'utf8');
  assert.equal(out.includes('hwNative'), true);
  assert.equal(out.includes('steamInvite'), true);
  assert.equal(out.includes('hwGhostSteam'), true);
  assert.equal(out.includes('mod-runtime'), true);
});
