"""Native setup logic on real isolated TCP PostgreSQL; not Windows CMD certification."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace
import uuid
import zipfile

import psycopg
from psycopg import sql
import pytest

ROOT=Path(__file__).resolve().parents[1]


def helper():
    assert importlib.util.find_spec('scripts.native_postgres'),'Missing safe native PostgreSQL provisioning'
    return importlib.import_module('scripts.native_postgres')


@pytest.fixture(scope='module')
def native_pg(tmp_path_factory):
    root=tmp_path_factory.mktemp('native-postgres').resolve();data=root/'data'
    password=secrets.token_urlsafe(48);pw=root/'init-password'
    pw.write_text(password);pw.chmod(0o600)
    tools={name:shutil.which(name) for name in ('initdb','pg_ctl')}
    assert all(tools.values()),'Real native integration requires installed PostgreSQL tools'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    subprocess.run([tools['initdb'],'-D',str(data),'-U','native_admin','--pwfile',str(pw),
                    '--auth-host=scram-sha-256','--auth-local=scram-sha-256','--encoding=UTF8','--locale=C'],
                   check=True,capture_output=True,text=True,timeout=30)
    pw.unlink()
    options=f"-h 127.0.0.1 -p {port} -k '' -c log_statement=none -c log_min_error_statement=panic"
    subprocess.run([tools['pg_ctl'],'-D',str(data),'-l',str(root/'private-test.log'),'-o',options,'-w','start'],
                   check=True,capture_output=True,text=True,timeout=30)
    def connect():
        return psycopg.connect(host='127.0.0.1',port=port,user='native_admin',password=password,
                               dbname='postgres',autocommit=True,connect_timeout=3)
    try:
        with connect() as c:assert c.pgconn.used_password
        yield SimpleNamespace(port=port,user='native_admin',password=password,connect=connect)
    finally:
        subprocess.run([tools['pg_ctl'],'-D',str(data),'-m','fast','-w','stop'],
                       check=True,capture_output=True,text=True,timeout=30)


@pytest.fixture
def target(tmp_path,native_pg):
    role='native_'+uuid.uuid4().hex[:14];database='native_'+uuid.uuid4().hex[:14]
    return tmp_path/'project space 學生',dict(port=native_pg.port,admin_user=native_pg.user,
             admin_password=native_pg.password,role=role,database=database)


def project_assets(root):
    root.mkdir(parents=True,exist_ok=True)
    paths=['docs/ml_artifact_bundle_manifest.json']
    paths += [r['restore_path'] for r in json.loads((ROOT/paths[0]).read_text())['files'].values()]
    for name in paths:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)


def windows_finish(monkeypatch,root,options):
    setup=importlib.import_module('scripts.lecturer_setup');pg=helper();prepare=pg.prepare_database
    project_assets(root)
    monkeypatch.setattr(setup,'ROOT',root)
    monkeypatch.setattr(setup,'platform',SimpleNamespace(system=lambda:'Windows',machine=lambda:'AMD64'))
    monkeypatch.setattr(pg,'prepare_database',lambda path:prepare(path,**options))
    return setup


def test_real_first_setup_and_repeated_setup_preserve_model_prediction_history(target,native_pg,monkeypatch):
    from app.main import create_app
    from app.settings import Settings
    from fastapi.testclient import TestClient
    root,options=target;setup=windows_finish(monkeypatch,root,options)
    assert setup.native_finish()==0
    config=Settings(_env_file=root/'.env');before=(root/'.env').read_bytes()
    with native_pg.connect() as c:
        assert c.execute('SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(options['role'],)).fetchone()==(True,False,False,False,False,False)
        assert c.execute('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s',(options['database'],)).fetchone()==(options['role'],)
    with TestClient(create_app(config)) as browser:
        token=browser.get('/api/session').json()['csrf_token'];headers={'X-CSRF-Token':token}
        game=browser.post('/api/games',json={'seed':42,'human_seat':1},headers=headers).json()
        prediction=browser.post('/api/games/'+game['game_id']+'/predict',json={'expected_turn_number':game['turn_number']},headers=headers)
        assert prediction.status_code==201
        saved=prediction.json();assert saved['model_version']=='discard_mlp_flexible_v1:ad05a5b2ce37'
        cookies=dict(browser.cookies)
    def unexpected(*args,**kwargs):pytest.fail('Existing configuration requested administrator/provisioning')
    monkeypatch.setattr(helper(),'prepare_database',unexpected)
    assert setup.native_finish()==0 and (root/'.env').read_bytes()==before
    assert setup.native_finish(check_only=True)==0
    with TestClient(create_app(Settings(_env_file=root/'.env'))) as browser:
        browser.cookies.update(cookies)
        assert browser.get('/api/predictions/'+saved['prediction_id']).status_code==200
        assert browser.get('/history/'+saved['prediction_id']).status_code==200
    assert native_pg.password not in (root/'.env').read_text()
    assert native_pg.password not in (root/'.local/native-postgres/pending.json').read_text()


def test_repeated_provisioning_reuses_credentials_without_resetting_database(target,native_pg):
    pg=helper();root,options=target
    first=pg.prepare_database(root,**options);pending=root/'.local/native-postgres/pending.json'
    before=pending.read_bytes()
    from sqlalchemy.engine import make_url
    url=make_url(first['database_url'])
    with psycopg.connect(host=url.host,port=url.port,user=url.username,password=url.password,dbname=url.database,autocommit=True) as c:
        c.execute('CREATE TABLE keep_history (value TEXT)');c.execute("INSERT INTO keep_history VALUES ('KEEP')")
    second=pg.prepare_database(root,**options)
    assert first==second and pending.read_bytes()==before
    with psycopg.connect(host=url.host,port=url.port,user=url.username,password=url.password,dbname=url.database) as c:
        assert c.execute('SELECT value FROM keep_history').fetchone()==('KEEP',)


@pytest.mark.parametrize('resource',['role','database'])
def test_foreign_catalog_resources_are_not_taken_over(target,native_pg,resource):
    pg=helper();root,options=target
    with native_pg.connect() as c:
        if resource=='role':c.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(options['role']),sql.Literal('synthetic-foreign-password')))
        else:c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(options['database'])))
        original=c.execute('SELECT oid,rolpassword FROM pg_authid WHERE rolname=%s',(options['role'],)).fetchone()
        owner=c.execute('SELECT datdba FROM pg_database WHERE datname=%s',(options['database'],)).fetchone()
    with pytest.raises(pg.NativeSetupError,match='existing|ownership|owned'):pg.prepare_database(root,**options)
    with native_pg.connect() as c:
        assert c.execute('SELECT oid,rolpassword FROM pg_authid WHERE rolname=%s',(options['role'],)).fetchone()==original
        assert c.execute('SELECT datdba FROM pg_database WHERE datname=%s',(options['database'],)).fetchone()==owner
    assert not (root/'.env').exists()


def test_wrong_admin_password_is_redacted_and_does_not_provision(target,native_pg,capsys):
    pg=helper();root,options=target;options['admin_password']='incorrect-private-password'
    with pytest.raises(pg.NativeSetupError) as failure:pg.prepare_database(root,**options)
    assert options['admin_password'] not in str(failure.value)+capsys.readouterr().out
    with native_pg.connect() as c:assert c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(options['role'],)).fetchone() is None
    assert not (root/'.env').exists()


def test_unavailable_local_postgres_fails_without_fallback(target):
    pg=helper();root,options=target
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));options['port']=probe.getsockname()[1]
    with pytest.raises(pg.NativeSetupError,match='PostgreSQL'):pg.prepare_database(root,**options)
    assert not (root/'.env').exists()


def test_acl_failure_precedes_secret_persistence_and_retry_can_succeed(target,native_pg,monkeypatch):
    pg=helper();root,options=target
    def denied(*args,**kwargs):raise PermissionError('Synthetic ACL failure')
    with monkeypatch.context() as fault:
        fault.setattr(pg,'protect_path',denied)
        with pytest.raises((PermissionError,pg.NativeSetupError)):pg.prepare_database(root,**options)
    assert not list((root/'.local/native-postgres').iterdir())
    with native_pg.connect() as c:assert c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(options['role'],)).fetchone() is None
    assert pg.prepare_database(root,**options)['database_url']


def test_failed_env_publication_preserves_staged_credentials_and_retries(target,monkeypatch):
    pg=helper();root,options=target;setup=windows_finish(monkeypatch,root,options)
    def disk_full(*args,**kwargs):raise pg.NativeSetupError('Synthetic full disk during publication')
    with monkeypatch.context() as fault:
        fault.setattr(pg,'publish_config',disk_full)
        with pytest.raises(pg.NativeSetupError):setup.native_finish()
    assert not (root/'.env').exists()
    pending=root/'.local/native-postgres/pending.json';original=pending.read_bytes()
    assert setup.native_finish()==0 and pending.read_bytes()==original
    assert (root/'.env').is_file()


def test_schema_failure_keeps_staged_credentials_for_safe_retry(target,monkeypatch):
    import app.db
    pg=helper();root,options=target;setup=windows_finish(monkeypatch,root,options)
    def unavailable(*args):raise app.db.DatabaseUnavailable('Synthetic schema failure')
    with monkeypatch.context() as fault:
        fault.setattr(app.db,'initialize_schema',unavailable)
        with pytest.raises(app.db.DatabaseUnavailable):setup.native_finish()
    assert not (root/'.env').exists()
    pending=root/'.local/native-postgres/pending.json';before=pending.read_bytes()
    assert setup.native_finish()==0 and pending.read_bytes()==before


@pytest.mark.parametrize('url',[
 'postgresql+psycopg://u:p@remote.example/db',
 'postgresql+psycopg://u:p@127.0.0.1/db?host=remote.example',
 'postgresql+psycopg://u:p@127.0.0.1/db?service=other',
])
def test_existing_effective_remote_target_is_refused_before_connect(monkeypatch,url):
    pg=helper()
    def unexpected(*args,**kwargs):pytest.fail('Unsafe target reached a connection')
    monkeypatch.setattr(pg.psycopg,'connect',unexpected)
    with pytest.raises(pg.NativeSetupError):pg.validate_database(url)


def test_private_pending_directory_never_claims_foreign_files(target):
    pg=helper();root,options=target;state=root/'.local/native-postgres';state.mkdir(parents=True)
    (state/'other-user-file').write_bytes(b'KEEP')
    with pytest.raises(pg.NativeSetupError):pg.prepare_database(root,**options)
    assert (state/'other-user-file').read_bytes()==b'KEEP' and len(list(state.iterdir()))==1


def test_pending_directory_symlink_is_rejected_without_touching_target(target,tmp_path):
    pg=helper();root,options=target;(root/'.local').mkdir(parents=True)
    other=tmp_path/'unrelated';other.mkdir();(root/'.local/native-postgres').symlink_to(other,target_is_directory=True)
    with pytest.raises((pg.NativeSetupError,RuntimeError,ValueError)):pg.prepare_database(root,**options)
    assert not list(other.iterdir())


def test_atomic_config_publication_preserves_existing_user_configuration(tmp_path):
    pg=helper();root=tmp_path/'root';root.mkdir();(root/'.env').write_bytes(b'EXISTING=KEEP\n')
    with pytest.raises(pg.NativeSetupError):pg.publish_config(root,'NEW=FORBIDDEN\n')
    assert (root/'.env').read_bytes()==b'EXISTING=KEEP\n'


def test_recurring_check_with_missing_config_never_requests_provisioning(tmp_path,monkeypatch):
    setup=importlib.import_module('scripts.lecturer_setup');pg=helper()
    monkeypatch.setattr(setup,'ROOT',tmp_path)
    monkeypatch.setattr(setup,'platform',SimpleNamespace(system=lambda:'Windows'))
    def unexpected(*args,**kwargs):pytest.fail('Recurring check attempted privileged provisioning')
    monkeypatch.setattr(pg,'prepare_database',unexpected)
    with pytest.raises((pg.NativeSetupError,ValueError,RuntimeError)):setup.native_finish(check_only=True)


def test_actual_runtime_export_contains_native_launchers_helper_and_pinned_assets(tmp_path):
    from scripts.build_lecturer_release import build_release
    from scripts.lecturer_assets import PINNED
    mapping=json.loads((ROOT/'packaging/runtime_allowlist.json').read_text())
    mapping.update(json.loads((ROOT/'packaging/phase4_3_allowlist.json').read_text()))
    build_release(ROOT,tmp_path/'release',mapping,include_audit=False)
    with zipfile.ZipFile(tmp_path/'release/mahjong-strategy-ai-lecturer-portable.zip') as archive:
        names=set(archive.namelist());prefix='mahjong-strategy-ai/'
        assert {prefix+n for n in ('setup-windows-native.cmd','run-windows-native.cmd','scripts/native_postgres.py')}.issubset(names)
        for path,sha in PINNED.items():assert hashlib.sha256(archive.read(prefix+path)).hexdigest()==sha
        assert not any('/.local/' in n or '/.venv/' in n or n.endswith('/.env') or n.endswith('.sql') for n in names)


def interrupted_connection(pg,monkeypatch,fragment):
    connect=pg._connect
    class Interrupted:
        def __init__(self,connection):self.connection=connection
        def __enter__(self):self.connection.__enter__();return self
        def __exit__(self,*args):return self.connection.__exit__(*args)
        def transaction(self):return self.connection.transaction()
        def execute(self,statement,*args,**kwargs):
            text=statement.as_string(self.connection) if isinstance(statement,sql.Composable) else statement
            if text.startswith(fragment):raise psycopg.OperationalError('Synthetic provisioning interruption')
            return self.connection.execute(statement,*args,**kwargs)
    monkeypatch.setattr(pg,'_connect',lambda **kwargs:Interrupted(connect(**kwargs)))


@pytest.mark.parametrize('fragment,recoverable',[('CREATE DATABASE',True),('COMMENT ON DATABASE',False)])
def test_interrupted_catalog_creation_reuses_password_or_fails_closed(target,native_pg,monkeypatch,fragment,recoverable):
    pg=helper();root,options=target
    with monkeypatch.context() as fault:
        interrupted_connection(pg,fault,fragment)
        with pytest.raises(pg.NativeSetupError):pg.prepare_database(root,**options)
    pending=root/'.local/native-postgres/pending.json';before=pending.read_bytes()
    with native_pg.connect() as c:
        identity=c.execute('SELECT oid,rolpassword FROM pg_authid WHERE rolname=%s',(options['role'],)).fetchone()
        assert identity
    if recoverable:assert pg.prepare_database(root,**options)['database_url']
    else:
        with pytest.raises(pg.NativeSetupError,match='ambiguous'):pg.prepare_database(root,**options)
    assert pending.read_bytes()==before
    with native_pg.connect() as c:assert c.execute('SELECT oid,rolpassword FROM pg_authid WHERE rolname=%s',(options['role'],)).fetchone()==identity


def test_pending_role_with_added_membership_is_rejected_before_database_creation(target,native_pg,monkeypatch):
    pg=helper();root,options=target
    with monkeypatch.context() as fault:
        interrupted_connection(pg,fault,'CREATE DATABASE')
        with pytest.raises(pg.NativeSetupError):pg.prepare_database(root,**options)
    with native_pg.connect() as c:c.execute(sql.SQL('GRANT pg_read_all_data TO {}').format(sql.Identifier(options['role'])))
    with pytest.raises(pg.NativeSetupError):pg.prepare_database(root,**options)
    with native_pg.connect() as c:assert c.execute('SELECT 1 FROM pg_database WHERE datname=%s',(options['database'],)).fetchone() is None


def test_initial_pending_file_flush_failure_leaves_no_orphan_and_can_retry(target,native_pg,monkeypatch):
    pg=helper();root,options=target
    def disk_full(*args):raise OSError('Synthetic fsync failure')
    with monkeypatch.context() as fault:
        fault.setattr(pg.os,'fsync',disk_full)
        with pytest.raises(OSError):pg.prepare_database(root,**options)
    assert not list((root/'.local/native-postgres').iterdir())
    with native_pg.connect() as c:assert c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(options['role'],)).fetchone() is None
    assert pg.prepare_database(root,**options)['database_url']


def test_existing_private_config_without_setup_tags_requires_no_admin(target,native_pg,monkeypatch):
    from scripts.lecturer_setup import write_native_config
    root,options=target;root.mkdir(parents=True);password=secrets.token_urlsafe(48)
    with native_pg.connect() as c:
        c.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(options['role']),sql.Literal(password)))
        c.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(options['database']),sql.Identifier(options['role'])))
    url=f'postgresql+psycopg://{options["role"]}:{password}@127.0.0.1:{options["port"]}/{options["database"]}'
    write_native_config(root,url);before=(root/'.env').read_bytes();setup=windows_finish(monkeypatch,root,options)
    def unexpected(*args,**kwargs):pytest.fail('Explicit valid existing config prompted for admin')
    monkeypatch.setattr(helper(),'prepare_database',unexpected)
    assert setup.native_finish()==0 and (root/'.env').read_bytes()==before


def test_native_dependencies_are_checked_but_not_reinstalled_when_marker_matches(tmp_path,monkeypatch):
    setup=importlib.import_module('scripts.lecturer_setup');project_assets(tmp_path)
    shutil.copyfile(ROOT/'requirements-runtime.txt',tmp_path/'requirements-runtime.txt')
    executable=tmp_path/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    executable.parent.mkdir(parents=True);executable.touch()
    (tmp_path/'.local').mkdir();marker=tmp_path/'.local/native-requirements.sha256'
    marker.write_text(hashlib.sha256((tmp_path/'requirements-runtime.txt').read_bytes()).hexdigest())
    monkeypatch.setattr(setup,'ROOT',tmp_path);commands=[]
    monkeypatch.setattr(setup.subprocess,'run',lambda command,**kwargs:commands.append(command))
    monkeypatch.setattr(setup.subprocess,'call',lambda command,**kwargs:0)
    assert setup.native_setup()==0
    assert not any('install' in command for command in commands)
    assert any(command[1:]==['-m','pip','check'] for command in commands)
    assert all(command[0]==str(executable) for command in commands)


def test_32_bit_python_is_rejected_before_installation(monkeypatch):
    setup=importlib.import_module('scripts.lecturer_setup')
    monkeypatch.setattr(setup.sys,'maxsize',2**31-1)
    def unexpected(*args):pytest.fail('32-bit Python reached installation preparation')
    monkeypatch.setattr(setup,'verify_assets',unexpected)
    with pytest.raises(ValueError,match='64-bit'):setup.native_setup()


@pytest.mark.parametrize('variable',['PGHOSTADDR','PGSERVICE','PGSERVICEFILE','MAHJONG_DATABASE_URL','MAHJONG_SESSION_SECRET'])
def test_native_environment_overrides_are_rejected_before_any_prompt_or_connection(tmp_path,monkeypatch,variable):
    pg=helper();root=tmp_path/'not-created'
    monkeypatch.setenv(variable,'untrusted-process-override')
    def unexpected(*args,**kwargs):pytest.fail('Process override reached a prompt or connection')
    monkeypatch.setattr('builtins.input',unexpected)
    monkeypatch.setattr(pg.getpass,'getpass',unexpected)
    monkeypatch.setattr(pg.psycopg,'connect',unexpected)
    with pytest.raises(pg.NativeSetupError,match='override|PGHOSTADDR|PGSERVICE|MAHJONG_'):pg.prepare_database(root)
    assert not root.exists()


def test_existing_database_validation_refuses_inherited_libpq_redirect(monkeypatch):
    pg=helper();monkeypatch.setenv('PGHOSTADDR','127.0.0.2')
    def unexpected(*args,**kwargs):pytest.fail('Inherited hostaddr reached libpq')
    monkeypatch.setattr(pg.psycopg,'connect',unexpected)
    with pytest.raises(pg.NativeSetupError):pg.validate_database('postgresql+psycopg://synthetic:synthetic@127.0.0.1/owned')


def test_windows_acl_success_without_verified_private_dacl_is_refused(tmp_path,monkeypatch):
    pg=helper();path=tmp_path/'private-empty-file';path.touch()
    monkeypatch.setattr(pg,'os',SimpleNamespace(name='nt',environ={'SystemRoot':'C:\\Windows'}))
    monkeypatch.setattr(pg.subprocess,'check_output',lambda *args,**kwargs:'"user","S-1-5-21-123"')
    monkeypatch.setattr(pg.subprocess,'run',lambda *args,**kwargs:subprocess.CompletedProcess([],0,stdout='',stderr=''))
    with pytest.raises(pg.NativeSetupError,match='ACL|verification'):pg.protect_path(path)
    assert path.read_bytes()==b''


def test_recreated_venv_installs_dependencies_even_with_matching_external_marker(tmp_path,monkeypatch):
    setup=importlib.import_module('scripts.lecturer_setup');project_assets(tmp_path)
    shutil.copyfile(ROOT/'requirements-runtime.txt',tmp_path/'requirements-runtime.txt')
    (tmp_path/'.local').mkdir();marker=tmp_path/'.local/native-requirements.sha256'
    marker.write_text(hashlib.sha256((tmp_path/'requirements-runtime.txt').read_bytes()).hexdigest())
    def create(builder,path):
        executable=path/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        executable.parent.mkdir(parents=True);executable.touch()
    monkeypatch.setattr(setup.venv.EnvBuilder,'create',create)
    monkeypatch.setattr(setup,'ROOT',tmp_path);commands=[]
    monkeypatch.setattr(setup.subprocess,'run',lambda command,**kwargs:commands.append(command))
    monkeypatch.setattr(setup.subprocess,'call',lambda *args,**kwargs:0)
    assert setup.native_setup()==0
    assert any(command[1:4]==['-m','pip','install'] for command in commands)
