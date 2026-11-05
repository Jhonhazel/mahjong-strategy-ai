"""Real HTTP → engine → v3 → PostgreSQL full-round acceptance demonstration."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import uuid

import numpy as np
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.bot_service import ShantenHeuristicBot
from app.settings import ROOT, Settings, V3_SHA256
from training.dataset_loader import file_sha256
from training.reporting import write_json_report
from training.train_mlp import weights_sha256


def _csrf(client):
    response=client.get('/api/session');assert response.status_code==200
    return {'X-CSRF-Token':response.json()['csrf_token']}


def _state_hash(state):
    return hashlib.sha256(state.obs.tobytes()+state.legal_mask.tobytes()+state.legal_discard_mask.tobytes()).hexdigest()


def run_workflow(settings,output,seeds=(42,43)):
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Use a new evidence filename; existing evidence is preserved')
    for old in ('artifacts/phase2','artifacts/phase2_1','artifacts/phase2_2','datasets','docs/evidence/phase2_1','docs/evidence/phase2_2'):
        if output.is_relative_to(ROOT/old):raise ValueError('Cannot overwrite older phase evidence')
    write_json_report(output,{'status':'RUNNING'})
    try:
        rounds=[];initial_weights=None;last_weights=None;model_version=None
        for seed in seeds:
            app=create_app(settings)
            with TestClient(app) as browser:
                headers=_csrf(browser)
                response=browser.post('/api/games',json={'seed':seed,'human_seat':1},headers=headers)
                assert response.status_code==201
                view=response.json();gid=view['game_id'];resources=app.state.resources;legacy=resources.games.games
                model_version=resources.runtime.ai.model_version
                weight_hash=weights_sha256(resources.runtime.ai._model.state_dict())
                if initial_weights is None:initial_weights=weight_hash
                assert weight_hash==initial_weights and file_sha256(settings.model_checkpoint_path)==V3_SHA256
                helper=ShantenHeuristicBot();rng=random.Random(seed);predictions=[];seen_phases=set();actions=0;claim_checked=False
                for _ in range(400):
                    assert browser.get('/api/games/'+gid).json()==view
                    if view['status']=='FINISHED':break
                    public=legacy.get_player_view(gid)
                    if view['status']=='WAITING_HUMAN_DISCARD':
                        state=legacy.get_human_encoded_turn(gid)
                        # Verification-only inspection of phase, never hidden tiles or wall data.
                        actual_phase=legacy._sessions[gid].engine.phase
                        if len(predictions)<2 or actual_phase not in seen_phases:
                            arrays=(state.obs.copy(),state.legal_mask.copy(),state.legal_discard_mask.copy())
                            before_hash=_state_hash(state)
                            response=browser.post('/api/games/'+gid+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
                            assert response.status_code==201
                            saved=response.json();assert saved['turn_phase']==actual_phase
                            assert saved['model_version']==model_version and saved['recommended_action_id']==saved['recommended_class_index']+2
                            assert all(state.legal_mask[item['action_id']] and item['action_id']==item['class_index']+2 for item in saved['top3'])
                            assert len(saved['top3'])==min(3,int(state.legal_discard_mask.sum()))
                            after=legacy.get_human_encoded_turn(gid)
                            assert all(np.array_equal(a,b) for a,b in zip(arrays,(after.obs,after.legal_mask,after.legal_discard_mask)))
                            assert legacy.get_player_view(gid)==public and after.turn_number==state.turn_number
                            assert browser.get('/api/games/'+gid).json()==view
                            assert weight_hash==weights_sha256(resources.runtime.ai._model.state_dict())
                            owner=resources.visitors.load(browser.cookies.get('mahjong_visitor')).owner_key
                            record=resources.history.get(owner,uuid.UUID(saved['prediction_id']))
                            assert record is not None and record.input_snapshot['obs']==arrays[0].tolist()
                            assert record.input_snapshot['legal_mask']==arrays[1].tolist()
                            assert record.input_snapshot['legal_discard_mask']==arrays[2].tolist()
                            assert record.output_snapshot['scores']==saved['scores'] and record.output_snapshot['top3']==saved['top3']
                            assert record.created_at.tzinfo is not None
                            detail=browser.get('/api/predictions/'+saved['prediction_id'])
                            assert detail.status_code==200 and detail.json()['output_snapshot']['top3']==saved['top3']
                            repeated=browser.post('/api/games/'+gid+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
                            assert repeated.status_code==200 and repeated.json()['reused'] and repeated.json()['prediction_id']==saved['prediction_id']
                            predictions.append({'prediction_id':saved['prediction_id'],'turn_number':saved['turn_number'],
                                                'turn_phase':saved['turn_phase'],'recommended_tile':saved['recommended_tile'],
                                                'top3':saved['top3'],'input_sha256_before':before_hash,
                                                'input_sha256_after':_state_hash(after),'persisted_state_digest':record.state_digest,
                                                'created_at':record.created_at.isoformat(),'model_version':model_version})
                            seen_phases.add(actual_phase)
                        chosen_id=helper.select_action(state,public.own_hand,public.seat_public_states[1].melds,rng)
                    else:
                        if not claim_checked:
                            failed=browser.post('/api/games/'+gid+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
                            assert failed.status_code==409 and browser.get('/api/games/'+gid).json()==view
                            claim_checked=True
                        choices=[a for a in public.legal_actions if a.action_type=='Hu'] or [a for a in public.legal_actions if a.action_type in ('Chi','Peng')] or list(public.legal_actions)
                        chosen_id=choices[0].action_id
                    response=browser.post('/api/games/'+gid+'/actions',json={'action_id':chosen_id,'expected_turn_number':view['turn_number']},headers=headers)
                    assert response.status_code==200
                    view=response.json();actions+=1
                assert view['status']=='FINISHED' and view['round_result']['ending'] in ('zimo','ron','draw')
                authoritative=legacy.get_player_view(gid).round_result
                assert view['round_result']['score_deltas']==list(authoritative.score_deltas)
                assert view['round_result']['ending']==authoritative.ending
                assert 'revealed_hands' not in view['round_result'] and len(predictions)>=2
                removed=predictions[0]['prediction_id'];remaining=predictions[1]['prediction_id']
                assert browser.delete('/api/predictions/'+removed,headers=headers).status_code==204
                assert browser.get('/api/predictions/'+removed).status_code==404
                assert browser.get('/api/games/'+gid).json()==view
                cookies=dict(browser.cookies)
                last_weights=weights_sha256(resources.runtime.ai._model.state_dict())
                assert initial_weights==last_weights and file_sha256(settings.model_checkpoint_path)==V3_SHA256
            with TestClient(create_app(settings)) as restarted:
                restarted.cookies.update(cookies)
                restored=restarted.get('/api/predictions/'+remaining)
                assert restored.status_code==200
                assert restored.json()['output_snapshot']['top3']==predictions[1]['top3']
                assert restarted.get('/api/games/'+gid).status_code==404
                total=restarted.get('/api/predictions').json()['total'];assert total>=1
            rounds.append({'seed':seed,'game_id':gid,'actions':actions,'predictions':predictions,'final_view':view,
                           'deleted_prediction_id':removed,'deleted_prediction_status':404,'history_after_restart':total,
                           'game_after_restart_status':404,'claim_prediction_unavailable_checked':claim_checked})
        assert {'SELF_TURN','POST_MELD_DISCARD'}.issubset({p['turn_phase'] for r in rounds for p in r['predictions']})
        result={'status':'PASS','model_version':model_version,'checkpoint_sha256':V3_SHA256,
                'weights_before':initial_weights,'weights_after':last_weights,'rounds':rounds,
                'database':'Real PostgreSQL','transport':'FastAPI TestClient ASGI HTTP',
                'policy':'Deterministic independent human-side test policy; model suggestions never auto-executed; no win-rate claim'}
        write_json_report(output,result);return result
    except BaseException as error:
        write_json_report(output,{'status':'FAIL','failure_type':type(error).__name__,'message':'Acceptance workflow failed; inspect the matching test/command evidence'})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/phase3/end_to_end_demo.json')
    args=parser.parse_args();result=run_workflow(Settings(),args.output)
    print(json.dumps({'status':result['status'],'rounds':len(result['rounds']),'model_version':result['model_version']},indent=2))


if __name__=='__main__':main()
