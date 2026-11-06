import { projectSeats } from './model.mjs';

const equal = (left, right) => JSON.stringify(left) === JSON.stringify(right);

// Snapshot differences, grouped by seat; this is deliberately NOT an event log.
export function publicUpdates(before, after) {
  if (!before || !after || before.game_id !== after.game_id || after.turn_number < before.turn_number) return [];
  const previous = new Map(projectSeats(before).map(seat => [seat.seat, seat]));
  const frames = [];
  for (const seat of projectSeats(after)) {
    const old = previous.get(seat.seat); if (!old) continue;
    const melds = value => value.melds.map(pack => ({ type: pack.type, tiles: pack.tiles }));
    const changes = [];
    if (!equal(old.discards, seat.discards)) changes.push('buangan');
    if (!equal(melds(old), melds(seat))) changes.push('meld');
    if (!equal(old.flowers, seat.flowers)) changes.push('bunga');
    if (!changes.length) continue;
    const prefix = old.discards.every((code, index) => seat.discards[index] === code);
    frames.push({ seat: seat.seat, position: seat.position,
      newDiscards: prefix ? seat.discards.map((_, index) => index).slice(old.discards.length) : [],
      newMelds: seat.melds.map((_, index) => index).slice(old.melds.length),
      message: seat.name + ': perubahan publik pada ' + changes.join(', ') + '.',
    });
  }
  if (!frames.length && (before.wall_tiles_remaining !== after.wall_tiles_remaining
      || before.status !== after.status || !equal(before.round_result, after.round_result))) {
    frames.push({ seat: null, position: null, newDiscards: [], newMelds: [], message: 'Informasi meja: perubahan publik telah dikonfirmasi.' });
  }
  return frames.slice(0, 4);
}

export class PublicPlayback {
  constructor({ scheduler = globalThis, reducedMotion = () => false, hidden = () => false } = {}) {
    this.scheduler = scheduler; this.reducedMotion = reducedMotion; this.hidden = hidden;
    this.speed = 'normal'; this.generation = 0; this.pending = null;
  }
  cancel() {
    ++this.generation;
    if (this.pending) {
      this.scheduler.clearTimeout(this.pending.id); this.pending.resolve(); this.pending = null;
    }
  }
  async play(before, after, emit) {
    this.cancel(); const generation = this.generation;
    if (this.reducedMotion() || this.hidden()) return;
    for (const frame of publicUpdates(before, after)) {
      if (generation !== this.generation || this.hidden() || this.reducedMotion()) break;
      emit(frame);
      await new Promise(resolve => {
        const id = this.scheduler.setTimeout(() => { this.pending = null; resolve(); }, this.speed === 'fast' ? 180 : 600);
        this.pending = { id, resolve };
      });
    }
    if (generation === this.generation) emit(null);
  }
}
