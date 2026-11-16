import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { rendererDocument, documentFixture, descendants } from './dom_fixture.mjs';
import { view, prediction } from './fixtures.mjs';
import { createGameRenderer, buildAdvice } from '../../app/static/phase4/view.mjs';

test('renderer works without removed action dropdown or identity panels and exposes every claim',()=>{
  const doc=rendererDocument();
  for(const id of ['legal-action','game-id','public-state'])doc.getElementById(id)?.remove();
  const state=view();
  state.legal_actions.push(...['Chi','Peng','Gang','AnGang','BuGang','Hu','Pass'].map((type,i)=>({action_id:100+i,action_type:type,tile:type==='Pass'?null:'T3',meld_tiles:type==='Chi'?['T2','T3','T4']:null})));
  const render=createGameRenderer(doc);
  const screen={view:state,selectedId:null,selectedIndex:null,busy:null,needsRefresh:false,message:'Pilih tile',tone:'info',prediction:null,savedNotice:null};
  assert.doesNotThrow(()=>render(screen));
  assert.deepEqual(descendants(doc.getElementById('claim-actions')).filter(n=>n.getAttribute('data-claim-id')).map(n=>Number(n.getAttribute('data-claim-id'))),state.legal_actions.filter(a=>a.action_type!=='Play').map(a=>a.action_id));
  assert.doesNotThrow(()=>render({...screen,view:null}));
});

test('advice keeps exact ranking and history link while hiding all internal identities',()=>{
  const result=prediction();const node=buildAdvice(documentFixture,{prediction:result,savedNotice:result,view:view()});
  assert.deepEqual(descendants(node).filter(n=>n.getAttribute('data-code')).map(n=>n.getAttribute('data-code')),result.recommendations.suggestions.map(r=>r.tile));
  for(const value of [result.prediction_id,result.game_id,result.model_version,result.encoder_version,'Identitas prediksi'])assert.ok(!node.textContent.includes(value));
  assert.equal(descendants(node).find(n=>n.tagName==='A').getAttribute('href'),'/history/'+result.prediction_id);
});

test('page entry has no stale listeners or focus for removed controls and keeps cancellation',()=>{
  const code=readFileSync(new URL('../../app/static/phase3.js',import.meta.url),'utf8');
  for(const id of ['game-seed','legal-action','playback-speed'])assert.ok(!code.includes("get('"+id+"')"));
  for(const event of ['visibilitychange','pagehide','skip-animation'])assert.ok(code.includes(event));
  assert.ok(code.includes('motion.matches'));
});
