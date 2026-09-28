const test = require('node:test');
const assert = require('node:assert/strict');
const {buildWebScripts} = require('../core/boot-list.cjs');

test('boot list puts the SDK first, then assets, then each mod web script', () => {
  assert.deepEqual(
    buildWebScripts([
      {id: 'hello-hw-mod', web: ['main.js']},
      {id: 'other', web: ['a.js', 'b.js']},
    ]),
    [
      'js/hw-mod-sdk.js',
      'js/hw-mod-assets.js',
      'js/hello-hw-mod/main.js',
      'js/other/a.js',
      'js/other/b.js',
    ],
  );
});

test('boot list still injects the SDK with an empty catalog', () => {
  assert.deepEqual(buildWebScripts([]), ['js/hw-mod-sdk.js', 'js/hw-mod-assets.js']);
});
