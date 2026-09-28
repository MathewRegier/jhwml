(() => {
  try {
    require(require('path').join(process.resourcesPath, 'mod-runtime', 'preload.cjs'));
  } catch (e) {}
})();
