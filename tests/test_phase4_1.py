import importlib.util
import json
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.phase3_support import postgres_engine, postgres_url, web_settings

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = [
    ('Mishael Julindra Putra', '32240013', 's32240013@student.ubm.ac.id'),
    ('Efraim Emanuelle Josrin', '32240015', 's32240015@student.ubm.ac.id'),
    ('Jhonhazel Lionel Tjokahn', '32240016', 's32240016@student.ubm.ac.id'),
    ('Roberto Ariyadhamma', '32240027', 's32240027@student.ubm.ac.id'),
    ('Michael Kurniawan', '32240033', 's32240033@student.ubm.ac.id'),
]


def test_lecturer_entry_reuses_factory_without_startup_side_effects(monkeypatch):
    import app.db
    import app.main
    import app.web.runtime
    def forbidden(*args, **kwargs):
        pytest.fail('Root import must not initialize DB or model')
    monkeypatch.setattr(app.db, 'create_db_engine', forbidden)
    monkeypatch.setattr(app.web.runtime, 'load_runtime_model', forbidden)
    monkeypatch.setattr(app.main, 'load_runtime_model', forbidden)
    monkeypatch.setenv('MAHJONG_DATABASE_URL', 'postgresql+psycopg://test@localhost/mahjong_test')
    monkeypatch.setenv('MAHJONG_SESSION_SECRET', secrets.token_urlsafe(40))
    entry = ROOT/'main.py'
    assert entry.is_file(), 'Missing lecturer main.py entry point'
    spec = importlib.util.spec_from_file_location('lecturer_test_entry', entry)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert isinstance(module.app, FastAPI)
    assert module.app.state.resources is None and not module.app.state.initializing
    def route_paths(routes):
        for route in routes:
            if hasattr(route, 'original_router'):
                yield from route_paths(route.original_router.routes)
            elif hasattr(route, 'path'):
                yield route.path
    paths = list(route_paths(module.app.routes))
    for path in ('/', '/game', '/contact', '/history', '/health/ready', '/api/games'):
        assert paths.count(path) == 1


def test_legacy_runner_still_uses_factory(monkeypatch, web_settings):
    import scripts.run_backend as runner
    calls = []
    monkeypatch.setattr(runner, 'Settings', lambda: web_settings)
    monkeypatch.setattr(runner.uvicorn, 'run', lambda *args, **kwargs: calls.append((args, kwargs)))
    runner.main()
    assert calls[0][0] == ('app.main:create_app',)
    assert calls[0][1]['factory'] and calls[0][1]['workers'] == 1


def test_official_roster_is_reproducible_exact_and_has_no_roles(web_settings, postgres_engine):
    # Preserve the historical testcase identity; the owner now authorizes equal roles.
    from app.main import create_app
    from app.web.contact import ContactRoster
    assert web_settings.contact_members_path.name == 'contact_members.public.json'
    roster = ContactRoster.from_path(web_settings.contact_members_path)
    assert roster.verified and len(roster.members) == 5
    assert [(m.name, m.student_id, m.email) for m in roster.members] == MEMBERS
    assert all(m.role for m in roster.members) and len({m.role for m in roster.members})==1
    with TestClient(create_app(web_settings)) as client:
        page = client.get('/contact')
        assert page.status_code == 200 and page.text.count('class="member-card"') == 5
        for member in MEMBERS:
            assert all(value in page.text for value in member)
        assert 'belum dikonfirmasi' not in page.text and 'Pembagian Tugas Kelompok 1' in page.text
        assert 'kelompok dan pembagian tugas belum diverifikasi' not in page.text
        assert page.text.count('<dt>Peran</dt>')==5


@pytest.mark.parametrize('missing', [True, False])
def test_explicit_missing_or_unverified_contact_still_has_fallback(web_settings, postgres_engine, tmp_path, missing):
    from app.main import create_app
    path = tmp_path/'roster.json'
    if not missing:
        path.write_text(json.dumps({'verified': False, 'members': [{'name': 'SYNTHETIC UNVERIFIED'}]}))
    with TestClient(create_app(web_settings.model_copy(update={'contact_members_path': path}))) as client:
        page = client.get('/contact')
        assert 'belum diverifikasi' in page.text and 'contact-incomplete' in page.text
        assert 'SYNTHETIC UNVERIFIED' not in page.text


def test_phase4_1_animation_node_contracts():
    node = shutil.which('node'); assert node, 'Node is required for presentation tests'
    result = subprocess.run([node, '--test', 'tests/frontend/playback.test.mjs'], cwd=ROOT,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
