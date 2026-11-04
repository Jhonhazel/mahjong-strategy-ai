"""Mask-aware metrics; zero-denominator per-class metrics are defined as zero."""
import numpy as np

from app.domain.tiles import TILE_LIST
from app.mlp import rank_legal_classes


def classification_metrics(log_probabilities: np.ndarray, targets: np.ndarray, legal_masks: np.ndarray, rankings=None) -> dict:
    default_rankings = rank_legal_classes(log_probabilities, legal_masks)
    n = len(log_probabilities)
    if not isinstance(targets, np.ndarray) or targets.shape != (n,) or targets.dtype.kind not in "iu" or np.any((targets < 0) | (targets >= 34)):
        raise ValueError("Targets must be integer class IDs 0..33")
    if not legal_masks[np.arange(n), targets].all():
        raise ValueError("A target is illegal")
    if not np.isneginf(log_probabilities[~legal_masks]).all():
        raise ValueError("Illegal classes must have log probability -inf")
    if not np.allclose(np.exp(log_probabilities).sum(axis=1), 1., rtol=1e-5, atol=1e-6):
        raise ValueError("Log probabilities must normalize over legal classes")
    ordered = default_rankings if rankings is None else rankings
    if len(ordered) != n:
        raise ValueError("Ranking count mismatch")
    for i, ranking in enumerate(ordered):
        if not np.array_equal(np.sort(ranking), np.flatnonzero(legal_masks[i])):
            raise ValueError("Rankings must contain every legal class exactly once")
        if np.any(np.diff(log_probabilities[i, ranking]) > 1e-10):
            raise ValueError("Rankings must descend by score; ties may use a seeded permutation")
    predicted = np.array([r[0] for r in ordered], dtype=np.int64)
    confusion = np.zeros((34, 34), dtype=np.int64)
    np.add.at(confusion, (targets, predicted), 1)
    true_positive = np.diag(confusion)
    support, predicted_counts = confusion.sum(axis=1), confusion.sum(axis=0)
    precision = np.divide(true_positive, predicted_counts, out=np.zeros(34), where=predicted_counts != 0)
    recall = np.divide(true_positive, support, out=np.zeros(34), where=support != 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(34), where=(precision + recall) != 0)
    return {
        "samples": n, "nll": float(-log_probabilities[np.arange(n), targets].astype(np.float64).mean()),
        "top1": float(np.mean(predicted == targets)),
        "top3": sum(int(targets[i] in ranking[:3]) for i, ranking in enumerate(ordered)) / n,
        "macro_f1_34": float(f1.mean()), "macro_f1_supported": float(f1[support > 0].mean()),
        "supported_classes": int(np.count_nonzero(support)),
        "legal_rate": float(legal_masks[np.arange(n), predicted].mean()),
        "per_class": [{"class_id": i, "tile": tile, "support": int(support[i]), "predicted_count": int(predicted_counts[i]), "precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i])} for i, tile in enumerate(TILE_LIST)],
        "confusion_matrix": confusion.tolist(),
        "definitions": {"top3": "Up to three legal classes; if fewer exist use all available", "macro_f1_34": "Mean F1 across all 34 classes, zero-denominator F1=0", "macro_f1_supported": "Mean only over classes with true support >0", "confusion_matrix": "Rows=true class, columns=predicted class", "nll": "Mean negative target log likelihood under legal masked distribution"},
    }
