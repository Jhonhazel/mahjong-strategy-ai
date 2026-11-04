"""Audit actual NPZ rows and verify aggregate duplication by row fingerprints."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

from app.domain.exceptions import CorruptedDatasetError
from app.domain.tiles import TILE_LIST
from training.dataset_loader import DATASET_ID, DATASET_REVISION, file_sha256
from training.reporting import write_json_report


def row_fingerprints(arrays):
    obs, mask, act, score = (arrays[k] for k in ("obs", "mask", "act", "score"))
    for i in range(len(act)):
        digest = hashlib.sha256(obs[i])
        digest.update(mask[i])
        digest.update(act[i:i + 1])
        digest.update(score[i:i + 1])
        yield digest.digest()


def validate_arrays(arrays, require_legal_labels=True):
    base_keys = {"obs", "mask", "act", "score"}
    if set(arrays) not in (base_keys, base_keys | {"match_id", "seat"}):
        raise CorruptedDatasetError(f"Unexpected array keys: {list(arrays)}")
    obs, mask, act, score = (arrays[k] for k in ("obs", "mask", "act", "score"))
    if act.ndim != 1:
        raise CorruptedDatasetError(f"act must be one-dimensional, found {act.shape}")
    n = len(act)
    required = {"obs": ((n, 38, 4, 9), np.int8), "mask": ((n, 235), np.bool_), "act": ((n,), np.int16), "score": ((n,), np.float32)}
    for key, (shape, dtype) in required.items():
        value = arrays[key]
        if value.shape != shape or value.dtype != dtype:
            raise CorruptedDatasetError(f"Invalid {key}: {value.shape} / {value.dtype}")
    if not np.isfinite(score).all():
        raise CorruptedDatasetError("Non-finite score")
    if np.any((act < 2) | (act >= 36)):
        raise CorruptedDatasetError("Action outside discard range 2..35")
    if require_legal_labels and not np.all(mask[np.arange(n), act]):
        raise CorruptedDatasetError("Recorded label is illegal in its mask")
    if obs[:, :, 3, 7:].any() or np.any((obs != 0) & (obs != 1)):
        raise CorruptedDatasetError("Non-binary observation or nonzero honor padding")
    if "match_id" in arrays:
        matches, seats = arrays["match_id"], arrays["seat"]
        if matches.shape != (n,) or matches.dtype.kind != "U" or np.any(matches == ""):
            raise CorruptedDatasetError("Invalid match_id metadata")
        if seats.shape != (n,) or seats.dtype != np.int8 or np.any((seats < 0) | (seats > 3)):
            raise CorruptedDatasetError("Invalid seat metadata")
    return n


def audit_decisions_directory(decisions_dir: Path, output_json_path: Path):
    paths = sorted(Path(decisions_dir).glob("*.npz"), key=lambda p: (p.stem.startswith("_"), p.name))
    report = {"status": "PASS", "dataset_id": DATASET_ID, "revision": DATASET_REVISION, "individual_player_file_count": 0, "aggregate_file_count": 0, "total_individual_decisions": 0, "illegal_label_count": 0, "individual_players": [], "aggregate_bundles_excluded_from_sum": [], "errors": []}
    all_rows = Counter()
    distribution = np.zeros(34, dtype=np.int64)
    if not paths:
        report["errors"].append({"reason": "No NPZ files"})
    for path in paths:
        try:
            with np.load(path, allow_pickle=False) as archive:
                arrays = {k: archive[k] for k in archive.files}
            n = validate_arrays(arrays, require_legal_labels=False)
            illegal = np.flatnonzero(~arrays["mask"][np.arange(n), arrays["act"]])
            fingerprints = Counter(row_fingerprints(arrays))
            entry = {"filename": path.name, "rows": n, "source_sha256": file_sha256(path), "arrays": {k: {"shape": list(v.shape), "dtype": str(v.dtype)} for k, v in arrays.items()}, "all_actions_legal_in_mask": not len(illegal), "illegal_label_count": len(illegal), "illegal_row_examples": illegal[:10].tolist()}
            if path.stem.startswith("_"):
                subset = not (fingerprints - all_rows)
                entry.update(verified_subset=subset, excluded_from_training=True)
                report["aggregate_bundles_excluded_from_sum"].append(entry)
                report["aggregate_file_count"] += 1
                if not subset or (path.stem == "_allfield" and fingerprints != all_rows):
                    raise CorruptedDatasetError("Aggregate is not the expected multiset of individual rows")
            else:
                report["individual_players"].append(entry)
                report["individual_player_file_count"] += 1
                report["total_individual_decisions"] += n
                report["illegal_label_count"] += len(illegal)
                all_rows.update(fingerprints)
                distribution += np.bincount(arrays["act"] - 2, minlength=34)
            if len(illegal):
                report["errors"].append({"filename": path.name, "reason": "Recorded labels illegal in masks", "count": len(illegal)})
            del arrays
        except (CorruptedDatasetError, ValueError, OSError, zipfile.BadZipFile) as exc:
            report["errors"].append({"filename": path.name, "reason": str(exc)})
    report.update(obs_shape_per_sample=[38, 4, 9], obs_dtype="int8", mask_shape_per_sample=[235], mask_dtype="bool", action_dtype="int16", score_dtype="float32", class_distribution_34_tiles={tile: int(distribution[i]) for i, tile in enumerate(TILE_LIST)}, distinct_row_fingerprints=len(all_rows), identical_extra_rows=sum(all_rows.values()) - len(all_rows))
    if report["errors"]:
        report["status"] = "FAIL"
    destination = Path(output_json_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json_report(destination, report)
    if report["errors"]:
        raise CorruptedDatasetError(f"Dataset audit failed; see {destination}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets"))
    args = parser.parse_args()
    report = audit_decisions_directory(args.root / "finalist_decisions", args.root / "audit_report.json")
    print(json.dumps({k: report[k] for k in ("status", "individual_player_file_count", "aggregate_file_count", "total_individual_decisions")}, indent=2))


if __name__ == "__main__":
    main()
