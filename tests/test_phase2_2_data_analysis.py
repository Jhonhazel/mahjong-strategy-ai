import copy
import json
from pathlib import Path

import numpy as np
import pytest

from tests.test_phase2_1_training import expanded_root


def test_group_development_lineage_excludes_all_historical_tests(expanded_root):
    from training.optimization_data import DevelopmentCorpus,development_splits,evaluation_lineage,development_bucket
    corpus=DevelopmentCorpus(expanded_root)
    before=(expanded_root/"data_contract.json").read_bytes()
    report=evaluation_lineage(corpus)
    historical=set(report["historical_test_match_ids"])
    train,val=development_splits(corpus,0)
    assert train.match_ids and val.match_ids and not train.match_ids.intersection(val.match_ids)
    assert not historical.intersection(train.match_ids|val.match_ids)
    assert train.match_ids|val.match_ids==set(report["permitted_development_match_ids"])
    assert all(development_bucket(m)==0 for m in val.match_ids)
    assert all(development_bucket(m)!=0 for m in train.match_ids)
    assert report["new_blind_test_available"] is False and report["evaluation_kind"]=="internal_group_development"
    assert (expanded_root/"data_contract.json").read_bytes()==before


def test_remapped_batches_cover_both_old_development_roles_without_test_rows(expanded_root):
    from training.optimization_data import DevelopmentCorpus,development_splits
    from training.expanded_dataset import split_for_match
    corpus=DevelopmentCorpus(expanded_root)
    for split in development_splits(corpus,0):
        matches=set();n=0
        for x,y,mask,meta in split.batches(13,seed=2026,epoch=1,shuffle=True):
            assert x.shape==(len(y),1368) and mask[np.arange(len(y)),y].all()
            assert all(split_for_match(str(m),corpus.contract['original_roles']) in ('train','validation') for m in meta['match_id'])
            n+=len(y);matches.update(meta['match_id'])
        assert n==split.samples and matches==split.match_ids
    a=development_splits(corpus,0);b=development_splits(corpus,1)
    assert a[0].identity!=b[0].identity and a[1].match_ids!=b[1].match_ids


def test_saved_v2_in_sample_reference_is_rejected(expanded_root):
    from training.optimization_data import DevelopmentCorpus,assert_fair_saved_v2
    corpus=DevelopmentCorpus(expanded_root)
    original_training=corpus.split('train').match_ids
    with pytest.raises(ValueError,match='previous training'):
        assert_fair_saved_v2(corpus,original_training)
    assert_fair_saved_v2(corpus,corpus.split('validation').match_ids)


def test_failed_new_audit_does_not_overwrite_old_contract(expanded_root,tmp_path):
    import shutil
    from training.optimization_data import DevelopmentCorpus
    from app.domain.exceptions import CorruptedDatasetError
    clone=tmp_path/'clone';shutil.copytree(expanded_root,clone)
    contract=clone/'data_contract.json';value=json.loads(contract.read_text());value['shards'].append(value['shards'][0]);contract.write_text(json.dumps(value))
    before=contract.read_bytes()
    with pytest.raises(CorruptedDatasetError):DevelopmentCorpus(clone)
    assert contract.read_bytes()==before


def test_score_diagnostics_calibration_ranks_and_nontrivial_strata_are_correct():
    from training.optimization_analysis import ScoreDiagnostics
    probabilities=np.zeros((3,34),np.float64)
    probabilities[0,0]=1.;probabilities[1,:2]=[.8,.2];probabilities[2,:4]=[.4,.3,.2,.1]
    masks=probabilities>0;logs=np.full(probabilities.shape,-np.inf);logs[masks]=np.log(probabilities[masks])
    targets=np.array([0,1,2],np.int64)
    diagnostic=ScoreDiagnostics(bins=2)
    diagnostic.update(logs,targets,masks)
    result=diagnostic.finish()
    assert result['ranks']['1']==result['ranks']['2']==result['ranks']['3']==1
    assert result['expected_calibration_error']==pytest.approx((1+ .8 + .4)/3-1/3)
    expected=np.mean(np.sum(probabilities**2,axis=1)-2*probabilities[np.arange(3),targets]+1)
    assert result['brier_score']==pytest.approx(expected)
    assert result['legal_choice_strata']['1']['top1']==1
    assert result['legal_choice_strata']['2-3']['top3']==1
    assert result['nontrivial']['samples']==2 and result['nontrivial']['top1']==0
    assert result['nontrivial']['top3']==1


def test_duplicate_audit_retains_rows_and_distinguishes_input_label_conflicts():
    from training.optimization_analysis import SignatureAudit
    audit=SignatureAudit()
    obs=np.zeros((38,4,9),np.int8);mask=np.zeros(34,bool);mask[:3]=True
    audit.add(obs,mask,0,0);audit.add(obs,mask,0,1);audit.add(obs,mask,1,1)
    different=obs.copy();different[6,0,0]=1
    audit.add(different,mask,0,2)
    report=audit.finish()
    assert report['observations']==4 and report['distinct_observable_signatures']==2
    assert report['repeated_labeled_observations']==1
    assert report['input_signatures_with_label_disagreement']==1
    assert report['fold0_vs_other_input_overlap_signatures']==1
    assert report['fold0_vs_other_labeled_overlap_signatures']==1
    assert report['coarse_hand_overlap_signatures']==1
    assert report['filtered_observations']==0


def test_identical_trajectory_groups_stay_in_one_fold_without_deleting_rows(expanded_root):
    from training.optimization_data import DevelopmentCorpus,development_splits,development_bucket,permitted_matches
    corpus=DevelopmentCorpus(expanded_root);ids=sorted(permitted_matches(corpus))
    first=ids[0];second=next(m for m in ids if development_bucket(m)!=development_bucket(first))
    representative=min(first,second);groups={first:representative,second:representative}
    grouped=DevelopmentCorpus(expanded_root,group_keys=groups)
    fold=development_bucket(first,groups)
    train,val=development_splits(grouped,fold)
    assert {first,second}.issubset(val.match_ids) and not train.match_ids.intersection(val.match_ids)
    assert train.samples+val.samples==sum(permitted_matches(corpus).values())
    with pytest.raises(ValueError,match='permitted'):
        DevelopmentCorpus(expanded_root,group_keys={'f'*24:representative})


@pytest.mark.parametrize('marker',['protocol.json','model_freeze.json'])
def test_diagnostics_cannot_rewrite_protocol_bound_lineage(expanded_root,tmp_path,monkeypatch,marker):
    import training.optimization_analysis as module
    output=tmp_path/'diagnostics';output.mkdir()
    (output/marker).write_text('{}')
    lineage=output/'evaluation_lineage.json';lineage.write_text('{"trajectory_group_keys":{"a":"a"}}')
    before={p.name:p.read_bytes() for p in output.iterdir()}
    monkeypatch.setattr(module,'load_checkpoint',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('injected later failure')))
    with pytest.raises(ValueError,match='protocol|frozen|bound'):
        module.run_error_analysis(expanded_root,output)
    assert {p.name:p.read_bytes() for p in output.iterdir()}==before


@pytest.mark.parametrize('protected',['artifacts/phase2','artifacts/phase2_1/nested','datasets/old'])
def test_diagnostics_rejects_protected_output_before_read_or_write(tmp_path,monkeypatch,protected):
    import training.optimization_analysis as module
    monkeypatch.chdir(tmp_path);output=tmp_path/protected;output.mkdir(parents=True)
    sentinel=output/'keep.json';sentinel.write_text('{"preserved":true}')
    monkeypatch.setattr(module,'DevelopmentCorpus',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('must reject before dataset read')))
    with pytest.raises(ValueError,match='protected'):
        module.run_error_analysis(tmp_path/'unused',output)
    assert list(output.iterdir())==[sentinel] and sentinel.read_text()=='{"preserved":true}'
