import csv
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def source_arrays_and_rows():
    with np.load(ROOT / "datasets/strict_decisions/accepted.npz", allow_pickle=False) as archive:
        arrays = {k: archive[k] for k in archive.files}
    with (ROOT / "datasets/decision_manifest.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return arrays, rows


def test_real_approved_snapshot_and_match_disjoint_preprocessing(tmp_path):
    from training.phase2_dataset import validate_dataset, prepare_split
    corpus = validate_dataset(ROOT, tmp_path / "validation.json")
    assert corpus.report["status"] == "PASS"
    assert corpus.report["run_id"] == "84c2606383794fa8bc072d5edac7b252"
    assert corpus.report["samples"] == 1879 and corpus.report["matches"] == 84
    splits = {name: prepare_split(corpus, name) for name in ("train", "validation", "test")}
    assert [len(s.targets) for s in splits.values()] == [1564, 213, 102]
    assert [len(set(s.match_ids)) for s in splits.values()] == [72, 7, 5]
    for a, b in [("train", "validation"), ("train", "test"), ("validation", "test")]:
        assert set(splits[a].match_ids).isdisjoint(splits[b].match_ids)
    arrays, _ = source_arrays_and_rows()
    for split in splits.values():
        assert split.features.shape == (len(split.targets), 1368) and split.features.dtype == np.float32
        assert split.legal_masks.dtype == np.bool_ and split.legal_masks.shape == (len(split.targets), 34)
        assert split.targets.dtype == np.int64
        np.testing.assert_array_equal(split.features, arrays["obs"][split.row_indices].reshape(-1, 1368).astype(np.float32))
        np.testing.assert_array_equal(split.legal_masks, arrays["mask"][split.row_indices, 2:36])
        np.testing.assert_array_equal(split.targets, arrays["act"][split.row_indices] - 2)
    assert len(corpus.report["player_identities"]) == 4
    assert len(corpus.report["class_distribution"]) == 34


@pytest.mark.parametrize("tamper", ["npz_hash", "manifest_hash", "run_id", "strategy", "source_hash", "audit_status"])
def test_tampered_snapshot_fails_and_writes_report(tmp_path, tamper):
    from training.phase2_dataset import validate_dataset
    from app.domain.exceptions import CorruptedDatasetError
    root = tmp_path / "project"
    datasets = root / "datasets"
    (datasets / "strict_decisions").mkdir(parents=True)
    for name in ("data_contract.json", "parity_report.json", "strict_audit_report.json", "decision_manifest.csv", "strict_decisions/accepted.npz"):
        shutil.copyfile(ROOT / "datasets" / name, datasets / name)
    for name in ("app/engine/feature_encoder.py", "app/engine/mcr_referee.py", "training/replay.py"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, root / name)
    contract = json.loads((datasets / "data_contract.json").read_text())
    if tamper == "npz_hash":
        with (datasets / "strict_decisions/accepted.npz").open("ab") as stream:
            stream.write(b"modified")
    elif tamper == "manifest_hash":
        with (datasets / "decision_manifest.csv").open("a") as stream:
            stream.write("\n")
    elif tamper == "source_hash":
        (root / "app/engine/feature_encoder.py").write_text("# changed encoder\n")
    elif tamper == "audit_status":
        audit = json.loads((datasets / "strict_audit_report.json").read_text())
        audit["status"] = "FAIL"
        (datasets / "strict_audit_report.json").write_text(json.dumps(audit))
    else:
        contract["run_id" if tamper == "run_id" else "selected_strategy"] = "wrong"
        (datasets / "data_contract.json").write_text(json.dumps(contract))
    report = tmp_path / "validation.json"
    report.write_text('{"status":"PASS"}')
    with pytest.raises(CorruptedDatasetError):
        validate_dataset(root, report)
    assert json.loads(report.read_text())["status"] == "FAIL"


@pytest.mark.parametrize("tamper", ["duplicate_row", "missing_row", "match", "seat", "action", "score", "uid", "source", "duplicate_identity"])
def test_manifest_alignment_rejects_wrong_real_row_identity(tamper):
    from training.phase2_dataset import validate_alignment
    from app.domain.exceptions import CorruptedDatasetError
    arrays, rows = source_arrays_and_rows()
    if tamper == "duplicate_row": rows[1]["dataset_row"] = rows[0]["dataset_row"]
    elif tamper == "missing_row": rows.pop()
    elif tamper == "duplicate_identity":
        for field in ("match_id", "seat", "decision_order"):
            rows[1][field] = rows[0][field]
    elif tamper == "uid": rows[0]["player_uid"] = ""
    elif tamper == "source": rows[0]["source_file"] = "_allfield.npz"
    else:
        field = {"match": "match_id", "seat": "seat", "action": "target_action_id", "score": "round_score"}[tamper]
        rows[0][field] = {"match": "0" * 24, "seat": "3", "action": "35", "score": "9999"}[tamper]
    with pytest.raises(CorruptedDatasetError):
        validate_alignment(arrays, rows)


def test_alignment_accepts_explicit_row_order_and_rejects_empty_mask():
    from training.phase2_dataset import validate_alignment
    from app.domain.exceptions import CorruptedDatasetError
    arrays, rows = source_arrays_and_rows()
    aligned = validate_alignment(arrays, list(reversed(rows)))
    assert [int(r["dataset_row"]) for r in aligned] == list(range(1879))
    arrays["mask"][0] = False
    with pytest.raises(CorruptedDatasetError):
        validate_alignment(arrays, rows)
