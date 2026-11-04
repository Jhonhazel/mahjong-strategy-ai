"""Pinned full-corpus strict replay, bounded atomic shards and resumable audits."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import csv
import gzip
import hashlib
import itertools
import json
import multiprocessing
from pathlib import Path
import re
import resource
import shutil
import tarfile
import time
import uuid

import numpy as np

from app.domain.exceptions import CorruptedDatasetError
from app.domain.models import ENCODER_VERSION
from app.domain.tiles import TILE_LIST
from training.dataset_loader import DATASET_ID, DATASET_REVISION, GAMES_SPEC, file_sha256, validate_safe_tar_member_name
from training.inspect_dataset import validate_arrays
from training.replay import replay_observers, replay_referee, terminal_display
from training.reporting import write_json_report
from training.verify_encoder_parity import _compare_decisions, partition_for_match

VERSION = "expanded_strict_v2"
SALT = "phase2.1-match-split-v1:"
SPLIT_ALGORITHM = "Preserve original roles (old test -> historical_test); new: sha256('phase2.1-match-split-v1:' + match_id), first8 big-endian mod100; <80 train, <90 validation, else test"
SPLITS = ("train", "validation", "test", "historical_test")
FIELDS = ["dataset_row", "dataset_file", "source_archive", "source_file", "source_hash", "source_ordinal", "match_id", "player_uid", "seat", "decision_order", "source_row", "target_action_id", "round_score", "encoder_version", "replay_status", "dataset_version", "sample_id", "split", "decision_kind"]
ID_PATTERN = re.compile(r"[0-9a-f]{24}")


def require(condition, message):
    if not condition:
        raise CorruptedDatasetError(message)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def original_roles(manifest):
    roles = {}
    with Path(manifest).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            match = row["match_id"]
            role = partition_for_match(match)
            roles[match] = "historical_test" if role == "test" else role
    require(bool(roles), "Missing original match roles")
    return roles


def split_for_match(match_id, roles):
    if match_id in roles:
        return roles[match_id]
    bucket = int.from_bytes(hashlib.sha256((SALT + match_id).encode()).digest()[:8], "big") % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


@dataclass(frozen=True)
class ExpansionConfig:
    archive: Path
    output: Path
    legacy_manifest: Path = Path("datasets/decision_manifest.csv")
    batch_games: int = 128
    workers: int = 2
    reserve_bytes: int = 1024**3


def inspect_archive(path, spec):
    require(path.stat().st_size == spec.expected_size and file_sha256(path) == spec.expected_sha256, "Source archive size/SHA-256 mismatch")
    # Consume the gzip trailer, including CRC, with a bounded decompression cap.
    total = 0
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(1024**2):
            total += len(chunk)
            require(total <= 10 * 1024**3, "Oversized decompressed source archive")
    entries, metadata, names = [], [], set()
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            validate_safe_tar_member_name(member.name)
            require(member.name not in names, "Duplicate archive member")
            require(member.isfile() or member.isdir(), "Unsafe archive member type")
            names.add(member.name)
            require(len(names) <= 100000, "Too many archive members")
            if member.isfile():
                require(member.name.startswith("finalist_games/"), "Unexpected source archive structure")
                require(0 < member.size <= 10 * 1024**2, "Oversized/empty source JSON")
                (entries if member.name.endswith(".json") else metadata).append({"source_file": member.name, "size": member.size})
    require(bool(entries), "No original source games")
    return entries, total, metadata


def iter_source(path, start, stop):
    ordinal = 0
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            if ordinal >= stop:
                break
            if ordinal >= start:
                yield ordinal, member.name, archive.extractfile(member).read()
            ordinal += 1


def verify_game(job):
    ordinal, name, payload, archive_hash, roles = job
    record = {"source_ordinal": ordinal, "source_file": name, "source_hash": hashlib.sha256(payload).hexdigest(), "match_id": Path(name).stem, "status": "replay_error", "parsed": False, "parity": {}, "accepted_samples": 0}
    samples = []
    try:
        game = json.loads(payload)
        record["parsed"] = True
        match = game["match_id"]
        require(isinstance(match, str) and ID_PATTERN.fullmatch(match) is not None, "Invalid match identity")
        record["match_id"] = match
        roster = game["players"]
        require(len(roster) == 4 and {r["seat"] for r in roster} == set(range(4)), "Missing or ambiguous roster")
        require(all(isinstance(r["uid"], str) and ID_PATTERN.fullmatch(r["uid"]) for r in roster), "Invalid roster UID")
        record["roster"] = {str(r["seat"]): r["uid"] for r in roster}
        require(name == f"finalist_games/{match}.json", "Source filename/match identity mismatch")
        terminal = terminal_display(game)
        record["ending"] = terminal["action"]
        record["source_event_counts"] = dict(Counter(e["output"]["display"]["action"] for e in game["log"] if "output" in e))
        if terminal["action"] not in ("HU", "HUANG"):
            record.update(status="excluded_abnormal_terminal", reason=f"Source terminal {terminal['action']}")
            return record, samples
        observed, served = replay_observers(game), replay_referee(game)
        counts, examples = _compare_decisions(observed, served)
        record["parity"] = dict(counts)
        require(counts["compared"] > 0, "No discard observations")
        if counts["exact"] != counts["compared"] or counts["unmatched_decisions"]:
            record.update(status="mismatch", reason="Observer/referee decision mismatch", examples=examples)
            return record, samples
        record["scores"] = terminal["score"]
        for seat in range(4):
            uid = record["roster"][str(seat)]
            for order, decision in enumerate(observed[seat]):
                action = decision.action_id
                require(2 <= action <= 35 and decision.state.legal_mask[action], "Illegal extracted label")
                row = {"source_archive": GAMES_SPEC.filename, "source_file": name, "source_hash": record["source_hash"], "source_ordinal": ordinal, "match_id": match, "player_uid": uid, "seat": seat, "decision_order": order, "source_row": decision.log_index, "target_action_id": action, "round_score": terminal["score"][seat], "encoder_version": ENCODER_VERSION, "replay_status": "verified_exact", "dataset_version": VERSION, "split": split_for_match(match, roles), "decision_kind": decision.kind}
                row["sample_id"] = canonical_hash([archive_hash, name, seat, order, decision.log_index])
                samples.append((row, decision.state))
        record.update(status="verified_exact", accepted_samples=len(samples))
    except Exception as exc:
        record.update(status="corrupt_json" if isinstance(exc, json.JSONDecodeError) else "invalid_label" if "Illegal" in str(exc) else "replay_error", reason=f"{type(exc).__name__}: {exc}")
        samples = []
    return record, samples


def read_commits(root, state):
    commits, cursor, seen = [], 0, {}
    for path in sorted((root / "shards").glob("*/commit.json")):
        value = json.loads(path.read_text())
        require(value["status"] == "COMMITTED" and value["run_id"] == state["run_id"] and value["source_start"] == cursor, "Noncontiguous or incompatible committed batch")
        require(value["source_end"] >= cursor and value["source_end"] < state["source_games"], "Invalid committed source range")
        require(set(value["sha256"]) == {"samples.npz", "manifest.csv.gz", "audit.jsonl"}, "Missing shard evidence")
        for name, digest in value["sha256"].items():
            require((path.parent / name).is_file() and file_sha256(path.parent / name) == digest, f"Committed {name} hash mismatch")
        records = [json.loads(line) for line in (path.parent / "audit.jsonl").read_text().splitlines()]
        require([r["source_ordinal"] for r in records] == list(range(cursor, value["source_end"] + 1)), "Incomplete attempted-game accounting")
        for record in records:
            match = record["match_id"]
            if match in seen:
                require(record["status"] in ("duplicate_ingestion", "conflicting_match_id"), "Duplicate match not excluded")
            else:
                seen[match] = record["source_hash"]
        value["path"] = str(path.parent.relative_to(root))
        commits.append(value)
        cursor = value["source_end"] + 1
    return commits, cursor, seen


def make_arrays(samples):
    n = len(samples)
    return {
        "obs": np.stack([s.obs for _, s in samples]) if n else np.empty((0, 38, 4, 9), np.int8),
        "mask": np.stack([s.legal_mask for _, s in samples]) if n else np.empty((0, 235), bool),
        "act": np.array([r["target_action_id"] for r, _ in samples], np.int16),
        "score": np.array([r["round_score"] for r, _ in samples], np.float32),
        "match_id": np.array([r["match_id"] for r, _ in samples], dtype="U24"),
        "seat": np.array([r["seat"] for r, _ in samples], np.int8),
        "uid": np.array([r["player_uid"] for r, _ in samples], dtype="U24"),
        "split": np.array([SPLITS.index(r["split"]) for r, _ in samples], np.int8),
        "post_meld": np.array([r["decision_kind"] == "post_meld" for r, _ in samples], bool),
        "decision_order": np.array([r["decision_order"] for r, _ in samples], np.int16),
        "source_row": np.array([r["source_row"] for r, _ in samples], np.int32),
        "source_ordinal": np.array([r["source_ordinal"] for r, _ in samples], np.int32),
    }


def validate_strict_arrays(arrays):
    base = ("obs", "mask", "act", "score", "match_id", "seat")
    extra = {"uid": "U24", "split": "int8", "post_meld": "bool", "decision_order": "int16", "source_row": "int32", "source_ordinal": "int32"}
    require(set(arrays) == set(base) | set(extra), "Unexpected expanded shard arrays")
    n = validate_arrays({k: arrays[k] for k in base})
    require(all(arrays[k].shape == (n,) and arrays[k].dtype == np.dtype(dtype) for k, dtype in extra.items()), "Expanded provenance array shape/dtype mismatch")
    require(not np.any((arrays["obs"] != 0) & (arrays["obs"] != 1)) and not arrays["obs"][:, :, 3, 7:].any(), "Invalid strict feature values")
    return n


def commit_batch(root, state, results):
    records = [record for record, _ in results]
    samples = [item for _, items in results for item in items]
    folder = root / "shards" / f"{records[0]['source_ordinal']:08d}"
    folder.mkdir(parents=True, exist_ok=True)
    require(not (folder / "commit.json").exists(), "Refusing to overwrite a committed shard")
    arrays = make_arrays(samples)
    validate_strict_arrays(arrays)
    # Only files in an uncommitted transaction may be replaced after interruption.
    temporary = folder / "samples.tmp"
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    temporary.replace(folder / "samples.npz")
    with gzip.open(folder / "manifest.tmp", "wt", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for i, (row, _) in enumerate(samples):
            writer.writerow(dict(row, dataset_row=i, dataset_file=str((folder / "samples.npz").relative_to(root))))
    (folder / "manifest.tmp").replace(folder / "manifest.csv.gz")
    with (folder / "audit.tmp").open("w") as stream:
        for record in records:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
    (folder / "audit.tmp").replace(folder / "audit.jsonl")
    value = {"status": "COMMITTED", "run_id": state["run_id"], "source_start": records[0]["source_ordinal"], "source_end": records[-1]["source_ordinal"], "samples": len(samples), "verified_matches": sum(r["status"] == "verified_exact" for r in records), "sha256": {name: file_sha256(folder / name) for name in ("samples.npz", "manifest.csv.gz", "audit.jsonl")}}
    write_json_report(folder / "commit.json", value)
    return dict(value, path=str(folder.relative_to(root)))


def _summary(root, state, commits, status):
    records = (json.loads(line) for c in commits for line in (root / c["path"] / "audit.jsonl").read_text().splitlines())
    statuses, parity, endings = Counter(), Counter(), Counter()
    parsed = 0
    for row in records:
        statuses[row["status"]] += 1
        parity.update(row["parity"])
        endings[row.get("ending", "unavailable")] += 1
        parsed += row["parsed"]
    attempted = sum(statuses.values())
    seconds = state.get("processing_seconds", 0.)
    return {"status": status, "dataset_version": VERSION, "run_id": state["run_id"], "source_games": state["source_games"], "attempted_games": attempted, "remaining_games": state["source_games"] - attempted, "parsed_games": parsed, "verified_matches": statuses["verified_exact"], "excluded_games": attempted - statuses["verified_exact"], "status_counts": dict(statuses), "parity": dict(parity), "replay_errors": statuses["replay_error"], "replay_mismatches": statuses["mismatch"], "invalid_label_attempts": statuses["invalid_label"], "duplicate_ingestions": statuses["duplicate_ingestion"], "accepted_samples": sum(c["samples"] for c in commits), "source_coverage": attempted / state["source_games"], "valid_match_fraction": statuses["verified_exact"] / attempted if attempted else 0., "match_endings": dict(endings), "processing_seconds": seconds, "games_per_second": attempted / seconds if seconds else 0., "disk_bytes": sum(p.stat().st_size for p in root.rglob('*') if p.is_file()), "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "source_archive_sha256": state["archive_sha256"], "source_position_range": [0, attempted - 1] if attempted else [], "complete": attempted == state["source_games"]}


def expand(config, max_games=None, spec=GAMES_SPEC):
    root, archive_path = Path(config.output), Path(config.archive)
    if root.resolve() == Path(config.legacy_manifest).parent.resolve():
        raise ValueError("Cannot overwrite original dataset directory")
    if not 1 <= config.batch_games <= 512 or not 1 <= config.workers <= 4 or config.reserve_bytes < 0 or max_games is not None and max_games < 1:
        raise ValueError("Invalid bounded expansion configuration")
    root.mkdir(parents=True, exist_ok=True)
    write_json_report(root / "data_contract.json", {"status": "BLOCKED", "reason": "Expansion/verification in progress"})
    started = time.perf_counter()
    try:
        entries, expanded_bytes, metadata_members = inspect_archive(archive_path, spec)
        roles = original_roles(config.legacy_manifest)
        identity = {"archive_sha256": spec.expected_sha256, "source_games": len(entries), "source_inventory_sha256": canonical_hash(entries), "legacy_manifest_sha256": file_sha256(Path(config.legacy_manifest)), "original_roles": roles, "split_salt": SALT, "dataset_version": VERSION, "encoder_version": ENCODER_VERSION}
        state_path = root / "progress.json"
        if state_path.exists():
            state = json.loads(state_path.read_text())
            require(all(state[k] == v for k, v in identity.items()), "Source/split/configuration changed during resume")
        else:
            state = dict(identity, run_id=uuid.uuid4().hex, processing_seconds=0., decompressed_source_bytes=expanded_bytes, non_game_members=metadata_members)
            write_json_report(state_path, state)
        inventory_path = root / "source_inventory.json"
        expected_inventory = {"archive_sha256": spec.expected_sha256, "entries": entries}
        if inventory_path.exists():
            require(json.loads(inventory_path.read_text()) == expected_inventory, "Persisted source inventory changed")
        else:
            # progress.json may have committed before an interrupted inventory write.
            # The pinned archive was revalidated above; rebuild only this missing file.
            write_json_report(inventory_path, expected_inventory)
        commits, cursor, seen = read_commits(root, state)
        stop = min(len(entries), max_games) if max_games is not None else len(entries)
        pool = ProcessPoolExecutor(max_workers=config.workers, mp_context=multiprocessing.get_context("spawn")) if config.workers > 1 else None
        status = "PAUSED"
        try:
            iterator = iter_source(archive_path, cursor, stop)
            while batch := list(itertools.islice(iterator, config.batch_games)):
                required = config.reserve_bytes + max(1024**2, sum(len(payload) for _, _, payload in batch) * 4)
                if shutil.disk_usage(root).free <= required:
                    state["resource_blocker"] = {"free_bytes": shutil.disk_usage(root).free, "required_free_bytes": required, "reason": "Disk reserve before next atomic batch"}
                    status = "RESOURCE_BLOCKED"
                    break
                jobs = [(i, name, payload, spec.expected_sha256, roles) for i, name, payload in batch]
                results = list(pool.map(verify_game, jobs, chunksize=1)) if pool else [verify_game(job) for job in jobs]
                for record, samples in results:
                    match = record["match_id"]
                    if match in seen:
                        record.update(status="duplicate_ingestion" if seen[match] == record["source_hash"] else "conflicting_match_id", reason="Match identity already processed", accepted_samples=0)
                        samples.clear()
                    else:
                        seen[match] = record["source_hash"]
                commits.append(commit_batch(root, state, results))
                cursor = commits[-1]["source_end"] + 1
                state.update(attempted_games=cursor, status="RUNNING", processing_seconds=state["processing_seconds"] + time.perf_counter() - started)
                started = time.perf_counter()
                write_json_report(state_path, state)
                if len(commits) % 10 == 0 or cursor == stop:
                    print(json.dumps({"attempted": cursor, "total": len(entries), "samples": sum(c["samples"] for c in commits), "seconds": round(state["processing_seconds"], 2), "disk_free": shutil.disk_usage(root).free}), flush=True)
        finally:
            if pool:
                pool.shutdown(wait=True, cancel_futures=True)
        state["processing_seconds"] += time.perf_counter() - started
        state.update(status=status, attempted_games=cursor)
        write_json_report(state_path, state)
        report = _summary(root, state, commits, status)
        report["non_game_members"] = metadata_members
        write_json_report(root / "expansion_report.json", report)
        if cursor == len(entries):
            audit = validate_expansion(root, archive=archive_path, require_ready=False)
            contract = {"status": "READY", "dataset_id": DATASET_ID, "dataset_revision": DATASET_REVISION, "run_id": state["run_id"], "dataset_version": VERSION, "encoder_version": ENCODER_VERSION, "source_archive": GAMES_SPEC.filename, "source_archive_sha256": spec.expected_sha256, "source_games": len(entries), "complete_source_coverage": True, "accepted_samples": audit["samples"], "accepted_matches": audit["matches"], "samples_sha256": audit["shard_inventory_sha256"], "samples_hash_kind": "canonical sha256 of committed compressed shard path/SHA inventory; not a single NPZ", "manifest_sha256": audit["manifest_inventory_sha256"], "grouping": {"key": "match_id", "algorithm": SPLIT_ALGORITHM}, "original_roles": roles, "splits": audit["splits"], "shards": [{"path": c["path"], "samples": c["samples"], "sha256": c["sha256"]} for c in commits], "historical_npz_approved": False, "obs": {"shape": [38, 4, 9], "dtype": "int8", "flat_size": 1368}, "legal_mask": {"shape": [235], "dtype": "bool"}, "legal_discard_mask": {"shape": [34], "dtype": "bool", "slice": [2, 36]}, "implementation_sha256": {p: file_sha256(Path(p)) for p in ("app/engine/feature_encoder.py", "app/engine/mcr_referee.py", "training/replay.py")}}
            write_json_report(root / "data_quality_report.json", audit)
            report["status"] = "READY"
            report["validation"] = {"status": "PASS", "provenance_coverage": 1., "illegal_labels": 0}
            write_json_report(root / "expansion_report.json", report)
            # No READY contract exists until the entire committed corpus passes validation.
            write_json_report(root / "data_contract.json", contract)
        return report
    except BaseException as exc:
        write_json_report(root / "data_contract.json", {"status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}"})
        write_json_report(root / "expansion_failure.json", {"status": "FAIL", "reason": repr(exc)})
        raise


def validate_expansion(root, archive=None, require_complete=True, require_ready=True):
    root = Path(root)
    try:
        return _validate_expansion(root, archive, require_complete, require_ready)
    except Exception as exc:
        write_json_report(root / "data_contract.json", {"status": "BLOCKED", "reason": f"Validation failed: {exc}"})
        if isinstance(exc, CorruptedDatasetError):
            raise
        raise CorruptedDatasetError(f"Expanded data validation failed: {exc}") from exc


def _validate_expansion(root, archive, require_complete, require_ready):
    state = json.loads((root / "progress.json").read_text())
    commits, cursor, _ = read_commits(root, state)
    require(not require_complete or cursor == state["source_games"], "Source corpus is not completely processed")
    if require_ready:
        contract = json.loads((root / "data_contract.json").read_text())
        require(contract["status"] == "READY" and contract["run_id"] == state["run_id"], "Expanded contract is not READY")
    inventory = json.loads((root / "source_inventory.json").read_text())["entries"]
    require(canonical_hash(inventory) == state["source_inventory_sha256"], "Source inventory changed")
    groups = {name: set() for name in SPLITS}
    stats = {name: {"samples": 0, "class_distribution": Counter(), "player_distribution": Counter(), "legal_count_distribution": Counter(), "phase_distribution": Counter()} for name in SPLITS}
    players, player_matches, match_samples = Counter(), defaultdict(set), Counter()
    accepted_matches, source_hashes, signatures = set(), {}, set()
    repeated, samples_total, post_meld, events = 0, 0, 0, Counter()
    for commit in commits:
        folder = root / commit["path"]
        attempts = [json.loads(line) for line in (folder / "audit.jsonl").read_text().splitlines()]
        require(not any(r["status"] == "conflicting_match_id" for r in attempts), "Conflicting duplicate match IDs block publication")
        accepted = {r["match_id"]: r for r in attempts if r["status"] == "verified_exact"}
        require(len(accepted) == commit["verified_matches"] and not accepted_matches.intersection(accepted), "Duplicate accepted match")
        accepted_matches.update(accepted)
        for row in attempts:
            ordinal = row["source_ordinal"]
            require(inventory[ordinal]["source_file"] == row["source_file"], "Source ordinal/path mismatch")
            source_hashes[ordinal] = row["source_hash"]
            if row["status"] == "verified_exact": events.update(row["source_event_counts"])
        with np.load(folder / "samples.npz", allow_pickle=False) as storage:
            arrays = {k: storage[k] for k in storage.files}
        n = validate_strict_arrays(arrays)
        require(n == commit["samples"] == sum(r["accepted_samples"] for r in attempts), "Shard sample count mismatch")
        orders, source_rows = defaultdict(list), set()
        with gzip.open(folder / "manifest.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames == FIELDS, "Manifest fields mismatch")
            count = 0
            for i, row in enumerate(reader):
                require(i < n and int(row["dataset_row"]) == i and row["dataset_file"] == str((folder / "samples.npz").relative_to(root)), "Manifest shard/row mismatch")
                match, seat, order, source_row = row["match_id"], int(row["seat"]), int(row["decision_order"]), int(row["source_row"])
                require(match in accepted and match == arrays["match_id"][i], "Unverified manifest match")
                attempt = accepted[match]
                role = split_for_match(match, state["original_roles"])
                require(row["split"] == role and row["encoder_version"] == ENCODER_VERSION and row["dataset_version"] == VERSION and row["replay_status"] == "verified_exact", "Manifest split/version mismatch")
                require(row["source_file"] == attempt["source_file"] and row["source_hash"] == attempt["source_hash"] and int(row["source_ordinal"]) == attempt["source_ordinal"], "Manifest source identity mismatch")
                require(row["source_archive"] == GAMES_SPEC.filename and row["player_uid"] == attempt["roster"][str(seat)], "Manifest archive/player mismatch")
                require(row["sample_id"] == canonical_hash([state["archive_sha256"], row["source_file"], seat, order, source_row]), "Stable sample identity mismatch")
                expected = {"seat": seat, "act": int(row["target_action_id"]), "score": float(row["round_score"]), "uid": row["player_uid"], "split": SPLITS.index(role), "post_meld": row["decision_kind"] == "post_meld", "decision_order": order, "source_row": source_row, "source_ordinal": attempt["source_ordinal"]}
                require(all(arrays[k][i] == value for k, value in expected.items()), "Manifest-to-array alignment mismatch")
                require(row["decision_kind"] in ("draw", "post_meld") and float(row["round_score"]) == attempt["scores"][seat], "Invalid decision kind/source score")
                key = (match, seat, source_row)
                require(key not in source_rows and source_row >= 0 and order >= 0, "Duplicate/invalid source decision")
                source_rows.add(key)
                orders[(match, seat)].append(order)
                groups[role].add(match)
                stat = stats[role]
                stat["samples"] += 1
                stat["class_distribution"][TILE_LIST[int(arrays["act"][i]) - 2]] += 1
                stat["player_distribution"][row["player_uid"]] += 1
                stat["legal_count_distribution"][str(int(arrays["mask"][i, 2:36].sum()))] += 1
                stat["phase_distribution"][row["decision_kind"]] += 1
                players[row["player_uid"]] += 1
                player_matches[row["player_uid"]].add(match)
                match_samples[match] += 1
                fingerprint = hashlib.sha256(arrays["obs"][i].tobytes() + arrays["mask"][i].tobytes() + arrays["act"][i:i+1].tobytes()).digest()
                repeated += fingerprint in signatures
                signatures.add(fingerprint)
                post_meld += int(expected["post_meld"])
                count += 1
            require(count == n, "Incomplete manifest rows")
        require(all(values == list(range(len(values))) for values in orders.values()), "Incomplete decision order")
        require(all(sum(len(v) for (match, _), v in orders.items() if match == key) == row["accepted_samples"] for key, row in accepted.items()), "Incomplete match sample coverage")
        samples_total += n
    require(samples_total > 0, "No accepted verified samples")
    intersections = {f"{a}_{b}": sorted(groups[a] & groups[b]) for i, a in enumerate(SPLITS) for b in SPLITS[i+1:]}
    require(not any(intersections.values()), "Group leakage")
    old_test = {m for m, role in state["original_roles"].items() if role == "historical_test"}
    require(not old_test.intersection(groups["train"] | groups["validation"] | groups["test"]), "Historical test leaked")
    if archive is not None:
        require(file_sha256(Path(archive)) == state["archive_sha256"], "Raw source archive hash mismatch")
        for ordinal, name, payload in iter_source(archive, 0, cursor):
            require(name == inventory[ordinal]["source_file"] and hashlib.sha256(payload).hexdigest() == source_hashes[ordinal], "Raw source payload/provenance mismatch")
    shard_digest = canonical_hash([{ "path": c["path"], "sha256": c["sha256"]["samples.npz"]} for c in commits])
    manifest_digest = canonical_hash([{ "path": c["path"], "sha256": c["sha256"]["manifest.csv.gz"]} for c in commits])
    audited_splits = {name: dict(stat, matches=len(groups[name])) for name, stat in stats.items()}
    if require_ready:
        require(contract["samples_sha256"] == shard_digest and contract["manifest_sha256"] == manifest_digest and contract["accepted_samples"] == samples_total and contract["accepted_matches"] == len(accepted_matches), "Published contract identity/count mismatch")
        expected_shards = [{"path": c["path"], "samples": c["samples"], "sha256": c["sha256"]} for c in commits]
        require(contract["shards"] == expected_shards, "Published shard inventory differs from audited commits")
        require(contract["original_roles"] == state["original_roles"] and contract["splits"] == audited_splits, "Published split roles/counts differ from audited data")
        require(contract["grouping"] == {"key": "match_id", "algorithm": SPLIT_ALGORITHM}, "Published split algorithm changed")
        require(contract["dataset_id"] == DATASET_ID and contract["dataset_revision"] == DATASET_REVISION and contract["dataset_version"] == state["dataset_version"] == VERSION and contract["encoder_version"] == state["encoder_version"] == ENCODER_VERSION, "Published dataset/encoder identity changed")
        require(contract["source_archive_sha256"] == state["archive_sha256"] and contract["source_games"] == state["source_games"] and contract["complete_source_coverage"] is True and contract["historical_npz_approved"] is False, "Published source coverage changed")
        expected_sources = {p: file_sha256(Path(p)) for p in ("app/engine/feature_encoder.py", "app/engine/mcr_referee.py", "training/replay.py")}
        require(contract["implementation_sha256"] == expected_sources, "Published encoder/referee implementation hash mismatch")
    return {"status": "PASS", "run_id": state["run_id"], "samples": samples_total, "matches": len(accepted_matches), "distinct_players": len(players), "provenance_coverage": 1., "illegal_labels": 0, "split_intersections": intersections, "historical_test_matches": sorted(old_test), "splits": {name: dict(stat, matches=len(groups[name])) for name, stat in stats.items()}, "players": dict(players), "matches_per_player": {p: len(v) for p, v in player_matches.items()}, "samples_per_match": dict(match_samples), "player_overlap": {f"{a}_{b}": sorted(set(stats[a]["player_distribution"]) & set(stats[b]["player_distribution"])) for i,a in enumerate(SPLITS) for b in SPLITS[i+1:]}, "repeated_feature_mask_label_observations": repeated, "repetition_policy": "Count naturally repeated states; do not delete distinct source decisions", "post_meld_samples": post_meld, "source_event_counts": dict(events), "shard_inventory_sha256": shard_digest, "manifest_inventory_sha256": manifest_digest, "source_positions_attempted": cursor, "source_complete": cursor == state["source_games"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("datasets/finalist_games.tar.gz"))
    parser.add_argument("--output", type=Path, default=Path("datasets/expanded_strict_v2"))
    parser.add_argument("--max-games", type=int, help="Operational milestone only; omit to resume through the entire corpus")
    parser.add_argument("--batch-games", type=int, default=128)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--audit-partial", action="store_true")
    args = parser.parse_args()
    if args.validate or args.audit_partial:
        report = validate_expansion(args.output, args.archive, require_complete=not args.audit_partial, require_ready=not args.audit_partial)
        write_json_report(args.output / ("partial_audit.json" if args.audit_partial else "revalidation.json"), report)
        print(json.dumps({k: report[k] for k in ("status", "samples", "matches", "distinct_players", "source_complete")}))
    else:
        report = expand(ExpansionConfig(args.archive, args.output, batch_games=args.batch_games, workers=args.workers), args.max_games)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
