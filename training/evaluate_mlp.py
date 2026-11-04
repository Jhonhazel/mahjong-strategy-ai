"""Evaluate the frozen best checkpoint; repeated runs only verify existing results."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
import torch

from app.mlp import rank_legal_classes
from app.model_checkpoint import checkpoint_sha256, load_checkpoint
from training.baselines import evaluate_baselines
from training.metrics import classification_metrics
from training.phase2_dataset import prepare_split, validate_dataset
from training.reporting import write_json_report
from training.train_mlp import predict_log_probabilities

SUMMARY_METRICS = ("nll", "top1", "top3", "macro_f1_34", "macro_f1_supported", "legal_rate")
EVALUATION_FILES = ("model_freeze.json", "test_predictions.json", "per_class_metrics.csv", "confusion_matrix.csv", "baseline_metrics.json")


def recalculate_metrics(rows: list[dict]) -> dict:
    """Independent plain-Python calculation from saved predictions, no metric helper."""
    if not rows:
        raise ValueError("Cannot evaluate empty predictions")
    supports, predicted_counts, correct = Counter(), Counter(), Counter()
    for row in rows:
        actual, predicted = row["target_class"], row["predicted_class"]
        if not 0 <= actual < 34 or not 0 <= predicted < 34 or not math.isfinite(row["target_log_probability"]):
            raise ValueError("Invalid saved prediction")
        supports[actual] += 1
        predicted_counts[predicted] += 1
        if actual == predicted:
            correct[actual] += 1
    f1 = {}
    for i in range(34):
        denominator = supports[i] + predicted_counts[i]
        f1[i] = 2 * correct[i] / denominator if denominator else 0.
    return {"nll": -math.fsum(row["target_log_probability"] for row in rows) / len(rows), "top1": sum(correct.values()) / len(rows), "top3": sum(row["target_class"] in row["top3"] for row in rows) / len(rows), "macro_f1_34": math.fsum(f1.values()) / 34, "macro_f1_supported": math.fsum(f1[i] for i in supports) / len(supports), "legal_rate": sum(row["predicted_class"] in row["legal_classes"] for row in rows) / len(rows)}


def _verify_saved_evidence(report_dir, existing, recomputed, predictions, metadata, metadata_path):
    try:
        hashes = existing["artifact_sha256"]
        if set(hashes) != set(EVALUATION_FILES):
            raise ValueError("Incomplete evaluation artifact checksums")
        for name in EVALUATION_FILES:
            path = report_dir / name
            if not path.is_file() or checkpoint_sha256(path) != hashes[name]:
                raise ValueError(f"Missing or changed evaluation artifact: {name}")
        if checkpoint_sha256(metadata_path) != existing["metadata_sha256"] or metadata.get("test_evaluation") != _evaluation_summary(existing):
            raise ValueError("Checkpoint final evaluation metadata is incomplete or changed")
        for key in ("checkpoint_sha256", "model_version", "phase1_run_id", "dataset_sha256", "manifest_sha256", "test_samples", "test_matches"):
            if existing[key] != recomputed[key]:
                raise ValueError(f"Evaluation identity mismatch: {key}")
        for key in SUMMARY_METRICS:
            if not math.isclose(existing["mlp"][key], recomputed["mlp"][key], rel_tol=0, abs_tol=1e-8):
                raise ValueError("Reverification metrics differ from the frozen evaluation")
        if existing["mlp"]["per_class"] != recomputed["mlp"]["per_class"] or existing["mlp"]["confusion_matrix"] != recomputed["mlp"]["confusion_matrix"] or existing["baselines"] != recomputed["baselines"]:
            raise ValueError("Per-class/confusion/baseline results differ")
        payload = json.loads((report_dir / "test_predictions.json").read_text(encoding="utf-8"))
        saved = payload["predictions"]
        if payload["checkpoint_sha256"] != existing["checkpoint_sha256"] or len(saved) != len(predictions):
            raise ValueError("Saved prediction identity/count mismatch")
        for before, after in zip(saved, predictions):
            for key in ("dataset_row", "match_id", "target_class", "predicted_class", "top3", "legal_classes"):
                if before[key] != after[key]:
                    raise ValueError(f"Saved prediction mismatch: {key}")
            if not math.isclose(before["target_log_probability"], after["target_log_probability"], abs_tol=1e-8, rel_tol=0) or not np.allclose(before["class_scores"], after["class_scores"], atol=1e-7, rtol=1e-5):
                raise ValueError("Saved prediction scores differ from actual model inference")
        independent = recalculate_metrics(saved)
        if not all(math.isclose(independent[k], existing["mlp"][k], rel_tol=0, abs_tol=1e-8) for k in SUMMARY_METRICS):
            raise ValueError("Saved prediction metric recalculation differs")
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Incomplete evaluation evidence: {exc}") from exc


def _evaluation_summary(result):
    return {"checkpoint_sha256": result["checkpoint_sha256"], "samples": result["test_samples"], "matches": result["test_matches"], "metrics": {k: result["mlp"][k] for k in SUMMARY_METRICS}, "report": "evaluation_metrics.json"}


def evaluate_checkpoint(checkpoint: Path, root: Path, report_dir: Path, verify_existing=False, resume=False):
    checkpoint, root, report_dir = Path(checkpoint), Path(root), Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "evaluation_metrics.json"
    if verify_existing and resume:
        raise ValueError("Choose verification or recovery, not both")
    existing, failed = None, None
    if report_path.exists():
        previous = json.loads(report_path.read_text(encoding="utf-8"))
        if resume:
            if previous.get("status") not in ("FAIL", "RUNNING"):
                raise ValueError("Recovery requires an incomplete/failed evaluation")
            failed = previous
        elif not verify_existing:
            raise ValueError("Held-out evaluation already exists; use --verify-existing for the same frozen model")
        else:
            existing = previous
            if existing.get("status") != "PASS":
                raise ValueError("Previous evaluation is incomplete; use --resume with the same frozen model")
    elif verify_existing or resume:
        raise ValueError("No existing evaluation to verify/resume")
    corpus = validate_dataset(root, report_dir / "data_validation.json")
    model, metadata = load_checkpoint(checkpoint, expected_contract=corpus.contract)
    torch.set_num_threads(1)
    frozen_hash = checkpoint_sha256(checkpoint)
    if existing is not None and existing["checkpoint_sha256"] != frozen_hash:
        raise ValueError("Frozen checkpoint differs from the held-out evaluation")
    if failed is not None and failed["checkpoint_sha256"] != frozen_hash:
        raise ValueError("Cannot resume evaluation with changed model weights")
    training, validation = prepare_split(corpus, "train"), prepare_split(corpus, "validation")
    validation_logs = predict_log_probabilities(model, validation, "cpu")
    validation_metrics = classification_metrics(validation_logs, validation.targets, validation.legal_masks)
    validation_difference = abs(validation_metrics["nll"] - metadata["validation_metrics"]["nll"])
    if validation_difference > 1e-5:
        raise ValueError("Reloaded checkpoint does not reproduce selected validation loss")
    freeze = {"status": "FROZEN", "checkpoint_sha256": frozen_hash, "architecture": metadata["architecture"], "preprocessing": metadata["preprocessing"], "training_config": metadata["training"]["config"], "best_epoch": metadata["training"]["best_epoch"], "dataset_sha256": metadata["dataset"]["npz_sha256"], "manifest_sha256": metadata["dataset"]["manifest_sha256"], "phase1_run_id": metadata["dataset"]["phase1_run_id"], "validation_reload_nll": validation_metrics["nll"], "validation_nll_difference": validation_difference, "test_used_for_selection": False, "frozen_at_utc": datetime.now(timezone.utc).isoformat()}
    freeze_path = report_dir / "model_freeze.json"
    if freeze_path.exists():
        old = json.loads(freeze_path.read_text(encoding="utf-8"))
        identity_keys = ("status", "checkpoint_sha256", "architecture", "preprocessing", "training_config", "best_epoch", "dataset_sha256", "manifest_sha256", "phase1_run_id", "test_used_for_selection")
        if not isinstance(old, dict) or any(old.get(k) != freeze[k] for k in identity_keys):
            raise ValueError("Frozen model/configuration/data identity mismatch")
    elif verify_existing or resume:
        raise ValueError("Missing original model freeze record")
    else:
        write_json_report(freeze_path, freeze)
    if not verify_existing:
        write_json_report(report_path, {"status": "RUNNING", "checkpoint_sha256": frozen_hash, "model_version": metadata["model_version"]})
    try:
        return _evaluate_and_publish(model, metadata, corpus, training, validation, validation_metrics, validation_difference, frozen_hash, checkpoint, report_dir, existing)
    except Exception as exc:
        if not verify_existing:
            write_json_report(report_path, {"status": "FAIL", "checkpoint_sha256": frozen_hash, "reason": repr(exc), "recovery": "Use --resume only with the same frozen model/configuration/data"})
        raise


def _evaluate_and_publish(model, metadata, corpus, training, validation, validation_metrics, validation_difference, frozen_hash, checkpoint, report_dir, existing):
    report_path = report_dir / "evaluation_metrics.json"
    # Only now create test tensors. No test object is passed to model selection.
    testing = prepare_split(corpus, "test")
    test_logs = predict_log_probabilities(model, testing, "cpu")
    mlp_metrics = classification_metrics(test_logs, testing.targets, testing.legal_masks)
    rankings = rank_legal_classes(test_logs, testing.legal_masks)
    probabilities = np.exp(test_logs)
    predictions = [{"dataset_row": int(testing.row_indices[i]), "match_id": str(testing.match_ids[i]), "target_class": int(testing.targets[i]), "predicted_class": int(rankings[i][0]), "top3": [int(c) for c in rankings[i][:3]], "legal_classes": np.flatnonzero(testing.legal_masks[i]).tolist(), "target_log_probability": float(test_logs[i, testing.targets[i]]), "class_scores": [float(p) for p in probabilities[i]]} for i in range(len(testing.targets))]
    independent = recalculate_metrics(predictions)
    if not all(math.isclose(independent[k], mlp_metrics[k], rel_tol=0, abs_tol=1e-8) for k in SUMMARY_METRICS):
        raise RuntimeError("Independent metric recalculation differs")
    seed = metadata["training"]["config"]["seed"]
    baseline_validation = evaluate_baselines(training.targets, validation, seed)
    baseline_test = evaluate_baselines(training.targets, testing, seed)
    if checkpoint_sha256(checkpoint) != frozen_hash:
        raise RuntimeError("Model checkpoint changed during evaluation")
    result = {"status": "PASS", "checkpoint_sha256": frozen_hash, "model_version": metadata["model_version"], "phase1_run_id": corpus.contract["run_id"], "dataset_sha256": corpus.contract["samples_sha256"], "manifest_sha256": corpus.contract["manifest_sha256"], "test_samples": len(testing.targets), "test_matches": len(set(testing.match_ids)), "selection": "Architecture/configuration/weights frozen before test; minimum validation NLL selected the checkpoint", "test_labels_used_for_selection": False, "evaluation_device": "cpu", "mlp": mlp_metrics, "validation_mlp_cpu": validation_metrics, "validation_reload_nll_difference": validation_difference, "baselines": {"seed": seed, "prior_laplace_alpha": 1., "fit_split": "train", "validation": baseline_validation, "test": baseline_test}, "independent_recalculation": {"status": "PASS", "method": "Plain Python counters and fsum from saved prediction records", "metrics": independent}, "limitation": "102 decisions from five held-out matches, only 33 supported classes; four known player identities with cross-split identity overlap. Classification behavior scores are not winning probabilities or unseen-player generalization."}
    if existing is not None:
        _verify_saved_evidence(report_dir, existing, result, predictions, metadata, checkpoint.with_suffix(".metadata.json"))
        return existing
    write_json_report(report_dir / "test_predictions.json", {"checkpoint_sha256": frozen_hash, "predictions": predictions})
    # Re-read the actual saved file rather than checking only the in-memory list.
    saved_predictions = json.loads((report_dir / "test_predictions.json").read_text(encoding="utf-8"))["predictions"]
    saved_metrics = recalculate_metrics(saved_predictions)
    if not all(math.isclose(saved_metrics[k], mlp_metrics[k], rel_tol=0, abs_tol=1e-8) for k in SUMMARY_METRICS):
        raise RuntimeError("Saved predictions did not preserve evaluation metrics")
    with (report_dir / "per_class_metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(mlp_metrics["per_class"][0]))
        writer.writeheader()
        writer.writerows(mlp_metrics["per_class"])
    with (report_dir / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["true/predicted"] + [row["tile"] for row in mlp_metrics["per_class"]])
        for row, values in zip(mlp_metrics["per_class"], mlp_metrics["confusion_matrix"]):
            writer.writerow([row["tile"]] + values)
    write_json_report(report_dir / "baseline_metrics.json", result["baselines"])
    metadata["test_evaluation"] = _evaluation_summary(result)
    write_json_report(checkpoint.with_suffix(".metadata.json"), metadata)
    result["artifact_sha256"] = {name: checkpoint_sha256(report_dir / name) for name in EVALUATION_FILES}
    result["metadata_sha256"] = checkpoint_sha256(checkpoint.with_suffix(".metadata.json"))
    # PASS is the final write, after required outputs and metadata are durable.
    write_json_report(report_path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/models/mahjong_discard_mlp.pt"))
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/phase2"))
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Recover failed artifact publication for the same frozen model only")
    args = parser.parse_args()
    result = evaluate_checkpoint(args.checkpoint, args.root, args.report_dir, args.verify_existing, args.resume)
    print(json.dumps({"status": result["status"], "test_samples": result["test_samples"], "test_matches": result["test_matches"], "mlp": {k: result["mlp"][k] for k in SUMMARY_METRICS}}, indent=2))


if __name__ == "__main__":
    main()
