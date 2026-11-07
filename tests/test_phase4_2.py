"""Release boundaries: bytes, isolation, tampering and persistent private config."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    assert importlib.util.find_spec(name), f'Missing Phase4.2 capability: {name}'
    return importlib.import_module(name)


@pytest.fixture
def release_source(tmp_path):
    root=tmp_path/'source';root.mkdir()
    manifest=json.loads((ROOT/'docs/ml_artifact_bundle_manifest.json').read_text())
    paths=['docs/ml_artifact_bundle_manifest.json',*[x['restore_path'] for x in manifest['files'].values()]]
    for name in paths:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    for name,data in {'main.py':'from app.demo import answer\n', 'app/__init__.py':'',
                      'app/demo.py':'answer=42\n','tests/old_test.py':'assert True\n',
                      'docs/evidence/old.txt':'historical evidence\n',
                      '.env':'MAHJONG_SESSION_SECRET=PRIVATE_DO_NOT_COPY\n',
                      'backup.sql':'PRIVATE_DATABASE_DO_NOT_COPY\n',
                      '.venv/ignored.txt':'GENERATED_ENVIRONMENT\n'}.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
    runtime={p:p for p in paths+['main.py','app/__init__.py','app/demo.py']}
    return root, runtime


def test_release_is_deterministic_and_separates_audit_without_copying_secrets(release_source,tmp_path):
    root,runtime=release_source;builder=module('scripts.build_lecturer_release')
    first=builder.build_release(root,tmp_path/'one',runtime)
    second=builder.build_release(root,tmp_path/'two',runtime)
    for name in ('mahjong-strategy-ai-lecturer-portable.zip','mahjong-strategy-ai-audit.zip'):
        assert (tmp_path/'one'/name).read_bytes()==(tmp_path/'two'/name).read_bytes()
    with zipfile.ZipFile(tmp_path/'one'/'mahjong-strategy-ai-lecturer-portable.zip') as z:
        names=z.namelist()
        assert 'mahjong-strategy-ai/main.py' in names
        assert not any('/tests/' in n or '/.env' in n or '/.venv/' in n or n.endswith('.sql') for n in names)
        manifest=json.loads(z.read('mahjong-strategy-ai/RELEASE_MANIFEST.json'))
        assert manifest['files']['app/demo.py']['sha256']==hashlib.sha256(b'answer=42\n').hexdigest()
    with zipfile.ZipFile(tmp_path/'one'/'mahjong-strategy-ai-audit.zip') as z:
        assert z.read('mahjong-strategy-ai-audit/docs/evidence/old.txt')==b'historical evidence\n'
        assert z.read('mahjong-strategy-ai-audit/tests/old_test.py')==b'assert True\n'
        assert not any('/.env' in n or '/.venv/' in n or n.endswith('.sql') for n in z.namelist())
    assert (root/'.env').read_text().endswith('PRIVATE_DO_NOT_COPY\n')
    assert first['runtime']['files']==second['runtime']['files']


@pytest.mark.parametrize('unsafe',['../outside.py','/absolute.py','C:/escape.py','a\\escape.py','.env'])
def test_release_rejects_unsafe_source_or_destination_paths(release_source,tmp_path,unsafe):
    root,runtime=release_source;runtime['app/demo.py']=unsafe
    with pytest.raises(ValueError): module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)
    assert not (tmp_path/'out').exists()


def test_release_rejects_symlink_even_to_a_file_inside_the_root(release_source,tmp_path):
    root,runtime=release_source
    (root/'alias.py').symlink_to(root/'app/demo.py');runtime['alias.py']='alias.py'
    with pytest.raises(ValueError): module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)


def test_release_rejects_missing_local_runtime_import(release_source,tmp_path):
    root,runtime=release_source;(root/'main.py').write_text('from app.missing import thing\n')
    with pytest.raises(ValueError,match='import'): module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)


def test_release_refuses_existing_output_without_modifying_it(release_source,tmp_path):
    root,runtime=release_source;out=tmp_path/'out';out.mkdir();(out/'user.txt').write_text('KEEP')
    with pytest.raises(FileExistsError): module('scripts.build_lecturer_release').build_release(root,out,runtime)
    assert (out/'user.txt').read_text()=='KEEP'


def test_release_detects_source_changes_between_manifest_and_archive_copy(release_source,tmp_path,monkeypatch):
    root,runtime=release_source;builder=module('scripts.build_lecturer_release')
    original=builder.check_no_secret;calls=[]
    def concurrent_edit(path):
        original(path)
        if path==root/'app/demo.py':
            calls.append(path)
            if len(calls)==2:path.write_text('answer=99\n')
    monkeypatch.setattr(builder,'check_no_secret',concurrent_edit)
    with pytest.raises(ValueError,match='changed'):builder.build_release(root,tmp_path/'out',runtime)


def test_release_refuses_tampered_required_model_before_output(release_source,tmp_path):
    root,runtime=release_source;(root/'artifacts/models/mahjong_discard_mlp_v3.pt').write_bytes(b'wrong')
    with pytest.raises(ValueError): module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)
    assert not (tmp_path/'out').exists()


def test_release_rejects_mapping_correct_host_model_to_wrong_package_destination(release_source,tmp_path):
    root,runtime=release_source;model='artifacts/models/mahjong_discard_mlp_v3.pt'
    runtime[model],runtime['app/demo.py']=runtime['app/demo.py'],runtime[model]
    with pytest.raises(ValueError):module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)
    assert not (tmp_path/'out').exists()


def test_asset_restore_verifies_all_members_and_preserves_identical_files(tmp_path):
    assets=module('scripts.lecturer_assets');root=tmp_path/'release';(root/'docs').mkdir(parents=True)
    shutil.copyfile(ROOT/'docs/ml_artifact_bundle_manifest.json',root/'docs/ml_artifact_bundle_manifest.json')
    bundle=ROOT/'artifacts/transfer/mahjong_discard_mlp_v3_inference.tar.gz'
    assets.restore_assets(root,bundle)
    path=root/'artifacts/models/mahjong_discard_mlp_v3.pt';before=path.stat().st_mtime_ns
    assert assets.verify_assets(root)['status']=='PASS'
    assets.restore_assets(root,bundle);assert path.stat().st_mtime_ns==before
    path.write_bytes(b'other model')
    with pytest.raises(ValueError): assets.restore_assets(root,bundle)
    assert path.read_bytes()==b'other model'


def test_asset_restore_rejects_tampered_bundle_without_extracting(tmp_path):
    assets=module('scripts.lecturer_assets');root=tmp_path/'release';(root/'docs').mkdir(parents=True)
    shutil.copyfile(ROOT/'docs/ml_artifact_bundle_manifest.json',root/'docs/ml_artifact_bundle_manifest.json')
    bundle=tmp_path/'wrong.tar.gz'
    with tarfile.open(bundle,'w:gz'): pass
    with pytest.raises(ValueError):assets.restore_assets(root,bundle)
    assert not (root/'artifacts').exists()


def test_native_config_is_private_persistent_and_does_not_rotate_secret(tmp_path):
    setup=module('scripts.lecturer_setup')
    url='postgresql+psycopg://synthetic:synthetic@127.0.0.1/mahjong_test'
    setup.write_native_config(tmp_path,url);path=tmp_path/'.env';first=path.read_bytes()
    assert 'MAHJONG_SESSION_SECRET=' in first.decode()
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    setup.write_native_config(tmp_path,url);assert path.read_bytes()==first


@pytest.mark.parametrize('url',['sqlite:///local.db','postgresql://u:p@remote.example/db','postgresql://u:p@127.0.0.1/db\nEVIL=x'])
def test_native_config_rejects_nonlocal_or_unsafe_database_urls(tmp_path,url):
    with pytest.raises(ValueError):module('scripts.lecturer_setup').write_native_config(tmp_path,url)
    assert not (tmp_path/'.env').exists()


def test_config_never_follows_a_symlink(tmp_path):
    outside=tmp_path/'private.txt';outside.write_text('KEEP');root=tmp_path/'release';root.mkdir()
    (root/'.env').symlink_to(outside)
    with pytest.raises(ValueError):module('scripts.lecturer_setup').write_native_config(root,'postgresql://u:p@localhost/db')
    assert outside.read_text()=='KEEP'


def test_compose_secrets_are_generated_once_without_secret_output(tmp_path,capsys):
    setup=module('scripts.lecturer_setup');setup.prepare_compose_secrets(tmp_path)
    names=('db_admin_password','db_password','session_secret')
    before={n:(tmp_path/n).read_bytes() for n in names}
    assert all(len(v)>=40 for v in before.values()) and len(set(before.values()))==3
    setup.prepare_compose_secrets(tmp_path)
    assert before=={n:(tmp_path/n).read_bytes() for n in names}
    assert stat.S_IMODE(tmp_path.stat().st_mode)==0o700
    assert all(v.decode() not in capsys.readouterr().out for v in before.values())


def test_macos_launcher_reports_the_selected_host_port(tmp_path):
    # Docker is external; this tests the real launcher's config/message handling.
    shutil.copyfile(ROOT/'setup-macos.sh',tmp_path/'setup-macos.sh')
    bin_dir=tmp_path/'bin';bin_dir.mkdir();docker=bin_dir/'docker'
    docker.write_text('#!/bin/sh\nexit 0\n');docker.chmod(0o755)
    result=subprocess.run(['sh','setup-macos.sh'],cwd=tmp_path,text=True,capture_output=True,
                          env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],MAHJONG_WEB_PORT='8890'))
    assert result.returncode==0
    assert 'http://127.0.0.1:8890/' in result.stdout


@pytest.mark.parametrize('name',['backup.dump','docs/backup.sql.gz','artifacts/credentials.json','private-notes.txt'])
def test_audit_does_not_admit_backups_credentials_or_unknown_root_files(release_source,tmp_path,name):
    root,runtime=release_source;path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('{"MAHJONG_SESSION_SECRET":"synthetic-private-value"}')
    module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)
    with zipfile.ZipFile(tmp_path/'out'/'mahjong-strategy-ai-audit.zip') as archive:
        assert 'mahjong-strategy-ai-audit/'+name not in archive.namelist()
    assert path.is_file()


def test_audit_rejects_credential_values_hidden_in_an_innocent_json_name(release_source,tmp_path):
    root,runtime=release_source;path=root/'docs/ordinary.json'
    path.write_text('{"config":{"MAHJONG_SESSION_SECRET":"synthetic-private-value"}}')
    with pytest.raises(ValueError,match='secret'):module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)
    assert not (tmp_path/'out').exists()


def test_prior_release_manifest_is_preserved_without_duplicate_zip_names(release_source,tmp_path):
    root,runtime=release_source;(root/'RELEASE_MANIFEST.json').write_text('{"original":"preserve"}')
    module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)
    with zipfile.ZipFile(tmp_path/'out'/'mahjong-strategy-ai-audit.zip') as archive:
        assert len(archive.namelist())==len(set(archive.namelist()))
        assert archive.read('mahjong-strategy-ai-audit/manifests/source_RELEASE_MANIFEST.json')==b'{"original":"preserve"}'


def test_runtime_mapping_cannot_overwrite_the_generated_manifest(release_source,tmp_path):
    root,runtime=release_source;(root/'note.md').write_text('preserve');runtime['note.md']='RELEASE_MANIFEST.json'
    with pytest.raises(ValueError):module('scripts.build_lecturer_release').build_release(root,tmp_path/'out',runtime)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('query',['host=remote.example','hostaddr=203.0.113.2','service=remote','host=127.0.0.1&host=remote.example'])
def test_native_setup_rejects_effective_connection_host_overrides(tmp_path,query):
    with pytest.raises(ValueError):
        module('scripts.lecturer_setup').write_native_config(tmp_path,'postgresql+psycopg://synthetic:synthetic@127.0.0.1/test?'+query)
    assert not (tmp_path/'.env').exists()
