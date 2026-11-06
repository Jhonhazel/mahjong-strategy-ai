import { WIND_NAMES } from './catalog.mjs';
import { tileSpec } from './tiles.mjs';

export function discardForTile(view, tile) {
  return view?.legal_actions.find(action => action.action_type === 'Play' && action.tile === tile) ?? null;
}

export function meldTiles(pack, human) {
  const count = ['GANG', 'ANGANG'].includes(pack.pack_type) ? 4 : 3;
  if (pack.tile == null || (pack.pack_type === 'ANGANG' && !human)) return Array(count).fill('back');
  const spec = tileSpec(pack.tile);
  if (spec.kind === 'unknown') return Array(count).fill('unknown');
  if (pack.pack_type === 'CHI') {
    if (!['characters', 'bamboo', 'circles'].includes(spec.kind) || spec.rank < 2 || spec.rank > 8) return Array(3).fill('unknown');
    return [spec.rank - 1, spec.rank, spec.rank + 1].map(rank => spec.code[0] + rank);
  }
  return Array(count).fill(spec.code);
}

export function projectSeats(view) {
  return view.seat_public_states.map(seat => {
    const human = seat.seat === view.human_seat;
    return {
      seat: seat.seat, human, position: ['bottom', 'right', 'top', 'left'][(seat.seat - view.human_seat + 4) % 4],
      name: human ? 'Anda' : 'Bot ' + WIND_NAMES[seat.seat],
      wind: WIND_NAMES[seat.seat], active: seat.seat === view.active_seat,
      concealedCount: seat.concealed_count,
      hand: human ? view.own_hand : Array(Math.min(14, Math.max(0, seat.concealed_count))).fill('back'),
      melds: seat.melds.map(pack => ({ type: pack.pack_type, offer: pack.offer, tiles: meldTiles(pack, human) })),
      flowers: seat.flowers, discards: seat.discards, wallRemaining: seat.wall_remaining,
    };
  });
}

export function parseSettings({ humanSeat, wind, seed, flowers }) {
  if (!/^[0-3]$/.test(String(humanSeat)) || !/^[0-3]$/.test(String(wind))) throw new Error('Pilih seat dan angin 0–3.');
  if (typeof flowers !== 'boolean') throw new Error('Pilihan bunga harus aktif atau nonaktif.');
  const raw = String(seed ?? '').trim();
  const number = raw === '' ? null : Number(raw);
  if (raw !== '' && (!/^\d+$/.test(raw) || !Number.isSafeInteger(number) || number < 0)) {
    throw new Error('Seed harus bilangan bulat 0–9.007.199.254.740.991.');
  }
  return { human_seat: Number(humanSeat), prevalent_wind: Number(wind), seed: number, include_flowers: flowers };
}

export function roundPresentation(view) {
  const result = view.round_result;
  if (!result) return null;
  const draw = result.ending === 'draw';
  return {
    title: draw ? 'Round selesai tanpa pemenang'
      : result.winner_seat === view.human_seat ? 'Anda menyelesaikan round'
      : 'Bot ' + WIND_NAMES[result.winner_seat] + ' menang',
    ending: result.ending,
    endingLabel: { zimo: 'Tarikan sendiri · Zimo', ron: 'Dari buangan · Ron', draw: 'Tanpa pemenang · Draw' }[result.ending],
    winner: result.winner_seat, discarder: result.discarder_seat, winningTile: result.win_tile,
    totalFan: result.total_fan, fans: result.fans, scoreDeltas: result.score_deltas, qianggang: result.qianggang,
  };
}
