(function (root) {
  'use strict';
  var VERSION = '1.0.0';
  var GAME = '1.99.2-s';
  var STATE_IDS = [35057, 29552];
  var PIXI_ID = 99430;

  function createSdk(win, options) {
    win = win || root;
    options = options || {};
    var listeners = Object.create(null);
    var pixiModules = null;
    var hooked = false;
    var booted = false;
    var lastSession = null;
    var lastCharacter = null;
    var lastIteration = null;
    var lastDead = false;
    var lastFinish = false;
    var lastMenu = null;
    var poll = null;
    var injected = false;

    var api = {
      version: VERSION,
      game: GAME,
      require: null,
      state: null,
      errors: [],
    };

    Object.defineProperty(api, 'mods', {
      get: function () {
        return Array.isArray(win.HW_MOD_CATALOG) ? win.HW_MOD_CATALOG : [];
      },
    });

    function log() {
      var args = ['[HWMod]'];
      for (var i = 0; i < arguments.length; i++) args.push(arguments[i]);
      try {
        if (win.console && win.console.log) win.console.log.apply(win.console, args);
      } catch (e) {}
    }

    function on(event, fn) {
      if (typeof fn !== 'function') return function () {};
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(fn);
      return function () {
        off(event, fn);
      };
    }

    function off(event, fn) {
      var list = listeners[event];
      if (!list) return;
      var i = list.indexOf(fn);
      if (i >= 0) list.splice(i, 1);
    }

    function emit(event, payload) {
      var list = listeners[event];
      if (!list) return;
      var copy = list.slice();
      for (var i = 0; i < copy.length; i++) {
        try {
          copy[i](payload);
        } catch (e) {
          api.errors.push(String((e && e.message) || e));
        }
      }
    }

    function wrap(obj, name, fn) {
      if (!obj || typeof obj[name] !== 'function' || typeof fn !== 'function') return false;
      var original = obj[name];
      function wrapped() {
        return fn.call(this, original, arguments);
      }
      wrapped.__hwmodWrap = true;
      wrapped.__hwmodOriginal = original.__hwmodOriginal || original;
      obj[name] = wrapped;
      return true;
    }

    function happyWheels() {
      var state = api.state;
      return (state && state.rootApp && state.rootApp.screenManager && state.rootApp.screenManager.currentScreen && state.rootApp.screenManager.currentScreen.happyWheels) || null;
    }

    function session() {
      return (api.state && api.state.currentSession) || null;
    }

    function character() {
      var s = session();
      return (s && s.character) || null;
    }

    function world() {
      var s = session();
      return (s && s.m_world) || null;
    }

    function controller() {
      var hw = happyWheels();
      if (!hw) return null;
      return {happyWheels: hw, sessionController: hw.sessionController || null};
    }

    function pixi() {
      if (pixiModules) return pixiModules;
      if (!api.require) return null;
      try {
        var p = api.require(PIXI_ID);
        if (!p) return null;
        var Graphics = p.Graphics;
        if (!Graphics) {
          for (var key in p) {
            if (!Object.prototype.hasOwnProperty.call(p, key)) continue;
            var C = p[key];
            if (typeof C === 'function' && C.prototype && typeof C.prototype.drawPolygon === 'function' && typeof C.prototype.beginFill === 'function') {
              Graphics = C;
              break;
            }
          }
        }
        pixiModules = {
          Container: p.mcf || p.Container,
          Sprite: p.kxk || p.Sprite,
          Texture: p.gPd || p.Texture,
          Matrix: p.uqu || p.Matrix,
          Rectangle: p.M_G || p.Rectangle,
          TextureCache: (p.WpD && p.WpD.TextureCache) || (p.utils && p.utils.TextureCache),
          Graphics: Graphics,
          raw: p,
        };
        return pixiModules;
      } catch (e) {
        return null;
      }
    }

    function playable(s) {
      return !!(s && !s.isMenu && !s.isEditorTest && (s.m_world || s.containerSprite));
    }

    function chunkQueue() {
      try {
        var keys = Object.keys(win);
        for (var i = 0; i < keys.length; i++) {
          var key = keys[i];
          if (!/^Tmu[A-Za-z0-9]+$/.test(key)) continue;
          var chunks = win[key];
          if (Array.isArray(chunks) && chunks.push !== Array.prototype.push) return chunks;
        }
      } catch (e) {}
      return null;
    }

    function grabState() {
      if (api.state && api.state.rootApp) return true;
      if (!api.require) return false;
      for (var i = 0; i < STATE_IDS.length; i++) {
        try {
          var w = api.require(STATE_IDS[i]);
          w = w && w.w;
          if (w && (w.rootApp || 'currentSession' in w || w.totalCharacters != null)) {
            api.state = w;
            return true;
          }
        } catch (e) {}
      }
      return false;
    }

    function attachRequire(requireFn) {
      api.require = requireFn;
      grabState();
    }

    function hookRenderer() {
      var renderer = api.state && api.state.rootApp && api.state.rootApp.renderer;
      if (!renderer || typeof renderer.render !== 'function' || hooked) return false;
      wrap(renderer, 'render', function (original, args) {
        var result = original.apply(this, args);
        peek();
        emit('tick', {session: session(), character: character(), world: world()});
        return result;
      });
      hooked = true;
      renderer.__hwmodTick = true;
      return true;
    }

    function peek() {
      grabState();
      if (api.state && api.state.rootApp && api.state.rootApp.renderer && !booted) {
        hookRenderer();
        booted = true;
        emit('boot', {state: api.state});
      }
      var s = session();
      var menu = !playable(s);
      if (lastMenu === null || menu !== lastMenu) {
        lastMenu = menu;
        if (menu) emit('menu', {session: s});
      }
      if (s && playable(s)) {
        if (s !== lastSession) {
          lastSession = s;
          lastCharacter = s.character || null;
          lastIteration = typeof s.iteration === 'number' ? s.iteration : null;
          lastDead = !!(s.character && s.character.dead);
          lastFinish = !!(s.replayData && s.replayData.completed);
          emit('session', s);
          if (s.character) emit('character', s.character);
        } else {
          if (typeof s.iteration === 'number' && lastIteration != null && s.iteration < lastIteration) {
            emit('restart', s);
            lastDead = !!(s.character && s.character.dead);
            lastFinish = !!(s.replayData && s.replayData.completed);
          }
          lastIteration = typeof s.iteration === 'number' ? s.iteration : lastIteration;
          var ch = s.character || null;
          if (ch && ch !== lastCharacter) {
            lastCharacter = ch;
            emit('character', ch);
          }
          var dead = !!(ch && ch.dead);
          if (dead && !lastDead) emit('death', ch);
          lastDead = dead;
          var finish = !!(s.replayData && s.replayData.completed);
          if (finish && !lastFinish) emit('finish', s);
          lastFinish = finish;
        }
      } else if (!s) {
        lastSession = null;
        lastCharacter = null;
      }
    }

    function inject() {
      if (api.require || injected) return;
      var chunks = chunkQueue();
      if (!chunks) return;
      injected = true;
      chunks.push([['hw-mod-sdk'], {}, function (requireFn) {
        attachRequire(requireFn);
      }]);
    }

    function scan() {
      inject();
      grabState();
      hookRenderer();
      peek();
      return api;
    }

    function start() {
      scan();
      if (typeof win.setInterval === 'function') {
        poll = win.setInterval(function () {
          scan();
        }, 100);
      }
    }

    function stop() {
      if (poll != null && typeof win.clearInterval === 'function') {
        win.clearInterval(poll);
        poll = null;
      }
    }

    api.on = on;
    api.off = off;
    api.emit = emit;
    api.session = session;
    api.character = character;
    api.world = world;
    api.controller = controller;
    api.pixi = pixi;
    api.wrap = wrap;
    api.log = log;
    api.scan = scan;
    api.stop = stop;
    api.happyWheels = happyWheels;

    if (options.autostart !== false) start();
    return api;
  }

  if (root && root.document) root.HWMod = createSdk(root);
  if (typeof module === 'object' && module.exports) {
    module.exports = {createSdk: createSdk, VERSION: VERSION, GAME: GAME};
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
