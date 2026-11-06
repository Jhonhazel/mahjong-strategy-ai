import hashlib
import json
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from tests.phase3_support import postgres_engine, postgres_url, web_settings

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.integration


def test_phase4_real_controller_two_rounds_v3_postgres_tcp(web_settings, postgres_engine, tmp_path, request):
    from app.main import create_app
    from app.settings import V3_SHA256
    from training.train_mlp import weights_sha256

    node = shutil.which('node')
    assert node, 'Phase4 frontend TCP acceptance NOT RUN: Node is required'
    app = create_app(web_settings)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, access_log=False, log_level='warning'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 20
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started, 'Temporary isolated Uvicorn did not start'
        model = app.state.resources.runtime.ai._model
        before = weights_sha256(model.state_dict())
        output = tmp_path / 'frontend_acceptance.json'
        result = subprocess.run([node, str(ROOT/'tests/frontend/live_driver.mjs'), f'http://127.0.0.1:{port}', str(output)],
                                capture_output=True, text=True, timeout=90, cwd=ROOT)
        assert result.returncode == 0, result.stdout + result.stderr
        evidence = json.loads(output.read_text())
        assert evidence['status'] == 'PASS' and len(evidence['rounds']) == 2
        assert all(round['final_view']['status'] == 'FINISHED' and round['deletion_verified'] for round in evidence['rounds'])
        assert any(round['offered_claims'] for round in evidence['rounds'])
        assert any(round['action_kinds'].get('Chi', 0) + round['action_kinds'].get('Peng', 0) for round in evidence['rounds'])
        assert any(p['turn_phase'] == 'POST_MELD_DISCARD' for round in evidence['rounds'] for p in round['predictions'])
        assert weights_sha256(model.state_dict()) == before
        assert hashlib.sha256(web_settings.model_checkpoint_path.read_bytes()).hexdigest() == V3_SHA256
        request.node.user_properties.append(('acceptance_summary', json.dumps({
            'rounds': [{key: round[key] for key in ('seed','actions','action_kinds','offered_claims','predictions','final_view','deletion_verified')} for round in evidence['rounds']],
            'duration_ms': evidence['duration_ms'], 'weights_before': before, 'weights_after': weights_sha256(model.state_dict())})))
    finally:
        server.should_exit = True
        thread.join(timeout=20)
        listener.close()
        assert not thread.is_alive(), 'Temporary Uvicorn did not shut down'
