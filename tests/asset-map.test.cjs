'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {packIndex, replacementUrl} = require('../core/asset-map.cjs');

const page = 'https://totaljerkface.com/__hw_app__/assets-abc/animate/character1/character1.png';

test('an asset pack replaces the matching game file', () => {
  const index = packIndex([{id: 'blue', files: ['animate/character1/character1.png']}]);
  const next = replacementUrl(page, index);
  assert.equal(next, 'https://totaljerkface.com/__hw_app__/mod-assets/blue/animate/character1/character1.png');
});

test('the first pack wins when two packs contain the same file', () => {
  const index = packIndex([
    {id: 'first', files: ['animate/character1/character1.png']},
    {id: 'second', files: ['animate/character1/character1.png']},
  ]);
  assert.match(replacementUrl(page, index), /\/mod-assets\/first\//);
});

test('low-detail image names use the full sheet when the pack has no scaled copy', () => {
  const index = packIndex([{id: 'blue', files: ['animate/character1/character1.png']}]);
  const small = page.replace('character1.png', 'character1@0.3x.png');
  const medium = page.replace('character1.png', 'character1@0.6x.png');
  assert.match(replacementUrl(small, index), /character1\.png$/);
  assert.match(replacementUrl(medium, index), /character1\.png$/);
});

test('a scaled file in the pack is used instead of the full sheet', () => {
  const index = packIndex([{id: 'blue', files: ['animate/character1/character1.png', 'animate/character1/character1@0.3x.png']}]);
  const small = page.replace('character1.png', 'character1@0.3x.png');
  assert.equal(decodeURIComponent(replacementUrl(small, index)).endsWith('character1@0.3x.png'), true);
});

test('requests outside the game asset folder are left alone', () => {
  const index = packIndex([{id: 'blue', files: ['animate/character1/character1.png']}]);
  assert.equal(replacementUrl('https://totaljerkface.com/__hw_app__/js/index.js', index), null);
  assert.equal(replacementUrl('https://example.com/assets-abc/animate/character1/character1.png?cache=1', index).split('?')[0].endsWith('character1.png'), true);
});
