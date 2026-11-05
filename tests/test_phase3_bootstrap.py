import secrets
from pathlib import Path

import pytest


def settings(**changes):
    from app.settings import Settings
    return Settings(_env_file=None, database_url='postgresql+psycopg://local@/mahjong_phase3_test',
                    session_secret=secrets.token_urlsafe(40), environment='test', **changes)


@pytest.mark.parametrize('changes',[
    {'session_secret':''}, {'database_url':'sqlite:///wrong.db'}, {'workers':2},
    {'max_active_games':0}, {'game_ttl_seconds':0},
    {'environment':'production','cookie_secure':False},
])
def test_settings_reject_unsafe_or_missing_values(changes):
    from app.settings import Settings
    values={'database_url':'postgresql+psycopg://local@/mahjong_phase3_test',
            'session_secret':secrets.token_urlsafe(40),'environment':'test',**changes}
    with pytest.raises(ValueError):Settings(_env_file=None,**values)


def test_runtime_paths_resolve_from_repository_not_working_directory(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    config=settings()
    assert config.model_checkpoint_path.is_absolute()
    assert config.model_checkpoint_path.name=='mahjong_discard_mlp_v3.pt'
    assert config.model_checkpoint_path.is_file()
    assert config.database_url.get_secret_value().startswith('postgresql+psycopg:')
    assert 'SecretStr' in repr(config) and config.session_secret.get_secret_value() not in repr(config)


def test_explicit_v3_runtime_loads_real_model_and_verified_metrics():
    from app.web.runtime import load_runtime_model
    runtime=load_runtime_model(settings())
    assert runtime.checkpoint_sha256=='ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720'
    assert sum(p.numel() for p in runtime.ai._model.parameters())==387746
    assert runtime.ai.encoder_version=='ijcai2026_mcr_v1_strict'
    assert runtime.metadata['test_evaluation']['kind']=='retrospective_known_test'
    assert runtime.metadata['test_evaluation']['metrics']['top1']==pytest.approx(.6434656460275325)


@pytest.mark.parametrize('asset',['model_checkpoint_path','model_metadata_path','dataset_contract_path'])
def test_missing_runtime_asset_fails_explicitly_without_model_fallback(tmp_path,asset):
    from app.web.runtime import load_runtime_model
    config=settings().model_copy(update={asset:tmp_path/'missing'})
    with pytest.raises(RuntimeError,match='v3'):load_runtime_model(config)


def test_corrupted_checkpoint_and_incompatible_metadata_fail(tmp_path):
    from app.web.runtime import load_runtime_model
    config=settings();bad=tmp_path/'bad.pt';bad.write_bytes(config.model_checkpoint_path.read_bytes()+b'corrupt')
    with pytest.raises(RuntimeError,match='v3'):load_runtime_model(config.model_copy(update={'model_checkpoint_path':bad}))
    bad_metadata=tmp_path/'metadata.json';bad_metadata.write_text('{"encoder_version":"incompatible"}')
    with pytest.raises(RuntimeError,match='v3'):load_runtime_model(config.model_copy(update={'model_metadata_path':bad_metadata}))


def test_local_database_tool_refuses_foreign_directory_and_unowned_start(tmp_path):
    from scripts.phase3_db import LocalPostgres
    root=tmp_path/'foreign';root.mkdir();(root/'personal.txt').write_text('keep')
    controller=LocalPostgres(root)
    with pytest.raises(ValueError,match='owned|unrelated'):controller.initialize()
    with pytest.raises(ValueError,match='owned'):controller.start()
    assert (root/'personal.txt').read_text()=='keep'


def test_local_database_urls_are_scoped_and_private(tmp_path):
    from scripts.phase3_db import LocalPostgres
    from sqlalchemy.engine import make_url
    controller=LocalPostgres(tmp_path/'local')
    url=make_url(controller.database_url('test'))
    assert url.drivername=='postgresql+psycopg' and url.database=='mahjong_phase3_test'
    assert url.password is None and str(tmp_path/'local'/'socket')==url.query['host']
    with pytest.raises(ValueError):controller.database_url('personal_database')
