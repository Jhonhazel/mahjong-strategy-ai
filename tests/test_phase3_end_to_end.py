import pytest

from tests.phase3_support import postgres_engine, postgres_url, web_settings

pytestmark=pytest.mark.integration


def test_real_two_round_web_model_postgres_workflow_and_restart(web_settings,postgres_engine,tmp_path):
    from scripts.demo_backend import run_workflow
    result=run_workflow(web_settings,tmp_path/'demo.json',seeds=(42,43))
    assert result['status']=='PASS' and len(result['rounds'])==2
    assert {p['turn_phase'] for r in result['rounds'] for p in r['predictions']}=={'SELF_TURN','POST_MELD_DISCARD'}
    assert all(r['final_view']['status']=='FINISHED' for r in result['rounds'])
    assert all(r['history_after_restart']>=1 for r in result['rounds'])
    assert all(r['deleted_prediction_status']==404 and r['game_after_restart_status']==404 for r in result['rounds'])
    assert result['weights_before']==result['weights_after']
    assert all(r['actions']>0 and r['predictions'] for r in result['rounds'])
