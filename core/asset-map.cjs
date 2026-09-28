'use strict';

function packIndex(packs) {
  const index = new Map();
  for (const pack of packs) {
    const owned = new Set(pack.files);
    for (const file of pack.files) {
      if (!index.has(file)) index.set(file, {id: pack.id, file});
    }
    for (const file of pack.files) {
      const dot = file.lastIndexOf('.');
      const slash = file.lastIndexOf('/');
      if (dot <= slash) continue;
      const stem = file.slice(0, dot);
      const ext = file.slice(dot);
      for (const mark of ['@0.3x', '@0.6x']) {
        const alias = stem + mark + ext;
        if (!owned.has(alias) && !index.has(alias)) index.set(alias, {id: pack.id, file});
      }
    }
  }
  return index;
}

function replacementUrl(original, index) {
  let parsed;
  try {
    parsed = new URL(original);
  } catch {
    return null;
  }
  const parts = parsed.pathname.split('/');
  const folder = parts.findIndex((part) => part.startsWith('assets-') && part.length > 7);
  if (folder < 0) return null;
  let rel = '';
  try {
    rel = parts.slice(folder + 1).map((part) => decodeURIComponent(part)).join('/');
  } catch {
    return null;
  }
  if (!rel || rel.includes('..')) return null;
  const hit = index.get(rel);
  if (!hit) return null;
  const tail = ['mod-assets', hit.id, ...hit.file.split('/')].map((part) => encodeURIComponent(part));
  parsed.pathname = parts.slice(0, folder).concat(tail).join('/');
  if (!parsed.pathname.startsWith('/')) parsed.pathname = `/${parsed.pathname}`;
  parsed.hash = '';
  return parsed.toString();
}

module.exports = {packIndex, replacementUrl};
