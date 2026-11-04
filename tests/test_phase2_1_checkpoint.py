import copy
import json
from pathlib import Path

import pytest

from tests.test_phase2_1_training import expanded_root


@pytest.fixture(scope="module")
def v2checkpoint(expanded_root,tmp_path_factory):
    from training.expanded_training import ShardCorpus,nested_match_subset,train_sharded,save_run_checkpoint
    from training.train_mlp import TrainConfig
    corpus=ShardCorpus(expanded_root)
    folder=tmp_path_factory.mktemp("v2-checkpoint")
    run=train_sharded(nested_match_subset(corpus.split("train"),80),corpus.split("validation"),TrainConfig(max_epochs=1,patience=1,device="cpu"),folder/"train")
    path=folder/"model.pt"
    metadata=save_run_checkpoint(run,corpus,path)
    return path,corpus,metadata


def test_v2_checkpoint_binds_expanded_run_contract_shards_and_preserves_parent_identity(v2checkpoint):
    from app.model_checkpoint import load_checkpoint
    path,corpus,metadata=v2checkpoint
    _,loaded=load_checkpoint(path,expected_contract=corpus.contract)
    dataset=loaded["dataset"]
    assert dataset["phase1_run_id"]=="84c2606383794fa8bc072d5edac7b252"
    assert dataset["expanded_run_id"]==corpus.contract["run_id"]
    assert dataset["contract_sha256"]==corpus.contract_sha256
    assert dataset["shards"]==corpus.contract["shards"]
    assert dataset["historical_test"]=={k:corpus.quality["splits"]["historical_test"][k] for k in ("samples","matches")}
    assert loaded["checkpoint_sha256"]==metadata["checkpoint_sha256"]


@pytest.mark.parametrize("key",["contract_sha256","shards","expanded_run_id","dataset_version"])
def test_v2_metadata_missing_provenance_rejected_before_deserialization(tmp_path,v2checkpoint,monkeypatch,key):
    import torch
    from app.model_checkpoint import load_checkpoint,CheckpointValidationError
    path,corpus,metadata=v2checkpoint
    value=copy.deepcopy(metadata)
    value["dataset"].pop(key)
    meta=tmp_path/"bad.json";meta.write_text(json.dumps(value))
    def forbidden(*args,**kwargs): raise AssertionError("Invalid metadata must not reach torch.load")
    monkeypatch.setattr(torch,"load",forbidden)
    with pytest.raises(CheckpointValidationError): load_checkpoint(path,meta,corpus.contract)


def test_new_model_live_round_uses_existing_service_both_phases_without_mutation(v2checkpoint):
    from scripts.demo_ai_prediction import run_demo
    path,corpus,_=v2checkpoint
    result=run_demo(path,42,1,True,contract_path=corpus.root/"data_contract.json")
    assert result["status"]=="FINISHED"
    assert {p["turn_phase"] for p in result["predictions"]}=={"SELF_TURN","POST_MELD_DISCARD"}
    assert all(p["state_unchanged"] and p["all_suggestions_legal"] for p in result["predictions"])
