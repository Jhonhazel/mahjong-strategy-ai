"""Fail-closed historical diagnosis and strict log re-extraction.

The accepted corpus is checked against independently driven live referee states;
it is never described as full parity with the historical NPZ archives.
"""
import argparse
from collections import Counter, OrderedDict
import csv
import hashlib
import json
from pathlib import Path
import tarfile
import traceback
import uuid

import numpy as np

from app.domain.exceptions import CorruptedDatasetError, ParityVerificationError
from app.domain.models import ENCODER_VERSION
from training.dataset_loader import DATASET_ID, DATASET_REVISION, file_sha256, validate_safe_tar_member_name
from training.inspect_dataset import validate_arrays
from training.replay import replay_observers, replay_referee, terminal_display
from training.reporting import write_json_report

MANIFEST_FIELDS = ["source_file", "source_row", "match_id", "player_uid", "seat", "decision_order", "target_action_id", "encoder_version", "replay_status", "source_hash", "dataset_file", "dataset_row", "round_score"]


def tracked_seats(game):
    roster, tracked = game["players"], game["our_players"]
    if len(roster) != 4 or {r["seat"] for r in roster} != set(range(4)) or not tracked:
        raise CorruptedDatasetError("Missing or ambiguous roster")
    # A bot can occupy several explicit seats in a self-play match. Each
    # (match_id, seat, uid) is already identified by the roster, not ambiguous.
    if any(not any(r["uid"] == uid for r in roster) for uid in tracked):
        raise CorruptedDatasetError("Tracked uid absent from roster")
    return [(r["uid"], r["seat"]) for r in roster if r["uid"] in tracked]


def partition_for_match(match_id: str) -> str:
    """A deterministic group identity contract, not a Phase 2 training pipeline."""
    bucket = int.from_bytes(hashlib.sha256(("phase1-match-groups-v1:" + match_id).encode()).digest()[:8], "big") % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


def validate_manifest(records):
    sources, groups = {}, {}
    for row in records:
        match = row.get("match_id")
        if not isinstance(match, str) or not match:
            raise CorruptedDatasetError("Missing match identity")
        source = (row["source_file"], str(row["source_row"]))
        if source in sources:
            raise CorruptedDatasetError("Duplicate or conflicting source row")
        sources[source] = match
        split = row.get("split", partition_for_match(match))
        if split not in ("train", "validation", "test") or (match in groups and groups[match] != split):
            raise CorruptedDatasetError("Cross-match split leakage or unknown split")
        groups[match] = split
    return {"match_count": len(groups), "sample_count": len(records), "overlap_count": 0, "group_counts": dict(Counter(groups.values()))}


class _HistoricalIndex:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.cache = OrderedDict()

    def _load(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        with np.load(self.directory / f"{key}.npz", allow_pickle=False) as z:
            arrays = {k: z[k] for k in ("obs", "mask", "act", "score")}
        index = {}
        # Hand/winds locate diagnostic candidates; only full ordered sequences
        # can be called exact. A candidate never creates provenance by itself.
        for row in range(len(arrays["act"])):
            signature = hashlib.sha256(arrays["obs"][row, :6]).digest()
            index.setdefault(signature, []).append(row)
        self.cache[key] = (arrays, index)
        if len(self.cache) > 3:
            self.cache.popitem(last=False)
        return arrays, index

    def compare(self, game, uid, seat, rows):
        player = game["our_players"][uid]["player"]
        keys = list(dict.fromkeys(k for k in (player, uid[:10]) if (self.directory / f"{k}.npz").is_file()))
        base = {"seat": seat, "player_uid": uid, "match_id": game["match_id"], "compared": 0, "obs_mismatches": 0, "mask_mismatches": 0, "act_mismatches": 0, "exact_decisions": 0}
        if len(keys) != 1:
            return dict(base, status="ambiguous" if keys else "not_in_npz", reason=f"player file candidates={keys}")
        rows = [r for r in rows if r.kind == "draw"]
        if not rows:
            return dict(base, status="no_discard")
        arrays, index = self._load(keys[0])
        signature = hashlib.sha256(rows[0].state.obs[:6]).digest()
        first_candidates = index.get(signature, [])
        labels = np.array([r.action_id for r in rows], dtype=np.int16)
        score = terminal_display(game)["score"][seat]
        offsets = [start for start in first_candidates if start + len(rows) <= len(arrays["act"]) and np.array_equal(arrays["act"][start:start + len(rows)], labels) and np.all(arrays["score"][start:start + len(rows)] == np.float32(score))]
        if len(offsets) != 1:
            return dict(base, source_file=f"{keys[0]}.npz", status="ambiguous" if len(offsets) > 1 else "not_in_npz", reason=f"first_hand_candidates={len(first_candidates)}, full_label_score_sequences={len(offsets)}")
        start = offsets[0]
        examples = []
        for i, row in enumerate(rows):
            same_obs = np.array_equal(arrays["obs"][start + i], row.state.obs)
            same_mask = np.array_equal(arrays["mask"][start + i], row.state.legal_mask)
            same_act = int(arrays["act"][start + i]) == row.action_id
            base["compared"] += 1
            base["obs_mismatches"] += int(not same_obs)
            base["mask_mismatches"] += int(not same_mask)
            base["act_mismatches"] += int(not same_act)
            base["exact_decisions"] += int(same_obs and same_mask and same_act)
            if not (same_obs and same_mask and same_act) and len(examples) < 3:
                examples.append({"source_row": start + i, "log_index": row.log_index, "after_chi_peng": row.after_claim, "different_obs_cells": int(np.count_nonzero(arrays["obs"][start + i] != row.state.obs)), "different_mask_bits": np.flatnonzero(arrays["mask"][start + i] != row.state.legal_mask).tolist(), "historical_hand_count": int(arrays["obs"][start + i, 2:6].sum()), "strict_hand_count": int(row.state.obs[2:6].sum())})
        return dict(base, source_file=f"{keys[0]}.npz", status="verified_exact" if base["exact_decisions"] == len(rows) else "mismatch", diagnostic_candidate_start=start, mismatch_examples=examples, note="Only normal-draw decisions compared; historical NPZ omit post-meld discard samples. No historical rows accepted for training.")


def _compare_decisions(observed, served):
    counts = Counter()
    examples = []
    for seat in range(4):
        left, right = observed[seat], served[seat]
        counts["unmatched_decisions"] += abs(len(left) - len(right))
        for a, b in zip(left, right):
            obs_equal = np.array_equal(a.state.obs, b.state.obs)
            mask_equal = np.array_equal(a.state.legal_mask, b.state.legal_mask)
            act_equal = a.action_id == b.action_id and a.log_index == b.log_index and a.kind == b.kind
            counts["compared"] += 1
            counts["obs_mismatches"] += int(not obs_equal)
            counts["mask_mismatches"] += int(not mask_equal)
            counts["act_mismatches"] += int(not act_equal)
            counts["exact"] += int(obs_equal and mask_equal and act_equal)
            if not (obs_equal and mask_equal and act_equal) and len(examples) < 5:
                examples.append({"seat": seat, "log_index": a.log_index, "obs_equal": obs_equal, "mask_equal": mask_equal, "act_equal": act_equal})
    return counts, examples


def verify_replay_parity(games_tar_path, decisions_dir, parity_json_path, match_index_json_path=None, max_games=100, min_verified_matches=50):
    if max_games < 1 or min_verified_matches < 1:
        raise ValueError("Positive replay limits required")
    output = Path(parity_json_path)
    root = output.parent
    root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    # Invalidate a previous approval before touching any input. Existing sample
    # files may remain, but can never be approved by a stale READY contract.
    write_json_report(root / "data_contract.json", {"status": "BLOCKED", "run_id": run_id, "reason": "Verification in progress"})
    write_json_report(output, {"status": "RUNNING", "run_id": run_id})
    attempts, historical, manifest, samples = [], [], [], []
    seen_matches = {}
    totals = Counter()
    archive_name = Path(games_tar_path).name
    archive_hash = None
    index = _HistoricalIndex(decisions_dir)
    try:
        archive_hash = file_sha256(Path(games_tar_path))
        with tarfile.open(games_tar_path, "r:gz") as tar:
            for member in tar:
                validate_safe_tar_member_name(member.name)
                if not member.isfile() or not member.name.endswith(".json"):
                    continue
                if len(attempts) >= max_games:
                    break
                record = {"source_file": member.name, "match_id": Path(member.name).stem, "status": "replay_error"}
                attempts.append(record)
                try:
                    if member.size > 10 * 1024**2:
                        raise CorruptedDatasetError("Oversized game JSON")
                    payload = tar.extractfile(member).read()
                    game = json.loads(payload)
                    match_id = game["match_id"]
                    if not isinstance(match_id, str) or not match_id:
                        raise CorruptedDatasetError("Missing string match_id")
                    record["match_id"] = match_id
                    source_hash = hashlib.sha256(payload).hexdigest()
                    if match_id in seen_matches:
                        prior_hash, prior_source = seen_matches[match_id]
                        record.update(status="duplicate_match_id" if prior_hash == source_hash else "conflicting_match_id", reason=f"Match identity already seen in {prior_source}", source_hash=source_hash)
                        continue
                    seen_matches[match_id] = (source_hash, member.name)
                    selected = tracked_seats(game)
                    record["tracked_seats"] = len(selected)
                    terminal = terminal_display(game)
                    if terminal["action"] not in ("HU", "HUANG"):
                        record.update(status="excluded_abnormal_terminal", reason=f"Source terminal {terminal['action']}; not a legal complete round")
                        continue
                    observed = replay_observers(game)
                    served = replay_referee(game)
                    counts, examples = _compare_decisions(observed, served)
                    totals.update(counts)
                    record.update(n_decisions=counts["compared"], compared_seats=4)
                    if counts["exact"] != counts["compared"] or counts["unmatched_decisions"]:
                        record.update(status="mismatch", reasons=examples)
                        continue
                    additions = []
                    for uid, seat in selected:
                        # All original comparison failures have a status and reason;
                        # diagnosis cannot invalidate independently verified strict data.
                        try:
                            historical.append(index.compare(game, uid, seat, observed[seat]))
                        except Exception as exc:
                            historical.append({"status": "replay_error", "match_id": match_id, "seat": seat, "player_uid": uid, "reason": repr(exc)})
                        for order, decision in enumerate(observed[seat]):
                            row = {"source_file": member.name, "source_row": decision.log_index, "match_id": match_id, "player_uid": uid, "seat": seat, "decision_order": order, "target_action_id": decision.action_id, "encoder_version": ENCODER_VERSION, "replay_status": "verified_exact", "source_hash": source_hash, "dataset_file": "strict_decisions/accepted.npz", "dataset_row": len(samples) + len(additions), "round_score": terminal["score"][seat]}
                            additions.append((row, decision))
                    # Validate provenance before accepting any sample from this game.
                    validate_manifest(manifest + [row for row, _ in additions])
                    for row, decision in additions:
                        manifest.append(row)
                        samples.append(decision)
                    event_counts = Counter(e["output"]["display"]["action"] for e in game["log"] if "output" in e)
                    record.update(status="verified_exact", accepted_samples=len(additions), source_hash=source_hash, source_event_counts=dict(event_counts))
                except Exception as exc:
                    record.update(status="replay_error", reason=repr(exc), traceback=traceback.format_exc(limit=3))
    except (OSError, tarfile.TarError, CorruptedDatasetError) as exc:
        attempts.append({"source_file": archive_name, "status": "replay_error", "reason": repr(exc)})
    statuses = Counter(row["status"] for row in attempts)
    historical_counts = Counter(row["status"] for row in historical)
    historical_compared = sum(row.get("compared", 0) for row in historical)
    historical_exact = sum(row.get("exact_decisions", 0) for row in historical)
    groups = validate_manifest(manifest)
    mismatch_count = totals["compared"] - totals["exact"] + totals["unmatched_decisions"]
    verified = len({row["match_id"] for row in attempts if row["status"] == "verified_exact"})
    passed = verified >= min_verified_matches and groups["match_count"] >= min_verified_matches and bool(samples) and mismatch_count == 0 and statuses["conflicting_match_id"] == 0
    report = {
        "status": "PASS" if passed else "FAIL", "run_id": run_id, "selected_strategy": "strict_reextraction", "encoder_version": ENCODER_VERSION,
        "scope": f"First {max_games} JSON files in pinned archive order; every attempted match reported; only complete verified tracked seats accepted",
        "n_games_inspected": len(attempts), "n_replay_attempts": len(attempts), "n_tracked_seats_inspected": sum(r.get("tracked_seats", 0) for r in attempts),
        "n_seats_compared": sum(r.get("compared_seats", 0) for r in attempts), "n_matches_verified": verified,
        "n_matches_failed_replay": statuses["replay_error"], "n_matches_excluded": statuses["excluded_abnormal_terminal"] + statuses["duplicate_match_id"], "n_matches_unmatched": statuses["not_in_npz"], "n_matches_ambiguous": statuses["ambiguous"] + statuses["conflicting_match_id"],
        "n_decisions_compared": totals["compared"], "n_exact_decisions": totals["exact"], "n_mismatches": mismatch_count,
        "obs_mismatches": totals["obs_mismatches"], "mask_mismatches": totals["mask_mismatches"], "act_mismatches": totals["act_mismatches"],
        "parity_rate": totals["exact"] / totals["compared"] if totals["compared"] else None,
        "parity_kind": "reextracted_training_vs_live_referee_full_match", "historical_npz_full_parity_claimed": False,
        "accepted_samples": len(samples), "accepted_matches": groups["match_count"], "provenance_coverage": len(manifest) / len(samples) if samples else None,
        "group_contract": groups, "status_counts": dict(statuses), "attempts": attempts,
        "historical_npz": {"status_counts": dict(historical_counts), "seats_inspected": len(historical), "decisions_compared": historical_compared, "exact_decisions": historical_exact, "obs_mismatches": sum(r.get("obs_mismatches", 0) for r in historical), "mask_mismatches": sum(r.get("mask_mismatches", 0) for r in historical), "act_mismatches": sum(r.get("act_mismatches", 0) for r in historical), "parity_rate": historical_exact / historical_compared if historical_compared else None, "training_approved_rows": 0, "records": historical},
    }
    contract = {"status": "READY" if passed else "BLOCKED", "run_id": run_id, "selected_strategy": "strict_reextraction", "dataset_id": DATASET_ID, "dataset_revision": DATASET_REVISION, "source_archive": archive_name, "source_archive_sha256": archive_hash, "encoder_version": ENCODER_VERSION, "obs": {"shape": [38, 4, 9], "dtype": "int8", "flat_size": 1368}, "legal_mask": {"shape": [235], "dtype": "bool"}, "legal_discard_mask": {"shape": [34], "dtype": "bool", "slice": [2, 36]}, "labels": {"dtype": "int16", "action_id_range": [2, 35], "class_idx": "action_id - 2", "meaning": "Observed player behavior; not an optimal strategy label"}, "accepted_samples": len(samples), "accepted_matches": groups["match_count"], "manifest": "decision_manifest.csv", "samples": "strict_decisions/accepted.npz", "historical_npz_approved": False, "grouping": {"key": "match_id", "algorithm": "sha256('phase1-match-groups-v1:' + match_id), first 8 bytes, big-endian, modulo 100; <80 train, <90 validation, else test", "evidence": groups}, "scope_note": "Only manifest rows accepted. Other original logs/NPZ need verification/re-extraction before training.", "comparison_method": "Same strict encoder; independent protocol observer replay and legal referee action replay with terminal score/fan validation"}
    source_root = Path(__file__).resolve().parents[1]
    contract["implementation_sha256"] = {name: file_sha256(source_root / name) for name in ("app/engine/feature_encoder.py", "app/engine/mcr_referee.py", "training/replay.py")}
    try:
        if passed:
            directory = root / "strict_decisions"
            directory.mkdir(exist_ok=True)
            arrays = {"obs": np.stack([r.state.obs for r in samples]), "mask": np.stack([r.state.legal_mask for r in samples]), "act": np.array([r.action_id for r in samples], dtype=np.int16), "score": np.array([r["round_score"] for r in manifest], dtype=np.float32)}
            validate_arrays(arrays)
            arrays.update(match_id=np.array([r["match_id"] for r in manifest]), seat=np.array([r["seat"] for r in manifest], dtype=np.int8))
            np.savez_compressed(directory / "accepted.npz", **arrays)
            contract["samples_sha256"] = file_sha256(directory / "accepted.npz")
            contract["stored_arrays"] = {k: {"shape": list(v.shape), "dtype": str(v.dtype)} for k, v in arrays.items()}
        with (root / "decision_manifest.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(manifest)
        contract["manifest_sha256"] = file_sha256(root / "decision_manifest.csv")
        if match_index_json_path:
            write_json_report(Path(match_index_json_path), attempts)
        write_json_report(output, report)
        # Publish READY last, only after all artifacts and PASS report exist.
        write_json_report(root / "data_contract.json", contract)
    except Exception as exc:
        report.update(status="FAIL", artifact_error=repr(exc))
        contract.update(status="BLOCKED", artifact_error=repr(exc))
        write_json_report(output, report)
        write_json_report(root / "data_contract.json", contract)
        raise ParityVerificationError(f"Artifact publication failed; see {output}") from exc
    if not passed:
        raise ParityVerificationError(f"Verified {verified} complete matches; need {min_verified_matches}. See {output}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets"))
    parser.add_argument("--max-games", type=int, default=100)
    parser.add_argument("--min-matches", type=int, default=50)
    args = parser.parse_args()
    report = verify_replay_parity(args.root / "finalist_games.tar.gz", args.root / "finalist_decisions", args.root / "parity_report.json", max_games=args.max_games, min_verified_matches=args.min_matches)
    print(json.dumps({k: report[k] for k in ("status", "n_matches_verified", "n_matches_failed_replay", "n_decisions_compared", "n_mismatches", "accepted_samples")}, indent=2))


if __name__ == "__main__":
    main()
