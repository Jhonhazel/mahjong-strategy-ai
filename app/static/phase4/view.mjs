import { WIND_NAMES } from './catalog.mjs';
import { createTile, tileSpec } from './tiles.mjs';
import { discardForTile, projectSeats, roundPresentation } from './model.mjs';

const ACTION_NAMES = { Play: 'Buang', Chi: 'Chi', Peng: 'Peng', Gang: 'Gang terbuka',
  AnGang: 'Gang tertutup', BuGang: 'Gang tambahan', Hu: 'Hu · menang', Pass: 'Lewati claim' };

function element(document, tag, className, text) {
  const node = document.createElement(tag); node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function tileGroup(document, codes, className, label) {
  const group = element(document, 'div', className);
  group.setAttribute('role', 'group'); group.setAttribute('aria-label', label);
  for (const code of codes) group.append(createTile(document, code));
  return group;
}
export function actionLabel(action) {
  return (ACTION_NAMES[action.action_type] ?? action.action_type) + (action.tile ? ' · ' + tileSpec(action.tile).label : '')
    + (action.action_type === 'Chi' && action.meld_tiles ? ' (' + action.meld_tiles.join(' · ') + ')' : '');
}

export function buildSeat(document, seat, view) {
  const node = element(document, 'section', 'player-seat' + (seat.human ? ' player-seat--human' : '') + (seat.active ? ' player-seat--active' : ''));
  node.setAttribute('aria-label', seat.name + ' · seat ' + seat.seat);
  const header = element(document, 'div', 'seat-heading');
  const wind = element(document, 'span', 'wind-token', ['東', '南', '西', '北'][seat.seat]); wind.setAttribute('aria-hidden', 'true');
  const names = element(document, 'div', 'seat-name'); names.append(element(document, 'h3', '', seat.name), element(document, 'span', '', 'Seat ' + seat.seat + ' · ' + seat.concealedCount + ' tile'));
  header.append(wind, names);
  if (seat.active && view.status !== 'FINISHED') header.append(element(document, 'span', 'seat-active', seat.human ? 'Giliran Anda' : 'Aktif'));
  node.append(header);
  if (!seat.human) node.append(tileGroup(document, seat.hand, 'concealed-hand', 'Tangan tertutup · ' + seat.concealedCount + ' tile'));
  // The human hand is moved into the full-width interactive zone by the page renderer.
  if (seat.human) {
    const hand = element(document, 'div', 'seat-hand');
    for (const [index, code] of seat.hand.entries()) {
      const action = discardForTile(view, code);
      hand.append(createTile(document, code, { interactive: Boolean(action), actionId: action?.action_id, index }));
    }
    node.append(hand);
  }
  if (seat.melds.length) {
    const melds = element(document, 'div', 'public-melds');
    for (const pack of seat.melds) melds.append(tileGroup(document, pack.tiles, 'meld-group', 'Meld ' + pack.type));
    node.append(melds);
  }
  if (seat.flowers.length) node.append(tileGroup(document, seat.flowers, 'public-flowers', 'Bunga terbuka'));
  const river = element(document, 'div', 'seat-river'); river.setAttribute('aria-label', 'Buangan ' + seat.name);
  river.append(element(document, 'span', 'river-label', 'Buangan · ' + seat.discards.length));
  river.append(tileGroup(document, seat.discards, 'river-tiles', 'Urutan buangan pemain ini'));
  node.append(river);
  return node;
}

export function buildAdvice(document, state) {
  const node = element(document, 'div', 'advice-body');
  const result = state.prediction;
  if (result) {
    node.append(element(document, 'p', 'advice-context', 'Top 3 · Turn ' + result.turn_number + ' · ' + (result.turn_phase === 'POST_MELD_DISCARD' ? 'Setelah meld' : 'Giliran sendiri')));
    const list = element(document, 'ol', 'advice-list');
    for (const [index, suggestion] of result.top3.entries()) {
      const row = element(document, 'li', index === 0 ? 'advice-item advice-item--first' : 'advice-item');
      row.append(element(document, 'span', 'advice-rank', '0' + (index + 1)), createTile(document, suggestion.tile));
      const name = element(document, 'div', 'advice-name');
      name.append(element(document, 'strong', '', tileSpec(suggestion.tile).label), element(document, 'span', 'tile-code', suggestion.tile));
      const score = element(document, 'span', 'advice-score', (suggestion.score * 100).toFixed(2));
      score.append(element(document, 'small', '', '% bobot'));
      row.append(name, score); list.append(row);
    }
    node.append(list, element(document, 'p', 'fine-print', 'Ini bobot rekomendasi discard, bukan probabilitas menang. Tidak ada aksi yang dijalankan otomatis.'));
  } else if (!state.savedNotice) {
    const empty = element(document, 'div', 'advisor-empty');
    empty.append(element(document, 'span', '', '01 · 02 · 03'), element(document, 'p', '', 'Top 3 rekomendasi muncul setelah Anda meminta prediksi pada giliran discard.'));
    node.append(empty);
  }
  if (state.savedNotice) {
    const notice = element(document, 'div', 'saved-notice');
    notice.append(element(document, 'p', '', result ? (state.savedNotice.reused ? 'Catatan tersimpan dipakai ulang.' : 'Prediksi tersimpan di History.')
      : 'Prediksi tersimpan untuk turn ' + state.savedNotice.turn_number + '. Rekomendasi tidak ditampilkan pada state yang belum terverifikasi atau telah berubah.'));
    const link = element(document, 'a', 'text-link', 'Buka detail tersimpan ↗');
    link.setAttribute('href', '/history/' + encodeURIComponent(state.savedNotice.prediction_id));
    notice.append(link);
    const provenance = element(document, 'details', 'advice-provenance');
    provenance.append(element(document, 'summary', '', 'Identitas prediksi'));
    const metadata = element(document, 'dl', 'technical-list');
    for (const [label, value] of [['Prediction ID', state.savedNotice.prediction_id], ['Model', state.savedNotice.model_version], ['Encoder', state.savedNotice.encoder_version]]) {
      metadata.append(element(document, 'dt', '', label), element(document, 'dd', 'mono', value));
    }
    provenance.append(metadata); notice.append(provenance); node.append(notice);
  }
  return node;
}

export function buildRound(document, view) {
  const result = roundPresentation(view);
  const node = element(document, 'div', 'result-content');
  if (!result) return node;
  node.append(element(document, 'p', 'eyebrow', 'ROUND SELESAI'), element(document, 'h2', '', result.title), element(document, 'p', 'result-ending', result.endingLabel));
  if (result.winningTile) node.append(createTile(document, result.winningTile));
  if (result.discarder !== null) node.append(element(document, 'p', '', 'Buangan dari seat ' + result.discarder + ' · ' + WIND_NAMES[result.discarder]));
  if (result.qianggang) node.append(element(document, 'p', '', 'Qianggang · menang saat gang tambahan'));
  if (result.ending !== 'draw') {
    node.append(element(document, 'h3', '', result.totalFan + ' total fan'));
    const fans = element(document, 'ul', 'fan-list');
    for (const fan of result.fans) fans.append(element(document, 'li', '', fan.fan_name_en + ' · ' + fan.fan_name_zh + ' — ' + fan.fan_points + ' × ' + fan.count));
    node.append(fans);
  }
  const scores = element(document, 'div', 'score-deltas');
  scores.setAttribute('aria-label', 'Perubahan skor dari engine');
  result.scoreDeltas.forEach((score, seat) => {
    const card = element(document, 'div', 'score-card' + (seat === view.human_seat ? ' score-card--human' : ''));
    card.append(element(document, 'span', '', (seat === view.human_seat ? 'Anda · ' : '') + WIND_NAMES[seat]), element(document, 'strong', '', (score > 0 ? '+' : '') + score)); scores.append(card);
  });
  node.append(scores, element(document, 'p', 'fine-print', 'Hasil, fan, dan perubahan skor dilaporkan oleh engine permainan.'));
  const again = element(document, 'a', 'button', 'Atur round berikutnya ↗'); again.setAttribute('href', '#game-setup'); node.append(again);
  return node;
}

export function createGameRenderer(document) {
  const get = id => document.getElementById(id);
  let lastView = null, lastAdvice = Symbol(), lastSaved = Symbol();
  const refresh = get('refresh-button'), predict = get('predict-button'), submit = get('submit-action'), choices = get('legal-action');
  return state => {
    const view = state.view, busy = Boolean(state.busy), blocked = busy || state.needsRefresh;
    get('game-message').textContent = state.message;
    get('game-message').className = 'game-message message--' + state.tone;
    get('game-state').hidden = !view;
    get('empty-table').hidden = Boolean(view);
    get('game-state').setAttribute('aria-busy', String(busy));
    for (const control of get('new-game').elements) control.disabled = busy && state.busy !== 'PRESENTING';
    refresh.disabled = busy || !view;
    predict.disabled = blocked || !view?.can_request_ai_prediction;
    predict.textContent = state.busy === 'PREDICTING' ? 'Menganalisis & menyimpan…' : '✧ Minta prediksi & simpan';
    submit.disabled = blocked || state.selectedId === null || !view?.legal_actions.length;
    submit.textContent = state.busy === 'SUBMITTING_ACTION' ? 'Menjalankan…' : state.selectedId === null ? 'Jalankan pilihan →'
      : 'Jalankan: ' + actionLabel(view.legal_actions.find(action => action.action_id === state.selectedId));
    choices.disabled = blocked || !view?.legal_actions.length;
    if (view !== lastView) {
      if (view) {
        for (const seat of projectSeats(view)) {
          const card = buildSeat(document, seat, view);
          if (seat.human) {
            const hand = card.querySelector('.seat-hand');
            get('human-hand').replaceChildren(...hand.children); hand.remove();
          }
          get('seat-' + seat.position).replaceChildren(card);
        }
        const center = element(document, 'div', 'center-content');
        center.append(element(document, 'span', 'center-wind', ['東', '南', '西', '北'][view.prevalent_wind]), element(document, 'span', 'center-round', 'Angin ' + WIND_NAMES[view.prevalent_wind]), element(document, 'strong', 'center-wall', view.wall_tiles_remaining), element(document, 'span', 'center-caption', 'tile tersisa'), element(document, 'span', 'turn-badge', 'Turn ' + view.turn_number));
        get('table-center').replaceChildren(center);
        choices.replaceChildren(element(document, 'option', '', 'Pilih tile atau aksi…')); choices.firstElementChild.value = '';
        const claims = [];
        for (const action of view.legal_actions) {
          const option = element(document, 'option', '', actionLabel(action)); option.value = action.action_id; choices.append(option);
          if (action.action_type !== 'Play') {
            const button = element(document, 'button', 'claim-button' + (action.action_type === 'Hu' ? ' claim-button--hu' : ''));
            button.type = 'button'; button.setAttribute('data-claim-id', action.action_id); button.setAttribute('aria-pressed', 'false');
            button.append(element(document, 'span', '', actionLabel(action)));
            if (action.meld_tiles?.length) button.append(tileGroup(document, action.meld_tiles, 'claim-preview', 'Tile meld'));
            else if (action.tile) button.append(createTile(document, action.tile));
            claims.push(button);
          }
        }
        get('claim-actions').replaceChildren(...claims);
        get('game-id').textContent = 'Game ' + view.game_id + ' · Seat Anda ' + view.human_seat;
        get('public-state').textContent = 'Turn ' + view.turn_number + ' · ' + view.status + ' · ' + view.wall_tiles_remaining + ' tile tersisa. Tangan lawan tetap tertutup.';
        get('round-result').hidden = !view.round_result;
        get('round-result').replaceChildren(buildRound(document, view));
        get('hand-hint').textContent = view.status === 'FINISHED' ? 'Round selesai. Lihat hasil di bawah.' : view.status === 'WAITING_HUMAN_CLAIM'
          ? 'Pilih claim atau lewati. Discard belum tersedia.' : 'Pilih satu tile legal, lalu konfirmasi langkah.';
      } else {
        get('round-result').hidden = true;
        for (const id of ['round-result', 'human-hand', 'claim-actions', 'table-center', 'seat-top', 'seat-left', 'seat-right', 'seat-bottom']) get(id).replaceChildren();
        get('game-id').textContent = ''; get('public-state').textContent = '';
        choices.replaceChildren(element(document, 'option', '', 'Pilih tile atau aksi…')); choices.firstElementChild.value = '';
      }
      lastView = view;
    }
    if (view) {
      choices.value = state.selectedId === null ? '' : String(state.selectedId);
      const ranks = new Map((state.prediction?.top3 ?? []).map((suggestion, index) => [suggestion.tile, index + 1]));
      for (const tile of get('human-hand').querySelectorAll('button[data-action-id]')) {
        const index = Number(tile.dataset.tileIndex), selected = state.selectedId === Number(tile.dataset.actionId)
          && (state.selectedIndex === null ? index === view.own_hand.indexOf(tile.dataset.code) : state.selectedIndex === index);
        const rank = ranks.get(tile.dataset.code);
        tile.disabled = blocked;
        tile.classList.toggle('is-selected', selected); tile.classList.toggle('is-advised', Boolean(rank)); tile.classList.toggle('is-first-advice', rank === 1);
        tile.setAttribute('aria-pressed', String(selected));
        tile.setAttribute('aria-label', tileSpec(tile.dataset.code).label + ' (' + tile.dataset.code + ')' + (selected ? ', pilihan Anda' : '') + (rank ? ', rekomendasi AI ' + rank : ''));
        for (const badge of tile.querySelectorAll('.tile-marker, .tile-chosen')) badge.remove();
        if (rank) { const badge = element(document, 'span', 'tile-marker', 'AI ' + rank); badge.setAttribute('aria-hidden', 'true'); tile.append(badge); }
        if (selected) { const badge = element(document, 'span', 'tile-chosen', 'Pilihan'); badge.setAttribute('aria-hidden', 'true'); tile.append(badge); }
      }
      for (const claim of get('claim-actions').querySelectorAll('button')) {
        claim.disabled = blocked;
        claim.setAttribute('aria-pressed', String(Number(claim.dataset.claimId) === state.selectedId));
      }
      get('round-result').hidden = !view.round_result || state.busy === 'PRESENTING';
      for (const position of ['top', 'left', 'right', 'bottom']) {
        const slot = get('seat-' + position), active = state.presentation?.position === position;
        slot.classList.toggle('is-public-update', active);
        for (const [index, tile] of [...slot.querySelectorAll('.river-tiles .mahjong-tile')].entries()) {
          tile.classList.toggle('is-arriving', active && state.presentation.newDiscards.includes(index));
        }
        for (const [index, pack] of [...slot.querySelectorAll('.meld-group')].entries()) {
          pack.classList.toggle('is-arriving', active && state.presentation.newMelds.includes(index));
        }
      }
    }
    get('advisor-availability').textContent = !view ? 'Mulai round untuk mengaktifkan advisor.' : view.status === 'FINISHED' ? 'Round sudah selesai.'
      : state.needsRefresh ? 'Perbarui state untuk melanjutkan keputusan.' : !view.can_request_ai_prediction ? 'Advisor tersedia saat giliran discard, bukan saat claim.' : 'Tersedia untuk giliran discard ini. Disimpan hanya saat Anda meminta.';
    if (lastAdvice !== state.prediction || lastSaved !== state.savedNotice) {
      get('prediction').replaceChildren(buildAdvice(document, state)); lastAdvice = state.prediction; lastSaved = state.savedNotice;
    }
  };
}
