import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { documentFixture, descendants } from './dom_fixture.mjs';

async function renderer() {
  const url = new URL('../../app/static/phase4/tiles.mjs', import.meta.url);
  assert.ok(existsSync(url), 'The local tile renderer feature is missing');
  return import(url.href);
}
test('all 42 canonical tiles have the verified symbol and accessible label', async () => {
  const { tileSpec } = await renderer();
  const codes = [...'WTB'].flatMap(suit => Array.from({ length: 9 }, (_, i) => suit + (i + 1)))
    .concat(['F1','F2','F3','F4','J1','J2','J3'], Array.from({ length: 8 }, (_, i) => 'H' + (i + 1)));
  for (const code of codes) {
    assert.equal(tileSpec(code).symbol, 'tile-'+code);
    assert.ok(tileSpec(code).label);
  }
  assert.equal(tileSpec('T1').label, 'Bambu 1');
  assert.equal(tileSpec('B1').label, 'Lingkaran 1');
  assert.equal(tileSpec('F1').label, 'Angin Timur');
  assert.equal(tileSpec('H1').label, 'Bunga 1');
});
test('invalid tile codes use a fixed harmless unknown symbol', async () => {
  const { tileSpec, createTile } = await renderer();
  for (const unsafe of ['<script>alert(1)</script>','W0','H9','F5',null,{},'../../private']) {
    assert.equal(tileSpec(unsafe).symbol, 'tile-unknown');
    const tile = createTile(documentFixture, unsafe);
    const nodes = descendants(tile);
    assert.ok(nodes.every(node => !['SCRIPT','FOREIGNOBJECT'].includes(node.tagName)));
    assert.ok(nodes.every(node => ![...node.attributes.keys()].some(name => name.startsWith('on'))));
    assert.ok(nodes.filter(node => node.tagName === 'USE').every(node => node.getAttribute('href') === '/static/tiles.svg#tile-unknown'));
  }
});
test('selectable tiles use real buttons with stable index and exact server action id', async () => {
  const { createTile } = await renderer();
  const first = createTile(documentFixture, 'B7', { interactive: true, index: 2, actionId: 28, selected: true, rank: 1 });
  const duplicate = createTile(documentFixture, 'B7', { interactive: true, index: 3, actionId: 28 });
  assert.equal(first.tagName, 'BUTTON');
  assert.equal(first.getAttribute('type'), 'button');
  assert.equal(first.getAttribute('data-action-id'), '28');
  assert.equal(duplicate.getAttribute('data-action-id'), '28');
  assert.equal(first.getAttribute('data-tile-index'), '2');
  assert.equal(duplicate.getAttribute('data-tile-index'), '3');
  assert.equal(first.getAttribute('aria-pressed'), 'true');
  assert.match(first.getAttribute('aria-label'), /Lingkaran 7/);
  assert.match(first.textContent, /AI 1/);
  assert.match(first.textContent, /Pilihan/);
});
test('concealed backs do not carry a hidden face or action', async () => {
  const { createTile } = await renderer();
  const tile = createTile(documentFixture, 'back');
  assert.equal(tile.tagName, 'SPAN');
  assert.equal(tile.getAttribute('aria-label'), 'Tile tertutup');
  assert.equal(tile.getAttribute('data-action-id'), null);
  assert.equal(descendants(tile).find(node => node.tagName === 'USE').getAttribute('href'), '/static/tiles.svg#tile-back');
});
test('noninteractive and pending tiles cannot submit an action', async () => {
  const { createTile } = await renderer();
  const publicTile = createTile(documentFixture, 'W5');
  const pending = createTile(documentFixture, 'W5', { interactive: true, actionId: 6, disabled: true });
  assert.equal(publicTile.tagName, 'SPAN');
  assert.equal(pending.disabled, true);
});
