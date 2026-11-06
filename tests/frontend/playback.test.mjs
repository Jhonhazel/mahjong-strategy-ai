import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { view, fakeApi, prediction } from './fixtures.mjs';
import { GameController } from '../../app/static/phase4/controller.mjs';
const url = new URL('../../app/static/phase4/playback.mjs', import.meta.url);
const module = existsSync(url) ? await import(url) : {};
const feature = name => { assert.equal(typeof module[name], 'function', 'Missing public presentation '+name); return module[name]; };
function clock() {
  const tasks = new Map(); let next = 0;
  return {tasks, setTimeout(fn, ms) {const id=++next;tasks.set(id,{fn,ms});return id;},clearTimeout(id){tasks.delete(id);},
    tick(){const [id,task]=tasks.entries().next().value;tasks.delete(id);task.fn();}};
}
function changed() {const value=view({turn_number:20});value.seat_public_states[2].discards.push('W1');return value;}

test('unchanged, missing, or different-game snapshots have no invented playback',()=>{
  const delta=feature('publicUpdates');assert.deepEqual(delta(view(),view()),[]);
  assert.deepEqual(delta(null,view()),[]);assert.deepEqual(delta(view(),view({game_id:'other'})),[]);
});
test('public discard and meld deltas are grouped by relative seat with no chronology claim',()=>{
  const updated=changed();updated.seat_public_states[0].melds.push({pack_type:'PENG',tile:'B2',offer:1});
  const frames=feature('publicUpdates')(view(),updated);
  assert.equal(frames.length,2);assert.deepEqual(new Set(frames.map(f=>f.seat)),new Set([0,2]));
  assert.equal(frames.find(f=>f.seat===2).position,'right');
  assert.deepEqual(frames.find(f=>f.seat===2).newDiscards,[0]);
  assert.deepEqual(frames.find(f=>f.seat===0).newMelds,[0]);
  assert.ok(frames.every(f=>/perubahan publik/.test(f.message)));
});
test('claimed/changed rivers do not invent an append sequence or expose hidden AnGang',()=>{
  const before=view(),after=view({turn_number:20});before.seat_public_states[0].discards=['W1','W2'];after.seat_public_states[0].discards=['W2'];
  after.seat_public_states[2].melds=[{pack_type:'ANGANG',tile:'J3',offer:0}];
  after.seat_public_states[2].concealed_hand=['J1'];
  const frames=feature('publicUpdates')(before,after);
  assert.deepEqual(frames.find(f=>f.seat===0).newDiscards,[]);
  assert.ok(!JSON.stringify(frames).includes('J3')&&!JSON.stringify(frames).includes('J1'));
});
for(const speed of ['normal','fast'])test(speed+' playback is bounded, cancellable, and resolves skip',async()=>{
  const timer=clock(),frames=[];const Player=feature('PublicPlayback');const player=new Player({scheduler:timer});player.speed=speed;
  const run=player.play(view(),changed(),frame=>frames.push(frame));
  assert.equal(timer.tasks.size,1);assert.equal([...timer.tasks.values()][0].ms,speed==='normal'?600:180);
  player.cancel();await run;assert.equal(timer.tasks.size,0);const count=frames.length;await Promise.resolve();assert.equal(frames.length,count);
});
test('reduced motion or hidden page bypasses all waits',async()=>{
  for(const option of ['reducedMotion','hidden']){
    const timer=clock();const Player=feature('PublicPlayback');const player=new Player({scheduler:timer,[option]:()=>true});
    await player.play(view(),changed(),()=>assert.fail('No paced frame when motion is bypassed'));
    assert.equal(timer.tasks.size,0);
  }
});
test('normal completion clears presentation and old scheduled work cannot update a new playback',async()=>{
  const timer=clock(),frames=[];const Player=feature('PublicPlayback');const player=new Player({scheduler:timer});
  const first=player.play(view(),changed(),frame=>frames.push(['old',frame]));
  const second=player.play(view(),changed(),frame=>frames.push(['new',frame]));
  await first;assert.equal(timer.tasks.size,1);timer.tick();await second;
  assert.equal(frames.at(-1)[0],'new');assert.equal(frames.at(-1)[1],null);assert.equal(timer.tasks.size,0);
});
test('accepted authoritative state stays current while playback blocks duplicate/stale decisions',async()=>{
  const timer=clock();const Player=feature('PublicPlayback');const player=new Player({scheduler:timer});
  const api=fakeApi({action:changed});const c=new GameController({api,presentation:player});await c.create({});await c.predict();
  c.selectTile(0);const run=c.submit();await Promise.resolve();await Promise.resolve();
  assert.equal(c.state.view.turn_number,20);assert.equal(c.state.busy,'PRESENTING');assert.equal(c.state.prediction,null);
  assert.equal(c.selectTile(0),false);assert.equal(await c.submit(),false);assert.equal(await c.predict(),false);
  c.skipAnimation();await run;assert.equal(c.state.busy,null);assert.equal(timer.tasks.size,0);
  assert.equal(api.requests.filter(r=>r.name==='action').length,1);
});
for(const operation of ['create','refresh','expired'])test('playback cancels safely for '+operation,async()=>{
  const timer=clock();const Player=feature('PublicPlayback');const player=new Player({scheduler:timer});
  const api=fakeApi({action:changed});const c=new GameController({api,presentation:player});await c.create({});c.selectTile(0);
  const run=c.submit();await Promise.resolve();await Promise.resolve();
  if(operation==='create'){api.createGame=async()=>view({game_id:'22222222-2222-4222-8222-222222222222'});await c.create({});}
  else {api.getGame=async()=>{if(operation==='expired')throw {status:404};return view({turn_number:40});};await c.refresh();}
  await run;assert.equal(timer.tasks.size,0);assert.equal(c.state.busy,null);assert.equal(c.state.presentation,null);
  if(operation==='expired')assert.equal(c.state.view,null);
  else if(operation==='refresh')assert.equal(c.state.view.turn_number,40);
  else assert.equal(c.state.view.game_id,'22222222-2222-4222-8222-222222222222');
});
