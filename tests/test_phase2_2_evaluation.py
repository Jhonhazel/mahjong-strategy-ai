import gzip
import json
import math
from pathlib import Path

import pytest

from tests.test_phase2_1_training import expanded_root


@pytest.fixture
def completed_matrix(expanded_root,tmp_path):
    from training.optimization_data import DevelopmentCorpus,build_trajectory_groups
    from training.optimization_runner import run_matrix
    from training.reporting import write_json_report
    from training.train_mlp import TrainConfig
    corpus=DevelopmentCorpus(expanded_root);output=tmp_path/'matrix';output.mkdir()
    groups=build_trajectory_groups(corpus);write_json_report(output/'trajectory_groups.json',groups)
    run_matrix(expanded_root,output,common_config=TrainConfig(max_epochs=1,patience=1,batch_size=32,device='cpu'))
    return DevelopmentCorpus(expanded_root,group_keys=groups['group_keys']),output,tmp_path/'v3.pt'


def test_single_model_saved_record_recalculation_has_hand_computed_metrics(tmp_path):
    from training.expanded_evaluation import recalculate_saved_predictions
    path=tmp_path/'single.jsonl.gz'
    records=[]
    for target,probabilities in [(0,[.8,.2]),(1,[.6,.4])]:
        records.append({'target_class':target,'legal_classes':[0,1],'predicted_class':0,'top3':[0,1],'target_log_probability':math.log(probabilities[target]),'class_scores':probabilities+[0.]*32})
    with gzip.open(path,'wt') as stream:
        for row in records:stream.write(json.dumps(row)+'\n')
    result=recalculate_saved_predictions(path,single_model_name='candidate_v3')['candidate_v3']
    assert result['top1']==.5 and result['top3']==result['legal_rate']==1
    assert result['nll']==pytest.approx(-math.log(.8*.4)/2)
    assert result['macro_f1_34']==pytest.approx((2/3)/34)
    assert result['macro_f1_supported']==pytest.approx(1/3)


def test_generic_paired_bootstrap_preserves_actual_comparison_names():
    from training.expanded_evaluation import match_bootstrap
    counts={'a':{'n':10,'correct':{'reference_E0':3,'candidate_v3':7}},'b':{'n':2,'correct':{'reference_E0':1,'candidate_v3':1}}}
    result=match_bootstrap(counts,100,2026,reference_model='reference_E0',candidate_model='candidate_v3')
    assert set(result['models'])=={'reference_E0','candidate_v3'}
    assert result['paired_delta_candidate_vs_reference']['point']==pytest.approx(4/12)
    assert result['matches']==2 and result['samples']==12


def test_candidate_freeze_and_matched_development_comparison_are_reproducible(completed_matrix):
    from training.optimization_evaluation import prepare_candidate,compare_models
    from training.optimization_data import development_splits
    corpus,output,checkpoint=completed_matrix
    frozen=prepare_candidate(corpus,output,checkpoint)
    assert frozen['status']=='FROZEN' and frozen['historical_test_used_for_selection'] is False
    models={'reference_E0':Path(frozen['reference_checkpoint']),'candidate_v3':checkpoint}
    split=development_splits(corpus,0)[1]
    result=compare_models(corpus,split,models,output/'development','internal_group_development',bootstrap_samples=20)
    assert result['status']=='PASS' and result['samples']==split.samples and result['matches']==len(split.match_ids)
    assert result['new_blind_test_available'] is False and result['independent_recalculation']=='PASS'
    assert all(m['legal_rate']==1 for m in result['models'].values())
    assert compare_models(corpus,split,models,output/'development','internal_group_development',bootstrap_samples=20,verify_existing=True)['status']=='PASS'


@pytest.mark.parametrize('artifact',['candidate_v3_predictions.jsonl.gz','reference_E0_analysis.json','confidence_intervals.json'])
def test_optimization_evaluation_rejects_saved_evidence_tampering(completed_matrix,artifact):
    from training.optimization_evaluation import prepare_candidate,compare_models
    from training.optimization_data import development_splits
    corpus,output,checkpoint=completed_matrix;frozen=prepare_candidate(corpus,output,checkpoint)
    models={'reference_E0':Path(frozen['reference_checkpoint']),'candidate_v3':checkpoint};split=development_splits(corpus,0)[1]
    compare_models(corpus,split,models,output/'development','internal_group_development',bootstrap_samples=20)
    target=output/'development'/artifact;target.write_bytes(target.read_bytes()+b'tampered')
    with pytest.raises(ValueError):compare_models(corpus,split,models,output/'development','internal_group_development',bootstrap_samples=20,verify_existing=True)


def test_changed_candidate_cannot_be_refrozen(completed_matrix):
    from training.optimization_evaluation import prepare_candidate
    corpus,output,checkpoint=completed_matrix;prepare_candidate(corpus,output,checkpoint)
    checkpoint.write_bytes(checkpoint.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='changed'):prepare_candidate(corpus,output,checkpoint)


def test_frozen_reference_cannot_change_after_candidate_export(completed_matrix):
    from training.optimization_evaluation import prepare_candidate
    corpus,output,checkpoint=completed_matrix;frozen=prepare_candidate(corpus,output,checkpoint)
    reference=Path(frozen['reference_checkpoint']);reference.write_bytes(reference.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='reference'):prepare_candidate(corpus,output,checkpoint)


def test_saved_v2_is_not_accepted_as_unseen_reference_on_new_development(completed_matrix):
    from app.model_checkpoint import load_checkpoint
    from training.optimization_data import development_splits
    from training.optimization_evaluation import assert_model_evaluation_allowed
    corpus,output,checkpoint=completed_matrix;_,metadata=load_checkpoint(Path('artifacts/models/mahjong_discard_mlp_v2.pt'))
    with pytest.raises(ValueError,match='training'):
        assert_model_evaluation_allowed(metadata,corpus,development_splits(corpus,0)[1].match_ids)


def test_prediction_write_failure_cannot_publish_pass(completed_matrix,monkeypatch):
    import training.optimization_evaluation as module
    from training.optimization_data import development_splits
    corpus,output,checkpoint=completed_matrix;frozen=module.prepare_candidate(corpus,output,checkpoint)
    models={'reference_E0':Path(frozen['reference_checkpoint']),'candidate_v3':checkpoint};split=development_splits(corpus,0)[1]
    monkeypatch.setattr(module,'analyze_model',lambda *a,**k:(_ for _ in ()).throw(OSError('injected prediction write failure')))
    with pytest.raises(OSError):module.compare_models(corpus,split,models,output/'development','internal_group_development',bootstrap_samples=20)
    assert json.loads((output/'development'/'metrics.json').read_text())['status']=='FAIL'


def test_real_v3_latency_and_two_game_rounds_preserve_weights_and_state(completed_matrix):
    from training.optimization_evaluation import prepare_candidate
    from training.optimization_finalize import verify_live_and_latency
    corpus,output,checkpoint=completed_matrix;prepare_candidate(corpus,output,checkpoint)
    result=verify_live_and_latency(corpus,output,checkpoint,seeds=(42,43),repetitions=10)
    assert result['status']=='PASS' and result['weights_unchanged']
    assert result['latency']['samples']==10 and result['latency']['p95_ms']>=0
    assert all(r['status']=='FINISHED' for r in result['rounds'])
    assert {p['turn_phase'] for r in result['rounds'] for p in r['predictions']}=={'SELF_TURN','POST_MELD_DISCARD'}


def test_test_evidence_requires_old_and_new_families_and_zero_failures(tmp_path,monkeypatch):
    import training.optimization_finalize as module
    regression_evidence=module.regression_evidence
    path=tmp_path/'suite.xml'
    families=['tests.test_mcr_engine_playthrough','tests.test_phase2_model','tests.test_phase2_1_training','tests.test_phase2_2_models','tests.test_phase2_2_data_analysis','tests.test_phase2_2_registry','tests.test_phase2_2_evaluation']
    cases=''.join(f'<testcase classname="{families[i%len(families)]}" name="unit{i}"/>' for i in range(260))
    monkeypatch.setattr(module,'collect_regression_cases',lambda:{(families[i%len(families)],f'unit{i}') for i in range(260)})
    path.write_text(f'<testsuites><testsuite tests="260" failures="0" errors="0" skipped="0">{cases}</testsuite></testsuites>')
    assert regression_evidence(path)['status']=='PASS'
    path.write_text('<testsuites><testsuite tests="260" failures="1" errors="0" skipped="0"/></testsuites>')
    with pytest.raises(ValueError):regression_evidence(path)


def test_retrospective_comparison_cannot_run_before_final_selection_freeze(completed_matrix):
    from training.optimization_evaluation import prepare_candidate,compare_models
    corpus,output,checkpoint=completed_matrix;frozen=prepare_candidate(corpus,output,checkpoint)
    corpus.allow_test=True;split=corpus.split('test')
    with pytest.raises(ValueError,match='frozen'):
        compare_models(corpus,split,{'reference_E0':Path(frozen['reference_checkpoint']),'candidate_v3':checkpoint},output/'retro','retrospective_known_test',bootstrap_samples=20)


def test_failed_comparison_verification_replaces_previous_pass(completed_matrix):
    from training.optimization_evaluation import prepare_candidate,compare_models
    from training.optimization_data import development_splits
    corpus,output,checkpoint=completed_matrix;frozen=prepare_candidate(corpus,output,checkpoint)
    models={'reference_E0':Path(frozen['reference_checkpoint']),'candidate_v3':checkpoint};split=development_splits(corpus,0)[1]
    compare_models(corpus,split,models,output/'development','internal_group_development',bootstrap_samples=20)
    status=output/'development/reverification.json';status.write_text('{"status":"PASS"}')
    leaf=output/'development/candidate_v3_predictions.jsonl.gz';leaf.write_bytes(leaf.read_bytes()+b'tampered')
    with pytest.raises(ValueError,match='evidence changed'):
        compare_models(corpus,split,models,output/'development','internal_group_development',bootstrap_samples=20,verify_existing=True)
    assert json.loads(status.read_text())['status']=='FAIL'


@pytest.fixture
def frozen_finalization(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import training.optimization_finalize as module
    from training.dataset_loader import file_sha256
    from training.reporting import write_json_report
    output=tmp_path/'final';output.mkdir();checkpoint=tmp_path/'v3.pt';checkpoint.write_bytes(b'frozen weights')
    metadata=checkpoint.with_suffix('.metadata.json');metadata.write_text('{}')
    dev=output/'development';dev.mkdir();leaf=dev/'candidate_v3_predictions.jsonl.gz';leaf.write_bytes(b'saved predictions')
    write_json_report(dev/'metrics.json',{'status':'PASS','artifact_sha256':{leaf.name:file_sha256(leaf)}})
    write_json_report(output/'trajectory_groups.json',{'group_keys':{}})
    write_json_report(output/'model_selection.json',{'decision':'RETAIN_V2'})
    junit=output/'suite.xml';junit.write_text('<testsuites/>')
    write_json_report(output/'regression_evidence.json',{'status':'PASS','junit_path':str(junit),'junit_sha256':file_sha256(junit)})
    write_json_report(output/'model_freeze.json',{'status':'FROZEN','checkpoint_sha256':file_sha256(checkpoint),'dataset_contract_sha256':'contract','historical_test_used_for_selection':False,'selection_evidence_sha256':{'development/metrics.json':file_sha256(dev/'metrics.json'),'regression_evidence.json':file_sha256(output/'regression_evidence.json')}})
    write_json_report(output/'final_evaluation.json',{'status':'PASS','artifact_sha256':{},'metadata_sha256':file_sha256(metadata)})
    corpus=SimpleNamespace(contract_sha256='contract',contract={},group_keys={},split=lambda name:SimpleNamespace(name=name))
    monkeypatch.setattr(module,'DevelopmentCorpus',lambda *a,**k:corpus)
    monkeypatch.setattr(module,'prepare_candidate',lambda *a,**k:{'reference_checkpoint':str(tmp_path/'reference.pt')})
    monkeypatch.setattr(module,'verify_candidate',lambda *a,**k:None)
    monkeypatch.setattr(module,'development_splits',lambda *a,**k:(None,SimpleNamespace(name='validation')))
    real_comparison=module._comparison
    retro={'status':'PASS','samples':1,'matches':1,'models':{'candidate_v3':{key:1. for key in module.METRICS}}}
    def comparison(*args,**kwargs):
        return retro if args[4]=='retrospective_known_test' else real_comparison(*args,**kwargs)
    monkeypatch.setattr(module,'_comparison',comparison)
    summary={'kind':'retrospective_known_test','new_blind_test_available':False,'selection_already_frozen':True,'samples':1,'matches':1,'checkpoint_sha256':file_sha256(checkpoint),'metrics':retro['models']['candidate_v3'],'report':'phase2_2/final_evaluation.json'}
    monkeypatch.setattr(module,'load_checkpoint',lambda *a,**k:(None,{'test_evaluation':summary}))
    return module,output,checkpoint,leaf


@pytest.mark.parametrize('change',['corrupt','delete'])
def test_frozen_final_verification_rejects_development_leaf_changes(frozen_finalization,change):
    module,output,checkpoint,leaf=frozen_finalization
    if change=='delete':leaf.unlink()
    else:leaf.write_bytes(b'corrupted development evidence')
    with pytest.raises(ValueError,match='evidence changed'):
        module.finish_optimization('unused',output,checkpoint,'unused.xml',verify_existing=True)


def test_failed_final_verification_replaces_previous_pass(frozen_finalization):
    module,output,checkpoint,leaf=frozen_finalization
    status=output/'reverification.json';status.write_text('{"status":"PASS"}')
    checkpoint.with_suffix('.metadata.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='metadata changed'):
        module.finish_optimization('unused',output,checkpoint,'unused.xml',verify_existing=True)
    assert json.loads(status.read_text())['status']=='FAIL'


def test_regression_gate_rejects_real_missing_family_and_duplicate_cases(tmp_path,monkeypatch):
    import xml.etree.ElementTree as ET
    from training.optimization_finalize import regression_evidence,collect_regression_cases
    # A caller's test selection must not narrow the expected complete inventory.
    monkeypatch.setenv('PYTEST_ADDOPTS','-k "not test_phase2_1_evaluation"')
    expected=collect_regression_cases()
    def xml(cases):
        root=ET.Element('testsuites');suite=ET.SubElement(root,'testsuite',tests=str(len(cases)),failures='0',errors='0',skipped='0')
        for classname,name in cases:ET.SubElement(suite,'testcase',classname=classname,name=name)
        return ET.ElementTree(root)
    remaining=[c for c in sorted(expected) if c[0]!='tests.test_phase2_1_evaluation']
    assert len(expected)-len(remaining)==11
    path=tmp_path/'incomplete.xml';xml(remaining).write(path)
    with pytest.raises(ValueError,match='incomplete|missing|inventory'):
        regression_evidence(path)
    xml([*sorted(expected),min(expected)]).write(path)
    with pytest.raises(ValueError,match='duplicated'):
        regression_evidence(path)


def test_rejected_duplicate_final_attempt_preserves_frozen_result(frozen_finalization):
    module,output,checkpoint,leaf=frozen_finalization
    before=(output/'final_evaluation.json').read_bytes()
    with pytest.raises(ValueError,match='verify-existing'):
        module.finish_optimization('unused',output,checkpoint,'unused.xml')
    assert (output/'final_evaluation.json').read_bytes()==before


def test_frozen_final_verification_rejects_changed_junit_evidence(frozen_finalization,monkeypatch):
    module,output,checkpoint,leaf=frozen_finalization
    # Isolate orchestration from repeated tensor inference, which has its own tests.
    retro={'samples':1,'matches':1,'models':{'candidate_v3':{key:1. for key in module.METRICS}}}
    monkeypatch.setattr(module,'_comparison',lambda *a,**k:retro)
    (output/'suite.xml').write_text('<testsuites changed="true"/>')
    with pytest.raises(ValueError,match='regression.*changed'):
        module.finish_optimization('unused',output,checkpoint,'unused.xml',verify_existing=True)


@pytest.mark.parametrize('leaf',['model.pt','model.metadata.json','history.json'])
def test_frozen_unselected_experiment_artifact_tampering_is_rejected(completed_matrix,leaf):
    from training.optimization_evaluation import prepare_candidate
    corpus,output,checkpoint=completed_matrix;frozen=prepare_candidate(corpus,output,checkpoint)
    rows=json.loads((output/'experiment_registry.json').read_text())['entries']
    row=next(r for r in rows if r['id']!=frozen['selected_experiment'] and r['checkpoint']!=frozen['reference_checkpoint'])
    path=Path(row['checkpoint']).parent/leaf;path.write_bytes(path.read_bytes()+b'tampered')
    with pytest.raises(ValueError,match='experiment artifact changed'):
        prepare_candidate(corpus,output,checkpoint)
