"""Filtering uses original normalized legal probabilities; no model/data mutation."""
import copy
import importlib
import pytest


def policy():return importlib.import_module('app.services.recommendation_policy')

def vector(values):return list(values)+[0.]*(34-len(values))

def mask(size):return [True]*size+[False]*(34-size)

@pytest.mark.parametrize('values,expected',[
    ([.60,.25,.15],[0,1,2]),([.62,.25,.08,.05],[0,1]),([.96,.03,.01],[0]),
    ([1/12]*12,[]),([.9,.10],[0,1]),([.900001,.099999],[0]),
    ([.3,.2,.15,.15,.1,.1],[0,1,2]),([.1]*10,[0,1,2]),
])
def test_complete_valid_distributions_use_exact_threshold_without_padding(values,expected):
    scores=vector(values);legal=mask(len(values));before=copy.deepcopy((scores,legal))
    result=policy().filter_recommendations(scores,legal)
    assert result['minimum_score']==.10 and result['maximum_suggestions']==3
    assert result['status']==('available' if expected else 'no_suggestions')
    assert [r['class_index'] for r in result['suggestions']]==expected
    assert [r['score'] for r in result['suggestions']]==[scores[i] for i in expected]
    assert (scores,legal)==before
    assert all(r['action_id']==r['class_index']+2 for r in result['suggestions'])

@pytest.mark.parametrize('damage',['nan','inf','negative','boolean','wrong_length','not_normalized','no_legal','illegal_positive','bad_mask'])
def test_invalid_scores_or_masks_are_errors_not_empty_results(damage):
    scores=vector([.6,.25,.15]);legal=mask(3)
    if damage=='nan':scores[0]=float('nan')
    elif damage=='inf':scores[0]=float('inf')
    elif damage=='negative':scores[0]=-.6
    elif damage=='boolean':scores[0]=True
    elif damage=='wrong_length':scores.pop()
    elif damage=='not_normalized':scores[0]=.8
    elif damage=='no_legal':legal=mask(0)
    elif damage=='illegal_positive':legal[0]=False
    else:legal[0]=1
    with pytest.raises(ValueError):policy().filter_recommendations(scores,legal)


def test_illegal_zero_classes_never_enter_suggestions_and_ties_use_class_order():
    scores=vector([.2,0.,.4,.4]);legal=[True,False,True,True]+[False]*30
    result=policy().filter_recommendations(scores,legal)
    assert [r['class_index'] for r in result['suggestions']]==[2,3,0]
    assert sum(r['score'] for r in policy().filter_recommendations(vector([.62,.25,.08,.05]),mask(4))['suggestions'])==pytest.approx(.87)


def test_node_contract_fixtures_match_the_single_server_policy():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'tests/frontend/recommendation_contracts.json').read_text())
    for case in data['cases'].values():
        result=case['prediction'];legal=[any(a['action_id']==i+2 for a in case['legal_actions']) for i in range(34)]
        assert policy().filter_recommendations(result['scores'],legal)==result['recommendations']
    actual=json.loads((root/'artifacts/phase3/api_examples.json').read_text())
    legal=[any(a['action_type']=='Play' and a['action_id']==i+2 for a in actual['game_response']['legal_actions']) for i in range(34)]
    assert policy().filter_recommendations(actual['prediction_response']['scores'],legal)==data['captured']
