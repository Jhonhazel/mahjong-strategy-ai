import { TILE_CATALOG } from './catalog.mjs';

export function tileSpec(code) {
  return typeof code === 'string' && Object.hasOwn(TILE_CATALOG, code)
    ? TILE_CATALOG[code] : TILE_CATALOG.unknown;
}

export function createTile(document, code, options = {}) {
  const spec = tileSpec(code);
  const interactive = options.interactive === true && Number.isInteger(options.actionId)
    && !['back', 'unknown'].includes(spec.kind);
  const node = document.createElement(interactive ? 'button' : 'span');
  node.className = 'mahjong-tile tile--' + spec.kind
    + (interactive ? ' tile--legal' : '') + (options.selected ? ' is-selected' : '')
    + (options.rank ? ' is-advised' : '') + (options.rank === 1 ? ' is-first-advice' : '');
  node.setAttribute('data-code', spec.code);
  node.setAttribute('aria-label', spec.label + (spec.rank ? ' (' + spec.code + ')' : '')
    + (options.selected ? ', pilihan Anda' : '') + (options.rank ? ', rekomendasi AI ' + options.rank : ''));
  if (interactive) {
    node.setAttribute('type', 'button');
    node.setAttribute('data-action-id', options.actionId);
    node.setAttribute('data-tile-index', options.index);
    node.setAttribute('aria-pressed', options.selected ? 'true' : 'false');
    node.disabled = Boolean(options.disabled);
  } else node.setAttribute('role', 'img');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 60 84');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('class', 'tile-art');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '/static/tiles.svg#' + spec.symbol);
  svg.append(use); node.append(svg);
  if (options.rank) {
    const badge = document.createElement('span'); badge.className = 'tile-marker';
    badge.setAttribute('aria-hidden', 'true'); badge.textContent = 'AI ' + options.rank; node.append(badge);
  }
  if (options.selected) {
    const badge = document.createElement('span'); badge.className = 'tile-chosen';
    badge.setAttribute('aria-hidden', 'true'); badge.textContent = 'Pilihan'; node.append(badge);
  }
  return node;
}
