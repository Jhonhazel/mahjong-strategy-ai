"""Read-only verification and preparation of the explicitly approved snapshot."""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from app.domain.exceptions import CorruptedDatasetError
from app.domain.models import ENCODER_VERSION
from app.domain.tiles import TILE_LIST
from app.mlp import encode_observations
from training.dataset_loader import DATASET_ID, DATASET_REVISION, file_sha256
from training.inspect_dataset import validate_arrays
from training.reporting import write_json_report
from training.verify_encoder_parity import partition_for_match

APPROVED_RUN_ID = "84c2606383794fa8bc072d5edac7b252"
APPROVED_NPZ_SHA256 = "45303f98bd1d1bca4ac1dbc9228de398456644030bce8b6cb74945be21d86f4d"
APPROVED_MANIFEST_SHA256 = "c496364986aba84efba65b19ae8c96e206bc7453d077ba7b0fc503e728687eb7"
EXPECTED_SPLITS = {"train": (72, 1564), "validation": (7, 213), "test": (5, 102)}
IMPLEMENTATION_FILES = ("app/engine/feature_encoder.py", "app/engine/mcr_referee.py", "training/replay.py")


def _require(condition, message):
    if not condition:
        raise CorruptedDatasetError(message)


@dataclass(frozen=True)
class VerifiedCorpus:
    arrays: dict[str, np.ndarray]
    manifest: list[dict[str, str]]
    contract: dict
    report: dict


@dataclass(frozen=True)
class PreparedSplit:
    name: str
    features: np.ndarray
    targets: np.ndarray
    legal_masks: np.ndarray
    match_ids: np.ndarray
    row_indices: np.ndarray


def validate_alignment(arrays, rows):
    n = validate_arrays(arrays)
    _require("match_id" in arrays and "seat" in arrays, "Strict corpus requires match_id and seat arrays")
    _require(len(rows) == n, "Manifest row count differs from NPZ")
    indexed, identities, source_rows, orders = {}, set(), set(), defaultdict(list)
    for row in rows:
        try:
            i, seat, action, order = (int(row[k]) for k in ("dataset_row", "seat", "target_action_id", "decision_order"))
            source_row, score = int(row["source_row"]), float(row["round_score"])
            match, uid = row["match_id"], row["player_uid"]
            _require(0 <= i < n and i not in indexed, "Duplicate/out-of-range dataset_row")
            _require(re.fullmatch(r"[0-9a-f]{24}", match) is not None and re.fullmatch(r"[0-9a-f]{24}", uid) is not None, "Missing or invalid match/player identity")
            _require(row["source_file"] == f"finalist_games/{match}.json" and source_row >= 0, "Source is not an original strict game decision")
            _require(row["dataset_file"] == "strict_decisions/accepted.npz", "Unexpected historical/aggregate dataset source")
            _require(row["encoder_version"] == ENCODER_VERSION and row["replay_status"] == "verified_exact", "Unverified or incompatible manifest row")
            _require(re.fullmatch(r"[0-9a-f]{64}", row["source_hash"]) is not None, "Invalid source hash")
            _require(match == arrays["match_id"][i] and seat == int(arrays["seat"][i]), "Manifest match/seat differs from NPZ")
            _require(action == int(arrays["act"][i]) and np.isfinite(score) and score == float(arrays["score"][i]), "Manifest action/score differs from NPZ")
            identity = (match, seat, order)
            source_identity = (row["source_file"], source_row)
            _require(order >= 0 and identity not in identities and source_identity not in source_rows, "Duplicate accepted sample identity")
            identities.add(identity)
            source_rows.add(source_identity)
            orders[(match, seat)].append(order)
            indexed[i] = row
        except (KeyError, ValueError, TypeError) as exc:
            raise CorruptedDatasetError(f"Malformed manifest row: {exc}") from exc
    _require(set(indexed) == set(range(n)), "Manifest dataset_row indices are incomplete")
    _require(all(sorted(v) == list(range(len(v))) for v in orders.values()), "Decision order is incomplete within match/seat")
    _require(arrays["mask"][:, 2:36].any(axis=1).all(), "A sample has no legal discard")
    return [indexed[i] for i in range(n)]


def prepare_split(corpus: VerifiedCorpus, name: str) -> PreparedSplit:
    if name not in EXPECTED_SPLITS:
        raise ValueError(f"Unknown split: {name}")
    indices = np.array([i for i, match in enumerate(corpus.arrays["match_id"]) if partition_for_match(str(match)) == name], dtype=np.int64)
    arrays = corpus.arrays
    return PreparedSplit(name, encode_observations(arrays["obs"][indices]), arrays["act"][indices].astype(np.int64) - 2, arrays["mask"][indices, 2:36].copy(), arrays["match_id"][indices].copy(), indices)


def _summarize_split(arrays, manifest, name):
    indices = [i for i, match in enumerate(arrays["match_id"]) if partition_for_match(str(match)) == name]
    labels = arrays["act"][indices] - 2
    counts = np.bincount(labels, minlength=34)
    return {"samples": len(indices), "matches": len(set(arrays["match_id"][indices])), "class_distribution": {t: int(counts[i]) for i, t in enumerate(TILE_LIST)}, "zero_support_classes": [t for i, t in enumerate(TILE_LIST) if counts[i] == 0], "player_distribution": dict(Counter(manifest[i]["player_uid"] for i in indices)), "legal_action_count_distribution": {str(k): v for k, v in sorted(Counter(arrays["mask"][indices, 2:36].sum(axis=1).tolist()).items())}}


def validate_dataset(root: Path, report_path: Path | None = None) -> VerifiedCorpus:
    root = Path(root)
    destination = Path(report_path) if report_path is not None else root / "artifacts/phase2/data_validation.json"
    write_json_report(destination, {"status": "RUNNING"})
    try:
        datasets = root / "datasets"
        contract = json.loads((datasets / "data_contract.json").read_text(encoding="utf-8"))
        parity = json.loads((datasets / "parity_report.json").read_text(encoding="utf-8"))
        audit = json.loads((datasets / "strict_audit_report.json").read_text(encoding="utf-8"))
        _require(contract["status"] == "READY" and parity["status"] == audit["status"] == "PASS", "Phase 1 contract/reports are not READY/PASS")
        _require(contract["selected_strategy"] == "strict_reextraction" and contract["historical_npz_approved"] is False, "Historical NPZ/incorrect strategy is not approved")
        _require(contract["dataset_id"] == DATASET_ID and contract["dataset_revision"] == DATASET_REVISION, "Unapproved dataset identity/revision")
        _require(contract["run_id"] == parity["run_id"] == APPROVED_RUN_ID, "Approved Phase 1 run ID mismatch")
        _require(contract["encoder_version"] == parity["encoder_version"] == ENCODER_VERSION, "Encoder version mismatch")
        _require(contract["samples"] == "strict_decisions/accepted.npz" and contract["manifest"] == "decision_manifest.csv", "Unexpected corpus paths")
        expected_specs = {"obs": {"shape": [38, 4, 9], "dtype": "int8", "flat_size": 1368}, "legal_mask": {"shape": [235], "dtype": "bool"}, "legal_discard_mask": {"shape": [34], "dtype": "bool", "slice": [2, 36]}}
        _require(all(contract[k] == value for k, value in expected_specs.items()), "Observation/mask contract mismatch")
        hashes = {"samples": file_sha256(datasets / contract["samples"]), "manifest": file_sha256(datasets / contract["manifest"])}
        _require(hashes["samples"] == contract["samples_sha256"] == APPROVED_NPZ_SHA256, "Accepted NPZ hash differs from approved snapshot")
        _require(hashes["manifest"] == contract["manifest_sha256"] == APPROVED_MANIFEST_SHA256, "Manifest hash differs from approved snapshot")
        _require(set(contract["implementation_sha256"]) == set(IMPLEMENTATION_FILES), "Unexpected implementation hash paths")
        source_hashes = {name: file_sha256(root / name) for name in IMPLEMENTATION_FILES}
        _require(source_hashes == contract["implementation_sha256"], "Phase 1 implementation hash mismatch")
        _require(audit["total_individual_decisions"] == 1879 and audit["illegal_label_count"] == 0 and len(audit["individual_players"]) == 1 and audit["individual_players"][0]["source_sha256"] == hashes["samples"], "Strict audit does not bind this accepted NPZ")
        with np.load(datasets / contract["samples"], allow_pickle=False) as archive:
            arrays = {k: archive[k] for k in archive.files}
        _require(set(arrays) == {"obs", "mask", "act", "score", "match_id", "seat"}, "Unexpected NPZ arrays")
        with (datasets / contract["manifest"]).open(encoding="utf-8", newline="") as stream:
            manifest = validate_alignment(arrays, list(csv.DictReader(stream)))
        _require(len(manifest) == contract["accepted_samples"] == parity["accepted_samples"] == 1879, "Accepted sample count mismatch")
        _require(len(set(arrays["match_id"])) == contract["accepted_matches"] == parity["accepted_matches"] == 84, "Accepted match count mismatch")
        split_reports = {name: _summarize_split(arrays, manifest, name) for name in EXPECTED_SPLITS}
        for name, (matches, samples) in EXPECTED_SPLITS.items():
            _require((split_reports[name]["matches"], split_reports[name]["samples"]) == (matches, samples), f"Approved {name} split changed")
        match_groups = {name: {str(m) for m in arrays["match_id"] if partition_for_match(str(m)) == name} for name in EXPECTED_SPLITS}
        intersections = {f"{a}_{b}": sorted(match_groups[a] & match_groups[b]) for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))}
        _require(not any(intersections.values()), "Match leakage between splits")
        signatures = []
        for i in range(len(manifest)):
            digest = hashlib.sha256(arrays["obs"][i])
            digest.update(arrays["mask"][i])
            digest.update(arrays["act"][i:i + 1])
            signatures.append(digest.hexdigest())
        counts = np.bincount(arrays["act"] - 2, minlength=34)
        report = {"status": "PASS", "run_id": contract["run_id"], "dataset_id": DATASET_ID, "dataset_revision": DATASET_REVISION, "encoder_version": ENCODER_VERSION, "samples": 1879, "matches": 84, "hashes": hashes, "implementation_sha256": source_hashes, "phase1_reports": {"contract_parity_run_ids_match": True, "strict_audit_run_id": audit.get("run_id"), "strict_audit_binding": "NPZ SHA-256 and sample count; Phase 1 schema has no run_id"}, "splits": split_reports, "match_intersections": intersections, "player_identities": sorted({r["player_uid"] for r in manifest}), "player_overlap_note": "Match-disjoint evaluation; some known players appear in multiple splits, not unseen-player generalization", "class_distribution": {t: int(counts[i]) for i, t in enumerate(TILE_LIST)}, "duplicate_sample_identities": 0, "repeated_feature_mask_label_rows": len(signatures) - len(set(signatures)), "preprocessing": "C-order int8 obs only -> float32[1368], no normalization; scores/IDs excluded", "split_algorithm": contract["grouping"]["algorithm"], "hash_limit": "Artifact identity checks do not independently prove every Mahjong rule"}
        write_json_report(destination, report)
        return VerifiedCorpus(arrays, manifest, contract, report)
    except Exception as exc:
        write_json_report(destination, {"status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"})
        if isinstance(exc, CorruptedDatasetError):
            raise
        raise CorruptedDatasetError(f"Phase 2 dataset validation failed: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, default=Path("artifacts/phase2/data_validation.json"))
    args = parser.parse_args()
    report = validate_dataset(args.root, args.report).report
    print(json.dumps({"status": report["status"], "samples": report["samples"], "matches": report["matches"], "splits": {k: {f: v[f] for f in ("samples", "matches", "zero_support_classes")} for k, v in report["splits"].items()}}, indent=2))


if __name__ == "__main__":
    main()
