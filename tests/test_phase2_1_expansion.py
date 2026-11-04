import copy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

import numpy as np
import pytest

from app.domain.exceptions import CorruptedDatasetError
from training.dataset_loader import DatasetSpec


@pytest.fixture(scope="module")
def source_games():
    games = []
    with tarfile.open("datasets/finalist_games.tar.gz", "r|gz") as archive:
        for member in archive:
            if member.isfile() and member.name.endswith(".json"):
                games.append((member.name, archive.extractfile(member).read()))
                if len(games) == 3:
                    break
    assert len(games) == 3
    return games


def make_archive(tmp_path, entries):
    path = tmp_path / "source.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path, DatasetSpec(path.name, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())


def config_for(tmp_path, archive, **kwargs):
    from training.expanded_dataset import ExpansionConfig
    return ExpansionConfig(archive, tmp_path / "expanded", batch_games=1, workers=1, reserve_bytes=0, **kwargs)


def test_versioned_split_preserves_all_original_roles_and_protects_old_test():
    from training.expanded_dataset import split_for_match, original_roles
    from training.verify_encoder_parity import partition_for_match
    roles = original_roles(Path("datasets/decision_manifest.csv"))
    assert len(roles) == 84 and list(roles.values()).count("historical_test") == 5
    for match, role in roles.items():
        assert role == ("historical_test" if partition_for_match(match) == "test" else partition_for_match(match))
        assert split_for_match(match, roles) == role
    match = "f" * 24
    bucket = int.from_bytes(hashlib.sha256(("phase2.1-match-split-v1:" + match).encode()).digest()[:8], "big") % 100
    assert split_for_match(match, roles) == ("train" if bucket < 80 else "validation" if bucket < 90 else "test")


def test_full_real_replay_extracts_all_four_roster_seats_with_exact_parity(tmp_path, source_games):
    from training.expanded_dataset import expand, validate_expansion
    archive, spec = make_archive(tmp_path, source_games)
    config = config_for(tmp_path, archive)
    report = expand(config, spec=spec)
    assert report["status"] == "READY" and report["source_games"] == report["attempted_games"] == 3
    assert report["verified_matches"] == 3 and report["excluded_games"] == 0
    assert report["accepted_samples"] == report["parity"]["exact"] == report["parity"]["compared"] > 100
    assert report["parity"]["obs_mismatches"] == report["parity"]["mask_mismatches"] == report["parity"]["act_mismatches"] == 0
    audit = validate_expansion(config.output, archive=archive)
    assert audit["status"] == "PASS" and audit["matches"] == 3 and audit["illegal_labels"] == 0
    assert audit["provenance_coverage"] == 1 and not any(audit["split_intersections"].values())
    for shard in sorted((config.output / "shards").glob("*/samples.npz")):
        with np.load(shard, allow_pickle=False) as arrays:
            assert set(arrays["seat"]) == {0, 1, 2, 3}
            assert arrays["obs"].dtype == np.int8


def test_interrupted_run_resumes_from_commits_without_replaying_or_duplicate_ingestion(tmp_path, source_games, monkeypatch):
    import training.expanded_dataset as module
    archive, spec = make_archive(tmp_path, source_games)
    config = config_for(tmp_path, archive)
    paused = module.expand(config, max_games=1, spec=spec)
    assert paused["status"] == "PAUSED" and paused["attempted_games"] == 1
    assert json.loads((config.output / "data_contract.json").read_text())["status"] == "BLOCKED"
    first = next((config.output / "shards").glob("*/commit.json"))
    before = first.read_bytes()
    original = module.verify_game
    def only_remaining(job):
        assert job[0] > 0, "Committed game must never be replayed"
        return original(job)
    monkeypatch.setattr(module, "verify_game", only_remaining)
    result = module.expand(config, spec=spec)
    assert result["status"] == "READY" and result["attempted_games"] == 3
    assert result["duplicate_ingestions"] == 0 and first.read_bytes() == before
    assert module.validate_expansion(config.output)["samples"] == result["accepted_samples"]


@pytest.mark.parametrize("kind", ["corrupt_json", "abnormal_terminal", "missing_response", "invalid_roster", "invalid_label"])
def test_every_invalid_attempt_has_an_explicit_exclusion_status(tmp_path, source_games, kind):
    from training.expanded_dataset import expand
    name, payload = source_games[0]
    game = json.loads(payload)
    if kind == "corrupt_json":
        payload = b"{invalid"
    else:
        if kind == "abnormal_terminal":
            next(e["output"]["display"] for e in reversed(game["log"]) if "output" in e)["action"] = "WA"
        elif kind == "invalid_roster":
            game["players"][0]["seat"] = game["players"][1]["seat"]
        else:
            for i, row in enumerate(game["log"]):
                output = row.get("output", {})
                if output.get("display", {}).get("action") == "DRAW":
                    seat = str(output["display"]["player"])
                    if kind == "missing_response":
                        game["log"][i + 1].pop(seat)
                    else:
                        game["log"][i + 1][seat]["response"] = "PLAY invalid"
                    break
        payload = json.dumps(game).encode()
    archive, spec = make_archive(tmp_path, [(name, payload)] + source_games[1:])
    config = config_for(tmp_path, archive)
    result = expand(config, spec=spec)
    assert result["attempted_games"] == 3 and result["excluded_games"] == 1
    assert result["verified_matches"] == 2
    records = [json.loads(line) for p in sorted((config.output / "shards").glob("*/audit.jsonl")) for line in p.read_text().splitlines()]
    assert len(records) == 3 and records[0]["status"] != "verified_exact" and records[0]["reason"]


@pytest.mark.parametrize("failure", ["checksum", "missing", "traversal", "duplicate_member"])
def test_archive_failure_is_fail_closed_and_never_leaves_ready(tmp_path, source_games, failure):
    from training.expanded_dataset import expand
    entries = source_games
    if failure == "traversal": entries = [("../escape.json", source_games[0][1])]
    if failure == "duplicate_member": entries = [source_games[0], source_games[0]]
    archive, spec = make_archive(tmp_path, entries)
    config = config_for(tmp_path, archive)
    config.output.mkdir()
    (config.output / "data_contract.json").write_text('{"status":"READY"}')
    if failure == "checksum": archive.write_bytes(b"corrupt")
    if failure == "missing": archive.unlink()
    with pytest.raises((CorruptedDatasetError, OSError)):
        expand(config, spec=spec)
    assert json.loads((config.output / "data_contract.json").read_text())["status"] == "BLOCKED"


@pytest.mark.parametrize("name", ["samples.npz", "manifest.csv.gz", "audit.jsonl"])
def test_committed_artifact_corruption_blocks_validation_and_resume(tmp_path, source_games, name):
    from training.expanded_dataset import expand, validate_expansion
    archive, spec = make_archive(tmp_path, source_games)
    config = config_for(tmp_path, archive)
    expand(config, spec=spec)
    target = next((config.output / "shards").glob("*/" + name))
    target.write_bytes(target.read_bytes() + b"tampered")
    with pytest.raises(CorruptedDatasetError): validate_expansion(config.output)
    with pytest.raises(CorruptedDatasetError): expand(config, spec=spec)
    assert json.loads((config.output / "data_contract.json").read_text())["status"] == "BLOCKED"


def test_low_disk_preserves_committed_shards_and_resumes_later(tmp_path, source_games, monkeypatch):
    import training.expanded_dataset as module
    archive, spec = make_archive(tmp_path, source_games)
    config = config_for(tmp_path, archive)
    module.expand(config, max_games=1, spec=spec)
    before = next((config.output / "shards").glob("*/commit.json")).read_bytes()
    real = module.shutil.disk_usage
    monkeypatch.setattr(module.shutil, "disk_usage", lambda p: type("Usage", (), {"free": 0})())
    result = module.expand(config, spec=spec)
    assert result["status"] == "RESOURCE_BLOCKED" and result["attempted_games"] == 1
    assert next((config.output / "shards").glob("*/commit.json")).read_bytes() == before
    monkeypatch.setattr(module.shutil, "disk_usage", real)
    assert module.expand(config, spec=spec)["status"] == "READY"


def test_interruption_before_commit_does_not_publish_or_duplicate_samples(tmp_path, source_games, monkeypatch):
    import training.expanded_dataset as module
    archive, spec = make_archive(tmp_path, source_games)
    config = config_for(tmp_path, archive)
    real_write = module.write_json_report
    def fail_commit(path, value):
        if Path(path).name == "commit.json": raise OSError("injected commit failure")
        return real_write(path, value)
    monkeypatch.setattr(module, "write_json_report", fail_commit)
    with pytest.raises(OSError, match="injected"): module.expand(config, spec=spec)
    assert json.loads((config.output / "data_contract.json").read_text())["status"] == "BLOCKED"
    monkeypatch.setattr(module, "write_json_report", real_write)
    result = module.expand(config, spec=spec)
    assert result["status"] == "READY" and result["attempted_games"] == 3


def test_original_output_directory_cannot_be_overwritten(tmp_path, source_games):
    from training.expanded_dataset import ExpansionConfig, expand
    archive, spec = make_archive(tmp_path, source_games)
    original = tmp_path / "old"
    original.mkdir()
    manifest = original / "decision_manifest.csv"
    manifest.write_bytes(Path("datasets/decision_manifest.csv").read_bytes())
    contract = original / "data_contract.json"
    contract.write_text('{"status":"READY","original":true}')
    before = contract.read_bytes()
    with pytest.raises(ValueError, match="original"):
        expand(ExpansionConfig(archive, original, legacy_manifest=manifest), spec=spec)
    assert contract.read_bytes() == before


def test_non_game_archive_metadata_is_reported_and_does_not_shift_game_ordinals(tmp_path, source_games):
    from training.expanded_dataset import expand
    archive, spec = make_archive(tmp_path, [source_games[0], ("finalist_games/_sid.txt", b"archive metadata"), *source_games[1:]])
    config = config_for(tmp_path, archive)
    result = expand(config, spec=spec)
    assert result["source_games"] == result["attempted_games"] == 3
    assert result["non_game_members"] == [{"source_file": "finalist_games/_sid.txt", "size": 16}]


def test_duplicate_ingestion_is_excluded_and_conflicting_match_identity_blocks_ready(tmp_path,source_games):
    from training.expanded_dataset import expand
    archive,spec=make_archive(tmp_path,[source_games[0],("finalist_games/duplicate.json",source_games[0][1])])
    result=expand(config_for(tmp_path,archive),spec=spec)
    assert result["verified_matches"]==1 and result["duplicate_ingestions"]==1
    conflict=tmp_path/"conflict";conflict.mkdir()
    archive,spec=make_archive(conflict,[source_games[0],("finalist_games/duplicate.json",source_games[0][1]+b" ")])
    config=config_for(conflict,archive)
    with pytest.raises(CorruptedDatasetError,match="Conflicting"):
        expand(config,spec=spec)
    assert json.loads((config.output/"data_contract.json").read_text())["status"]=="BLOCKED"


def test_naturally_repeated_state_does_not_delete_distinct_source_decisions(tmp_path,source_games):
    from training.expanded_dataset import expand,validate_expansion
    game=json.loads(source_games[0][1]);game["match_id"]="f"*24
    archive,spec=make_archive(tmp_path,[source_games[0],("finalist_games/"+game["match_id"]+".json",json.dumps(game).encode())])
    config=config_for(tmp_path,archive)
    result=expand(config,spec=spec)
    audit=validate_expansion(config.output)
    assert result["verified_matches"]==2 and audit["repeated_feature_mask_label_observations"]>0
    assert result["accepted_samples"]==2*audit["repeated_feature_mask_label_observations"]


def test_final_report_failure_leaves_blocked_and_completed_shards_can_be_republished(tmp_path,source_games,monkeypatch):
    import training.expanded_dataset as module
    archive,spec=make_archive(tmp_path,source_games)
    config=config_for(tmp_path,archive)
    real=module.write_json_report
    def fail(path,value):
        if Path(path).name=="data_quality_report.json":raise OSError("injected final publication failure")
        return real(path,value)
    monkeypatch.setattr(module,"write_json_report",fail)
    with pytest.raises(OSError,match="injected"):module.expand(config,spec=spec)
    assert json.loads((config.output/"data_contract.json").read_text())["status"]=="BLOCKED"
    before={str(p):p.read_bytes() for p in (config.output/"shards").glob("*/commit.json")}
    monkeypatch.setattr(module,"write_json_report",real)
    assert module.expand(config,spec=spec)["status"]=="READY"
    assert all(Path(p).read_bytes()==value for p,value in before.items())


def test_missing_initial_inventory_is_rebuilt_from_pinned_archive_on_resume(tmp_path,source_games,monkeypatch):
    import training.expanded_dataset as module
    archive,spec=make_archive(tmp_path,source_games)
    config=config_for(tmp_path,archive)
    real=module.write_json_report
    def fail(path,value):
        if Path(path).name=="source_inventory.json":raise OSError("interrupted initial inventory")
        return real(path,value)
    monkeypatch.setattr(module,"write_json_report",fail)
    with pytest.raises(OSError,match="interrupted"):module.expand(config,spec=spec)
    assert (config.output/"progress.json").is_file()
    monkeypatch.setattr(module,"write_json_report",real)
    result=module.expand(config,spec=spec)
    assert result["status"]=="READY" and result["attempted_games"]==3
