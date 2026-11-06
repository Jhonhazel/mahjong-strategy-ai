import { createHttpClient } from './phase4/http.mjs';
import { GameController } from './phase4/controller.mjs';
import { parseSettings } from './phase4/model.mjs';
import { createGameRenderer } from './phase4/view.mjs';
import { createDeletion } from './phase4/deletion.mjs';
import { PublicPlayback } from './phase4/playback.mjs';

const api = createHttpClient({ csrfToken: document.querySelector('meta[name="csrf-token"]')?.content ?? '' });
const get = id => document.getElementById(id);

for (const form of document.querySelectorAll('form[data-delete-id]')) {
  const button = form.querySelector('button'), message = form.querySelector('.delete-message');
  const remove = createDeletion({ api,
    onPending: pending => { button.disabled = pending; form.setAttribute('aria-busy', String(pending)); if (pending) message.textContent = 'Menghapus…'; },
    onSuccess: () => { message.textContent = 'Prediksi dihapus.'; window.location.assign('/history'); },
    onError: text => { message.textContent = text; },
  });
  form.addEventListener('submit', event => { event.preventDefault(); void remove(form.dataset.deleteId); });
}

if (get('game-state')) {
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const presentation = new PublicPlayback({ reducedMotion: () => motion.matches, hidden: () => document.hidden });
  const renderGame = createGameRenderer(document);
  const controller = new GameController({ api, presentation, render: state => {
    renderGame(state);
    get('skip-animation').disabled = state.busy !== 'PRESENTING';
    get('refresh-button').disabled = Boolean(state.busy && state.busy !== 'PRESENTING') || !state.view;
  },
    onGame: id => { const url = new URL(window.location.href); url.searchParams.set('game_id', id); window.history.replaceState(null, '', url); },
  });
  const focusHand = () => {
    if (document.hidden) return;
    if (controller.state.view?.status === 'FINISHED') get('round-result').focus({ preventScroll: false });
    else (get('human-hand').querySelector('button:not(:disabled)') ?? get('claim-actions').querySelector('button:not(:disabled)') ?? get('refresh-button')).focus({ preventScroll: true });
  };
  get('new-game').addEventListener('submit', async event => {
    event.preventDefault();
    let settings;
    try { settings = parseSettings({ humanSeat: get('human-seat').value, wind: get('prevalent-wind').value, seed: get('game-seed').value, flowers: get('include-flowers').checked }); }
    catch (error) { get('game-message').textContent = error.message; get('game-message').className = 'game-message message--error'; get('game-seed').focus(); return; }
    if (await controller.create(settings)) { get('game-setup').open = false; focusHand(); }
  });
  get('human-hand').addEventListener('click', event => {
    const tile = event.target.closest('button[data-tile-index]');
    if (tile && get('human-hand').contains(tile)) controller.selectTile(Number(tile.dataset.tileIndex));
  });
  get('claim-actions').addEventListener('click', event => {
    const action = event.target.closest('button[data-claim-id]');
    if (action && get('claim-actions').contains(action)) controller.selectAction(Number(action.dataset.claimId));
  });
  get('legal-action').addEventListener('change', event => {
    if (event.target.value !== '') controller.selectAction(Number(event.target.value));
    else { controller.clearSelection(); controller.emit(); }
  });
  get('action-form').addEventListener('submit', async event => { event.preventDefault(); if (await controller.submit()) focusHand(); });
  get('predict-button').addEventListener('click', () => { void controller.predict(); });
  get('refresh-button').addEventListener('click', () => { void controller.refresh(); });
  get('playback-speed').addEventListener('change', event => { presentation.speed = event.target.value === 'fast' ? 'fast' : 'normal'; });
  get('skip-animation').addEventListener('click', () => controller.skipAnimation());
  document.addEventListener('visibilitychange', () => { if (document.hidden) controller.skipAnimation(); });
  window.addEventListener('pagehide', () => controller.skipAnimation());
  motion.addEventListener('change', event => { if (event.matches) controller.skipAnimation(); });
  get('round-result').addEventListener('click', event => { if (event.target.closest('a[href="#game-setup"]')) { get('game-setup').open = true; get('human-seat').focus(); } });
  controller.emit();
  if (get('game-state').dataset.gameId) {
    get('game-setup').open = false;
    void controller.refresh(get('game-state').dataset.gameId);
  }
}
