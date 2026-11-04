"""Validation baselines fitted on training labels only; test waits for freeze."""
import argparse
import json
from pathlib import Path

import numpy as np

from app.mlp import rank_legal_classes
from training.metrics import classification_metrics
from training.phase2_dataset import prepare_split, validate_dataset
from training.reporting import write_json_report


def class_prior_log_probabilities(training_targets: np.ndarray, legal_masks: np.ndarray) -> np.ndarray:
    if training_targets.ndim != 1 or not len(training_targets) or training_targets.dtype.kind not in "iu" or np.any((training_targets < 0) | (training_targets >= 34)):
        raise ValueError("Training labels must be nonempty integer classes 0..33")
    # Alpha=1 keeps NLL finite for a legal class without training support.
    counts = np.bincount(training_targets, minlength=34).astype(np.float64) + 1.
    rank_legal_classes(np.broadcast_to(counts, legal_masks.shape), legal_masks)
    weights = np.where(legal_masks, counts, 0.)
    probabilities = weights / weights.sum(axis=1, keepdims=True)
    logs = np.full(probabilities.shape, -np.inf)
    logs[legal_masks] = np.log(probabilities[legal_masks])
    return logs


def random_legal_log_probabilities(legal_masks: np.ndarray, seed: int):
    rank_legal_classes(np.zeros(legal_masks.shape), legal_masks)
    rng = np.random.default_rng(seed)
    logs = np.full(legal_masks.shape, -np.inf)
    rankings = []
    for i, mask in enumerate(legal_masks):
        legal = np.flatnonzero(mask)
        logs[i, legal] = -np.log(len(legal))
        rankings.append(rng.permutation(legal))
    return logs, rankings


def evaluate_baselines(training_targets, split, seed=2026):
    prior = class_prior_log_probabilities(training_targets, split.legal_masks)
    random_logs, random_rankings = random_legal_log_probabilities(split.legal_masks, seed)
    return {"class_prior": classification_metrics(prior, split.targets, split.legal_masks), "uniform_random_legal": classification_metrics(random_logs, split.targets, split.legal_masks, random_rankings)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, default=Path("artifacts/phase2/baseline_metrics.json"))
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    corpus = validate_dataset(args.root, args.report.parent / "data_validation.json")
    train, validation = prepare_split(corpus, "train"), prepare_split(corpus, "validation")
    result = {"fit_split": "train", "seed": args.seed, "prior_laplace_alpha": 1., "validation": evaluate_baselines(train.targets, validation, args.seed), "test_status": "NOT_EVALUATED; waits for frozen model"}
    write_json_report(args.report, result)
    print(json.dumps({name: {k: value[k] for k in ("nll", "top1", "top3", "macro_f1_34", "legal_rate")} for name, value in result["validation"].items()}, indent=2))


if __name__ == "__main__":
    main()
