import copy
from concurrent.futures import ThreadPoolExecutor
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from tests.phase3_support import postgres_engine, postgres_url, web_settings
from training.train_mlp import weights_sha256

pytestmark = pytest.mark.integration


@pytest.fixture
def client(web_settings,postgres_engine):
    from app.main import create_app
    with TestClient(create_app(web_settings),raise_server_exceptions=False) as http:
        yield http


def csrf(http):
    response=http.get('/api/session');assert response.status_code==200
    return {'X-CSRF-Token':response.json()['csrf_token']}


def game(http,headers,**parameters):
    response=http.post('/api/games',json={'seed':42,'human_seat':0,**parameters},headers=headers)
    assert response.status_code==201,response.text
    return response.json()


def test_http_startup_loads_v3_once_readiness_and_cookie_flags(client,monkeypatch):
    headers=csrf(client)
    cookie=client.cookies.get('mahjong_visitor');assert cookie
    response=client.get('/api/session')
    assert response.json()['csrf_token']==headers['X-CSRF-Token']
    response=client.get('/health/live');assert response.json()=={'status':'alive'}
    assert client.get('/health/ready').status_code==200
    resources=client.app.state.resources
    assert resources.runtime.checkpoint_sha256=='ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720'
    def forbidden(*a,**k):raise AssertionError('No per-request model reload')
    monkeypatch.setattr('app.web.runtime.AIDiscardPredictionService',forbidden)
    view=game(client,headers)
    assert client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers).status_code==201
    assert client.get('/health/ready').status_code==200
    independent=TestClient(client.app,raise_server_exceptions=False)
    try:
        response=independent.get('/api/session')
        value=response.headers['set-cookie'].lower()
        assert 'httponly' in value and 'samesite=lax' in value
    finally:independent.close()


def test_http_game_ownership_validation_csrf_and_readonly_get(client):
    headers=csrf(client);view=game(client,headers);path='/api/games/'+view['game_id']
    assert client.get(path).json()==view and client.get(path).json()==view
    other=TestClient(client.app,raise_server_exceptions=False)
    try:
        other_headers=csrf(other)
        assert other.get(path).status_code==404
        assert other.post(path+'/actions',json={'action_id':2,'expected_turn_number':view['turn_number']},headers=other_headers).status_code==404
        assert other.post(path+'/predict',json={'expected_turn_number':view['turn_number']},headers=other_headers).status_code==404
    finally:other.close()
    assert client.post('/api/games',json={},headers={}).status_code==403
    assert client.post('/api/games',json={},headers={**headers,'Origin':'https://other.invalid'}).status_code==403
    assert client.post('/api/games',json={'wall':[]},headers=headers).status_code==422
    assert client.post(path+'/predict',json={'expected_turn_number':view['turn_number'],'obs':[]},headers=headers).status_code==422
    assert client.post('/api/games',content='x'*17000,headers=headers).status_code==413


def test_real_http_prediction_persists_exact_input_output_without_mutation(client):
    headers=csrf(client);view=game(client,headers);gid=view['game_id'];resources=client.app.state.resources
    state=resources.games.games.get_human_encoded_turn(gid)
    before=(state.obs.copy(),state.legal_mask.copy(),state.legal_discard_mask.copy())
    weight_hash=weights_sha256(resources.runtime.ai._model.state_dict())
    response=client.post(f'/api/games/{gid}/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
    assert response.status_code==201,response.text
    saved=response.json();assert not saved['reused']
    assert saved['model_version']==resources.runtime.ai.model_version
    assert saved['recommended_action_id']==saved['recommended_class_index']+2
    assert all(state.legal_mask[item['action_id']] and item['action_id']==item['class_index']+2 for item in saved['top3'])
    assert [item['score'] for item in saved['top3']]==sorted([item['score'] for item in saved['top3']],reverse=True)
    assert len(saved['scores'])==34 and sum(saved['scores'])==pytest.approx(1.,abs=1e-5)
    assert client.get(f'/api/games/{gid}').json()==view
    after=resources.games.games.get_human_encoded_turn(gid)
    assert all(np.array_equal(a,b) for a,b in zip(before,(after.obs,after.legal_mask,after.legal_discard_mask)))
    assert weight_hash==weights_sha256(resources.runtime.ai._model.state_dict())
    detail=client.get('/api/predictions/'+saved['prediction_id']);assert detail.status_code==200
    data=detail.json();assert data['input_snapshot']['obs']==before[0].tolist()
    assert data['input_snapshot']['legal_mask']==before[1].tolist()
    assert data['input_snapshot']['legal_discard_mask']==before[2].tolist()
    assert data['output_snapshot']['top3']==saved['top3'] and data['output_snapshot']['scores']==saved['scores']
    repeated=client.post(f'/api/games/{gid}/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
    assert repeated.status_code==200 and repeated.json()['reused'] and repeated.json()['prediction_id']==saved['prediction_id']
    assert client.get('/api/predictions').json()['total']==1


def test_http_history_owner_isolation_delete_and_invalid_id(client):
    headers=csrf(client);view=game(client,headers);gid=view['game_id']
    saved=client.post(f'/api/games/{gid}/predict',json={'expected_turn_number':view['turn_number']},headers=headers).json()
    path='/api/predictions/'+saved['prediction_id'];other=TestClient(client.app,raise_server_exceptions=False)
    try:
        other_headers=csrf(other)
        assert other.get('/api/predictions').json()['total']==0
        assert other.get(path).status_code==404 and other.delete(path,headers=other_headers).status_code==404
    finally:other.close()
    assert client.delete(path).status_code==403
    assert client.get('/api/predictions/not-an-id').status_code==422
    assert client.get('/api/predictions?limit=101').status_code==422
    assert client.delete(path,headers=headers).status_code==204
    assert client.get(path).status_code==404 and client.delete(path,headers=headers).status_code==404
    assert client.get('/api/games/'+gid).json()==view


def test_http_action_stale_illegal_and_simultaneous_duplicate(client):
    headers=csrf(client);view=game(client,headers);path='/api/games/'+view['game_id']+'/actions'
    assert client.post(path,json={'action_id':0,'expected_turn_number':view['turn_number']},headers=headers).status_code==400
    assert client.post(path,json={'action_id':2,'expected_turn_number':view['turn_number']+1},headers=headers).status_code==409
    action=view['legal_actions'][0]['action_id'];payload={'action_id':action,'expected_turn_number':view['turn_number']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:client.post(path,json=payload,headers=headers),range(2)))
    assert sorted(r.status_code for r in responses)==[200,409]


def test_http_failed_database_commit_returns503_no_row_and_no_game_change(client):
    headers=csrf(client);view=game(client,headers);resources=client.app.state.resources;path='/api/games/'+view['game_id']
    def fail_commit(connection):raise OperationalError('injected commit failure',None,None)
    event.listen(resources.engine,'commit',fail_commit)
    try:
        failed=client.post(path+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
        assert failed.status_code==503 and 'saved' not in failed.json()
    finally:event.remove(resources.engine,'commit',fail_commit)
    assert client.get('/api/predictions').json()['total']==0 and client.get(path).json()==view
    assert client.post(path+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers).status_code==201


def test_readiness_failure_is_sanitized_and_liveness_remains_healthy(client,monkeypatch):
    from app.db import DatabaseUnavailable
    def unavailable(*a,**k):raise DatabaseUnavailable('private internal failure')
    monkeypatch.setattr('app.web.api.check_schema',unavailable)
    response=client.get('/health/ready')
    assert response.status_code==503 and 'private internal' not in response.text
    assert client.get('/health/live').status_code==200


def test_real_postgres_history_survives_web_restart_but_active_game_does_not(web_settings,postgres_engine):
    from app.main import create_app
    with TestClient(create_app(web_settings)) as first:
        headers=csrf(first);view=game(first,headers)
        saved=first.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers).json()
        cookies=dict(first.cookies)
    with TestClient(create_app(web_settings)) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get('/api/predictions/'+saved['prediction_id']).status_code==200
        assert restarted.get('/api/games/'+view['game_id']).status_code==404


def test_missing_model_or_database_blocks_startup_without_leaking_private_paths(web_settings,postgres_engine,tmp_path):
    from app.main import create_app
    missing=web_settings.model_copy(update={'model_checkpoint_path':tmp_path/'private_missing.pt'})
    with pytest.raises(RuntimeError):
        with TestClient(create_app(missing)):pass
    bad=web_settings.model_copy(update={'database_url':type(web_settings.database_url)('postgresql+psycopg://local@/missing_test?host=/private/tmp/nonexistent_mahjong_socket')})
    with pytest.raises(RuntimeError):
        with TestClient(create_app(bad)):pass
