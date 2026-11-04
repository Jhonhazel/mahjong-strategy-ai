import json
from pathlib import Path
import subprocess
import sys


def test_real_saved_model_demo_finishes_round_without_prediction_mutation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    import pytest
    if not (root / "artifacts/models/mahjong_discard_mlp.pt").is_file():
        pytest.skip("Train the local Phase 2 checkpoint before the real model demonstration")
    output = tmp_path / "demo.json"
    run = subprocess.run([sys.executable, "-m", "scripts.demo_ai_prediction", "--smoke", "--seed", "42", "--human-seat", "1", "--output", str(output)], cwd=root, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    report = json.loads(output.read_text())
    assert report["status"] == "FINISHED" and report["seed"] == 42
    assert report["predictions"]
    assert all(p["state_unchanged"] and p["all_suggestions_legal"] for p in report["predictions"])
    assert all(1 <= len(p["prediction"]["top3"]) <= 3 for p in report["predictions"])
    assert sum(report["round_result"]["score_deltas"]) == 0
    assert "not winning chances" in run.stdout
