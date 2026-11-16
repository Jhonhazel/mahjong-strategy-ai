"""Real engine/PostgreSQL with explicit score injection for empty-result coverage."""
import copy
from dataclasses import replace
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from tests.phase4_support import phase4_client,postgres_engine,postgres_url,web_settings
from tests.test_phase3_http import csrf,game
from app.services.ai_prediction_service import DiscardSuggestion
from app.domain.tiles import index_to_tile


def uniform_model(client,monkeypatch):
    ai=client.app.state.resources.runtime.ai;original=ai.predict
    def predict(state):
        raw=original(state);indices=[i for i,legal in enumerate(state.legal_discard_mask) if legal]
        assert len(indices)>10,'This fixture needs enough legal discards for an empty projection'
        scores=tuple(1/len(indices) if i in indices else 0. for i in range(34))
        top=tuple(DiscardSuggestion(index_to_tile(i),i,i+2,scores[i]) for i in indices[:3]);best=top[0]
        return replace(raw,scores=scores,top3=top,recommended_tile=best.tile,recommended_class_index=best.class_index,recommended_action_id=best.action_id)
    monkeypatch.setattr(ai,'predict',predict)


def test_empty_analysis_commits_reuses_and_projects_old_snapshot_without_writes(phase4_client,monkeypatch):
    client=phase4_client;headers=csrf(client);view=game(client,headers);uniform_model(client,monkeypatch)
    route='/api/games/'+view['game_id'];payload={'expected_turn_number':view['turn_number']}
    response=client.post(route+'/predict',json=payload,headers=headers);assert response.status_code==201
    saved=response.json();assert saved['top3'] and saved['recommended_tile']
    assert saved['recommendations']=={'suggestions':[],'minimum_score':.1,'maximum_suggestions':3,'status':'no_suggestions'}
    assert client.get(route).json()==view
    repeated=client.post(route+'/predict',json=payload,headers=headers);assert repeated.status_code==200
    assert repeated.json()['prediction_id']==saved['prediction_id'] and repeated.json()['reused']
    assert client.get('/api/predictions').json()['total']==1
    history_text=client.get('/history').text
    assert '1 hasil analisis tersimpan' in history_text and '1 saran tersimpan' not in history_text
    resources=client.app.state.resources;visitor=resources.visitors.load(client.cookies.get('mahjong_visitor'))
    from uuid import UUID
    record=resources.history.get(visitor.owner_key,UUID(saved['prediction_id']))
    before=copy.deepcopy((record.input_snapshot,record.output_snapshot,record.created_at))
    assert 'recommendations' not in record.output_snapshot
    monkeypatch.setattr(resources.runtime.ai,'predict',lambda *a:pytest.fail('History must not reinfer'))
    for path in ('/api/predictions','/api/predictions/'+saved['prediction_id']):
        body=client.get(path).json();item=body['items'][0] if 'items' in body else body
        assert item['recommendations']==saved['recommendations']
    for path in ('/history','/history/'+saved['prediction_id']):
        page=client.get(path);assert page.status_code==200
        assert 'Pada giliran ini, belum ada saran yang memenuhi batas minimal 10%.' in page.text
        assert '/static/tiles.svg#tile-'+saved['recommended_tile'] not in page.text
        assert 'batas minimal 10% yang berlaku sekarang' in page.text
    record=resources.history.get(visitor.owner_key,UUID(saved['prediction_id']))
    assert (record.input_snapshot,record.output_snapshot,record.created_at)==before


def test_empty_analysis_storage_error_is_not_a_success(phase4_client,monkeypatch):
    client=phase4_client;headers=csrf(client);view=game(client,headers);uniform_model(client,monkeypatch)
    def fail_commit(connection):raise OperationalError('injected test failure',None,None)
    engine=client.app.state.resources.engine;event.listen(engine,'commit',fail_commit)
    try:
        response=client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
        assert response.status_code==503 and 'recommendations' not in response.json()
    finally:event.remove(engine,'commit',fail_commit)
    assert client.get('/api/predictions').json()['total']==0
    assert client.get('/api/games/'+view['game_id']).json()==view


def test_real_checkpoint_response_and_history_use_same_server_projection(phase4_client):
    from app.services.recommendation_policy import filter_recommendations
    client=phase4_client;headers=csrf(client);view=game(client,headers)
    response=client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
    assert response.status_code==201
    result=response.json();mask=[any(a['action_type']=='Play' and a['action_id']==i+2 for a in view['legal_actions']) for i in range(34)]
    assert result['recommendations']==filter_recommendations(result['scores'],mask)
    assert client.get('/api/predictions/'+result['prediction_id']).json()['recommendations']==result['recommendations']


def test_page_policy_and_evaluation_label_match_server_configuration(phase4_client):
    from app.services.recommendation_policy import RECOMMENDATION_POLICY as policy
    page=phase4_client.get('/game').text
    assert f'data-minimum-score="{policy.minimum_score}"' in page
    assert f'data-maximum-suggestions="{policy.maximum_suggestions}"' in page
    assert f'AI menampilkan maksimal {policy.maximum_suggestions} saran dengan bobot minimal {policy.minimum_label}.' in page
    model=phase4_client.get('/model').text
    assert 'Hasil evaluasi model sebelum penerapan batas minimal saran.' in model and '86,55%' in model
    schema=phase4_client.get('/openapi.json').json()['components']['schemas']
    assert 'recommendations' in schema['SavedPredictionOut']['properties']
    assert 'recommendations' in schema['HistorySummaryOut']['properties']

@pytest.mark.parametrize('values,count',[([.6,.25,.15],3),([.62,.25,.08,.05],2),([.96,.03,.01],1)])
def test_game_and_history_render_only_the_same_filtered_candidates(phase4_client,monkeypatch,values,count):
    client=phase4_client;headers=csrf(client);view=game(client,headers)
    ai=client.app.state.resources.runtime.ai;original=ai.predict
    def controlled(state):
        raw=original(state);legal=[i for i,b in enumerate(state.legal_discard_mask) if b]
        scores=[0.]*34
        for index,value in zip(legal,values):scores[index]=value
        top=tuple(DiscardSuggestion(index_to_tile(i),i,i+2,scores[i]) for i in sorted(legal,key=lambda i:(-scores[i],i))[:3]);best=top[0]
        return replace(raw,scores=tuple(scores),top3=top,recommended_tile=best.tile,recommended_class_index=best.class_index,recommended_action_id=best.action_id)
    monkeypatch.setattr(ai,'predict',controlled)
    response=client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers);assert response.status_code==201
    saved=response.json();shown=saved['recommendations']['suggestions'];assert len(shown)==count
    assert [r['score'] for r in shown]==values[:count]
    assert client.get('/api/predictions').json()['items'][0]['recommendations']==saved['recommendations']
    detail=client.get('/history/'+saved['prediction_id']);listing=client.get('/history')
    assert detail.text.count('<tr>')==count+1
    for suggestion in shown:
        assert all('/static/tiles.svg#tile-'+suggestion['tile'] in html for html in (listing.text,detail.text))
    for suggestion in saved['top3'][count:]:
        assert all('/static/tiles.svg#tile-'+suggestion['tile'] not in html for html in (listing.text,detail.text))
    assert client.get('/api/games/'+view['game_id']).json()==view
