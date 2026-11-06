import { discardForTile } from './model.mjs';
import { HttpError, messageFor } from './http.mjs';

const key = view => view ? view.game_id + ':' + view.turn_number : '';
const idleMode = view => !view ? 'NO_GAME' : ({
  WAITING_HUMAN_DISCARD: 'ACTIVE_DISCARD', WAITING_HUMAN_CLAIM: 'ACTIVE_CLAIM', FINISHED: 'FINISHED',
})[view.status] ?? 'ERROR';

// Validate the response used to claim a committed save. This checks protocol
// shape and supplied server membership; it computes no Mahjong legality/ranking.
function verifiedPrediction(result, view) {
  const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value);
  const text = value => typeof value === 'string' && value.length > 0 && value.length <= 500;
  const score = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;
  const classIndex = value => Number.isInteger(value) && value >= 0 && value < 34;
  const legal = suggestion => suggestion && classIndex(suggestion.class_index) && score(suggestion.score)
    && suggestion.action_id === suggestion.class_index + 2
    && view.legal_actions.some(action => action.action_type === 'Play'
      && action.action_id === suggestion.action_id && action.tile === suggestion.tile);
  if (!result || !uuid(result.prediction_id) || result.game_id !== view.game_id
      || result.turn_number !== view.turn_number || result.seat !== view.human_seat
      || !['SELF_TURN', 'POST_MELD_DISCARD'].includes(result.turn_phase)
      || !text(result.model_version) || !text(result.encoder_version) || !text(result.score_meaning)
      || typeof result.reused !== 'boolean' || !Array.isArray(result.scores)
      || result.scores.length !== 34 || !result.scores.every(score)
      || !Array.isArray(result.top3) || result.top3.length < 1 || result.top3.length > 3
      || !result.top3.every(legal)
      || !result.top3.every((item, index) => index === 0 || result.top3[index - 1].score >= item.score)
      || new Set(result.top3.map(item => item.tile)).size !== result.top3.length
      || !result.top3.every(item => item.score === result.scores[item.class_index])
      || result.top3[0].tile !== result.recommended_tile
      || result.top3[0].action_id !== result.recommended_action_id
      || result.top3[0].class_index !== result.recommended_class_index) throw new HttpError(0);
  return result;
}

export class GameController {
  constructor({ api, render = () => {}, onGame = () => {}, presentation = null }) {
    this.api = api; this.render = render; this.onGame = onGame;
    this.presentation = presentation;
    this.gameId = null; this.readSequence = 0; this.operationSequence = 0; this.activeOperation = 0; this.urlGame = null;
    this.state = { view: null, selectedId: null, selectedIndex: null, prediction: null, savedNotice: null,
      busy: null, presentation: null, mode: 'NO_GAME', message: 'Pilih pengaturan, lalu mulai round Anda.', tone: 'info', needsRefresh: false };
  }
  emit() { this.render({ ...this.state }); }
  begin(kind) {
    if (this.state.busy === 'PRESENTING') {
      this.skipAnimation(); this.state.busy = null;
    }
    if (this.state.busy && !(kind === 'REFRESHING' && this.state.busy === 'REFRESHING')) return null;
    const token = ++this.operationSequence; this.activeOperation = token;
    this.state.prediction = null;
    this.state.busy = kind; this.state.mode = kind; this.state.tone = 'info';
    this.state.message = 'Memproses permintaan…'; this.emit(); return token;
  }
  finish(token) {
    if (token !== this.activeOperation) return;
    this.state.busy = null;
    if (!['ERROR', 'EXPIRED'].includes(this.state.mode)) this.state.mode = idleMode(this.state.view);
    if (this.state.view && this.urlGame !== this.state.view.game_id) {
      this.urlGame = this.state.view.game_id; this.onGame(this.urlGame);
    }
    this.emit();
  }
  clearSelection() { this.state.selectedId = null; this.state.selectedIndex = null; this.selectionKey = ''; }
  skipAnimation() {
    this.presentation?.cancel(); this.state.presentation = null; this.emit();
  }
  setView(view) {
    if (!view || typeof view.game_id !== 'string' || !Number.isInteger(view.turn_number)
        || !Array.isArray(view.legal_actions) || !Array.isArray(view.own_hand)) throw new HttpError(0);
    this.presentation?.cancel(); this.state.presentation = null;
    const changed = key(view) !== key(this.state.view);
    const differentGame = this.state.view && this.state.view.game_id !== view.game_id;
    if (changed) { this.clearSelection(); this.state.prediction = null; }
    if (differentGame) this.state.savedNotice = null;
    this.gameId = view.game_id; this.state.view = view; this.state.needsRefresh = false;
    this.state.mode = idleMode(view);
    if (!view.can_request_ai_prediction) this.state.prediction = null;
    if (!view.legal_actions.some(action => action.action_id === this.state.selectedId)) this.clearSelection();
  }
  fail(error) {
    this.presentation?.cancel(); this.state.presentation = null;
    this.state.prediction = null;
    this.state.message = messageFor(error); this.state.tone = 'error'; this.state.mode = 'ERROR';
    this.state.needsRefresh = !error?.status || error.status >= 500 || [401, 403].includes(error.status);
    if ([401, 404].includes(error?.status)) {
      this.state.view = null; this.clearSelection(); this.state.prediction = null; this.state.mode = 'EXPIRED';
    }
  }
  async read(id) {
    const sequence = ++this.readSequence;
    const view = await this.api.getGame(id);
    if (sequence !== this.readSequence || id !== this.gameId) return false;
    if (view.game_id !== id) throw new HttpError(0);
    if (this.state.view?.game_id === id && view.turn_number < this.state.view.turn_number) return false;
    this.setView(view); return true;
  }
  async create(settings) {
    const token = this.begin('CREATING_GAME'); if (token === null) return false;
    ++this.readSequence;
    try {
      const view = await this.api.createGame(settings);
      ++this.readSequence; this.setView(view); this.clearSelection();
      this.state.prediction = null; this.state.savedNotice = null;
      this.state.message = 'Round dimulai. Pilih keputusan Anda.'; this.state.tone = 'success'; return true;
    } catch (error) { this.fail(error); return false; }
    finally { this.finish(token); }
  }
  async refresh(id = this.gameId) {
    if (!id) return false;
    const token = this.begin('REFRESHING'); if (token === null) return false;
    this.gameId = id;
    try {
      const accepted = await this.read(id);
      if (accepted) { this.state.message = 'State meja sudah diperbarui.'; this.state.tone = 'info'; }
      return accepted;
    } catch (error) {
      if (token === this.activeOperation) this.fail(error);
      return false;
    } finally { this.finish(token); }
  }
  selectAction(id) {
    if (this.state.busy || this.state.needsRefresh || !this.state.view?.legal_actions.some(action => action.action_id === id)) return false;
    this.state.selectedId = id; this.state.selectedIndex = null; this.selectionKey = key(this.state.view);
    this.emit(); return true;
  }
  selectTile(index) {
    const view = this.state.view;
    if (!Number.isInteger(index) || !view || index < 0 || index >= view.own_hand.length) return false;
    const action = discardForTile(view, view.own_hand[index]);
    if (!action || !this.selectAction(action.action_id)) return false;
    this.state.selectedIndex = index; this.emit(); return true;
  }
  async reconcileAction(id, error) {
    this.clearSelection(); this.state.prediction = null; this.state.needsRefresh = true;
    const uncertain = !error?.status || error.status >= 500;
    try {
      const accepted = await this.read(id);
      if (!accepted) this.state.needsRefresh = true;
      this.state.message = uncertain
        ? 'Status aksi sempat belum pasti. Periksa state terbaru dan pilih keputusan Anda kembali.'
        : messageFor(error);
      this.state.tone = 'warning';
    } catch (readError) {
      this.fail(readError); this.state.needsRefresh = true;
      this.state.message = 'Status aksi belum pasti. ' + messageFor(readError);
    }
  }
  async submit() {
    const view = this.state.view;
    if (this.state.busy || this.state.needsRefresh || !view || this.selectionKey !== key(view)) return false;
    const action = view.legal_actions.find(option => option.action_id === this.state.selectedId);
    if (!action) return false;
    const token = this.begin('SUBMITTING_ACTION'); if (token === null) return false;
    ++this.readSequence;
    try {
      const updated = await this.api.action(view.game_id, { action_id: action.action_id, expected_turn_number: view.turn_number });
      if (!updated || typeof updated !== 'object' || updated.game_id !== view.game_id
          || !Number.isInteger(updated.turn_number) || updated.turn_number < view.turn_number) throw new HttpError(0);
      ++this.readSequence; this.setView(updated); this.clearSelection();
      this.state.prediction = null; this.state.savedNotice = null;
      if (this.presentation) {
        this.state.busy = 'PRESENTING'; this.state.mode = 'PRESENTING';
        try {
          await this.presentation.play(view, updated, frame => {
            if (token !== this.activeOperation || this.state.view !== updated) return;
            this.state.presentation = frame;
            if (frame) this.state.message = frame.message;
            this.emit();
          });
        } catch { this.presentation.cancel(); }
        if (token !== this.activeOperation) return false;
        this.state.presentation = null;
      }
      this.state.message = 'Langkah diterima. State meja sudah diperbarui.'; this.state.tone = 'success'; return true;
    } catch (error) {
      if (!error?.status || error.status >= 500 || [400, 409].includes(error.status)) await this.reconcileAction(view.game_id, error);
      else { this.clearSelection(); this.fail(error); }
      return false;
    } finally { this.finish(token); }
  }
  async predict() {
    const view = this.state.view;
    if (this.state.busy || this.state.needsRefresh || !view?.can_request_ai_prediction) return false;
    const token = this.begin('PREDICTING'); if (token === null) return false;
    ++this.readSequence;
    try {
      const result = verifiedPrediction(await this.api.predict(view.game_id, { expected_turn_number: view.turn_number }), view);
      this.state.savedNotice = result; this.state.prediction = null;
      this.emit();
      try {
        const verified = await this.read(view.game_id);
        if (verified && key(result) === key(this.state.view) && this.state.view.can_request_ai_prediction) {
          this.state.prediction = result;
          this.state.message = result.reused ? 'Prediksi tersimpan sebelumnya dipakai ulang.' : 'Prediksi tersimpan. Keputusan langkah tetap milik Anda.';
          this.state.tone = 'success';
        } else {
          this.state.message = 'Prediksi tersimpan untuk giliran sebelumnya. Lihat detailnya di History.';
          this.state.tone = 'warning';
        }
      } catch (readError) {
        this.fail(readError); this.state.needsRefresh = true;
        this.state.message = 'Prediksi tersimpan. State terkini belum dapat diverifikasi. ' + messageFor(readError);
        this.state.tone = 'warning';
      }
      return true;
    } catch (error) {
      this.state.prediction = null;
      if (error?.status === 409) await this.reconcileAction(view.game_id, error);
      else this.fail(error);
      return false;
    }
    finally { this.finish(token); }
  }
}
