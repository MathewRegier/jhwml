'use strict';

function buildWebScripts(catalog) {
  const scripts = [];
  for (const mod of catalog || []) {
    for (const script of mod.web || []) {
      if (typeof script === 'string' && script) scripts.push('js/' + mod.id + '/' + script);
    }
  }
  scripts.unshift('js/hw-mod-assets.js');
  scripts.unshift('js/hw-mod-sdk.js');
  return scripts;
}

module.exports = {buildWebScripts};
