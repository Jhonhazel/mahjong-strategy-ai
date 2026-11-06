// Acceptance harness only: real HTTP + the shipped controller, no alternate Mahjong engine.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { createHttpClient } from '../../app/static/phase4/http.mjs';
import { GameController } from '../../app/static/phase4/controller.mjs';
import { createDeletion } from '../../app/static/phase4/deletion.mjs';

const [base, output] = process.argv.slice(2);
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
const requests = [], cookies = new Map();
// Node fetch has no browser cookie jar. This local test adapter retains the
// real HttpOnly response cookie in memory; neither cookie nor CSRF is reported.
const fetchImpl = async (path, options = {}) => {
  const headers = new Headers(options.headers);
  if (cookies.size) headers.set('Cookie', [...cookies].map(([key, value]) => key + '=' + value).join('; '));
  const started = performance.now();
  const response = await fetch(base + path, { ...options, headers });
  for (const value of response.headers.getSetCookie()) {
    const pair = value.split(';')[0], split = pair.indexOf('=');
    cookies.set(pair.slice(0, split), pair.slice(split + 1));
  }
  requests.push({ method: options.method ?? 'GET', path, status: response.status, elapsed_ms: Number((performance.now() - started).toFixed(3)) });
  return response;
};
const api = createHttpClient({ fetchImpl });
await api.getSession();
const controller = new GameController({ api });
const rounds = [];
const started = performance.now();
for (const [index, seed] of [42, 43].entries()) {
  assert.equal(await controller.create({ human_seat: 1, prevalent_wind: index, seed, include_flowers: index === 1 }), true);
  const initial = structuredClone(controller.state.view), saved = [], actionKinds = {}, claimOptions = new Set();
  let steps = 0;
  for (; steps < 400; steps++) {
    const view = controller.state.view;
    assert.deepEqual(await api.getGame(view.game_id), view);
    if (view.status === 'FINISHED') break;
    for (const action of view.legal_actions) if (action.action_type !== 'Play') claimOptions.add(action.action_type);
    if (view.can_request_ai_prediction && (saved.length < 2 || !saved.some(result => result.turn_phase === 'POST_MELD_DISCARD'))) {
      const before = structuredClone(view);
      assert.equal(await controller.predict(), true);
      const prediction = controller.state.prediction;
      assert.ok(prediction && prediction.prediction_id && prediction.game_id === view.game_id);
      assert.equal(prediction.turn_number, view.turn_number);
      assert.deepEqual(controller.state.view, before);
      assert.equal(prediction.model_version, 'discard_mlp_flexible_v1:ad05a5b2ce37');
      for (const suggestion of prediction.top3) assert.ok(view.legal_actions.some(action => action.action_type === 'Play' && action.action_id === suggestion.action_id && action.tile === suggestion.tile));
      const detail = await api.getPrediction(prediction.prediction_id);
      assert.deepEqual(detail.output_snapshot.top3, prediction.top3);
      const previousActions = requests.filter(request => request.path.endsWith('/actions')).length;
      assert.equal(await controller.predict(), true);
      assert.equal(controller.state.prediction.reused, true);
      assert.equal(controller.state.prediction.prediction_id, prediction.prediction_id);
      assert.equal(requests.filter(request => request.path.endsWith('/actions')).length, previousActions);
      saved.push({ prediction_id: prediction.prediction_id, turn_number: prediction.turn_number,
        turn_phase: prediction.turn_phase, recommended_tile: prediction.recommended_tile, top3: prediction.top3,
        checkpoint_sha256: detail.checkpoint_sha256, model_version: prediction.model_version, reused_verified: true });
    }
    // A deterministic acceptance choice among server options, never model-driven
    // and never a client implementation of legality or scoring.
    const action = view.legal_actions.find(item => item.action_type === 'Hu')
      ?? view.legal_actions.find(item => ['Chi', 'Peng', 'Gang', 'AnGang', 'BuGang'].includes(item.action_type))
      ?? view.legal_actions[0];
    assert.ok(action);
    if (action.action_type === 'Play') {
      assert.equal(controller.selectTile(view.own_hand.indexOf(action.tile)), true);
      assert.equal(controller.state.selectedId, action.action_id);
    } else assert.equal(controller.selectAction(action.action_id), true);
    assert.equal(await controller.submit(), true);
    actionKinds[action.action_type] = (actionKinds[action.action_type] ?? 0) + 1;
    assert.equal(controller.state.prediction, null); assert.equal(controller.state.selectedId, null);
    assert.ok(controller.state.view.turn_number >= view.turn_number);
  }
  const final = controller.state.view;
  assert.equal(final.status, 'FINISHED'); assert.ok(steps < 400 && saved.length >= 2);
  assert.ok(['draw', 'zimo', 'ron'].includes(final.round_result.ending));
  assert.equal(final.round_result.score_deltas.length, 4);
  assert.equal(final.round_result.score_deltas.reduce((sum, value) => sum + value, 0), 0);
  const history = await api.listPredictions(100, 0);
  for (const prediction of saved) assert.ok(history.items.some(item => item.prediction_id === prediction.prediction_id));
  let removed = false;
  const remove = createDeletion({ api, onPending: () => {}, onSuccess: () => { removed = true; }, onError: message => assert.fail(message) });
  assert.equal(await remove(saved[0].prediction_id), true); assert.equal(removed, true);
  await assert.rejects(api.getPrediction(saved[0].prediction_id), error => error.status === 404);
  assert.deepEqual(await api.getGame(final.game_id), final);
  assert.equal((await api.getPrediction(saved[1].prediction_id)).prediction_id, saved[1].prediction_id);
  rounds.push({ seed, human_seat: 1, prevalent_wind: index, include_flowers: index === 1,
    game_id: initial.game_id, initial_turn: initial.turn_number, initial_hand: initial.own_hand,
    actions: steps, action_kinds: actionKinds, offered_claims: [...claimOptions], predictions: saved,
    final_view: final, deleted_prediction_id: saved[0].prediction_id, deletion_verified: true });
}
const evidence = { status: 'PASS', transport: 'Real localhost Uvicorn TCP using shipped ES-module controller and HTTP client',
  database: 'Isolated project PostgreSQL test database', inference: 'Real pinned MLP v3, CPU',
  policy: 'Test-only first supplied action with claim/Hu priority. No frontend rule engine or model auto-discard.',
  duration_ms: Number((performance.now() - started).toFixed(3)), rounds, requests };
if (output) await writeFile(output, JSON.stringify(evidence, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ status: evidence.status, rounds: rounds.length, actions: rounds.map(round => round.actions), duration_ms: evidence.duration_ms }));
