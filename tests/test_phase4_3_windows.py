"""Cross-platform unit evidence only; these do not certify a Windows executable."""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import zipfile

import pytest


def launcher():
    assert importlib.util.find_spec('scripts.windows_launcher'),'Missing offline launcher implementation'
    return importlib.import_module('scripts.windows_launcher')


def test_first_run_uses_owned_unicode_path_and_preserves_secrets_and_ports(tmp_path):
    module=launcher();root=tmp_path/'Mahjong 學生 space'
    first=module.prepare_state(root);before=(root/'state.json').read_bytes()
    second=module.prepare_state(root)
    assert first==second and (root/'state.json').read_bytes()==before
    assert first['db_port']!=first['web_port']
    assert len(first['session_secret'])>=40 and first['session_secret']!=first['app_password']


def test_first_run_never_claims_a_nonempty_foreign_directory(tmp_path):
    root=tmp_path/'foreign';root.mkdir();(root/'history.txt').write_text('KEEP')
    module=launcher()
    with pytest.raises(module.LauncherError):module.prepare_state(root)
    assert (root/'history.txt').read_text()=='KEEP' and not (root/'state.json').exists()


def test_owned_profile_missing_private_config_refuses_without_rotating_or_touching_data(tmp_path):
    module=launcher();root=tmp_path/'owned';module.prepare_state(root)
    data=root/'data';data.mkdir();(data/'PG_VERSION').write_text('14')
    (data/'history-sentinel').write_bytes(b'KEEP EXISTING DATABASE')
    (root/'state.json').unlink()
    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(module.LauncherError,match='restore the original private config'):
        module.prepare_state(root)
    assert not (root/'state.json').exists()
    assert {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}==before


def test_profile_symlink_is_rejected_without_touching_target(tmp_path):
    target=tmp_path/'original';target.mkdir();root=tmp_path/'alias';root.symlink_to(target,target_is_directory=True)
    module=launcher()
    with pytest.raises(module.LauncherError):module.prepare_state(root)
    assert not list(target.iterdir())


def test_a_held_instance_lock_blocks_duplicate_controller(tmp_path):
    module=launcher();root=tmp_path/'state';module.prepare_state(root)
    with module.SingleInstance(root/'instance.lock'):
        with pytest.raises(module.AlreadyRunning):
            with module.SingleInstance(root/'instance.lock'):pass
    with module.SingleInstance(root/'instance.lock'):pass


def test_port_collision_does_not_modify_or_kill_the_other_listener():
    module=launcher()
    with socket.socket() as held:
        held.bind(('127.0.0.1',0));held.listen()
        with pytest.raises(module.LauncherError):module.require_free_port(held.getsockname()[1])
        assert held.getsockname()[1]>0


class Process:
    def __init__(self,code=None):self.code=code
    def poll(self):return self.code


def test_browser_readiness_requires_model_and_database_and_owned_port():
    module=launcher();responses=iter([{'status':'ready','model':'loading','database':'ready'},
                                    {'status':'ready','model':'ready','database':'ready'}]);times=[0.]
    result=module.wait_ready('http://127.0.0.1:18001/health/ready',Process(),timeout=1,
                            fetch=lambda _:next(responses),owns_port=lambda:True,
                            clock=lambda:times[0],sleep=lambda x:times.__setitem__(0,times[0]+x))
    assert result and times[0]>0


@pytest.mark.parametrize('exited,owns',[(None,False),(1,True)])
def test_readiness_fails_bounded_when_child_exits_or_other_process_owns_port(exited,owns):
    module=launcher();times=[0.]
    with pytest.raises(module.LauncherError):
        module.wait_ready('http://127.0.0.1:18001/health/ready',Process(exited),timeout=.2,
                          fetch=lambda _:{'status':'ready','model':'ready','database':'ready'},owns_port=lambda:owns,
                          clock=lambda:times[0],sleep=lambda x:times.__setitem__(0,times[0]+x))


def test_database_provision_does_not_recreate_existing_owned_database():
    module=launcher();statements=[]
    def query(sql):
        statements.append(sql)
        return 'f|f|f' if 'pg_roles' in sql else 'mahjong_app'
    module.ensure_database(query,'syntheticpassword')
    assert all(s.startswith('SELECT') for s in statements)


def test_database_provision_rejects_wrong_owner_without_destructive_sql():
    module=launcher();statements=[]
    def query(sql):
        statements.append(sql);return 'f|f|f' if 'pg_roles' in sql else 'other_owner'
    with pytest.raises(module.LauncherError):module.ensure_database(query,'syntheticpassword')
    assert not any(s.startswith(('DROP','ALTER','CREATE')) for s in statements)


def test_private_diagnostics_redact_every_generated_credential():
    module=launcher();secrets=['synthetic_session','synthetic_admin','synthetic_app']
    message=module.redact(' '.join(secrets),secrets)
    assert not any(s in message for s in secrets)


def test_cleanup_stops_only_the_process_object_created_by_launcher(tmp_path):
    module=launcher();marker=tmp_path/'stopped'
    code="import signal,time;from pathlib import Path;signal.signal(signal.SIGINT,lambda *_:(Path("+repr(str(marker))+").write_text('stopped'),exit(0)));print('ready',flush=True);time.sleep(30)"
    child=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,text=True)
    assert child.stdout.readline().strip()=='ready'
    module.stop_owned(child)
    assert child.poll()==0 and marker.read_text()=='stopped'


def test_runtime_manifest_rejects_changed_executable_and_traversal(tmp_path):
    module=launcher();(tmp_path/'runtime.exe').write_bytes(b'synthetic executable, not run')
    digest=hashlib.sha256((tmp_path/'runtime.exe').read_bytes()).hexdigest()
    manifest={'files':{'runtime.exe':digest}}
    (tmp_path/'RUNTIME_MANIFEST.json').write_text(json.dumps(manifest));module.verify_package(tmp_path)
    (tmp_path/'runtime.exe').write_bytes(b'changed')
    with pytest.raises(module.LauncherError):module.verify_package(tmp_path)
    (tmp_path/'RUNTIME_MANIFEST.json').write_text(json.dumps({'files':{'../outside.exe':digest}}))
    with pytest.raises(module.LauncherError):module.verify_package(tmp_path)


def test_pg_provenance_requires_trusted_origin_hash_and_explicit_license_review(tmp_path):
    assert importlib.util.find_spec('scripts.build_windows_package'),'Missing native Windows build workflow'
    builder=importlib.import_module('scripts.build_windows_package')
    path=tmp_path/'pg.zip';path.write_bytes(b'synthetic archive, not executed')
    metadata={'download_url':'https://untrusted.example/pg.zip','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'license_reviewed':True,'version':'14.19'}
    with pytest.raises(ValueError):builder.verify_pg_input(path,metadata)
    metadata['download_url']='https://get.enterprisedb.com/postgresql/pg.zip';metadata['license_reviewed']=False
    with pytest.raises(ValueError):builder.verify_pg_input(path,metadata)


def test_private_profile_is_protected_before_any_secret_file_is_written(tmp_path):
    module=launcher();root=tmp_path/'profile';seen=[]
    def protect(path):
        assert path==root and not (root/'state.json').exists();seen.append(path)
    module.prepare_state(root,protect=protect)
    assert seen==[root]


def test_pg_archive_never_extracts_traversal_or_symlink_members(tmp_path):
    assert importlib.util.find_spec('scripts.build_windows_package'),'Missing Windows packaging safety checks'
    builder=importlib.import_module('scripts.build_windows_package');archive=tmp_path/'pg.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside.exe',b'bad')
    with pytest.raises(ValueError):builder.extract_postgres(archive,tmp_path/'output')
    assert not (tmp_path/'outside.exe').exists()


def test_new_owned_postgres_is_stoppable_even_if_post_start_authentication_fails(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'state';config=module.prepare_state(root)
    (root/'data').mkdir();(root/'data/PG_VERSION').write_text('14\n')
    pg=module.PostgresRuntime(tmp_path/'package',root,config);commands=[];running=[False]
    def command(name,*args,**kwargs):
        commands.append((name,args))
        if name=='psql':raise module.LauncherError('Synthetic authentication failure')
        if args[-1]=='status':return subprocess.CompletedProcess([],0 if running[0] else 3,stdout='',stderr='')
        if args[-1]=='start':running[0]=True
        if args[-1]=='stop':running[0]=False
        return subprocess.CompletedProcess([],0,stdout='',stderr='')
    monkeypatch.setattr(pg,'command',command)
    with pytest.raises(module.LauncherError):pg.start()
    pg.stop()
    assert not running[0]


def test_pg_provenance_does_not_copy_unknown_private_metadata_into_build_report(tmp_path):
    builder=importlib.import_module('scripts.build_windows_package');path=tmp_path/'pg.zip';path.write_bytes(b'synthetic')
    metadata={'download_url':'https://get.enterprisedb.com/postgresql/postgresql-14.19-1-windows-x64-binaries.zip',
              'version':'14.19','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'license_reviewed':True,'password':'synthetic_private'}
    verified=builder.verify_pg_input(path,metadata)
    assert 'password' not in verified


def test_first_run_acl_failure_leaves_no_marker_or_private_config(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'new profile'
    def unexpected_secret(*args):pytest.fail('Credentials generated before protection succeeded')
    def denied(path):raise PermissionError('Simulated ACL failure')
    monkeypatch.setattr(module.secrets,'token_urlsafe',unexpected_secret)
    with pytest.raises(PermissionError,match='ACL failure'):module.prepare_state(root,protect=denied)
    assert root.is_dir() and not list(root.iterdir())


def test_first_run_retry_after_acl_failure_succeeds_without_manual_cleanup(tmp_path):
    module=launcher();root=tmp_path/'retry 學生'
    def denied(path):raise PermissionError('Simulated ACL failure')
    with pytest.raises(PermissionError):module.prepare_state(root,protect=denied)
    def protect(path):assert not list(path.iterdir())
    config=module.prepare_state(root,protect=protect)
    assert json.loads((root/'owner.json').read_text())=={'application':module.APP_ID,'root':str(root.resolve())}
    assert json.loads((root/'state.json').read_text())==config
    assert config['db_port']!=config['web_port']
    assert all(len(config[name])>=40 for name in ('session_secret','admin_password','app_password'))


@pytest.mark.parametrize('filename',['owner.json','state.json'])
def test_partial_initial_json_write_is_rolled_back_and_can_retry(tmp_path,monkeypatch,filename):
    module=launcher();root=tmp_path/'new';dump=module.json.dump
    def partial(value,stream,**kwargs):
        selected='owner.json' if 'application' in value else 'state.json'
        if selected==filename:
            stream.write('{');raise OSError('Simulated partial JSON write')
        return dump(value,stream,**kwargs)
    with monkeypatch.context() as fault:
        fault.setattr(module.json,'dump',partial)
        with pytest.raises(OSError,match='partial JSON'):module.prepare_state(root)
    assert not list(root.iterdir())
    config=module.prepare_state(root)
    assert json.loads((root/'state.json').read_text())==config


def test_first_run_secret_generation_failure_leaves_retryable_empty_profile(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'new'
    def unavailable(*args):raise RuntimeError('Simulated entropy failure')
    with monkeypatch.context() as fault:
        fault.setattr(module.secrets,'token_urlsafe',unavailable)
        with pytest.raises(RuntimeError,match='entropy failure'):module.prepare_state(root)
    assert not list(root.iterdir())
    assert module.prepare_state(root)['app_id']==module.APP_ID


def test_first_run_generated_config_validation_failure_does_not_persist_state(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'new'
    with monkeypatch.context() as fault:
        fault.setattr(module.secrets,'token_urlsafe',lambda *_:'short')
        with pytest.raises(module.LauncherError,match='Invalid stored secret'):module.prepare_state(root)
    assert not list(root.iterdir())
    assert len(module.prepare_state(root)['session_secret'])>=40


def test_existing_valid_profile_reuses_bytes_without_writing_private_files(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'existing';original=module.prepare_state(root)
    before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in root.iterdir()}
    def unexpected(*args,**kwargs):pytest.fail('Existing private state must not be rewritten or rotated')
    monkeypatch.setattr(module,'write_private',unexpected)
    monkeypatch.setattr(module.secrets,'token_urlsafe',unexpected)
    assert module.prepare_state(root,protect=lambda _:None)==original
    assert {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in root.iterdir()}==before


@pytest.mark.parametrize('damage',['foreign_owner','incompatible_keys','invalid_port','invalid_secret','malformed_json'])
def test_existing_foreign_or_invalid_private_state_is_never_recovered(tmp_path,monkeypatch,damage):
    module=launcher();root=tmp_path/'existing';module.prepare_state(root)
    path=root/('owner.json' if damage=='foreign_owner' else 'state.json')
    value=json.loads(path.read_text())
    if damage=='foreign_owner':value['application']='another-app'
    elif damage=='incompatible_keys':value['unknown_format']=1
    elif damage=='invalid_port':value['db_port']=0
    elif damage=='invalid_secret':value['app_password']='short'
    path.write_text('{' if damage=='malformed_json' else json.dumps(value))
    before={p.name:p.read_bytes() for p in root.iterdir()}
    def unexpected(*args,**kwargs):pytest.fail('Existing invalid state must fail closed')
    monkeypatch.setattr(module,'write_private',unexpected)
    monkeypatch.setattr(module.secrets,'token_urlsafe',unexpected)
    with pytest.raises((module.LauncherError,ValueError)):module.prepare_state(root)
    assert {p.name:p.read_bytes() for p in root.iterdir()}==before


def test_junction_profile_is_refused_without_claiming_its_contents(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'junction';root.mkdir();(root/'sentinel').write_bytes(b'KEEP')
    monkeypatch.setattr(Path,'is_junction',lambda path:path==root,raising=False)
    with pytest.raises(module.LauncherError,match='Symlink/junction'):module.prepare_state(root)
    assert list(root.iterdir())==[root/'sentinel'] and (root/'sentinel').read_bytes()==b'KEEP'


@pytest.mark.parametrize('filename',['owner.json','state.json'])
def test_first_run_exclusive_create_collision_never_deletes_the_other_file(tmp_path,monkeypatch,filename):
    module=launcher();root=tmp_path/'new';open_file=module.os.open
    def collision(path,flags,*args,**kwargs):
        if Path(path)==root/filename and flags&module.os.O_EXCL:
            Path(path).write_bytes(b'OTHER WRITER')
        return open_file(path,flags,*args,**kwargs)
    monkeypatch.setattr(module.os,'open',collision)
    with pytest.raises((OSError,module.LauncherError)):module.prepare_state(root)
    assert (root/filename).read_bytes()==b'OTHER WRITER'


def test_first_run_failure_with_unexpected_data_fails_closed_without_removing_any_files(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'new';dump=module.json.dump
    def partial(value,stream,**kwargs):
        if 'app_id' in value:
            (root/'data').mkdir();(root/'data/PG_VERSION').write_bytes(b'14\n')
            stream.write('{');raise OSError('Simulated ambiguous first-run failure')
        return dump(value,stream,**kwargs)
    with monkeypatch.context() as fault:
        fault.setattr(module.json,'dump',partial)
        with pytest.raises((OSError,module.LauncherError)):module.prepare_state(root)
    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert before['data/PG_VERSION']==b'14\n' and 'owner.json' in before and 'state.json' in before
    with pytest.raises((module.LauncherError,ValueError)):module.prepare_state(root)
    assert {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}==before


def test_first_run_rollback_preserves_a_replaced_private_file(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'new';write=module.write_private
    replacement=tmp_path/'replacement';replacement.write_bytes(b'OTHER WRITER')
    def replaced(path,value,**kwargs):
        write(path,value,**kwargs)
        if path.name=='state.json':
            replacement.replace(path);raise OSError('Simulated replaced state failure')
    with monkeypatch.context() as fault:
        fault.setattr(module,'write_private',replaced)
        with pytest.raises((OSError,module.LauncherError)):module.prepare_state(root)
    assert (root/'state.json').read_bytes()==b'OTHER WRITER' and (root/'owner.json').is_file()
    with pytest.raises((module.LauncherError,ValueError)):module.prepare_state(root)


def test_first_run_rollback_rechecks_a_file_replaced_after_directory_snapshot(tmp_path,monkeypatch):
    module=launcher();root=tmp_path/'new';dump=module.json.dump;no_links=module.no_links
    replacement=tmp_path/'replacement';replacement.write_bytes(b'OTHER WRITER')
    fault={'failed':False,'replaced':False}
    def partial(value,stream,**kwargs):
        if 'app_id' in value:
            stream.write('{');fault['failed']=True;raise OSError('Simulated partial state write')
        return dump(value,stream,**kwargs)
    def late_replacement(path):
        if fault['failed'] and path==root/'state.json' and not fault['replaced']:
            replacement.replace(path);fault['replaced']=True
        return no_links(path)
    with monkeypatch.context() as injected:
        injected.setattr(module.json,'dump',partial)
        injected.setattr(module,'no_links',late_replacement)
        with pytest.raises((OSError,module.LauncherError)):module.prepare_state(root)
    assert fault['replaced']
    assert (root/'state.json').is_file() and (root/'state.json').read_bytes()==b'OTHER WRITER'
    assert (root/'owner.json').is_file()
    with pytest.raises((module.LauncherError,ValueError)):module.prepare_state(root)
