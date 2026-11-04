import json
from pathlib import Path
import shutil
import tarfile

import pytest

from tests.test_phase2_1_expansion import make_archive


@pytest.fixture(scope="module")
def frozen_fixture(tmp_path_factory):
    from training.expanded_dataset import ExpansionConfig,expand
    from training.expanded_training import run_experiments
    from training.train_mlp import TrainConfig
    folder=tmp_path_factory.mktemp("fresh-evaluation")
    games=[]
    with tarfile.open("datasets/finalist_games.tar.gz","r|gz") as archive:
        for member in archive:
            if member.isfile() and member.name.endswith(".json"):
                games.append((member.name,archive.extractfile(member).read()))
                if len(games)==150:break
    archive,spec=make_archive(folder,games)
    dataset=folder/"expanded"
    expand(ExpansionConfig(archive,dataset,batch_games=32,workers=1,reserve_bytes=0),spec=spec)
    output,model=folder/"artifacts",folder/"v2.pt"
    run_experiments(dataset,output,model,TrainConfig(max_epochs=1,patience=1,device="cpu"),budgets=(50,))
    return dataset,output,model


def case(tmp_path,frozen_fixture):
    dataset,output,model=frozen_fixture
    destination=tmp_path/"report";shutil.copytree(output,destination)
    checkpoint=tmp_path/"v2.pt"
    shutil.copyfile(model,checkpoint)
    shutil.copyfile(model.with_suffix(".metadata.json"),checkpoint.with_suffix(".metadata.json"))
    freeze=json.loads((destination/"selection_freeze.json").read_text())
    freeze["checkpoint"]=str(checkpoint)
    (destination/"selection_freeze.json").write_text(json.dumps(freeze))
    return dataset,destination,checkpoint


def test_frozen_common_cohort_evaluation_and_independent_saved_recalculation(tmp_path,frozen_fixture):
    from training.expanded_evaluation import evaluate_expanded,recalculate_saved_predictions
    from training.expanded_training import ShardCorpus
    dataset,output,checkpoint=case(tmp_path,frozen_fixture)
    result=evaluate_expanded(dataset,output,checkpoint,bootstrap_samples=50)
    split=ShardCorpus(dataset,allow_test=True).split("test")
    assert result["status"]=="PASS" and result["test_samples"]==split.samples and result["test_matches"]==len(split.match_ids)>0
    assert {"original_phase2","full_original","selected_v2"}.issubset(result["models"])
    assert all(m["legal_rate"]==1 for m in result["models"].values())
    assert not split.match_ids.intersection(json.loads((dataset/"data_contract.json").read_text())["original_roles"])
    independent=recalculate_saved_predictions(output/"test_predictions.jsonl.gz")
    for name,metrics in result["models"].items():
        for key in ("top1","top3","macro_f1_34","macro_f1_supported","nll","legal_rate"):
            assert independent[name][key]==pytest.approx(metrics[key],abs=1e-7)
    assert result["confidence_intervals"]["matches"]==len(split.match_ids)
    assert evaluate_expanded(dataset,output,checkpoint,verify_existing=True,bootstrap_samples=50)["status"]=="PASS"


@pytest.mark.parametrize("artifact",["model_freeze.json","test_predictions.jsonl.gz","per_class_metrics.csv","protocol.json"])
def test_reverification_rejects_missing_or_modified_artifacts(tmp_path,frozen_fixture,artifact):
    from training.expanded_evaluation import evaluate_expanded
    dataset,output,checkpoint=case(tmp_path,frozen_fixture)
    evaluate_expanded(dataset,output,checkpoint,bootstrap_samples=20)
    target=output/artifact
    target.write_bytes(target.read_bytes()+b"changed")
    with pytest.raises((ValueError,KeyError,json.JSONDecodeError)):
        evaluate_expanded(dataset,output,checkpoint,verify_existing=True,bootstrap_samples=20)


def test_metadata_publication_failure_cannot_leave_pass_and_same_frozen_model_can_resume(tmp_path,frozen_fixture,monkeypatch):
    import training.expanded_evaluation as module
    dataset,output,checkpoint=case(tmp_path,frozen_fixture)
    real=module.write_json_report
    def fail(path,value):
        if Path(path)==checkpoint.with_suffix(".metadata.json"):raise OSError("injected metadata publication failure")
        return real(path,value)
    monkeypatch.setattr(module,"write_json_report",fail)
    with pytest.raises(OSError,match="injected"):module.evaluate_expanded(dataset,output,checkpoint,bootstrap_samples=20)
    assert json.loads((output/"evaluation_metrics.json").read_text())["status"]=="FAIL"
    monkeypatch.setattr(module,"write_json_report",real)
    assert module.evaluate_expanded(dataset,output,checkpoint,resume=True,bootstrap_samples=20)["status"]=="PASS"


@pytest.mark.parametrize("change",["weights","protocol","missing_freeze","metadata"])
def test_frozen_identity_cannot_be_changed_before_test(tmp_path,frozen_fixture,change):
    from training.expanded_evaluation import evaluate_expanded
    dataset,output,checkpoint=case(tmp_path,frozen_fixture)
    if change=="weights":checkpoint.write_bytes(checkpoint.read_bytes()+b"tampered")
    elif change=="protocol":(output/"protocol.json").write_text('{}')
    elif change=="missing_freeze":(output/"selection_freeze.json").unlink()
    else:
        path=checkpoint.with_suffix(".metadata.json")
        metadata=json.loads(path.read_text());metadata["training"]["config"]["weight_decay"]=.123
        path.write_text(json.dumps(metadata))
    with pytest.raises((ValueError,OSError)):
        evaluate_expanded(dataset,output,checkpoint,bootstrap_samples=20)
    report=output/"evaluation_metrics.json"
    assert not report.exists() or json.loads(report.read_text())["status"]!="PASS"


def test_paired_match_bootstrap_identical_models_has_zero_difference():
    from training.expanded_evaluation import match_bootstrap
    counts={"m1":{"n":10,"correct":{"original_phase2":3,"selected_v2":3}},"m2":{"n":2,"correct":{"original_phase2":2,"selected_v2":2}}}
    a=match_bootstrap(counts,100,2026)
    assert a==match_bootstrap(counts,100,2026)
    assert a["matches"]==2 and a["resamples"]==100
    assert a["paired_delta_selected_vs_phase2"]["interval_95"]==[0.,0.]
