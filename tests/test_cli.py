import json
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize("entry", [["-m", "scripts.play_cli_round"], ["scripts/play_cli_round.py"]])
def test_automated_cli_completes_real_service_round(tmp_path, entry):
    output = tmp_path / "round.json"
    run = subprocess.run([sys.executable, *entry, "--auto-human-demo", "--seed", "42", "--human-seat", "1", "--output", str(output)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    report = json.loads(output.read_text())
    assert report["status"] == "FINISHED"
    assert 1 <= report["turn_number"] <= 600
    assert report["human_decisions"] > 0
    assert sum(report["round_result"]["score_deltas"]) == 0
    assert "FINISHED" in run.stdout
