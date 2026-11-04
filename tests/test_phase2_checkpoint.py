import copy
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pytest
import torch


@pytest.fixture(scope="module")
def checkpoint_fixture(tmp_path_factory):
    """Temporary unit artifact; not used as the final trained checkpoint."""
    from app.model_checkpoint import build_metadata
    from training.phase2_dataset import validate_dataset, prepare_split
    from training.train_mlp import TrainConfig, train_model
    root = Path(__file__).resolve().parents[1]
    corpus = validate_dataset(root, tmp_path_factory.mktemp("gate") / "data.json")
    config = TrainConfig(max_epochs=1, patience=1, batch_size=32, device="cpu", seed=7)
    run = train_model(prepare_split(corpus, "train"), prepare_split(corpus, "validation"), config)
    summary = {"status": "PASS", "config": asdict(config), "device": "cpu", "epochs_executed": 1, "best_epoch": run.best_epoch, "elapsed_seconds": run.elapsed_seconds, "optimizer_steps": run.optimizer_steps, "initial_weights_sha256": run.initial_weights_sha256, "best_weights_sha256": run.best_weights_sha256, "best_validation_metrics": run.best_validation_metrics, "test_labels_used_for_selection": False, "environment": {"torch": str(torch.__version__)}}
    return run.model, build_metadata(corpus.contract, corpus.report, summary), corpus.contract


def test_cpu_state_dict_roundtrip_and_independent_metadata(tmp_path, checkpoint_fixture):
    from app.model_checkpoint import save_checkpoint, load_checkpoint
    model, metadata, contract = checkpoint_fixture
    model.eval()
    features = torch.rand(3, 1368)
    with torch.inference_mode(): expected = model(features).clone()
    path = tmp_path / "model.pt"
    saved = save_checkpoint(model, path, metadata)
    loaded, actual_metadata = load_checkpoint(path, expected_contract=contract)
    assert actual_metadata["checkpoint_sha256"] == saved["checkpoint_sha256"]
    assert actual_metadata["encoder_version"] == "ijcai2026_mcr_v1_strict"
    assert loaded.training is False
    assert all(p.device.type == "cpu" for p in loaded.parameters())
    with torch.inference_mode(): assert torch.equal(expected, loaded(features))
    state = torch.load(path, map_location="cpu", weights_only=True)
    assert state and all(isinstance(v, torch.Tensor) for v in state.values())
    assert "checkpoint_sha256" not in metadata


@pytest.mark.parametrize("tamper", ["input", "output", "encoder", "tiles", "actions", "dataset", "preprocessing", "corrupt", "missing"])
def test_checkpoint_rejects_incompatible_or_corrupt_artifacts(tmp_path, checkpoint_fixture, tamper):
    from app.model_checkpoint import CheckpointValidationError, save_checkpoint, load_checkpoint
    model, metadata, contract = checkpoint_fixture
    path = tmp_path / "model.pt"
    save_checkpoint(model, path, metadata)
    metadata_path = path.with_suffix(".metadata.json")
    value = json.loads(metadata_path.read_text())
    if tamper == "input": value["architecture"]["input_dim"] = 1
    elif tamper == "output": value["output_classes"] = 35
    elif tamper == "encoder": value["encoder_version"] = "historical"
    elif tamper == "tiles": value["tile_order"].reverse()
    elif tamper == "actions": value["class_to_action"][0] = 0
    elif tamper == "dataset": value["dataset"]["npz_sha256"] = "0" * 64
    elif tamper == "preprocessing": value["preprocessing"]["order"] = "F"
    elif tamper == "corrupt": path.write_bytes(b"truncated")
    else: path.unlink()
    metadata_path.write_text(json.dumps(value))
    with pytest.raises(CheckpointValidationError):
        load_checkpoint(path, expected_contract=contract)


def test_metadata_is_rejected_before_deserialization(tmp_path, checkpoint_fixture, monkeypatch):
    from app.model_checkpoint import CheckpointValidationError, save_checkpoint, load_checkpoint
    model, metadata, _ = checkpoint_fixture
    path = tmp_path / "model.pt"
    save_checkpoint(model, path, metadata)
    meta_path = path.with_suffix(".metadata.json")
    value = json.loads(meta_path.read_text())
    value["encoder_version"] = "incompatible"
    meta_path.write_text(json.dumps(value))
    def unsafe(*args, **kwargs):
        raise AssertionError("Deserialization must not occur for incompatible metadata")
    monkeypatch.setattr(torch, "load", unsafe)
    with pytest.raises(CheckpointValidationError):
        load_checkpoint(path)
