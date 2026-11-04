import json
from pathlib import Path

import pytest

from tests.test_phase2_checkpoint import checkpoint_fixture


def save_unit_checkpoint(tmp_path, checkpoint_fixture):
    from app.model_checkpoint import save_checkpoint
    model, metadata, _ = checkpoint_fixture
    checkpoint = tmp_path / "unit.pt"
    save_checkpoint(model, checkpoint, metadata)
    return checkpoint, Path(__file__).resolve().parents[1], tmp_path / "reports"


def test_frozen_checkpoint_evaluation_is_complete_and_independently_recalculated(tmp_path, checkpoint_fixture):
    from app.model_checkpoint import save_checkpoint, checkpoint_sha256
    from training.evaluate_mlp import evaluate_checkpoint, recalculate_metrics
    model, metadata, _ = checkpoint_fixture
    checkpoint = tmp_path / "model.pt"
    save_checkpoint(model, checkpoint, metadata)
    before_hash = checkpoint_sha256(checkpoint)
    root = Path(__file__).resolve().parents[1]
    reports = tmp_path / "reports"
    result = evaluate_checkpoint(checkpoint, root, reports)
    assert result["status"] == "PASS"
    assert result["test_samples"] == 102 and result["test_matches"] == 5
    assert result["mlp"]["legal_rate"] == 1.
    assert result["independent_recalculation"]["status"] == "PASS"
    assert checkpoint_sha256(checkpoint) == before_hash
    assert json.loads((reports / "model_freeze.json").read_text())["checkpoint_sha256"] == before_hash
    rows = json.loads((reports / "test_predictions.json").read_text())["predictions"]
    recalculated = recalculate_metrics(rows)
    for name in ("top1", "top3", "nll", "macro_f1_34", "macro_f1_supported", "legal_rate"):
        assert recalculated[name] == pytest.approx(result["mlp"][name], abs=1e-8)
    report_hash = checkpoint_sha256(reports / "evaluation_metrics.json")
    with pytest.raises(ValueError, match="verify-existing"):
        evaluate_checkpoint(checkpoint, root, reports)
    verified = evaluate_checkpoint(checkpoint, root, reports, verify_existing=True)
    assert verified["status"] == "PASS"
    assert checkpoint_sha256(reports / "evaluation_metrics.json") == report_hash


def test_independent_metrics_have_hand_checked_expected_values():
    from training.evaluate_mlp import recalculate_metrics
    import math
    rows = [{"target_class": y, "predicted_class": p, "top3": [0, 1, 2], "legal_classes": [0, 1, 2], "target_log_probability": math.log(prob)} for y, p, prob in [(0, 0, .6), (0, 1, .2), (1, 1, .8), (2, 1, .2)]]
    result = recalculate_metrics(rows)
    assert result["top1"] == .5 and result["top3"] == 1.
    assert result["macro_f1_34"] == pytest.approx((2/3 + .5)/34)
    assert result["macro_f1_supported"] == pytest.approx((2/3 + .5)/3)


@pytest.mark.parametrize("tamper", ["missing_freeze", "missing_predictions", "empty_predictions", "changed_freeze"])
def test_reverification_rejects_missing_or_changed_saved_evidence(tmp_path, checkpoint_fixture, tamper):
    from training.evaluate_mlp import evaluate_checkpoint
    checkpoint, root, reports = save_unit_checkpoint(tmp_path, checkpoint_fixture)
    evaluate_checkpoint(checkpoint, root, reports)
    if tamper == "missing_freeze":
        (reports / "model_freeze.json").unlink()
    elif tamper == "missing_predictions":
        (reports / "test_predictions.json").unlink()
    elif tamper == "empty_predictions":
        (reports / "test_predictions.json").write_text('{"predictions":[]}')
    else:
        freeze = json.loads((reports / "model_freeze.json").read_text())
        freeze["training_config"]["seed"] += 1
        (reports / "model_freeze.json").write_text(json.dumps(freeze))
    with pytest.raises(ValueError):
        evaluate_checkpoint(checkpoint, root, reports, verify_existing=True)


def test_metadata_write_failure_cannot_publish_pass_and_same_frozen_model_can_resume(tmp_path, checkpoint_fixture, monkeypatch):
    from training import evaluate_mlp as module
    checkpoint, root, reports = save_unit_checkpoint(tmp_path, checkpoint_fixture)
    metadata_path = checkpoint.with_suffix(".metadata.json")
    real_writer = module.write_json_report
    def fail_metadata(path, value):
        if Path(path) == metadata_path:
            raise OSError("unit metadata publication failure")
        return real_writer(path, value)
    with monkeypatch.context() as patch:
        patch.setattr(module, "write_json_report", fail_metadata)
        with pytest.raises(OSError, match="publication failure"):
            module.evaluate_checkpoint(checkpoint, root, reports)
    assert json.loads((reports / "evaluation_metrics.json").read_text())["status"] == "FAIL"
    assert json.loads(metadata_path.read_text())["test_evaluation"] is None
    with pytest.raises(ValueError):
        module.evaluate_checkpoint(checkpoint, root, reports, verify_existing=True)
    resumed = module.evaluate_checkpoint(checkpoint, root, reports, resume=True)
    assert resumed["status"] == "PASS"
    assert json.loads(metadata_path.read_text())["test_evaluation"] is not None
    assert module.evaluate_checkpoint(checkpoint, root, reports, verify_existing=True)["status"] == "PASS"
