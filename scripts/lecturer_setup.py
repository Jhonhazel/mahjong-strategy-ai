"""Explicit, idempotent local setup; no engine/model/security fallbacks."""
import argparse
import asyncio
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import time
from urllib.parse import parse_qs,quote,urlsplit
import venv

from scripts.lecturer_assets import safe_path,verify_assets

ROOT=Path(__file__).resolve().parents[1]
SECRET_NAMES=('db_admin_password','db_password','session_secret')


def private_write(path,text,mode=0o600):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode),'w',encoding='utf-8') as stream:stream.write(text)
    path.chmod(mode)


def write_native_config(root,database_url,*,session_secret=None):
    root=Path(root).resolve();path=safe_path(root,'.env')
    if any(ord(c)<32 for c in database_url):raise ValueError('Database URL must be a single line')
    parsed=urlsplit(database_url)
    query=parse_qs(parsed.query,keep_blank_values=True)
    if set(query)-{'host','port','sslmode'} or any(len(values)!=1 for values in query.values()):
        raise ValueError('Connection override fields are not allowed in local setup')
    socket=query.get('host',[''])[0]
    local_socket=socket==str(root/'.local/phase3-postgres/socket')
    if ('host' in query and (not local_socket or parsed.hostname is not None)) or ('port' in query and not local_socket):
        raise ValueError('Query parameters must not override the local database host')
    if parsed.port is not None and not 1<=parsed.port<=65535:raise ValueError('Invalid database port')
    if 'port' in query and not 1<=int(query['port'][0])<=65535:raise ValueError('Invalid socket database port')
    if parsed.scheme not in ('postgresql','postgresql+psycopg') or not parsed.path.strip('/') or (parsed.hostname not in ('localhost','127.0.0.1','::1') and not local_socket):
        raise ValueError('Use an explicitly provisioned local PostgreSQL database')
    if path.exists():return path
    secret=session_secret or secrets.token_urlsafe(48)
    text='MAHJONG_DATABASE_URL='+json.dumps(database_url)+'\nMAHJONG_SESSION_SECRET='+json.dumps(secret)+'\nMAHJONG_ENVIRONMENT=local\nMAHJONG_WORKERS=1\n'
    if platform.system()=='Windows':
        from scripts.native_postgres import publish_config
        publish_config(root,text)
    else:private_write(path,text)
    return path


def prepare_compose_secrets(directory):
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('Secret directory cannot be a symlink')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700);directory.chmod(0o700)
    paths=[safe_path(directory,name) for name in SECRET_NAMES]
    existing=[p.exists() for p in paths]
    if any(existing) and not all(existing):raise ValueError('Partial secret set: restore original files, do not rotate database credentials')
    for path in paths:
        if path.exists():
            value=path.read_text().strip()
            if len(value)<40 or len(set(value))<8:raise ValueError('Invalid stored local secret')
        else:
            # Host parent0700 protects files;0444 permits the granted non-root container to read its mounted secret.
            private_write(path,secrets.token_urlsafe(48)+'\n',0o444)


async def application_probe(config):
    from app.main import create_app
    app=create_app(config)
    async with app.router.lifespan_context(app):
        if app.state.resources is None:raise RuntimeError('Application resources did not initialize')


def native_finish(run=False,*,check_only=False):
    from app.settings import Settings
    from scripts.phase3_db import LocalPostgres
    pending=None;windows=platform.system()=='Windows'
    pg=None if windows else LocalPostgres()
    if windows:
        from scripts import native_postgres
        native_postgres.ensure_local_environment()
        native_postgres.no_links(ROOT/'.env')
        if (run or check_only) and not (ROOT/'.env').is_file():
            raise native_postgres.NativeSetupError('Run setup-windows-native.cmd first; recurring startup never provisions PostgreSQL')
    if not (ROOT/'.env').exists():
        url=os.environ.get('MAHJONG_SETUP_DATABASE_URL')
        if windows:
            pending=({'database_url':url,'session_secret':secrets.token_urlsafe(48)} if url else native_postgres.prepare_database(ROOT))
        elif not url and platform.system()=='Darwin':
            pg.initialize();pg.start();url=pg.database_url('dev')
        if not windows:
            if not url:url=getpass.getpass('Local PostgreSQL URL (hidden; create an empty owned DB first): ')
            write_native_config(ROOT,url)
    config=Settings(_env_file=None,**pending) if pending else Settings(_env_file=ROOT/'.env')
    if windows:
        native_postgres.validate_database(config.database_url.get_secret_value())
        if not pending:native_postgres.protect_path(ROOT/'.env')
    else:
        write_native_config(ROOT,config.database_url.get_secret_value())
        if pg.marker.is_file() and config.database_url.get_secret_value()==pg.database_url('dev'):pg.start()
    verify_assets(ROOT)
    if check_only:
        asyncio.run(application_probe(config));print('Native model/database readiness OK; no provisioning performed');return 0
    if run:
        return subprocess.call([sys.executable,'-m','scripts.run_backend'],cwd=ROOT)
    from app.db import create_db_engine,initialize_schema
    engine=create_db_engine(config)
    try:initialize_schema(engine)
    finally:engine.dispose()
    asyncio.run(application_probe(config))
    if pending:write_native_config(ROOT,config.database_url.get_secret_value(),session_secret=config.session_secret.get_secret_value())
    print('Setup native PASS: real PostgreSQL schema and v3 lifespan ready. Run the launcher; open http://127.0.0.1:8000/')
    return 0


def native_setup():
    windows=platform.system()=='Windows'
    if (sys.implementation.name!='cpython' or sys.version_info[:2]!=(3,12) or sys.maxsize<=2**32
            or platform.machine().lower() not in (('amd64','x86_64') if windows else ('arm64','aarch64','amd64','x86_64'))):
        raise ValueError('Use 64-bit CPython3.12; Windows native remains unverified')
    verify_assets(ROOT)
    directory=safe_path(ROOT,'.venv')
    created=not directory.exists()
    if created:venv.EnvBuilder(with_pip=True).create(directory)
    executable=directory/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    requirements=ROOT/'requirements-runtime.txt'
    fingerprint=hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker=ROOT/'.local/native-requirements.sha256';marker.parent.mkdir(exist_ok=True,mode=0o700)
    install=created or not marker.exists() or marker.read_text()!=fingerprint
    if install:
        try:
            if windows:subprocess.run([str(executable),'-m','pip','install','torch==2.15.0','--index-url','https://download.pytorch.org/whl/cpu','--no-deps'],check=True,cwd=ROOT)
            subprocess.run([str(executable),'-m','pip','install','-r',str(requirements)],check=True,cwd=ROOT)
        except subprocess.CalledProcessError:
            raise RuntimeError('Runtime install failed. If PyMahjongGB compilation failed, install Microsoft C++ Build Tools with C++/Windows SDK and retry') from None
    subprocess.run([str(executable),'-m','pip','check'],check=True,cwd=ROOT)
    subprocess.run([str(executable),'-c',"import sys,struct,torch,MahjongGB,fastapi,psycopg; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8; assert torch.__version__.split('+')[0]=='2.15.0'; assert sys.platform!='win32' or torch.version.cuda is None; torch.zeros(1,device='cpu')"],check=True,cwd=ROOT)
    if install:marker.write_text(fingerprint)
    return subprocess.call([str(executable),'-m','scripts.lecturer_setup','--finish'],cwd=ROOT)


def container_start():
    from app.settings import Settings
    from app.db import create_db_engine,initialize_schema
    password=Path('/run/secrets/db_password').read_text().strip()
    secret=Path('/run/secrets/session_secret').read_text().strip()
    os.environ['MAHJONG_DATABASE_URL']='postgresql+psycopg://mahjong_app:'+quote(password,safe='')+'@db/mahjong'
    os.environ['MAHJONG_SESSION_SECRET']=secret
    config=Settings();verify_assets(ROOT)
    engine=create_db_engine(config)
    try:initialize_schema(engine)
    finally:engine.dispose()
    os.execv(sys.executable,[sys.executable,'-m','scripts.run_backend'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--finish',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--container',action='store_true');parser.add_argument('--compose-secrets',action='store_true')
    parser.add_argument('--check',action='store_true',help='Validate existing native config/model/database without provisioning')
    args=parser.parse_args();started=time.monotonic()
    try:
        if args.compose_secrets:prepare_compose_secrets(Path('/state'));print('Private Compose secrets ready; existing values preserved');return 0
        if args.container:container_start();return 0
        result=native_finish(run=args.run,check_only=args.check) if args.finish or args.run or args.check else native_setup()
        if not args.run:print(f'Setup elapsed: {time.monotonic()-started:.2f}s')
        return result
    except (ValueError,RuntimeError,OSError,subprocess.CalledProcessError) as error:
        if type(error).__name__=='NativeSetupError':print(str(error),file=sys.stderr)
        print('Setup/start FAILED. Check README_START_HERE: Python3.12/compiler, local PostgreSQL URL/auth/schema, private config, exact v3 assets. No fallback used.',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
