import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { documentFixture as document, descendants, rendererDocument } from './dom_fixture.mjs';
import { view, prediction } from './fixtures.mjs';
import { projectSeats } from '../../app/static/phase4/model.mjs';

const path = new URL('../../app/static/phase4/view.mjs', import.meta.url);
const module = existsSync(path) ? await import(path) : {};
const available = name => { assert.equal(typeof module[name], 'function', 'missing presentation feature: ' + name); return module[name]; };

test('seat renderer gives opponents only backs and human exact legal buttons with duplicate indices', () => {
  const state = view();
  for (const seat of projectSeats(state)) {
    const node = available('buildSeat')(document, seat, state);
    const tiles = descendants(node).filter(item => item.getAttribute('data-code'));
    const hand = tiles.filter(item => item.tagName === 'BUTTON');
    if (!seat.human) {
      assert.equal(hand.length, 0);
      assert.equal(tiles.filter(item => item.getAttribute('data-code') === 'back').length, seat.concealedCount);
    } else {
      assert.equal(hand.length, state.own_hand.length);
      assert.deepEqual(hand.filter(item => item.getAttribute('data-code') === 'T2').map(item => item.getAttribute('data-tile-index')), ['2', '3']);
    }
  }
});

test('advisor preserves exact Top3 order and uses score preference explanation with no automatic action', () => {
  const result = prediction();
  const node = available('buildAdvice')(document, { prediction: result, savedNotice: result, view: view() });
  assert.deepEqual(descendants(node).filter(item => item.getAttribute('data-code')).map(item => item.getAttribute('data-code')), result.top3.map(item => item.tile));
  assert.match(node.textContent, /bobot rekomendasi/);
  assert.match(node.textContent, /bukan probabilitas menang/);
  const links = descendants(node).filter(item => item.tagName === 'A');
  assert.equal(links[0].getAttribute('href'), '/history/' + result.prediction_id);
  assert.equal(descendants(node).filter(item => item.tagName === 'BUTTON').length, 0);
});

test('historical saved prediction shows identity without displaying stale Top3 tile advice', () => {
  const result = prediction();
  const node = available('buildAdvice')(document, { prediction: null, savedNotice: result, view: view() });
  assert.equal(descendants(node).filter(item => item.getAttribute('data-code')).length, 0);
  assert.match(node.textContent, /tersimpan/);
  assert.equal(descendants(node).find(item => item.tagName === 'A').getAttribute('href'), '/history/' + result.prediction_id);
});

test('round renderer shows real seat zero, exact score deltas and null draw result safely', () => {
  const state = view();
  state.round_result = { ending: 'ron', winner_seat: 0, discarder_seat: 2, total_fan: 8, win_tile: 'J1',
    qianggang: false, fans: [{ fan_name_en: '<unsafe>', fan_name_zh: '测试', fan_points: 8, count: 1 }], score_deltas: [32, -8, -16, -8] };
  const node = available('buildRound')(document, state);
  assert.match(node.textContent, /Bot Timur menang/);
  assert.match(node.textContent, /Barat/);
  assert.match(node.textContent, /32/);
  assert.match(node.textContent, /<unsafe>/); // DOM text, never parsed HTML.
  assert.equal(descendants(node).filter(item => item.tagName === 'SCRIPT').length, 0);
  state.round_result = { ...state.round_result, ending: 'draw', winner_seat: null, discarder_seat: null, fans: [], score_deltas: [0, 0, 0, 0], win_tile: null };
  assert.match(available('buildRound')(document, state).textContent, /tanpa pemenang/);
});
test('expired finished view clears round result, game identity and public summary',()=>{
  const doc=rendererDocument();const render=available('createGameRenderer')(doc);
  const finished=view({status:'FINISHED',legal_actions:[],can_request_ai_prediction:false,
    round_result:{ending:'draw',winner_seat:null,discarder_seat:null,win_tile:null,total_fan:0,fans:[],score_deltas:[0,0,0,0],qianggang:false}});
  const state={view:finished,selectedId:null,selectedIndex:null,prediction:null,savedNotice:null,busy:null,message:'Selesai',tone:'info',needsRefresh:false};
  render(state);assert.match(doc.getElementById('round-result').textContent,/tanpa pemenang/);
  assert.equal(doc.getElementById('round-result').hidden,false);
  render({...state,view:null,mode:'EXPIRED',needsRefresh:true});
  assert.equal(doc.getElementById('round-result').hidden,true);
  assert.equal(doc.getElementById('round-result').textContent,'');
  assert.equal(doc.getElementById('game-id').textContent,'');
  assert.equal(doc.getElementById('public-state').textContent,'');
  assert.equal(doc.getElementById('human-hand').children.length,0);
});
test('meld label never misrepresents Chi offer position as a source seat',()=>{
  const state=view();state.seat_public_states[1].melds=[{pack_type:'CHI',tile:'T3',offer:2}];
  const node=available('buildSeat')(document,projectSeats(state).find(seat=>seat.human),state);
  const meld=descendants(node).find(item=>item.className==='meld-group');
  assert.doesNotMatch(meld.getAttribute('aria-label'),/sumber|seat|relatif/);
  assert.match(meld.getAttribute('aria-label'),/CHI/);
});
test('advisor exposes exact saved prediction identity and model provenance as text',()=>{
  const result=prediction();const node=available('buildAdvice')(document,{prediction:result,savedNotice:result,view:view()});
  assert.ok(node.textContent.includes(result.prediction_id));
  assert.ok(node.textContent.includes(result.model_version));
  assert.ok(node.textContent.includes(result.encoder_version));
});
