// First HWMod — ride card HUD.
// Tutorial: https://mathewregier.github.io/jhwml/first-mod.html
// Each STEP below is a heading in that page. Read this file top to bottom.

(function () {
  'use strict';

  // STEP 4 — The loader injects hw-mod-sdk.js before this file.
  // If HWMod is missing, the launcher that patched the game is too old.
  var hw = window.HWMod;
  if (!hw) {
    console.warn('[first-hw-mod] window.HWMod is missing. Run a current JHWML launcher, then restart the game.');
    return;
  }

  // STEP 5 — Happy Wheels is a normal web page inside Electron.
  // A DOM overlay is the simplest UI. pointer-events:none so clicks still hit the game.
  var card = document.createElement('div');
  card.id = 'first-hw-mod';
  card.style.cssText = [
    'position:fixed',
    'top:10px',
    'left:10px',
    'z-index:20000',
    'width:196px',
    'pointer-events:none',
    'font:700 12px "Trebuchet MS",Tahoma,sans-serif',
    'color:#f4ead4',
    'background:#1a1208',
    'border:3px solid #111',
    'box-shadow:4px 4px 0 #000',
  ].join(';');
  card.innerHTML =
    '<div style="background:#c41200;color:#fff;padding:5px 8px;letter-spacing:.08em;">RIDE CARD</div>' +
    '<div id="first-hw-mod-body" style="padding:8px;line-height:1.45;"></div>';
  document.documentElement.appendChild(card);
  var body = card.querySelector('#first-hw-mod-body');

  var deaths = 0;
  var phase = 'MENU';

  function setBody(html) {
    body.innerHTML = html;
  }

  function paint(extra) {
    setBody(
      '<div>' + phase + '</div>' +
      '<div>attempt ' + extra.attempt + '</div>' +
      '<div>deaths ' + deaths + '</div>' +
      '<div>' + extra.pos + '</div>' +
      '<div style="margin-top:6px;font-weight:400;opacity:.75;">HWMod ' + hw.version + ' · ' + hw.game + '</div>'
    );
  }

  function cameraLine(character) {
    try {
      var focus = character && character.cameraFocus;
      var point = focus && ((focus.GetWorldCenter && focus.GetWorldCenter()) || (focus.GetPosition && focus.GetPosition()));
      if (point && typeof point.x === 'number') {
        return 'x ' + point.x.toFixed(1) + '  y ' + point.y.toFixed(1);
      }
    } catch (err) {}
    return 'x —  y —';
  }

  function attemptNumber(session) {
    if (session && typeof session.iteration === 'number') return String(session.iteration);
    return '—';
  }

  // STEP 6 — Subscribe to named events. Do not scan webpack yourself.
  hw.on('boot', function () {
    hw.log('first-hw-mod boot', hw.version, hw.game);
    phase = 'BOOT';
    paint({attempt: '—', pos: 'waiting for a session'});
  });

  hw.on('menu', function () {
    phase = 'MENU';
    deaths = 0;
    paint({attempt: '—', pos: 'open a level'});
  });

  hw.on('session', function (session) {
    phase = 'RIDING';
    deaths = 0;
    paint({attempt: attemptNumber(session), pos: cameraLine(hw.character())});
  });

  hw.on('character', function () {
    if (phase === 'MENU') return;
    phase = 'RIDING';
  });

  hw.on('restart', function (session) {
    phase = 'RIDING';
    deaths = 0;
    paint({attempt: attemptNumber(session), pos: cameraLine(hw.character())});
  });

  hw.on('death', function () {
    deaths += 1;
    phase = 'DEAD';
  });

  hw.on('finish', function () {
    phase = 'FINISHED';
  });

  // STEP 7 — tick fires after the game draws a frame.
  // Read bodies here. Do not call world.Step — the game (or Shared Physics) already did.
  hw.on('tick', function (info) {
    var session = info.session || hw.session();
    if (!session || session.isMenu) {
      if (phase !== 'MENU') {
        phase = 'MENU';
        deaths = 0;
      }
      paint({attempt: '—', pos: 'open a level'});
      return;
    }
    var character = info.character || hw.character();
    if (phase !== 'DEAD' && phase !== 'FINISHED') phase = 'RIDING';
    paint({
      attempt: attemptNumber(session),
      pos: cameraLine(character),
    });
  });
})();
