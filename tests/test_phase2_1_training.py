from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tarfile

import numpy as np
import pytest
import torch

from tests.test_phase2_1_expansion import make_archive
from training.dataset_loader import DatasetSpec
from training.train_mlp import TrainConfig


@pytest.fixture(scope="module")
def expanded_root(tmp_path_factory):
    from training.expanded_dataset import ExpansionConfig, expand
    folder = tmp_path_factory.mktemp("expanded-training")
    games = []
    with tarfile.open("datasets/finalist_games.tar.gz", "r|gz") as archive:
        for member in archive:
            if member.isfile() and member.name.endswith(".json"):
                games.append((member.name, archive.extractfile(member).read()))
                if len(games) == 35: break
    archive, spec = make_archive(folder, games)
    config = ExpansionConfig(archive, folder / "expanded", batch_games=8, workers=1, reserve_bytes=0)
    result = expand(config, spec=spec)
    assert result["status"] == "READY"
    return config.output


def test_sharded_loader_only_exposes_train_validation_before_freeze(expanded_root):
    from training.expanded_training import ShardCorpus
    corpus = ShardCorpus(expanded_root)
    train, validation = corpus.split("train"), corpus.split("validation")
    assert train.samples > 0 and validation.samples > 0
    assert not train.match_ids.intersection(validation.match_ids)
    for name in ("test", "historical_test"):
        with pytest.raises(ValueError, match="locked"):
            corpus.split(name)


def test_batches_are_bounded_float32_legal_and_reproducibly_shuffled(expanded_root):
    from training.expanded_training import ShardCorpus
    split = ShardCorpus(expanded_root).split("train")
    def fingerprint(epoch):
        digest, count = hashlib.sha256(), 0
        for features, targets, masks, meta in split.batches(7, seed=19, epoch=epoch, shuffle=True):
            assert 0 < len(targets) <= 7 and features.shape == (len(targets),1368)
            assert features.dtype == np.float32 and targets.dtype == np.int64 and masks.dtype == np.bool_
            assert masks[np.arange(len(targets)),targets].all()
            assert set(meta["match_id"]).issubset(split.match_ids)
            digest.update(features.tobytes() + targets.tobytes())
            count += len(targets)
        assert count == split.samples
        return digest.digest()
    assert fingerprint(1) == fingerprint(1) != fingerprint(2)


def test_nested_learning_curve_subsets_are_match_complete_and_training_only(expanded_root):
    from training.expanded_training import ShardCorpus, nested_match_subset
    train = ShardCorpus(expanded_root).split("train")
    small = nested_match_subset(train, 50)
    large = nested_match_subset(train, 200)
    assert small.match_ids.issubset(large.match_ids) and large.match_ids.issubset(train.match_ids)
    assert small.samples >= 50 and large.samples >= 200
    assert small.match_ids == nested_match_subset(train, 50).match_ids
    assert sum(len(y) for _,y,_,_ in small.batches(32)) == small.samples


def test_streaming_metrics_equal_existing_independent_batch_metrics():
    from training.expanded_training import MetricAccumulator
    from training.metrics import classification_metrics
    logits = torch.tensor([[1.,2.,3.] + [0.]*31, [2.,2.,0.] + [0.]*31, [3.,0.,1.] + [0.]*31])
    masks = np.zeros((3,34),bool)
    masks[:,:3] = True
    from app.mlp import masked_log_probabilities
    logs = masked_log_probabilities(logits, torch.from_numpy(masks)).numpy()
    targets=np.array([2,1,1],np.int64)
    acc=MetricAccumulator()
    acc.update(logs[:1],targets[:1],masks[:1])
    acc.update(logs[1:],targets[1:],masks[1:])
    actual, expected=acc.finish(),classification_metrics(logs,targets,masks)
    for key in ("nll","top1","top3","macro_f1_34","macro_f1_supported","legal_rate"):
        assert actual[key] == pytest.approx(expected[key], abs=1e-8)
    assert actual["confusion_matrix"] == expected["confusion_matrix"]
    assert actual["per_class"] == expected["per_class"]


@pytest.mark.parametrize("kind",["illegal_target","unnormalized","nonfinite"])
def test_streaming_metrics_reject_invalid_probabilities_or_targets(kind):
    from training.expanded_training import MetricAccumulator
    masks=np.zeros((1,34),bool); masks[0,:2]=True
    logs=np.full((1,34),-np.inf); logs[0,:2]=np.log(.5)
    targets=np.array([0],np.int64)
    if kind=="illegal_target": targets[0]=2
    if kind=="unnormalized": logs[0,0]=0.
    if kind=="nonfinite": logs[0,0]=np.nan
    with pytest.raises(ValueError): MetricAccumulator().update(logs,targets,masks)


def test_real_streamed_training_updates_weights_selects_validation_and_reloads_cpu(expanded_root,tmp_path):
    from training.expanded_training import ShardCorpus, train_sharded, evaluate_stream
    from training.train_mlp import weights_sha256
    corpus=ShardCorpus(expanded_root)
    train=nested(corpus,80)
    result=train_sharded(train,corpus.split("validation"),TrainConfig(max_epochs=3,patience=2,batch_size=16,device="cpu"),tmp_path)
    assert result.summary["status"]=="PASS"
    assert result.summary["initial_weights_sha256"] != result.summary["best_weights_sha256"] == weights_sha256(result.model.state_dict())
    assert result.summary["optimizer_steps"]>0
    assert result.summary["best_validation_metrics"]["nll"] == min(r["validation_loss"] for r in result.summary["history"])
    assert evaluate_stream(result.model,corpus.split("validation"),32)["nll"] == pytest.approx(result.summary["best_validation_metrics"]["nll"],abs=1e-6)
    assert result.summary["test_labels_used_for_selection"] is False and result.model.training is False
    assert all(t.device.type=="cpu" for t in result.model.state_dict().values())


def nested(corpus,n):
    from training.expanded_training import nested_match_subset
    return nested_match_subset(corpus.split("train"),n)


def test_epoch_checkpoint_resume_matches_uninterrupted_cpu_training(expanded_root,tmp_path):
    from training.expanded_training import ShardCorpus,train_sharded
    corpus=ShardCorpus(expanded_root)
    train,validation=nested(corpus,80),corpus.split("validation")
    config=TrainConfig(max_epochs=4,patience=4,batch_size=16,device="cpu",seed=17)
    full=train_sharded(train,validation,config,tmp_path/"full")
    paused=train_sharded(train,validation,config,tmp_path/"resume",stop_after_epoch=2)
    assert paused.summary["status"]=="PAUSED"
    resumed=train_sharded(train,validation,config,tmp_path/"resume",resume=True)
    assert resumed.summary["best_weights_sha256"]==full.summary["best_weights_sha256"]
    assert resumed.summary["history"]==full.summary["history"]
    with pytest.raises(ValueError,match="identity"):
        train_sharded(train,validation,replace(config,seed=18),tmp_path/"resume",resume=True)


def test_training_rejects_heldout_split_before_accessing_targets(tmp_path):
    from training.expanded_training import train_sharded
    class HeldOut:
        name="test"
        @property
        def match_ids(self): raise AssertionError("Held-out data accessed")
    with pytest.raises(ValueError,match="train.*validation"):
        train_sharded(HeldOut(),HeldOut(),TrainConfig(),tmp_path)


def test_loader_rejects_corrupt_expanded_contract_before_training(expanded_root,tmp_path):
    from training.expanded_training import ShardCorpus
    from app.domain.exceptions import CorruptedDatasetError
    import shutil
    clone=tmp_path/"expanded"
    shutil.copytree(expanded_root,clone)
    contract=json.loads((clone/"data_contract.json").read_text())
    contract["accepted_samples"]+=1
    (clone/"data_contract.json").write_text(json.dumps(contract))
    with pytest.raises(CorruptedDatasetError): ShardCorpus(clone)


def test_experiments_freeze_protocol_select_validation_only_and_never_open_test(expanded_root,tmp_path,monkeypatch):
    from training.expanded_training import ShardCorpus,run_experiments
    original=ShardCorpus.split
    def training_only(self,name):
        assert name not in ("test","historical_test"), "Experiments must not open held-out splits"
        return original(self,name)
    monkeypatch.setattr(ShardCorpus,"split",training_only)
    result=run_experiments(expanded_root,tmp_path/"experiments",tmp_path/"v2.pt",TrainConfig(max_epochs=2,patience=1,device="cpu"),budgets=(50,250))
    assert result["status"]=="FROZEN"
    assert result["test_labels_used_for_selection"] is False
    comparison=json.loads((tmp_path/"experiments"/"experiment_comparison.json").read_text())
    assert result["validation_nll"]==min(r["validation"]["nll"] for r in comparison["eligible_full_data_candidates"])
    curve=json.loads((tmp_path/"experiments"/"learning_curve.json").read_text())
    assert len(curve["points"])==3 and [p["train_samples"] for p in curve["points"]]==sorted(p["train_samples"] for p in curve["points"])
    before=(tmp_path/"experiments"/"selection_freeze.json").read_bytes()
    with pytest.raises(ValueError,match="frozen"):
        run_experiments(expanded_root,tmp_path/"experiments",tmp_path/"v2.pt",TrainConfig(max_epochs=2,patience=1,device="cpu"))
    assert (tmp_path/"experiments"/"selection_freeze.json").read_bytes()==before


@pytest.mark.parametrize("change",["duplicate_shard","omitted_shard","substituted_shard","roles","split_counts","encoder_source"])
def test_published_contract_must_match_all_audited_fields_before_loading(expanded_root,tmp_path,change):
    from training.expanded_training import ShardCorpus
    from app.domain.exceptions import CorruptedDatasetError
    import shutil
    root=tmp_path/"expanded";shutil.copytree(expanded_root,root)
    path=root/"data_contract.json";value=json.loads(path.read_text())
    if change=="duplicate_shard":value["shards"].append(value["shards"][0])
    elif change=="omitted_shard":value["shards"].pop()
    elif change=="substituted_shard":value["shards"][0]["path"]="shards/99999999"
    elif change=="roles":value["original_roles"][next(iter(value["original_roles"]))]="test"
    elif change=="split_counts":value["splits"]["train"]["samples"]+=1
    else:value["implementation_sha256"]["app/engine/feature_encoder.py"]="0"*64
    path.write_text(json.dumps(value))
    with pytest.raises(CorruptedDatasetError):ShardCorpus(root)


def test_interrupted_resume_pointer_retains_previous_complete_checkpoint(tmp_path,monkeypatch):
    import training.expanded_training as module
    path=tmp_path/"training_resume.pt"
    module.save_training_state(path,{"history":[{"epoch":1}],"model":{"weight":torch.tensor([1.])}})
    original=path.with_suffix(".sha256.json").read_bytes()
    real=module.write_json_report
    def fail(pointer,value):raise OSError("interrupted resume pointer")
    monkeypatch.setattr(module,"write_json_report",fail)
    with pytest.raises(OSError,match="interrupted"):
        module.save_training_state(path,{"history":[{"epoch":1},{"epoch":2}],"model":{"weight":torch.tensor([2.])}})
    monkeypatch.setattr(module,"write_json_report",real)
    assert path.with_suffix(".sha256.json").read_bytes()==original
    pointer=json.loads(original)
    committed=path.parent/pointer.get("generation",path.name)
    assert hashlib.sha256(committed.read_bytes()).hexdigest()==pointer["sha256"], "Last committed generation must remain recoverable"
    loaded=module.load_training_state(path)
    assert len(loaded["history"])==1 and loaded["model"]["weight"].item()==1.
