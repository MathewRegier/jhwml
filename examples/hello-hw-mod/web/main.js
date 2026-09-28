(() => {
  'use strict';
  const hw = window.HWMod;
  if (!hw) {
    console.warn('[hello-hw-mod] window.HWMod is missing. Run a current JHWML launcher.');
    return;
  }

  const box = document.createElement('div');
  box.id = 'hello-hw-mod';
  box.style.cssText = 'position:fixed;left:8px;bottom:8px;z-index:20000;padding:8px 10px;background:#111c;color:#eee;font:12px Trebuchet MS,sans-serif;pointer-events:none;border-radius:4px;';
  box.textContent = 'HWMod waiting…';
  document.documentElement.appendChild(box);

  function line(text) {
    box.textContent = text;
    hw.log(text);
  }

  hw.on('boot', () => line('HWMod boot ' + hw.version + ' / ' + hw.game));
  hw.on('session', () => line('session · iteration ' + (hw.session()?.iteration ?? '?')));
  hw.on('menu', () => line('menu'));
  hw.on('death', () => line('death'));
  hw.on('finish', () => line('finish'));
  hw.on('restart', () => line('restart'));
  hw.on('tick', () => {
    const s = hw.session();
    if (!s || s.isMenu) return;
    box.textContent = 'tick ' + (s.iteration ?? 0) + (s.character?.dead ? ' · dead' : '');
  });
})();
