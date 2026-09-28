const test = require('node:test');
const assert = require('node:assert/strict');
const {createSdk, VERSION, GAME} = require('../core/hw-mod-sdk.js');

function fakeWin(extra) {
  return Object.assign({console: {log() {}}}, extra || {});
}

test('event bus on/off/wrap and mods getter', () => {
  const win = fakeWin({HW_MOD_CATALOG: [{id: 'hello-hw-mod', name: 'Hello', web: ['main.js']}]});
  const sdk = createSdk(win, {autostart: false});
  assert.equal(sdk.version, VERSION);
  assert.equal(sdk.game, GAME);
  assert.deepEqual(sdk.mods, win.HW_MOD_CATALOG);
  const seen = [];
  function onSession(s) { seen.push(s); }
  sdk.on('session', onSession);
  sdk.emit('session', {ok: 1});
  sdk.off('session', onSession);
  sdk.emit('session', {ok: 2});
  assert.deepEqual(seen, [{ok: 1}]);
  const obj = {n: 0, inc() { this.n += 1; return this.n; }};
  assert.equal(sdk.wrap(obj, 'inc', function (original, args) {
    original.apply(this, args);
    return this.n * 10;
  }), true);
  assert.equal(obj.inc(), 10);
});

test('scan emits boot, session, tick, death, restart, and finish', () => {
  const renderer = {render(value) { return value; }};
  const session = {
    isMenu: false,
    isEditorTest: false,
    m_world: {},
    containerSprite: {},
    iteration: 5,
    character: {dead: false},
    replayData: {completed: false},
  };
  const win = fakeWin();
  const sdk = createSdk(win, {autostart: false});
  sdk.state = {rootApp: {renderer}, currentSession: session};
  const events = [];
  ['boot', 'session', 'tick', 'death', 'restart', 'finish'].forEach((name) => {
    sdk.on(name, () => events.push(name));
  });
  sdk.scan();
  assert.deepEqual(events, ['boot', 'session']);
  assert.equal(sdk.session(), session);
  assert.equal(sdk.character(), session.character);
  assert.equal(sdk.world(), session.m_world);
  assert.equal(renderer.render('ok'), 'ok');
  assert.ok(events.includes('tick'));
  session.character.dead = true;
  sdk.scan();
  assert.ok(events.includes('death'));
  session.iteration = 1;
  session.character.dead = false;
  sdk.scan();
  assert.ok(events.includes('restart'));
  session.replayData.completed = true;
  sdk.scan();
  assert.ok(events.includes('finish'));
});

test('pixi() and state come from require without exposing ids to the caller', () => {
  function Container() {}
  function Sprite() {}
  const Texture = {from() {}};
  function Rectangle() {}
  function Graphics() {}
  Graphics.prototype.drawPolygon = function () {};
  Graphics.prototype.beginFill = function () {};
  const state = {rootApp: {renderer: {render() {}}}, currentSession: null, totalCharacters: 11};
  const pixiRaw = {mcf: Container, kxk: Sprite, gPd: Texture, M_G: Rectangle, WpD: {TextureCache: {}}, Gfx: Graphics};
  const sdk = createSdk(fakeWin(), {autostart: false});
  sdk.require = (id) => {
    if (id === 29552) return {w: state};
    if (id === 99430) return pixiRaw;
    return null;
  };
  sdk.scan();
  assert.equal(sdk.state, state);
  const pixi = sdk.pixi();
  assert.equal(pixi.Container, Container);
  assert.equal(pixi.Sprite, Sprite);
  assert.equal(pixi.raw, pixiRaw);
  assert.equal(typeof pixi.Graphics, 'function');
});
