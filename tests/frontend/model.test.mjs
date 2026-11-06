import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { view } from './fixtures.mjs';
async function model() {
  const url = new URL('../../app/static/phase4/model.mjs', import.meta.url);
  assert.ok(existsSync(url), 'The board/selection projection feature is missing');
  return import(url.href);
}
for (let human = 0; human < 4; human++) {
  test('human seat '+human+' stays bottom with right/top/left relative opponents', async () => {
    const { projectSeats } = await model();
    const seats = projectSeats(view({ human_seat: human }));
    assert.equal(seats.length, 4);
    for (const seat of seats) assert.equal(seat.position, ['bottom','right','top','left'][(seat.seat-human+4)%4]);
    assert.equal(seats.find(seat => seat.position === 'bottom').seat, human);
  });
}
test('projection shows only human faces and public rivers/melds, hiding opponent AnGang', async () => {
  const { projectSeats } = await model();
  const source = view(); const human = source.human_seat; const bot = (human+1)%4;
  source.seat_public_states[bot].concealed_hand = ['J1','J2']; // hostile/private extra ignored
  source.seat_public_states[bot].melds = [{ pack_type:'ANGANG', tile:'J3', offer:0 }];
  source.seat_public_states[bot].discards = ['W1','B2'];
  const seats = projectSeats(source);
  assert.deepEqual(seats.find(s => s.seat === human).hand, source.own_hand);
  const opponent = seats.find(s => s.seat === bot);
  assert.ok(opponent.hand.every(code => code === 'back'));
  assert.equal(opponent.hand.length, source.seat_public_states[bot].concealed_count);
  assert.deepEqual(opponent.melds[0].tiles, ['back','back','back','back']);
  assert.deepEqual(opponent.discards, ['W1','B2']);
  assert.ok(!JSON.stringify(opponent).includes('concealed_hand'));
});
test('meld projection follows public middle tile and preserves unknown concealment', async () => {
  const { meldTiles } = await model();
  assert.deepEqual(meldTiles({ pack_type:'CHI', tile:'T3' }, false), ['T2','T3','T4']);
  assert.deepEqual(meldTiles({ pack_type:'PENG', tile:'B2' }, false), ['B2','B2','B2']);
  assert.deepEqual(meldTiles({ pack_type:'GANG', tile:'J1' }, false), ['J1','J1','J1','J1']);
  assert.deepEqual(meldTiles({ pack_type:'ANGANG', tile:null }, false), ['back','back','back','back']);
  assert.deepEqual(meldTiles({ pack_type:'ANGANG', tile:'W4' }, true), ['W4','W4','W4','W4']);
});
test('discard selection uses a supplied Play option rather than a hand index', async () => {
  const { discardForTile } = await model();
  const source = view();
  assert.equal(discardForTile(source, 'T2').action_id, 12);
  assert.equal(discardForTile(source, 'H1'), null);
  source.legal_actions = source.legal_actions.filter(a => a.tile !== 'T2');
  assert.equal(discardForTile(source, 'T2'), null);
});
test('settings accept exact safe seed boundary and null random seed', async () => {
  const { parseSettings } = await model();
  assert.deepEqual(parseSettings({ humanSeat:'3', wind:'2', seed:'9007199254740991', flowers:true }),
    { human_seat:3, prevalent_wind:2, seed:Number.MAX_SAFE_INTEGER, include_flowers:true });
  assert.equal(parseSettings({ humanSeat:'0',wind:'0',seed:'',flowers:false }).seed, null);
  for (const seed of ['9007199254740992','9007199254740993','-1','1.5','NaN','1e9']) {
    assert.throws(() => parseSettings({ humanSeat:'0',wind:'0',seed,flowers:false }));
  }
});
test('settings reject out of range seats and nonboolean flower options', async () => {
  const { parseSettings } = await model();
  for (const changes of [{ humanSeat:'4' },{ wind:'-1' },{ flowers:'true' }]) {
    assert.throws(() => parseSettings({ humanSeat:'0',wind:'0',seed:'',flowers:false,...changes }));
  }
});
test('round presentation handles draws, seat zero and actual score deltas without scoring', async () => {
  const { roundPresentation } = await model();
  assert.equal(roundPresentation(view()), null);
  const result = { ending:'ron',winner_seat:0,discarder_seat:1,total_fan:9,win_tile:'B7',fans:[],score_deltas:[33,-17,-8,-8] };
  const shown = roundPresentation(view({ status:'FINISHED',round_result:result }));
  assert.equal(shown.winner, 0); assert.equal(shown.discarder, 1);
  assert.deepEqual(shown.scoreDeltas, result.score_deltas);
  const draw = roundPresentation(view({ status:'FINISHED',round_result:{...result,ending:'draw',winner_seat:null,discarder_seat:null,win_tile:null,total_fan:0,score_deltas:[0,0,0,0]} }));
  assert.equal(draw.winner, null); assert.match(draw.title, /tanpa pemenang/i);
});
