from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import time

import pytest

from tests.phase3_support import postgres_engine, postgres_url, web_settings
from tests.test_phase3_http import client, csrf, game

pytestmark=pytest.mark.integration


def test_concurrent_http_predictions_reuse_one_committed_record(client):
    headers=csrf(client);view=game(client,headers);url='/api/games/'+view['game_id']+'/predict'
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _:client.post(url,json={'expected_turn_number':view['turn_number']},headers=headers),range(4)))
    assert sorted(r.status_code for r in responses)==[200,200,200,201]
    assert len({r.json()['prediction_id'] for r in responses})==1
    assert client.get('/api/predictions').json()['total']==1
    assert client.get('/api/games/'+view['game_id']).json()==view


def test_prediction_action_serialization_does_not_block_another_game(client,monkeypatch):
    headers=csrf(client);view=game(client,headers);gid=view['game_id'];resources=client.app.state.resources
    entered=threading.Event();release=threading.Event();original=resources.history.save
    def blocked(owner,snapshot):
        if str(snapshot.game_id)==gid:
            entered.set();assert release.wait(5),'Test barrier timed out'
        return original(owner,snapshot)
    monkeypatch.setattr(resources.history,'save',blocked)
    with ThreadPoolExecutor(max_workers=3) as pool:
        prediction=pool.submit(client.post,f'/api/games/{gid}/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
        try:
            assert entered.wait(2)
            independent=pool.submit(game,client,headers,seed=43)
            second=independent.result(timeout=2)
            assert second['game_id']!=gid
            action=pool.submit(client.post,f'/api/games/{gid}/actions',json={'action_id':view['legal_actions'][0]['action_id'],'expected_turn_number':view['turn_number']},headers=headers)
            time.sleep(.05);assert not action.done()
        finally:release.set()
        saved=prediction.result(timeout=3);advanced=action.result(timeout=3)
    assert saved.status_code==201 and advanced.status_code==200
    assert saved.json()['turn_number']==view['turn_number'] and advanced.json()['turn_number']>view['turn_number']
    detail=client.get('/api/predictions/'+saved.json()['prediction_id']).json()
    assert detail['input_snapshot']['turn_number']==view['turn_number']


def test_inflight_prediction_is_not_evicted_by_idle_expiry_or_other_game_sweep(client,monkeypatch):
    headers=csrf(client);resources=client.app.state.resources;resources.games.ttl=.5
    view=game(client,headers);gid=view['game_id'];entered=threading.Event();release=threading.Event();original=resources.history.save
    def blocked(owner,snapshot):
        entered.set();assert release.wait(5),'Test barrier timed out'
        return original(owner,snapshot)
    monkeypatch.setattr(resources.history,'save',blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        prediction=pool.submit(client.post,f'/api/games/{gid}/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
        try:
            assert entered.wait(2);time.sleep(.6)
            independent=pool.submit(game,client,headers,seed=43)
            assert independent.result(timeout=2)['game_id']!=gid
        finally:release.set()
        assert prediction.result(timeout=3).status_code==201
    assert client.get('/api/games/'+gid).json()==view


@pytest.mark.parametrize('violation',['illegal_result','mutated_input','empty_discard_mask'])
def test_failed_prediction_invariants_never_insert_a_fake_history_row(client,monkeypatch,violation):
    headers=csrf(client);view=game(client,headers);resources=client.app.state.resources;legacy=resources.games.games
    original_state=legacy.get_human_encoded_turn;original_predict=resources.runtime.ai.predict
    if violation=='empty_discard_mask':
        import numpy as np
        def unavailable(gid):
            state=original_state(gid)
            return replace(state,legal_discard_mask=np.zeros(34,dtype=bool))
        monkeypatch.setattr(legacy,'get_human_encoded_turn',unavailable)
    elif violation=='mutated_input':
        monkeypatch.setattr(legacy,'get_human_encoded_turn',lambda gid:replace(original_state(gid),obs=original_state(gid).obs.copy()))
        def mutated(state):
            result=original_predict(state);state.obs[0,0,0]=1-state.obs[0,0,0];return result
        monkeypatch.setattr(resources.runtime.ai,'predict',mutated)
    else:
        monkeypatch.setattr(resources.runtime.ai,'predict',lambda state:replace(original_predict(state),recommended_action_id=235))
    response=client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
    assert response.status_code==(409 if violation=='empty_discard_mask' else 503)
    assert client.get('/api/predictions').json()['total']==0
    assert client.get('/api/games/'+view['game_id']).json()==view


def test_api_mutation_does_not_create_a_session_and_cross_site_bootstrap_is_rejected(client):
    assert client.post('/api/games',json={}).status_code==401
    assert client.cookies.get('mahjong_visitor') is None
    response=client.get('/api/session',headers={'Sec-Fetch-Site':'cross-site','Origin':'https://other.invalid'})
    assert response.status_code==403 and 'set-cookie' not in response.headers
    assert client.cookies.get('mahjong_visitor') is None


def test_reentrant_lifespan_rejected_without_disrupting_the_running_app(web_settings,postgres_engine):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app=create_app(web_settings)
    with TestClient(app) as first:
        existing=app.state.resources
        with pytest.raises(RuntimeError,match='already active'):
            with TestClient(app):pass
        assert app.state.resources is existing and first.get('/health/ready').status_code==200
    assert app.state.resources is None
