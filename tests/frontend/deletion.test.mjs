import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { deferred } from './fixtures.mjs';
import { HttpError } from '../../app/static/phase4/http.mjs';
const path = new URL('../../app/static/phase4/deletion.mjs', import.meta.url);
const module = existsSync(path) ? await import(path) : {};
const factory = options => { assert.equal(typeof module.createDeletion, 'function', 'missing guarded history deletion'); return module.createDeletion(options); };

test('confirmed history deletion waits for server success and ignores double submission', async () => {
  const waiting = deferred(), events = [], calls = [];
  const remove = factory({ api: { deletePrediction: id => { calls.push(id); return waiting.promise; } },
    onPending: value => events.push(['pending', value]), onSuccess: () => events.push(['success']), onError: value => events.push(['error', value]) });
  const request = remove('owned-record');
  assert.equal(await remove('owned-record'), false);
  assert.deepEqual(calls, ['owned-record']); assert.deepEqual(events, [['pending', true]]);
  waiting.resolve(null); assert.equal(await request, true);
  assert.deepEqual(events, [['pending', true], ['success'], ['pending', false]]);
});

for (const status of [0, 401, 403, 404, 503]) test('history deletion failure ' + status + ' never reports or navigates as success', async () => {
  const events = [];
  const remove = factory({ api: { deletePrediction: async () => { throw new HttpError(status); } },
    onPending: value => events.push(['pending', value]), onSuccess: () => events.push(['success']), onError: value => events.push(['error', value]) });
  assert.equal(await remove('owned-record'), false);
  assert.equal(events.filter(event => event[0] === 'success').length, 0);
  assert.equal(events[1][0], 'error'); assert.equal(typeof events[1][1], 'string');
  assert.deepEqual(events.at(-1), ['pending', false]);
});
