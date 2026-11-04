"""Portable local state_dict artifacts; validate metadata before deserialization."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

import torch

from app.domain.exceptions import MahjongError
from app.domain.models import ENCODER_VERSION
from app.domain.tiles import TILE_LIST
from app.mlp import MLP_SPEC, MahjongDiscardMLP,parameter_count,validate_architecture


class CheckpointValidationError(MahjongError):
    pass


def checkpoint_sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_metadata(contract: dict, data_report: dict, training_summary: dict,model_spec=None) -> dict:
    if training_summary["status"] != "PASS" or training_summary["test_labels_used_for_selection"] is not False:
        raise CheckpointValidationError("Only completed train/validation-only runs may be saved")
    spec=validate_architecture(MLP_SPEC if model_spec is None else model_spec)
    return {
        "format_version": 1, "status": "TRAINED", "architecture": spec, "parameter_count": parameter_count(spec),
        "input_shape": [38, 4, 9], "input_dtype": "int8", "output_classes": 34,
        "preprocessing": {"order": "C", "model_dtype": "float32", "normalization": "none", "features": "obs_only"},
        "tile_order": list(TILE_LIST), "class_to_action": list(range(2, 36)), "encoder_version": ENCODER_VERSION,
        "dataset": {"id": contract["dataset_id"], "revision": contract["dataset_revision"], "phase1_run_id": contract["run_id"], "npz_sha256": contract["samples_sha256"], "manifest_sha256": contract["manifest_sha256"], "accepted_samples": contract["accepted_samples"], "accepted_matches": contract["accepted_matches"], "split_algorithm": contract["grouping"]["algorithm"], "splits": {name: {k: report[k] for k in ("samples", "matches")} for name, report in data_report["splits"].items()}},
        "training": {"config": copy.deepcopy(training_summary["config"]), "optimizer": "AdamW", "loss": "masked_cross_entropy", "initialized_from_random": True, "best_epoch": training_summary["best_epoch"], "epochs_executed": training_summary["epochs_executed"], "device": training_summary["device"], "elapsed_seconds": training_summary["elapsed_seconds"], "optimizer_steps": training_summary["optimizer_steps"], "initial_weights_sha256": training_summary["initial_weights_sha256"], "best_weights_sha256": training_summary["best_weights_sha256"], "selection": "lowest validation masked NLL", "test_labels_used_for_selection": False},
        "validation_metrics": copy.deepcopy(training_summary["best_validation_metrics"]), "test_evaluation": None,
        "torch_version": str(torch.__version__), "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "score_meaning": "Masked model distribution over observed discard behavior; not calibrated winning probabilities",
    }


def _validate_development_metadata(metadata):
    def require(condition,message):
        if not condition:raise ValueError(message)
    digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(metadata['optimization_phase']=='2.2','Unknown optimization phase')
    dataset=metadata['dataset'];dev=metadata['development']
    require(dataset.get('dataset_version')=='expanded_strict_v2','Optimization dataset version mismatch')
    require(dev['version']=='phase2.2-dev-v1' and dev['evaluation_kind']=='internal_group_development','Unknown development protocol')
    require(dev['selection_metric']=='validation_nll' and dev['new_blind_test_available'] is False and dev['historical_test_labels_used_for_selection'] is False,'Invalid development/test lineage claim')
    require(dev['fold_salt']=='phase2.2-dev-fold-v1:' and dev['fold_count']==5 and type(dev['fold_id'])is int and 0<=dev['fold_id']<5,'Invalid development fold')
    values={}
    for role in ('training','validation','historical_test'):
        ids=dev[role+'_match_ids']
        require(isinstance(ids,list) and all(isinstance(m,str) and re.fullmatch(r'[0-9a-f]{24}',m) for m in ids),'Invalid development match IDs')
        require(ids==sorted(set(ids)) and digest(ids)==dev[role+'_match_ids_sha256'],'Development match identity checksum mismatch')
        values[role]=set(ids)
    train,val,historical=(values[k] for k in ('training','validation','historical_test'))
    require(bool(train) and bool(val) and not train&val and not historical&(train|val),'Development/historical test overlap')
    require(len(train|val)==dataset['splits']['train']['matches']+dataset['splits']['validation']['matches'],'Development pool match count mismatch')
    require(len(historical)==dataset['splits']['test']['matches']+dataset['historical_test']['matches'],'Historical test exclusion count mismatch')
    groups=dev['trajectory_group_keys'];pool=train|val
    require(isinstance(groups,dict) and set(groups).issubset(pool) and set(groups.values()).issubset(pool),'Trajectory group outside development pool')
    require(all(groups.get(rep,rep)==rep and rep<=member for member,rep in groups.items()),'Invalid canonical trajectory group')
    bucket=lambda match:int.from_bytes(hashlib.sha256((dev['fold_salt']+groups.get(match,match)).encode()).digest()[:8],'big')%5
    require(all(bucket(m)!=dev['fold_id'] for m in train) and all(bucket(m)==dev['fold_id'] for m in val),'Development IDs disagree with declared fold')
    require(dev['training_samples']==metadata['training']['training_subset']['samples'] and len(train)==metadata['training']['training_subset']['matches'],'Actual training subset count mismatch')
    require(dev['validation_samples']==metadata['validation_metrics']['samples'] and dev['training_samples']+dev['validation_samples']==dataset['splits']['train']['samples']+dataset['splits']['validation']['samples'],'Development sample count mismatch')
    require(dev['seed']==metadata['training']['config']['seed'],'Development seed mismatch')
    for key in ('protocol_sha256','lineage_content_sha256','history_sha256'):
        require(isinstance(dev[key],str) and re.fullmatch(r'[0-9a-f]{64}',dev[key]) is not None,'Invalid development evidence checksum')
    require(isinstance(dev['history_reference'],str) and bool(dev['history_reference']),'Missing training history reference')


def validate_metadata(metadata: dict, expected_contract: dict | None = None, require_hash=True):
    def check(condition, message):
        if not condition:
            raise CheckpointValidationError(message)
    try:
        check(metadata["format_version"] == 1 and metadata["status"] == "TRAINED", "Unsupported/untrained checkpoint format")
        spec=validate_architecture(metadata['architecture'])
        check(metadata["parameter_count"] == parameter_count(spec), "Incompatible MLP parameter count")
        check(metadata["input_shape"] == [38, 4, 9] and metadata["input_dtype"] == "int8" and metadata["output_classes"] == 34, "Incompatible input/output contract")
        check(metadata["encoder_version"] == ENCODER_VERSION, "Incompatible encoder version")
        check(metadata["tile_order"] == list(TILE_LIST) and metadata["class_to_action"] == list(range(2, 36)), "Tile/action mapping mismatch")
        check(metadata["preprocessing"] == {"order": "C", "model_dtype": "float32", "normalization": "none", "features": "obs_only"}, "Incompatible preprocessing")
        training, dataset = metadata["training"], metadata["dataset"]
        check(training["loss"] == "masked_cross_entropy" and training["initialized_from_random"] is True and training["test_labels_used_for_selection"] is False, "Training provenance mismatch")
        check(1 <= training["best_epoch"] <= training["epochs_executed"] and training["optimizer_steps"] > 0, "Invalid selected epoch/training steps")
        check(training["initial_weights_sha256"] != training["best_weights_sha256"], "Weights were not trained")
        for key in ("npz_sha256", "manifest_sha256"):
            check(isinstance(dataset[key], str) and re.fullmatch(r"[0-9a-f]{64}", dataset[key]) is not None, "Invalid dataset checksum")
        check(isinstance(dataset["id"], str) and bool(dataset["id"]) and isinstance(dataset["phase1_run_id"], str) and bool(dataset["phase1_run_id"]), "Missing dataset identity")
        check(set(dataset["splits"]) == {"train", "validation", "test"} and dataset["accepted_samples"] > 0, "Missing split metadata")
        if "dataset_version" in dataset or "expanded_run_id" in dataset:
            check(dataset["dataset_version"] == "expanded_strict_v2" and isinstance(dataset["expanded_run_id"], str) and bool(dataset["expanded_run_id"]), "Invalid expanded dataset identity")
            for key in ("contract_sha256", "contract_content_sha256"):
                check(re.fullmatch(r"[0-9a-f]{64}", dataset[key]) is not None, "Missing expanded contract checksum")
            shards = dataset["shards"]
            check(isinstance(shards, list) and bool(shards) and len({s["path"] for s in shards}) == len(shards), "Invalid expanded shard inventory")
            check(all(isinstance(s["path"], str) and re.fullmatch(r"shards/[0-9]{8}", s["path"]) and s["samples"] >= 0 and set(s["sha256"]) == {"samples.npz", "manifest.csv.gz", "audit.jsonl"} and all(re.fullmatch(r"[0-9a-f]{64}", v) for v in s["sha256"].values()) for s in shards), "Invalid expanded shard metadata")
            digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            check(digest([{"path": s["path"], "sha256": s["sha256"]["samples.npz"]} for s in shards]) == dataset["npz_sha256"], "Expanded sample inventory checksum mismatch")
            check(digest([{"path": s["path"], "sha256": s["sha256"]["manifest.csv.gz"]} for s in shards]) == dataset["manifest_sha256"], "Expanded manifest inventory checksum mismatch")
            check(sum(s["samples"] for s in shards) == dataset["accepted_samples"], "Expanded shard sample count mismatch")
            check(sum(v["samples"] for v in dataset["splits"].values()) + dataset["historical_test"]["samples"] == dataset["accepted_samples"], "Expanded historical split count mismatch")
        if expected_contract is not None:
            check(expected_contract["status"] == "READY" and expected_contract["encoder_version"] == ENCODER_VERSION, "Expected data contract is not ready")
            run_key = "expanded_run_id" if expected_contract.get("dataset_version") == "expanded_strict_v2" else "phase1_run_id"
            pairs = {"id": "dataset_id", "revision": "dataset_revision", run_key: "run_id", "npz_sha256": "samples_sha256", "manifest_sha256": "manifest_sha256", "accepted_samples": "accepted_samples", "accepted_matches": "accepted_matches"}
            check(all(dataset[a] == expected_contract[b] for a, b in pairs.items()), "Checkpoint dataset identity differs from expected contract")
            check(dataset["split_algorithm"] == expected_contract["grouping"]["algorithm"], "Split algorithm mismatch")
            if run_key == "expanded_run_id":
                check(dataset["contract_content_sha256"] == digest(expected_contract), "Expanded contract content mismatch")
        if 'optimization_phase' in metadata or 'development' in metadata:
            _validate_development_metadata(metadata)
        if require_hash:
            check(re.fullmatch(r"[0-9a-f]{64}", metadata["checkpoint_sha256"]) is not None, "Invalid checkpoint checksum")
            check(metadata["model_version"] == f"{spec['architecture_version']}:{metadata['checkpoint_sha256'][:12]}", "Model version/checksum mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        raise CheckpointValidationError(f"Malformed model metadata: {exc}") from exc


def _write_metadata(path, metadata):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(metadata, stream, indent=2, allow_nan=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_checkpoint(model: MahjongDiscardMLP, path: Path, metadata: dict) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = copy.deepcopy(metadata)
    validate_metadata(value, require_hash=False)
    if model.architecture!=value['architecture'] or sum(p.numel() for p in model.parameters())!=value['parameter_count']:
        raise CheckpointValidationError("Model and metadata architecture differ")
    state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
    if not all(tensor.dtype == torch.float32 and torch.isfinite(tensor).all() for tensor in state.values()):
        raise CheckpointValidationError("Weights must be finite float32 tensors")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
        torch.save(state, temporary)
        temporary.replace(path)
        value["checkpoint_sha256"] = checkpoint_sha256(path)
        value["model_version"] = f"{value['architecture']['architecture_version']}:{value['checkpoint_sha256'][:12]}"
        _write_metadata(path.with_suffix(".metadata.json"), value)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return value


def load_checkpoint(path: Path, metadata_path: Path | None = None, expected_contract: dict | None = None):
    path = Path(path)
    metadata_path = Path(metadata_path) if metadata_path is not None else path.with_suffix(".metadata.json")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        validate_metadata(metadata, expected_contract)
        if checkpoint_sha256(path) != metadata["checkpoint_sha256"]:
            raise CheckpointValidationError("Checkpoint SHA-256 mismatch")
        state = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(state, dict) or not state or not all(isinstance(k, str) and isinstance(v, torch.Tensor) and v.dtype == torch.float32 and torch.isfinite(v).all() for k, v in state.items()):
            raise CheckpointValidationError("Checkpoint must contain finite float32 state_dict tensors")
        digest=hashlib.sha256()
        for name,tensor in sorted(state.items()):
            digest.update(name.encode());digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
        if digest.hexdigest()!=metadata['training']['best_weights_sha256']:
            raise CheckpointValidationError("Selected weight-content checksum mismatch")
        model = MahjongDiscardMLP(metadata['architecture'])
        model.load_state_dict(state, strict=True)
        model.eval()
        return model, metadata
    except CheckpointValidationError:
        raise
    except Exception as exc:
        raise CheckpointValidationError(f"Cannot load validated local checkpoint: {exc}") from exc
