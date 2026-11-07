"""Per-user offline supervisor. Windows execution remains a separate release gate."""
import contextlib
import json
import os
from pathlib import Path
import platform
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import quote,urlsplit
import webbrowser

from scripts.lecturer_assets import file_hash,safe_path,verify_assets

APP_ID='mahjong-strategy-ai-offline-v1'
KEYS={'app_id','pg_major','db_port','web_port','session_secret','admin_password','app_password'}


class LauncherError(RuntimeError):pass
class AlreadyRunning(LauncherError):pass


def no_links(path):
    path=Path(path)
    for item in (path,*path.parents):
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()):
            raise LauncherError('Symlink/junction paths are not supported for owned runtime/state')
    return path


def write_private(path,value,*,created=None):
    no_links(path)
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as stream:
        if created is not None:
            identity=os.fstat(stream.fileno());created.append((path,(identity.st_dev,identity.st_ino)))
        json.dump(value,stream,indent=2);stream.write('\n')


def require_free_port(port):
    try:
        with socket.socket() as probe:
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            probe.bind(('127.0.0.1',port))
    except OSError:raise LauncherError('Configured local port is occupied; no other process was stopped') from None


def prepare_state(root,*,protect=None):
    root=no_links(root)
    marker=root/'owner.json';config=root/'state.json';expected={'application':APP_ID,'root':str(root.resolve())}
    no_links(marker);no_links(config)
    if root.exists() and any(root.iterdir()) and not marker.is_file():
        raise LauncherError('Refusing to claim a nonempty directory without this application ownership marker')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    new_profile=not marker.exists()
    if not new_profile:
        if json.loads(marker.read_text(encoding='utf-8'))!=expected:raise LauncherError('Foreign state ownership marker')
        if not config.is_file():
            raise LauncherError('Owned state config is missing; restore the original private config before starting')
    if protect:protect(root)
    if new_profile:
        with socket.socket() as db,socket.socket() as web:
            db.bind(('127.0.0.1',0));web.bind(('127.0.0.1',0))
            ports=(db.getsockname()[1],web.getsockname()[1])
        data={'app_id':APP_ID,'pg_major':14,'db_port':ports[0],'web_port':ports[1],
              'session_secret':secrets.token_urlsafe(48),'admin_password':secrets.token_urlsafe(48),
              'app_password':secrets.token_urlsafe(48)}
    else:data=json.loads(config.read_text(encoding='utf-8'))
    if set(data)!=KEYS or data['app_id']!=APP_ID or data['pg_major']!=14:
        raise LauncherError('Incompatible owned state config; no data was replaced')
    if any(type(data[p]) is not int or not 1024<=data[p]<=65535 for p in ('db_port','web_port')) or data['db_port']==data['web_port']:
        raise LauncherError('Invalid persisted local ports')
    for name in ('session_secret','admin_password','app_password'):
        if not isinstance(data[name],str) or len(data[name])<40 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in data[name]):
            raise LauncherError('Invalid stored secret; restore the original private config')
    if new_profile:
        created=[]
        try:
            write_private(marker,expected,created=created)
            write_private(config,data,created=created)
        except BaseException as error:
            # Roll back only this attempt's exact files, never an ambiguous profile.
            try:
                no_links(root);current={}
                for path in root.iterdir():
                    identity=path.lstat();current[path]=(identity.st_dev,identity.st_ino)
                if current!=dict(created) or any(not identity[1] for _,identity in created):
                    raise LauncherError('Incomplete first-run state changed; inspect existing files before recovery') from error
                for path,expected_identity in reversed(created):
                    no_links(path);identity=path.lstat()
                    if (identity.st_dev,identity.st_ino)!=expected_identity:
                        raise LauncherError('First-run file changed during cleanup; inspect existing private state before recovery') from error
                    path.unlink()
            except OSError as cleanup_error:
                raise LauncherError('Incomplete first-run cleanup; inspect existing private state before recovery') from cleanup_error
            raise
    return data


class SingleInstance:
    def __init__(self,path):self.path=path;self.file=None
    def __enter__(self):
        no_links(self.path);self.file=os.fdopen(os.open(self.path,os.O_RDWR|os.O_CREAT,0o600),'r+b')
        if self.file.seek(0,2)==0:self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();raise AlreadyRunning('An owned launcher is already running') from None
        return self
    def __exit__(self,*args):self.file.close()


def fetch_ready(url):
    with urllib.request.urlopen(url,timeout=1) as response:
        if response.status!=200:return {}
        return json.loads(response.read(4096))


def wait_ready(url,process,timeout=40,*,fetch=fetch_ready,owns_port=lambda:True,clock=time.monotonic,sleep=time.sleep):
    parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.path!='/health/ready':
        raise LauncherError('Readiness must use this owned loopback endpoint')
    deadline=clock()+timeout
    while clock()<deadline:
        if process.poll() is not None:raise LauncherError('Application exited before readiness; inspect private diagnostics')
        try:
            if owns_port() and fetch(url)=={'status':'ready','model':'ready','database':'ready'}:return True
        except (OSError,ValueError):pass
        sleep(.1)
    raise LauncherError('Timed out waiting for owned model/database/application readiness')


def redact(message,values):
    for value in values:message=message.replace(value,'<redacted>')
    return message


def stop_owned(process,timeout=8):
    if process is None or process.poll() is not None:return
    try:process.send_signal(signal.CTRL_BREAK_EVENT if os.name=='nt' else signal.SIGINT)
    except OSError:process.terminate()
    try:process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)


def verify_package(root):
    try:
        root=no_links(root).resolve();manifest=safe_path(root,'RUNTIME_MANIFEST.json')
        if manifest.stat().st_size>8*1024*1024:raise ValueError('Invalid runtime manifest size')
        records=json.loads(manifest.read_text(encoding='utf-8'))['files']
        actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=manifest}
        if actual!=set(records):raise ValueError('Incomplete/extra package files')
        for name,digest in records.items():
            path=safe_path(root,name);no_links(path)
            if file_hash(path)!=digest:raise ValueError('Changed runtime component')
    except (OSError,ValueError,KeyError):raise LauncherError('Runtime integrity failed; extract the verified complete ZIP again') from None


def ensure_database(query,password):
    flags=query("SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname='mahjong_app'").strip()
    if not flags:query("CREATE ROLE mahjong_app LOGIN PASSWORD '"+password+"' NOSUPERUSER NOCREATEDB NOCREATEROLE")
    elif flags!='f|f|f':raise LauncherError('Existing app role has unexpected privileges; no role was changed')
    owner=query("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='mahjong'").strip()
    if not owner:query('CREATE DATABASE mahjong OWNER mahjong_app')
    elif owner!='mahjong_app':raise LauncherError('Existing database has a different owner; no database was overwritten')


def child_environment():
    return {k:v for k,v in os.environ.items() if not k.startswith(('PG','MAHJONG_','PYTHON'))}


@contextlib.contextmanager
def external_dll_search():
    frozen=os.name=='nt' and getattr(sys,'frozen',False)
    if frozen:
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:yield
    finally:
        if frozen:ctypes.windll.kernel32.SetDllDirectoryW(str(sys._MEIPASS))


class PostgresRuntime:
    def __init__(self,package,state,config):
        self.bin=package/'postgres-runtime/bin';self.state=state;self.config=config;self.data=no_links(state/'data');self.owned=False;self.started=False
    def command(self,name,*args,input=None,check=True):
        env=child_environment();env['PGPASSWORD']=self.config['admin_password']
        with external_dll_search():
            result=subprocess.run([str(self.bin/(name+'.exe')),*map(str,args)],input=input,text=True,encoding='utf-8',errors='replace',
                                  capture_output=True,timeout=45,env=env,cwd=self.state)
        if check and result.returncode:
            message=redact(result.stderr,[self.config[k] for k in ('session_secret','admin_password','app_password')])
            raise LauncherError(name+' failed: '+message[-1000:])
        return result
    def query(self,sql):
        return self.command('psql','--no-psqlrc','--set=ON_ERROR_STOP=1','-At','-h','127.0.0.1','-p',self.config['db_port'],
                            '-U','mahjong_admin','-d','postgres',input=sql+';\n').stdout.strip()
    def start(self):
        if not (self.data/'PG_VERSION').exists():
            if self.data.exists() and any(self.data.iterdir()):raise LauncherError('Incomplete database directory; no data removed')
            pw=no_links(self.state/'init-password.txt')
            if pw.exists():raise LauncherError('Incomplete initialization credential file; inspect private state')
            with os.fdopen(os.open(pw,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='ascii') as stream:stream.write(self.config['admin_password']+'\n')
            try:self.command('initdb','-D',self.data,'-U','mahjong_admin','--pwfile',pw,'--auth-host=scram-sha-256','--auth-local=scram-sha-256','--encoding=UTF8','--locale=C')
            finally:pw.unlink()
        if (self.data/'PG_VERSION').read_text().strip()!='14':raise LauncherError('Wrong database major version; no automatic upgrade/downgrade')
        running=self.command('pg_ctl','-D',self.data,'status',check=False).returncode==0
        if not running:
            require_free_port(self.config['db_port'])
            self.started=True
            self.command('pg_ctl','-D',self.data,'-l',self.state/'postgres-private.log','-w','-t','30','-o',
                         '-h 127.0.0.1 -p '+str(self.config['db_port'])+' -c log_statement=none -c log_min_error_statement=panic','start')
        directory=Path(self.query('SHOW data_directory')).resolve()
        if directory!=self.data.resolve():raise LauncherError('Database endpoint belongs to another data directory')
        self.owned=True;ensure_database(self.query,self.config['app_password'])
    def stop(self):
        if (self.started or self.owned) and self.command('pg_ctl','-D',self.data,'status',check=False).returncode==0:
            self.command('pg_ctl','-D',self.data,'-m','fast','-w','-t','20','stop')


def secure_windows_directory(root):
    # Restricted to the already verified application-owned profile, never global ACLs.
    import csv
    system=Path(os.environ['SystemRoot'])/'System32'
    output=subprocess.check_output([str(system/'whoami.exe'),'/user','/fo','csv','/nh'],text=True)
    sid=next(csv.reader([output.strip()]))[1]
    if not sid.startswith('S-1-'):raise LauncherError('Cannot determine current Windows user SID')
    subprocess.run([str(system/'icacls.exe'),str(root),'/inheritance:r','/grant:r',
                    '*'+sid+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],capture_output=True,check=True)


def owned_app_port(pid,port):
    system=Path(os.environ['SystemRoot'])/'System32'
    lines=subprocess.check_output([str(system/'netstat.exe'),'-ano','-p','TCP'],text=True).splitlines()
    return any(len(parts)>=5 and parts[0]=='TCP' and parts[1]=='127.0.0.1:'+str(port)
               and parts[-2]=='LISTENING' and parts[-1]==str(pid) for parts in map(str.split,lines))


def run_offline(package,assets,*,stop=False):
    if os.name!='nt' or platform.machine().lower() not in ('amd64','x86_64'):
        raise LauncherError('This executable requires Windows x64; no cross-platform executable claim')
    verify_package(package);verify_assets(assets)
    root=no_links(Path(os.environ['LOCALAPPDATA'])/'MahjongStrategyAI')
    if stop and not root.exists():print('Mahjong is not running');return 0
    config=prepare_state(root,protect=secure_windows_directory)
    control=no_links(root/'stop.request');url='http://127.0.0.1:'+str(config['web_port'])
    if stop:
        try:
            with SingleInstance(root/'instance.lock'):print('Mahjong launcher is not running');return 0
        except AlreadyRunning:
            control.touch(exist_ok=True);print('Stop requested; history/config will be retained');return 0
    try:lock=SingleInstance(root/'instance.lock');lock.__enter__()
    except AlreadyRunning:raise LauncherError('Already running; use its existing console/browser or Stop Mahjong') from None
    database=PostgresRuntime(package,root,config);app=None
    try:
        if control.exists():control.unlink()
        database.start();require_free_port(config['web_port'])
        env=child_environment();env.update(MAHJONG_DATABASE_URL='postgresql+psycopg://mahjong_app:'+quote(config['app_password'],safe='')+'@127.0.0.1:'+str(config['db_port'])+'/mahjong',
            MAHJONG_SESSION_SECRET=config['session_secret'],MAHJONG_ENVIRONMENT='local',MAHJONG_COOKIE_SECURE='false',
            MAHJONG_WORKERS='1',MAHJONG_HOST='127.0.0.1',MAHJONG_PORT=str(config['web_port']))
        subprocess.run([sys.executable,'--init-schema'],env=env,cwd=root,check=True)
        app=subprocess.Popen([sys.executable,'--serve'],env=env,cwd=root,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        wait_ready(url+'/health/ready',app,owns_port=lambda:owned_app_port(app.pid,config['web_port']))
        print('Mahjong ready: '+url+' . Use Stop Mahjong or Ctrl+C to close cleanly.')
        if not webbrowser.open(url):print('Browser did not open automatically; open the URL above.')
        while app.poll() is None and not control.exists():time.sleep(.2)
        return 0 if app.poll() in (None,0) else 1
    except KeyboardInterrupt:return 0
    except Exception as error:
        message=redact(type(error).__name__+': '+str(error),[config[k] for k in ('session_secret','admin_password','app_password')])
        with (root/'diagnostics.txt').open('a',encoding='utf-8') as stream:stream.write(message+'\n')
        raise LauncherError(message+'; private diagnostics: '+str(root/'diagnostics.txt')) from None
    finally:
        try:stop_owned(app)
        finally:
            try:database.stop()
            finally:lock.__exit__()
