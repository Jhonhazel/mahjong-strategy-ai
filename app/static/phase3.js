'use strict';
(() => {
  const section = document.getElementById('game-state');
  if (!section) return;
  const message = document.getElementById('game-message');
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const choices = document.getElementById('legal-action');
  let current = null;
  let pending = false;
  async function api(path, method = 'GET', payload) {
    const headers = { 'X-CSRF-Token': csrf };
    if (payload !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, { method, headers, credentials: 'same-origin', body: payload === undefined ? undefined : JSON.stringify(payload) });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) throw new Error(data?.detail?.message || `Request gagal (${response.status})`);
    return data;
  }
  function render(view) {
    if (current && (current.game_id !== view.game_id || current.turn_number !== view.turn_number)) {
      document.getElementById('prediction').textContent = '';
    }
    current = view; section.hidden = false;
    document.getElementById('game-status').textContent = `${view.status} · turn ${view.turn_number}`;
    document.getElementById('game-id').textContent = `Game ${view.game_id} · seat Anda ${view.human_seat}`;
    document.getElementById('own-hand').textContent = `Hand Anda: ${view.own_hand.join(' ')}`;
    document.getElementById('public-state').textContent = JSON.stringify(view.seat_public_states, null, 2);
    document.getElementById('round-result').textContent = view.round_result ? JSON.stringify(view.round_result, null, 2) : 'Round belum selesai.';
    choices.replaceChildren();
    for (const action of view.legal_actions) {
      const option = document.createElement('option'); option.value = action.action_id; option.textContent = `${action.action_id}: ${action.label}`; choices.append(option);
    }
    document.getElementById('predict-button').disabled = !view.can_request_ai_prediction;
    document.getElementById('submit-action').disabled = view.legal_actions.length === 0;
    const url = new URL(window.location.href); url.searchParams.set('game_id', view.game_id); window.history.replaceState(null, '', url);
  }
  async function run(operation) {
    if (pending) return; pending = true; message.textContent = 'Memproses…';
    try { await operation(); message.textContent = 'Selesai.'; }
    catch (error) { message.textContent = error.message + ' Refresh halaman jika sesi sudah kedaluwarsa.'; }
    finally { pending = false; }
  }
  document.getElementById('new-game').addEventListener('submit', event => {
    event.preventDefault(); run(async () => {
      const seed = document.getElementById('game-seed').value;
      render(await api('/api/games', 'POST', { human_seat: Number(document.getElementById('human-seat').value), seed: seed === '' ? null : Number(seed) }));
      document.getElementById('prediction').textContent = '';
    });
  });
  document.getElementById('action-form').addEventListener('submit', event => {
    event.preventDefault(); if (!current || !choices.value) return;
    run(async () => { render(await api(`/api/games/${current.game_id}/actions`, 'POST', { action_id: Number(choices.value), expected_turn_number: current.turn_number })); document.getElementById('prediction').textContent = ''; });
  });
  document.getElementById('predict-button').addEventListener('click', () => {
    if (!current) return;
    run(async () => { const result = await api(`/api/games/${current.game_id}/predict`, 'POST', { expected_turn_number: current.turn_number }); document.getElementById('prediction').textContent = `Tersimpan: ${result.prediction_id}${result.reused ? ' (dipakai ulang)' : ''}\nRekomendasi: ${result.recommended_tile}\n` + result.top3.map(item => `${item.tile}: ${item.score.toFixed(6)}`).join('\n') + '\n' + result.score_meaning; });
  });
  document.getElementById('refresh-button').addEventListener('click', () => { if (current) run(async () => render(await api(`/api/games/${current.game_id}`))); });
  if (section.dataset.gameId) run(async () => render(await api(`/api/games/${encodeURIComponent(section.dataset.gameId)}`)));
})();
