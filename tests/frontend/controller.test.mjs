import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { view,prediction,deferred,fakeApi } from './fixtures.mjs';
async function controller(api) {
  const url=new URL('../../app/static/phase4/controller.mjs',import.meta.url);
  assert.ok(existsSync(url),'The guarded game controller feature is missing');
  const { GameController }=await import(url.href);
  const instance=new GameController({api});await instance.create({});
  return instance;
}
test('duplicate hand tiles select one actual server action and submit current turn',async () => {
  const api=fakeApi();const c=await controller(api);
  assert.equal(c.selectTile(3),true);assert.equal(c.state.selectedId,12);
  assert.equal(c.selectTile(2),true);assert.equal(c.state.selectedId,12);
  assert.equal(c.selectAction(234),false);
  await c.submit();
  assert.deepEqual(api.requests.find(r=>r.name==='action').args,[view().game_id,{action_id:12,expected_turn_number:4}]);
  assert.equal(c.state.selectedId,null);assert.equal(c.state.prediction,null);
});
test('only supplied action ids can be selected, including all claim and Kong types',async () => {
  const options=['Pass','Hu','Chi','Peng','Gang','AnGang','BuGang'].map((kind,i)=>({action_id:[0,1,36,99,133,167,201][i],action_type:kind,label:kind,tile:'W1',meld_tiles:['W1','W1','W1']}));
  const api=fakeApi({createGame:()=>view({legal_actions:options,status:'WAITING_HUMAN_CLAIM'})});const c=await controller(api);
  for(const action of options){assert.equal(c.selectAction(action.action_id),true);assert.equal(c.state.selectedId,action.action_id);}
  assert.equal(c.selectAction(37),false);assert.equal(c.selectAction(-1),false);
});
test('busy mutation guard prevents duplicate submissions and optimistic hand removal',async () => {
  const pending=deferred();const api=fakeApi({action:()=>pending.promise});const c=await controller(api);
  c.selectTile(0);const oldHand=c.state.view.own_hand.slice();
  const first=c.submit();const second=c.submit();
  assert.equal(api.requests.filter(r=>r.name==='action').length,1);
  assert.deepEqual(c.state.view.own_hand,oldHand);assert.equal(c.state.busy,'SUBMITTING_ACTION');
  pending.resolve(view({turn_number:20}));await Promise.all([first,second]);
  assert.equal(c.state.busy,null);
});
test('old GET responses cannot overwrite newer authoritative state',async () => {
  const first=deferred(),second=deferred();let count=0;
  const api=fakeApi({getGame:()=>++count===1?first.promise:second.promise});const c=await controller(api);
  const older=c.refresh(),newer=c.refresh();
  second.resolve(view({turn_number:20}));await newer;
  first.resolve(view({turn_number:10}));await older;
  assert.equal(c.state.view.turn_number,20);assert.equal(c.state.busy,null);
});
test('an old GET completion cannot clear the busy guard of a newer pending GET',async () => {
  const first=deferred(),second=deferred();let count=0;
  const api=fakeApi({getGame:()=>++count===1?first.promise:second.promise});const c=await controller(api);
  const older=c.refresh(),newer=c.refresh();first.resolve(view({turn_number:10}));await older;
  assert.equal(c.state.view.turn_number,4);assert.equal(c.state.busy,'REFRESHING');
  second.resolve(view({turn_number:20}));await newer;assert.equal(c.state.busy,null);
});
test('409 refreshes state and requires new selection without retrying action',async () => {
  const api=fakeApi({action:()=>{throw {status:409};},getGame:()=>view({turn_number:20})});const c=await controller(api);
  c.selectTile(0);await c.submit();
  assert.equal(c.state.view.turn_number,20);assert.equal(c.state.selectedId,null);
  assert.equal(api.requests.filter(r=>r.name==='action').length,1);
  assert.equal(api.requests.filter(r=>r.name==='getGame').length,1);
});
test('uncertain action outcome reconciles GET and never blindly resubmits',async () => {
  const api=fakeApi({action:()=>{throw new TypeError('network lost');},getGame:()=>view({turn_number:20})});const c=await controller(api);
  c.selectTile(0);await c.submit();
  assert.equal(c.state.view.turn_number,20);assert.equal(c.state.selectedId,null);
  assert.match(c.state.message,/belum pasti|tidak pasti/);
  assert.equal(api.requests.filter(r=>r.name==='action').length,1);
});
test('prediction is explicit, uses current turn, preserves Top3 order and never executes action',async () => {
  const api=fakeApi();const c=await controller(api);
  assert.equal(api.requests.filter(r=>r.name==='predict').length,0);
  await c.predict();
  assert.deepEqual(api.requests.find(r=>r.name==='predict').args,[view().game_id,{expected_turn_number:4}]);
  assert.deepEqual(c.state.prediction.top3,prediction().top3);
  assert.equal(c.state.savedNotice.prediction_id,prediction().prediction_id);
  assert.equal(api.requests.filter(r=>r.name==='action').length,0);
  assert.equal(c.state.view.turn_number,4);
});
test('another tab advancing before prediction verification leaves a saved historical notice only',async () => {
  const api=fakeApi({getGame:()=>view({turn_number:20})});const c=await controller(api);await c.predict();
  assert.equal(c.state.view.turn_number,20);assert.equal(c.state.prediction,null);
  assert.equal(c.state.savedNotice.prediction_id,prediction().prediction_id);
  assert.match(c.state.message,/tersimpan/);
});
test('committed prediction followed by failed GET is never falsely labelled unsaved or highlighted',async () => {
  const api=fakeApi({getGame:()=>{throw {status:503};}});const c=await controller(api);await c.predict();
  assert.equal(c.state.prediction,null);assert.equal(c.state.savedNotice.prediction_id,prediction().prediction_id);
  assert.match(c.state.message,/tersimpan/);assert.equal(c.state.needsRefresh,true);
});
test('failed prediction saving503 never produces a saved-success notice',async () => {
  const api=fakeApi({predict:()=>{throw {status:503};}});const c=await controller(api);await c.predict();
  assert.equal(c.state.prediction,null);assert.equal(c.state.savedNotice,null);
  assert.equal(api.requests.filter(r=>r.name==='action').length,0);
});
test('changing turn clears old prediction and selection; changing game clears saved context',async () => {
  let current=view();const api=fakeApi({getGame:()=>current,createGame:()=>current});const c=await controller(api);
  c.selectTile(0);await c.predict();assert.ok(c.state.prediction);
  current=view({turn_number:20});await c.refresh();
  assert.equal(c.state.prediction,null);assert.equal(c.state.selectedId,null);
  current=view({game_id:'22222222-2222-4222-8222-222222222222'});await c.create({});
  assert.equal(c.state.savedNotice,null);assert.equal(c.state.selectedId,null);
});
test('404 and401 clear active controls without fabricating a replacement identity',async () => {
  for(const status of [404,401]){
    const api=fakeApi({getGame:()=>{throw {status};}});const c=await controller(api);await c.refresh();
    assert.equal(c.state.view,null);assert.equal(c.state.mode,'EXPIRED');
    assert.equal(c.state.selectedId,null);assert.equal(c.state.prediction,null);
    assert.equal(api.requests.filter(r=>r.name==='createGame').length,1);
  }
});
test('reused predictions preserve saved identity and server reused flag',async () => {
  const api=fakeApi({predict:()=>prediction({reused:true})});const c=await controller(api);await c.predict();
  assert.equal(c.state.prediction.reused,true);assert.equal(c.state.savedNotice.prediction_id,prediction().prediction_id);
});
test('prediction409 reconciles current server turn and never retries prediction',async () => {
  const api=fakeApi({predict:()=>{throw {status:409};},getGame:()=>view({turn_number:20})});
  const c=await controller(api);
  assert.equal(await c.predict(),false);
  assert.equal(c.state.view.turn_number,20);assert.equal(c.state.prediction,null);
  assert.equal(api.requests.filter(r=>r.name==='predict').length,1);
  assert.equal(api.requests.filter(r=>r.name==='getGame').length,1);
});
test('manual refresh clears current advice immediately and keeps saved identity on503',async () => {
  let failed=false;const api=fakeApi({getGame:()=>{if(failed)throw {status:503};return view();}});
  const c=await controller(api);const frames=[];c.render=state=>frames.push(state);await c.predict();
  const id=c.state.savedNotice.prediction_id;assert.ok(c.state.prediction);failed=true;
  await c.refresh();
  assert.equal(c.state.needsRefresh,true);assert.equal(c.state.prediction,null);
  assert.equal(frames.at(-1).prediction,null);assert.equal(c.state.savedNotice.prediction_id,id);
});
test('repeat prediction does not leave rendered old advice during delayed state confirmation',async () => {
  const waiting=deferred();let delayed=false;
  const api=fakeApi({getGame:()=>delayed?waiting.promise:view()});const c=await controller(api);await c.predict();
  const frames=[];c.render=state=>frames.push(state);delayed=true;
  const request=c.predict();await Promise.resolve();await Promise.resolve();
  assert.equal(c.state.busy,'PREDICTING');assert.equal(frames.at(-1).prediction,null);
  assert.ok(frames.at(-1).savedNotice.prediction_id);
  waiting.resolve(view());await request;assert.ok(c.state.prediction);
});
for(const [label,changes] of [
  ['empty',null],['missing identity',{prediction_id:undefined}],['unsafe identity',{prediction_id:'../other'}],
  ['wrong game',{game_id:'22222222-2222-4222-8222-222222222222'}],['wrong turn',{turn_number:20}],
  ['wrong seat',{seat:2}],['missing model',{model_version:''}],['missing phase',{turn_phase:'OTHER'}],
  ['illegal recommended action',{recommended_action_id:234}],['empty Top3',{top3:[]}],
  ['invalid score',{top3:[{...prediction().top3[0],score:NaN}]}],
  ['mismatched Top3',{top3:[{...prediction().top3[0],tile:'H1'}]}],['missing scores',{scores:[]}],
])test('malformed prediction success '+label+' cannot claim saved identity or display advice',async()=>{
  const api=fakeApi({predict:()=>changes===null?{}:prediction(changes)});const c=await controller(api);
  assert.equal(await c.predict(),false);assert.equal(c.state.prediction,null);assert.equal(c.state.savedNotice,null);
  assert.equal(c.state.needsRefresh,true);assert.doesNotMatch(c.state.message,/Prediksi tersimpan/);
});

for(const [label,response] of [
  ['cross-game',()=>view({game_id:'22222222-2222-4222-8222-222222222222',turn_number:1})],
  ['regressed turn',()=>view({turn_number:3})],
  ['missing object',()=>null],
  ['noninteger turn',()=>view({turn_number:4.5})],
  ['invalid structure',()=>view({turn_number:20,own_hand:null})],
])test('P4-A01 rejects '+label+' action success and reconciles only the original game',async()=>{
  const authoritative=view({turn_number:20});
  const api=fakeApi({action:response,getGame:()=>authoritative});const c=await controller(api);
  const urls=[],frames=[];c.onGame=id=>urls.push(id);c.render=state=>frames.push(state);
  assert.equal(c.selectTile(0),true);
  assert.equal(await c.submit(),false);
  assert.deepEqual(c.state.view,authoritative);assert.equal(c.gameId,view().game_id);
  assert.ok(frames.every(state=>state.view?.game_id===view().game_id));
  assert.ok(urls.every(id=>id===view().game_id));assert.equal(c.urlGame,view().game_id);
  assert.doesNotMatch(c.state.message,/Langkah diterima/);assert.match(c.state.message,/belum pasti/);
  assert.equal(c.state.selectedId,null);assert.equal(c.state.busy,null);
  assert.deepEqual(api.requests.filter(request=>request.name==='action').map(request=>request.args),
    [[view().game_id,{action_id:6,expected_turn_number:4}]]);
  assert.deepEqual(api.requests.filter(request=>request.name==='getGame').map(request=>request.args),[[view().game_id]]);
});

test('P4-A01 failed reconciliation keeps the original action outcome uncertain and blocks another mutation',async()=>{
  const api=fakeApi({action:()=>view({game_id:'22222222-2222-4222-8222-222222222222'}),getGame:()=>{throw {status:503};}});
  const c=await controller(api);c.selectTile(0);
  assert.equal(await c.submit(),false);assert.equal(c.gameId,view().game_id);
  assert.equal(c.state.view.game_id,view().game_id);assert.equal(c.state.view.turn_number,4);
  assert.equal(c.state.needsRefresh,true);assert.match(c.state.message,/Status aksi belum pasti/);
  assert.equal(c.selectTile(0),false);assert.equal(await c.submit(),false);
  assert.equal(api.requests.filter(request=>request.name==='action').length,1);
  assert.deepEqual(api.requests.filter(request=>request.name==='getGame').map(request=>request.args),[[view().game_id]]);
});

for(const [label,initial,updated] of [
  ['advancing',()=>view(),()=>view({turn_number:20})],
  ['same turn',()=>view(),()=>view()],
  ['finished',()=>view(),()=>view({turn_number:20,status:'FINISHED',legal_actions:[],can_request_ai_prediction:false,
    round_result:{ending:'draw',winner_seat:null,discarder_seat:null,win_tile:null,total_fan:0,fans:[],score_deltas:[0,0,0,0],qianggang:false}})],
  ['claim transition',()=>view({status:'WAITING_HUMAN_CLAIM',can_request_ai_prediction:false,
    legal_actions:[{action_id:0,action_type:'Pass',tile:null,meld_tiles:null,label:'Pass'}]}),()=>view({turn_number:20})],
])test('P4-A01 accepts valid '+label+' response without action retry or reconciliation GET',async()=>{
  const expected=updated();const api=fakeApi({createGame:initial,action:()=>expected});const c=await controller(api);
  if(c.state.view.can_request_ai_prediction)await c.predict();
  const reads=api.requests.filter(request=>request.name==='getGame').length;
  c.selectAction(c.state.view.legal_actions[0].action_id);
  assert.equal(await c.submit(),true);assert.deepEqual(c.state.view,expected);
  assert.equal(c.state.selectedId,null);assert.equal(c.state.prediction,null);assert.equal(c.state.busy,null);
  assert.match(c.state.message,/Langkah diterima/);
  assert.equal(api.requests.filter(request=>request.name==='action').length,1);
  assert.equal(api.requests.filter(request=>request.name==='getGame').length,reads);
});

for(const label of ['ascending Top3','incorrect action/class mapping'])test('P4-A02 rejects '+label+' without sorting, trusting a save, or playing',async()=>{
  const result=prediction();
  if(label==='ascending Top3'){
    result.top3.reverse();const first=result.top3[0];
    result.recommended_tile=first.tile;result.recommended_action_id=first.action_id;result.recommended_class_index=first.class_index;
  }else{
    const [first,second]=result.top3;const left=first.class_index,right=second.class_index;
    [first.class_index,second.class_index]=[right,left];
    [result.scores[left],result.scores[right]]=[result.scores[right],result.scores[left]];
    result.recommended_class_index=first.class_index;
  }
  // All unrelated score/membership/first-recommendation checks stay coherent.
  for(const suggestion of result.top3){
    assert.equal(suggestion.score,result.scores[suggestion.class_index]);
    assert.ok(view().legal_actions.some(action=>action.action_id===suggestion.action_id&&action.tile===suggestion.tile));
  }
  assert.equal(result.top3[0].class_index,result.recommended_class_index);
  const before=structuredClone(result);const api=fakeApi({predict:()=>result});const c=await controller(api);
  assert.equal(await c.predict(),false);assert.equal(c.state.prediction,null);assert.equal(c.state.savedNotice,null);
  assert.equal(c.state.needsRefresh,true);assert.doesNotMatch(c.state.message,/Prediksi tersimpan|pasti gagal/);
  assert.equal(api.requests.filter(request=>request.name==='action').length,0);
  assert.equal(api.requests.filter(request=>request.name==='predict').length,1);
  assert.equal(api.requests.filter(request=>request.name==='getGame').length,0);
  assert.deepEqual(result,before);
});

for(const tied of [false,true])test('P4-A02 accepts '+(tied?'equal adjacent scores':'valid descending Top3')+' unchanged',async()=>{
  const result=prediction();
  if(tied){result.top3[1].score=result.top3[0].score;result.scores[result.top3[1].class_index]=result.top3[1].score;}
  const before=structuredClone(result);const api=fakeApi({predict:()=>result});const c=await controller(api);
  assert.equal(await c.predict(),true);assert.deepEqual(c.state.prediction,before);
  assert.equal(c.state.savedNotice.prediction_id,before.prediction_id);assert.deepEqual(result,before);
  assert.equal(api.requests.filter(request=>request.name==='action').length,0);
});
