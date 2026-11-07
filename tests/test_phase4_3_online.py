import json
from pathlib import Path
import secrets
import subprocess
import importlib
import importlib.util

import pytest
from pydantic import ValidationError

from app.settings import Settings

ROOT=Path(__file__).resolve().parents[1]


def config(**extra):
    return Settings(_env_file=None,database_url='postgresql+psycopg://synthetic@localhost/mahjong_test',
                    session_secret=secrets.token_urlsafe(48),**extra)


@pytest.mark.parametrize('value',['*','172.30.43.0/28','proxy.example','0.0.0.0','::','224.0.0.1'])
def test_forwarded_headers_never_accept_wildcard_network_or_nonhost_trust(value):
    with pytest.raises(ValidationError):config(trusted_proxy_ips=[value])


def test_explicit_proxy_addresses_are_canonical_and_duplicates_do_not_expand_trust():
    settings=config(trusted_proxy_ips=['172.30.43.2','0:0:0:0:0:0:0:1','172.30.43.2'])
    assert getattr(settings,'trusted_proxy_ips',None)==['172.30.43.2','::1']


@pytest.mark.parametrize('trusted,enabled',[([],False),(['172.30.43.2'],True)])
def test_runner_trusts_only_the_configured_proxy_and_preserves_direct_default(monkeypatch,trusted,enabled):
    import scripts.run_backend as runner
    calls=[];settings=config(trusted_proxy_ips=trusted)
    monkeypatch.setattr(runner,'Settings',lambda:settings)
    monkeypatch.setattr(runner.uvicorn,'run',lambda *a,**kw:calls.append(kw))
    runner.main()
    assert calls[0]['proxy_headers'] is enabled
    if enabled:assert calls[0]['forwarded_allow_ips']=='172.30.43.2'
    assert calls[0]['workers']==1


def test_production_still_rejects_insecure_cookies():
    with pytest.raises(ValidationError):config(environment='production',cookie_secure=False)


def test_runtime_only_export_does_not_rearchive_research_data(tmp_path):
    result=subprocess.run([str(ROOT/'.venv/bin/python'),'-m','scripts.build_lecturer_release',
                           '--runtime-only','--output',str(tmp_path/'release')],cwd=ROOT,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    import zipfile
    assert not (tmp_path/'release/mahjong-strategy-ai-audit.zip').exists()
    manifest=json.loads((tmp_path/'release/release_manifest.json').read_text())
    assert 'audit' not in manifest
    with zipfile.ZipFile(tmp_path/'release/mahjong-strategy-ai-lecturer-portable.zip') as archive:
        assert 'mahjong-strategy-ai/main.py' in archive.namelist()
        assert not any('/tests/' in n or '/shards/' in n for n in archive.namelist())


@pytest.mark.parametrize('url',['http://localhost:8000','https://synthetic:synthetic@example.test','https://example.test/path','https://example.test?token=synthetic'])
def test_online_smoke_never_sends_credentials_or_uses_plaintext(url):
    assert importlib.util.find_spec('scripts.smoke_online'), 'Missing HTTPS smoke test utility'
    with pytest.raises(ValueError):importlib.import_module('scripts.smoke_online').validate_origin(url)
