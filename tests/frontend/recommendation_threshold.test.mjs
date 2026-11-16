import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GameController } from '../../app/static/phase4/controller.mjs';
import { buildAdvice,createGameRenderer } from '../../app/static/phase4/view.mjs';
import { rendererDocument,documentFixture,descendants } from './dom_fixture.mjs';
import { view,prediction,fakeApi } from './fixtures.mjs';
const contracts=JSON.parse(readFileSync(new URL('./recommendation_contracts.json',import.meta.url),'utf8'));
function fixture(name){const item=structuredClone(contracts.cases[name]);return {result:item.prediction,v:view({legal_actions:item.legal_actions,own_hand:item.legal_actions.map(a=>a.tile)})};}
for(const [name,count] of [['three',3],['two',2],['one',1],['empty',0]])test(name+' filtered result succeeds with exactly '+count+' cards and highlights',async()=>{
  const {result,v}=fixture(name);const api=fakeApi({createGame:()=>v,getGame:()=>v,predict:()=>result});
  const c=new GameController({api,recommendationPolicy:contracts.policy});await c.create({});
  assert.equal(await c.predict(),true);assert.equal(c.state.prediction.recommendations.suggestions.length,count);
  const node=buildAdvice(documentFixture,c.state);assert.equal(descendants(node).filter(n=>n.getAttribute('data-code')).length,count);
  const doc=rendererDocument();createGameRenderer(doc)(c.state);
  assert.equal(doc.getElementById('human-hand').querySelectorAll('.is-advised').length,count);
  assert.equal(c.selectTile(0),true);assert.notEqual(c.state.selectedId,null);
  if(!count){assert.match(node.textContent,/Belum ada saran yang memenuhi batas minimal 10% pada giliran ini\. Anda tetap dapat memilih tile yang ingin dibuang\./);assert.match(c.state.message,/Hasil analisis disimpan/);assert.doesNotMatch(c.state.message,/Saran tersimpan/);}
  else assert.deepEqual(descendants(node).filter(n=>n.getAttribute('data-code')).map(n=>n.getAttribute('data-code')),result.recommendations.suggestions.map(r=>r.tile));
});
for(const damage of ['below','missing','illegal','nan','renormalized','wrong_status','fake_empty','wrong_policy','omitted_field','raw_sum','illegal_positive','raw_nan'])test('malformed filtered response '+damage+' is an error instead of empty success',async()=>{
  const {result,v}=fixture('two');const r=result.recommendations;
  if(damage==='below')r.suggestions.push(structuredClone(result.top3[2]));
  if(damage==='missing')r.suggestions.pop();
  if(damage==='illegal')r.suggestions[0].action_id=234;
  if(damage==='nan')r.suggestions[0].score=NaN;
  if(damage==='renormalized')r.suggestions[0].score=.62/.87;
  if(damage==='wrong_status')r.status='no_suggestions';
  if(damage==='fake_empty'){r.suggestions=[];r.status='no_suggestions';}
  if(damage==='wrong_policy')r.minimum_score=.09;
  if(damage==='omitted_field')delete result.recommendations;
  if(damage==='raw_sum')result.scores[3]+=.01;
  if(damage==='illegal_positive'){result.scores[33]=.01;result.scores[3]-=.01;}
  if(damage==='raw_nan')result.scores[3]=NaN;
  const c=new GameController({api:fakeApi({createGame:()=>v,getGame:()=>v,predict:()=>result}),recommendationPolicy:contracts.policy});await c.create({});
  assert.equal(await c.predict(),false);assert.equal(c.state.prediction,null);assert.equal(c.state.savedNotice,null);assert.equal(c.state.tone,'error');
});
test('empty analysis failure cannot claim a committed save',async()=>{
  const {v}=fixture('empty');const c=new GameController({api:fakeApi({createGame:()=>v,predict:()=>{throw {status:503};}}),recommendationPolicy:contracts.policy});await c.create({});
  assert.equal(await c.predict(),false);assert.equal(c.state.savedNotice,null);assert.equal(c.state.prediction,null);assert.doesNotMatch(c.state.message,/Hasil analisis disimpan/);
});
