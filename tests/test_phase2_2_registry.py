import copy
from dataclasses import asdict
from pathlib import Path

import pytest

from tests.test_phase2_1_training import expanded_root
from training.train_mlp import TrainConfig


def test_registry_is_deterministic_rejects_duplicate_ids_and_changed_protocol(tmp_path):
    from training.optimization_runner import ExperimentRegistry,protocol_config
    protocol=protocol_config('a'*64,'b'*64)
    assert protocol==protocol_config('a'*64,'b'*64)
    registry=ExperimentRegistry(tmp_path,protocol)
    entry={'id':'E0_f0_s2026','architecture':{'version':'unit'},'config':asdict(TrainConfig()),'fold':0}
    registry.register(entry)
    with pytest.raises(ValueError,match='Duplicate'):registry.register(entry)
    registry.register(entry,resume=True)
    changed=copy.deepcopy(entry);changed['fold']=1
    with pytest.raises(ValueError,match='identity'):registry.register(changed,resume=True)
    other=copy.deepcopy(protocol);other['primary_seed']=7
    with pytest.raises(ValueError,match='protocol'):ExperimentRegistry(tmp_path,other)


def test_regularization_changes_one_axis_from_development_evidence_only():
    from app.mlp import architecture_spec
    from training.optimization_runner import regularization_candidate
    config=TrainConfig(batch_size=256,device='cpu')
    source={'architecture':architecture_spec((256,128),.2),'config':asdict(config),'generalization_gap':.01}
    spec,adjusted,reason=regularization_candidate(source)
    assert spec['dropout']==.1 and asdict(adjusted)==asdict(config)
    source['generalization_gap']=.05
    spec,adjusted,reason=regularization_candidate(source)
    assert spec==source['architecture'] and adjusted.weight_decay==.001
    assert sum(asdict(adjusted)[k]!=asdict(config)[k] for k in asdict(config))==1


def test_promotion_uses_paired_development_runs_and_safety_not_historical_test():
    from training.optimization_runner import promotion_decision
    def metrics(nll,top1):return {'nll':nll,'top1':top1,'top3':.85,'macro_f1_34':.6,'legal_rate':1.}
    pairs=[{'reference':metrics(1.3,.57),'candidate':metrics(1.15,.63)} for _ in range(3)]
    result=promotion_decision(pairs,{'p95_ms':2.},safety_pass=True)
    assert result['decision']=='PROMOTE_V3' and result['test_used_for_selection'] is False
    pairs[1]['candidate']['nll']=1.4
    assert promotion_decision(pairs,{'p95_ms':2.},safety_pass=True)['decision']=='RETAIN_V2'
    assert promotion_decision(pairs,{'p95_ms':2.},safety_pass=False)['decision']=='INCONCLUSIVE'


def test_real_registry_case_matches_declared_fold_architecture_and_checkpoint(expanded_root,tmp_path):
    from app.mlp import architecture_spec
    from app.model_checkpoint import load_checkpoint
    from training.optimization_data import DevelopmentCorpus,development_splits,evaluation_lineage
    from training.optimization_runner import ExperimentRegistry,protocol_config,run_case
    from training.expanded_dataset import canonical_hash
    corpus=DevelopmentCorpus(expanded_root);lineage=evaluation_lineage(corpus)
    config=TrainConfig(max_epochs=2,patience=1,batch_size=32,device='cpu')
    protocol=protocol_config(corpus.contract_sha256,canonical_hash(lineage),config);registry=ExperimentRegistry(tmp_path,protocol)
    row=run_case(corpus,registry,'E1',architecture_spec((128,),.2),config,0)
    assert row['status']=='PASS' and row['model_seed']==2026
    model,metadata=load_checkpoint(Path(row['checkpoint']),expected_contract=corpus.contract)
    train,val=development_splits(corpus,0)
    assert metadata['development']['training_match_ids']==sorted(train.match_ids)
    assert metadata['development']['validation_match_ids']==sorted(val.match_ids)
    assert set(metadata['development']['historical_test_match_ids']).isdisjoint(train.match_ids|val.match_ids)
    assert metadata['architecture']==row['architecture']
    assert run_case(corpus,registry,'E1',row['architecture'],TrainConfig(max_epochs=2,patience=1,batch_size=32,device='cpu'),0,resume=True)['checkpoint_sha256']==row['checkpoint_sha256']


def test_case_rejects_historical_or_unknown_fold_before_training(expanded_root,tmp_path):
    from app.mlp import architecture_spec
    from training.optimization_data import DevelopmentCorpus,evaluation_lineage
    from training.optimization_runner import ExperimentRegistry,protocol_config,run_case
    from training.expanded_dataset import canonical_hash
    corpus=DevelopmentCorpus(expanded_root);r=ExperimentRegistry(tmp_path,protocol_config(corpus.contract_sha256,canonical_hash(evaluation_lineage(corpus))))
    with pytest.raises(ValueError,match='fold'):
        run_case(corpus,r,'E1',architecture_spec((128,),.2),TrainConfig(max_epochs=1,device='cpu'),5)


@pytest.fixture(scope='module')
def optimization_checkpoint(expanded_root,tmp_path_factory):
    from app.mlp import architecture_spec
    from training.optimization_data import DevelopmentCorpus,evaluation_lineage
    from training.optimization_runner import ExperimentRegistry,protocol_config,run_case
    from training.expanded_dataset import canonical_hash
    corpus=DevelopmentCorpus(expanded_root);config=TrainConfig(max_epochs=1,patience=1,batch_size=32,device='cpu')
    registry=ExperimentRegistry(tmp_path_factory.mktemp('optimization-checkpoint'),protocol_config(corpus.contract_sha256,canonical_hash(evaluation_lineage(corpus)),config))
    row=run_case(corpus,registry,'E1',architecture_spec((128,),.2),config,0)
    return corpus,registry,row,config


@pytest.mark.parametrize('tamper',['overlap','historical','protocol','blind_claim','missing_phase','missing_development'])
def test_development_metadata_rejected_before_weights_deserialization(optimization_checkpoint,tmp_path,monkeypatch,tamper):
    import json,torch
    from app.model_checkpoint import load_checkpoint,CheckpointValidationError
    corpus,registry,row,config=optimization_checkpoint
    path=Path(row['checkpoint']);metadata=json.loads(path.with_suffix('.metadata.json').read_text())
    if tamper=='overlap':metadata['development']['training_match_ids'][0]=metadata['development']['validation_match_ids'][0]
    elif tamper=='historical':metadata['development']['historical_test_match_ids'].append('f'*24)
    elif tamper=='protocol':metadata['development']['protocol_sha256']='bad'
    elif tamper=='blind_claim':metadata['development']['new_blind_test_available']=True
    elif tamper=='missing_phase':metadata.pop('optimization_phase')
    else:metadata.pop('development')
    destination=tmp_path/'bad.json';destination.write_text(json.dumps(metadata))
    called=[]
    def forbidden(*args,**kwargs):
        called.append(True)
        raise AssertionError('Must validate development metadata first')
    monkeypatch.setattr(torch,'load',forbidden)
    with pytest.raises(CheckpointValidationError):load_checkpoint(path,destination,corpus.contract)
    assert not called,'Invalid development metadata reached weights deserialization'


def test_completed_registry_metrics_cannot_disagree_with_frozen_checkpoint(optimization_checkpoint):
    from training.optimization_runner import run_case
    corpus,registry,row,config=optimization_checkpoint
    original=copy.deepcopy(row['validation'])
    try:
        row['validation']['nll']=0.;registry.save()
        with pytest.raises(ValueError,match='metric'):
            run_case(corpus,registry,'E1',row['architecture'],config,0,resume=True)
    finally:row['validation']=original;registry.save()
