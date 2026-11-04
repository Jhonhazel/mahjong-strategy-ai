import json

import numpy as np
import pytest


def write_fixture(path, illegal=False):
    """Synthetic validator fixture from a real engine, never corpus parity evidence."""
    from app.engine.mcr_referee import MCRRefereeEngine
    state = MCRRefereeEngine(seed=2).get_seat_encoded_state(0)
    act = int(np.flatnonzero(state.legal_discard_mask)[0]) + 2
    mask = state.legal_mask.copy()
    if illegal:
        mask[act] = False
    np.savez_compressed(path, obs=state.obs[None], mask=mask[None], act=np.array([act], dtype=np.int16), score=np.array([0], dtype=np.float32))


def test_aggregate_rows_are_verified_copies_and_never_double_counted(tmp_path):
    from training.inspect_dataset import audit_decisions_directory
    write_fixture(tmp_path / "player.npz")
    write_fixture(tmp_path / "_allfield.npz")
    report = audit_decisions_directory(tmp_path, tmp_path / "report.json")
    assert report["individual_player_file_count"] == 1
    assert report["total_individual_decisions"] == 1
    assert report["aggregate_bundles_excluded_from_sum"][0]["verified_subset"]


def test_audit_writes_failure_report_before_raising(tmp_path):
    from training.inspect_dataset import audit_decisions_directory
    from app.domain.exceptions import CorruptedDatasetError
    write_fixture(tmp_path / "bad.npz", illegal=True)
    with pytest.raises(CorruptedDatasetError):
        audit_decisions_directory(tmp_path, tmp_path / "report.json")
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["status"] == "FAIL" and report["errors"]
    assert report["total_individual_decisions"] == 1
    assert report["illegal_label_count"] == 1


def test_strict_corpus_metadata_is_validated_without_discarding_identity(tmp_path):
    from training.inspect_dataset import audit_decisions_directory
    path = tmp_path / "accepted.npz"
    write_fixture(path)
    with np.load(path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    arrays.update(match_id=np.array(["synthetic-validator-fixture"]), seat=np.array([0], dtype=np.int8))
    np.savez_compressed(path, **arrays)
    report = audit_decisions_directory(tmp_path, tmp_path / "report.json")
    assert report["status"] == "PASS" and report["total_individual_decisions"] == 1


def test_scalar_action_replaces_stale_audit_pass_with_failure(tmp_path):
    from training.inspect_dataset import audit_decisions_directory
    from app.domain.exceptions import CorruptedDatasetError
    path = tmp_path / "malformed.npz"
    write_fixture(path)
    with np.load(path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    arrays["act"] = np.array(2, dtype=np.int16)
    np.savez_compressed(path, **arrays)
    report_path = tmp_path / "report.json"
    report_path.write_text('{"status":"PASS"}')
    with pytest.raises(CorruptedDatasetError):
        audit_decisions_directory(tmp_path, report_path)
    report = json.loads(report_path.read_text())
    assert report["status"] == "FAIL"
    assert report["errors"][0]["filename"] == "malformed.npz"
