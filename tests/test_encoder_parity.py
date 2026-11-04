import csv
import json
from pathlib import Path
import tarfile

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "datasets/finalist_games.tar.gz"


def real_game():
    if not ARCHIVE.exists():
        pytest.skip("Real IJCAI corpus not acquired: run python -m training.dataset_loader")
    with tarfile.open(ARCHIVE, "r:gz") as tar:
        member = next(m for m in tar if m.isfile() and m.name.endswith(".json"))
        return json.load(tar.extractfile(member))


@pytest.mark.dataset
def test_real_full_match_strict_events_match_independent_referee_replay():
    from training.replay import replay_observers, replay_referee
    game = real_game()
    observed = replay_observers(game)
    served = replay_referee(game)
    assert set(observed) == {0, 1, 2, 3}
    assert sum(len(v) for v in observed.values()) > 20
    assert any(d.kind == "post_meld" for rows in observed.values() for d in rows)
    for seat in range(4):
        assert len(observed[seat]) == len(served[seat])
        for training, serving in zip(observed[seat], served[seat]):
            assert training.log_index == serving.log_index
            assert training.action_id == serving.action_id
            assert np.array_equal(training.state.obs, serving.state.obs)
            assert np.array_equal(training.state.legal_mask, serving.state.legal_mask)
            assert training.state.legal_mask[training.action_id]


@pytest.mark.dataset
def test_same_public_uid_in_two_seats_keeps_both_explicit_seat_identities():
    from training.verify_encoder_parity import tracked_seats
    if not ARCHIVE.exists():
        pytest.skip("Real corpus not acquired")
    with tarfile.open(ARCHIVE, "r:gz") as tar:
        game = json.load(tar.extractfile("finalist_games/693e6aea416c555f2909fd27.json"))
    assert tracked_seats(game) == [("692e88f12ab5c344942824ef", 0), ("692e88f12ab5c344942824ef", 2)]


@pytest.mark.dataset
def test_real_draw_terminal_scores_from_content_are_verified():
    from training.replay import replay_observers, replay_referee
    if not ARCHIVE.exists():
        pytest.skip("Real corpus not acquired")
    with tarfile.open(ARCHIVE, "r:gz") as tar:
        game = json.load(tar.extractfile("finalist_games/693db22b416c555f29090926.json"))
    observed, served = replay_observers(game), replay_referee(game)
    assert sum(map(len, observed.values())) == sum(map(len, served.values()))


def test_match_group_contract_rejects_conflicts_and_supports_disjoint_groups():
    from training.verify_encoder_parity import validate_manifest, partition_for_match
    from app.domain.exceptions import CorruptedDatasetError
    records = [{"source_file": "a.json", "source_row": i, "match_id": f"game-{i // 3}", "split": partition_for_match(f"game-{i // 3}")} for i in range(900)]
    report = validate_manifest(records)
    assert report["match_count"] == 300 and report["overlap_count"] == 0
    for a, b in [("train", "validation"), ("train", "test"), ("validation", "test")]:
        assert {r['match_id'] for r in records if r['split'] == a}.isdisjoint({r['match_id'] for r in records if r['split'] == b})
    duplicate = dict(records[0], match_id="another-game")
    with pytest.raises(CorruptedDatasetError):
        validate_manifest(records + [duplicate])
    with pytest.raises(CorruptedDatasetError):
        validate_manifest(records + [dict(records[0], source_row=1000, split="validation" if records[0]["split"] != "validation" else "test")])


@pytest.mark.dataset
def test_failed_replay_writes_report_and_cannot_pass_gate(tmp_path):
    from training.verify_encoder_parity import verify_replay_parity
    from app.domain.exceptions import ParityVerificationError
    from tests.test_dataset_resilience import tar_bytes
    game = real_game()
    # Break real data, retaining a traceable public record; never fake parity.
    game["log"] = game["log"][:4]
    source = tmp_path / "truncated_games.tar.gz"
    source.write_bytes(tar_bytes("games/bad.json", json.dumps(game).encode()))
    with pytest.raises(ParityVerificationError):
        verify_replay_parity(source, ROOT / "datasets/finalist_decisions", tmp_path / "parity_report.json", max_games=1, min_verified_matches=1)
    report = json.loads((tmp_path / "parity_report.json").read_text())
    assert report["status"] == "FAIL"
    assert report["n_matches_failed_replay"] == 1
    assert report["n_decisions_compared"] == 0
    assert report["parity_rate"] is None


def test_missing_archive_invalidates_previous_ready_artifacts(tmp_path):
    from training.verify_encoder_parity import verify_replay_parity
    from app.domain.exceptions import ParityVerificationError
    report = tmp_path / "parity_report.json"
    contract = tmp_path / "data_contract.json"
    report.write_text('{"status":"PASS"}')
    contract.write_text('{"status":"READY"}')
    with pytest.raises(ParityVerificationError):
        verify_replay_parity(tmp_path / "missing.tar.gz", tmp_path, report, max_games=1, min_verified_matches=1)
    result, data_contract = json.loads(report.read_text()), json.loads(contract.read_text())
    assert result["status"] == "FAIL"
    assert data_contract["status"] == "BLOCKED"
    assert result["run_id"] == data_contract["run_id"]
    assert result["n_matches_failed_replay"] == 1


@pytest.mark.dataset
def test_artifact_write_failure_publishes_fail_and_blocked_contract(tmp_path):
    from training.verify_encoder_parity import verify_replay_parity
    from app.domain.exceptions import ParityVerificationError
    from tests.test_dataset_resilience import tar_bytes
    source = tmp_path / "one.tar.gz"
    source.write_bytes(tar_bytes("one.json", json.dumps(real_game()).encode()))
    (tmp_path / "strict_decisions").write_text("occupied; must preserve")
    report = tmp_path / "parity_report.json"
    (tmp_path / "data_contract.json").write_text('{"status":"READY"}')
    with pytest.raises(ParityVerificationError):
        verify_replay_parity(source, ROOT / "datasets/finalist_decisions", report, max_games=1, min_verified_matches=1)
    assert json.loads(report.read_text())["status"] == "FAIL"
    assert json.loads((tmp_path / "data_contract.json").read_text())["status"] == "BLOCKED"
    assert (tmp_path / "strict_decisions").read_text() == "occupied; must preserve"


@pytest.mark.dataset
def test_duplicate_real_match_cannot_satisfy_distinct_match_gate(tmp_path):
    from training.verify_encoder_parity import verify_replay_parity
    from app.domain.exceptions import ParityVerificationError
    import io
    payload = json.dumps(real_game()).encode()
    archive = tmp_path / "duplicate.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("first.json", "duplicate.json"):
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            tar.addfile(member, io.BytesIO(payload))
    report = tmp_path / "parity_report.json"
    with pytest.raises(ParityVerificationError):
        verify_replay_parity(archive, ROOT / "datasets/finalist_decisions", report, max_games=2, min_verified_matches=2)
    result = json.loads(report.read_text())
    assert result["status"] == "FAIL"
    assert result["n_matches_verified"] == result["accepted_matches"] == 1
    assert result["status_counts"]["duplicate_match_id"] == 1
    assert result["accepted_samples"] == 10  # Pinned real source match: seat 2's ten discards.


@pytest.mark.dataset
@pytest.mark.slow
def test_real_at_least_50_complete_matches_and_accepted_provenance():
    report_path = ROOT / "datasets/parity_report.json"
    if not report_path.exists():
        pytest.skip("Run python -m training.verify_encoder_parity first")
    report = json.loads(report_path.read_text())
    assert report["status"] == "PASS"
    assert report["n_matches_verified"] >= 50
    assert report["n_mismatches"] == 0
    assert report["n_decisions_compared"] > 0
    assert report["parity_rate"] == report["n_exact_decisions"] / report["n_decisions_compared"]
    contract = json.loads((ROOT / "datasets/data_contract.json").read_text())
    assert contract["selected_strategy"] == "strict_reextraction"
    with (ROOT / "datasets/decision_manifest.csv").open(newline="", encoding="utf-8") as stream:
        manifest = list(csv.DictReader(stream))
    assert len(manifest) == report["accepted_samples"]
    assert all(r["match_id"] and r["source_hash"] and r["replay_status"] == "verified_exact" for r in manifest)
    with np.load(ROOT / "datasets/strict_decisions/accepted.npz", allow_pickle=False) as arrays:
        assert len(arrays["obs"]) == len(manifest)
        assert np.all(arrays["mask"][np.arange(len(manifest)), arrays["act"]])
        assert np.array_equal(arrays["score"], np.array([r["round_score"] for r in manifest], dtype=np.float32))
