"""Explicit local PostgreSQL provisioning; never used by application startup."""
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
from urllib.parse import quote

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from scripts.windows_launcher import no_links

APP_ID='mahjong-native-postgres-v1'
ROLE='mahjong_app'
DATABASE='mahjong_phase3_dev'
FIELDS={'application','root','port','role','database','password','session_secret','token'}

WINDOWS_ACL_SCRIPT=r'''
$ErrorActionPreference='Stop'
$p=ConvertFrom-Json -InputObject ([Console]::In.ReadToEnd())
$user=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
$sids=@(@($user.Value,'S-1-5-18') | Select-Object -Unique)
$inherit=[System.Security.AccessControl.InheritanceFlags]::None
if ([System.IO.Directory]::Exists($p)) {
    $acl=[System.Security.AccessControl.DirectorySecurity]::new()
    $inherit=[System.Security.AccessControl.InheritanceFlags]'ObjectInherit, ContainerInherit'
} elseif ([System.IO.File]::Exists($p)) {
    $acl=[System.Security.AccessControl.FileSecurity]::new()
} else { throw 'Private path missing' }
$acl.SetOwner($user)
$acl.SetAccessRuleProtection($true,$false)
foreach ($sid in $sids) {
    $id=[System.Security.Principal.SecurityIdentifier]::new($sid)
    $rule=[System.Security.AccessControl.FileSystemAccessRule]::new($id,
        [System.Security.AccessControl.FileSystemRights]::FullControl,$inherit,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow)
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $p -AclObject $acl
$actual=Get-Acl -LiteralPath $p
$rules=@($actual.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]))
if (-not $actual.AreAccessRulesProtected -or $rules.Count -ne $sids.Count -or
    $actual.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $user.Value) { throw 'Private ACL mismatch' }
foreach ($sid in $sids) {
    $matching=@($rules | Where-Object { $_.IdentityReference.Value -eq $sid })
    if ($matching.Count -ne 1) { throw 'Private ACL principal mismatch' }
    $r=$matching[0]
    if ($r.IsInherited -or $r.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
        $r.FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl -or
        $r.InheritanceFlags -ne $inherit -or $r.PropagationFlags -ne [System.Security.AccessControl.PropagationFlags]::None) { throw 'Private ACL rights mismatch' }
}
Write-Output 'PRIVATE_ACL_VERIFIED'
'''


class NativeSetupError(RuntimeError):pass


def protect_path(path):
    """Apply protection before writing secrets, including explicit file ACLs."""
    no_links(path)
    if os.name!='nt':path.chmod(0o700 if path.is_dir() else 0o600);return
    try:
        executable=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        encoded=base64.b64encode(WINDOWS_ACL_SCRIPT.encode('utf-16le')).decode('ascii')
        result=subprocess.run([str(executable),'-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                              input=json.dumps(str(path)),text=True,encoding='utf-8',capture_output=True,check=True,timeout=20)
        if result.stdout.strip()!='PRIVATE_ACL_VERIFIED':raise NativeSetupError('Windows private ACL verification did not complete')
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        raise NativeSetupError('Cannot protect native setup files with Windows ACLs; fix permissions and retry') from None


def ensure_local_environment():
    # The subsequent FastAPI CLI inherits this same CMD environment, too.
    blocked=('PGHOSTADDR','PGSERVICE','PGSERVICEFILE','MAHJONG_DATABASE_URL','MAHJONG_SESSION_SECRET')
    if any(os.environ.get(name) for name in blocked):
        raise NativeSetupError('Clear PGHOSTADDR/PGSERVICE/PGSERVICEFILE and MAHJONG_DATABASE_URL/MAHJONG_SESSION_SECRET process overrides in this CMD session before native setup/start; private .env is authoritative')


def _directory(root):
    root=no_links(Path(root));local=no_links(root/'.local');state=no_links(local/'native-postgres')
    local.mkdir(parents=True,exist_ok=True,mode=0o700)
    state.mkdir(exist_ok=True,mode=0o700)
    if any(p.name!='pending.json' for p in state.iterdir()):
        raise NativeSetupError('Unknown private setup files; inspect them before retrying. No data was removed')
    return state


def _publish(stage,path,text):
    """Publish a complete private file with no overwrite, on the same filesystem."""
    no_links(stage);no_links(path)
    descriptor,name=tempfile.mkstemp(prefix='.new-',dir=stage)
    temporary=Path(name);identity=os.fstat(descriptor)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as stream:
            protect_path(temporary)
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path)
    finally:
        observed=temporary.lstat()
        if (observed.st_dev,observed.st_ino)==(identity.st_dev,identity.st_ino):temporary.unlink()
        else:raise NativeSetupError('Private staging file changed; inspect it before recovery')


def publish_config(root,text):
    root=no_links(Path(root));path=no_links(root/'.env')
    if path.exists():raise NativeSetupError('Existing configuration was preserved; rerun validation instead of replacing it')
    stage=_directory(root);protect_path(stage)
    try:_publish(stage,path,text)
    except OSError:raise NativeSetupError('Private config publication failed; pending credentials preserved. Retry setup') from None


def _pending(root,port,role,database):
    root=no_links(Path(root)).resolve();stage=_directory(root);path=no_links(stage/'pending.json')
    if path.exists():
        try:
            if path.stat().st_size>8192:raise ValueError
            data=json.loads(path.read_text(encoding='utf-8'))
            if (set(data)!=FIELDS or data['application']!=APP_ID or data['root']!=str(root)
                    or data['role']!=role or data['database']!=database
                    or type(data['port']) is not int or not 1<=data['port']<=65535
                    or (port is not None and data['port']!=port)):raise ValueError
            if any(not isinstance(data[k],str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}',data[k])
                   or len(set(data[k]))<8 for k in ('password','session_secret','token')):raise ValueError
        except (ValueError,KeyError,TypeError):
            raise NativeSetupError('Invalid or incompatible pending config; restore the original private file, do not rotate credentials') from None
        protect_path(stage);protect_path(path);return data
    protect_path(stage)
    if port is None:
        try:port=int(input('Local PostgreSQL port [5432]: ').strip() or '5432')
        except ValueError:raise NativeSetupError('Use a valid local PostgreSQL port') from None
    if type(port) is not int or not 1<=port<=65535:raise NativeSetupError('Invalid local PostgreSQL port')
    data={'application':APP_ID,'root':str(root),'port':port,'role':role,'database':database,
          'password':secrets.token_urlsafe(48),'session_secret':secrets.token_urlsafe(48),'token':secrets.token_urlsafe(48)}
    try:_publish(stage,path,json.dumps(data,indent=2)+'\n')
    except FileExistsError:return _pending(root,port,role,database)
    return data


def _connect(**kwargs):
    ensure_local_environment()
    connection=psycopg.connect(**kwargs,autocommit=True,connect_timeout=5,
                               options='-c statement_timeout=5000 -c lock_timeout=5000')
    if not connection.pgconn.used_password:
        connection.close();raise NativeSetupError('PostgreSQL password authentication is required; no trust fallback is used')
    return connection


def validate_database(database_url):
    ensure_local_environment()
    try:
        url=make_url(database_url)
        if (url.drivername not in ('postgresql','postgresql+psycopg') or url.host not in ('127.0.0.1','localhost','::1')
                or not url.database or not url.username or not url.password or set(url.query)-{'sslmode'}
                or any(not isinstance(v,str) for v in url.query.values())):raise ValueError
    except (ValueError,TypeError,ArgumentError):raise NativeSetupError('Native setup requires a local TCP PostgreSQL URL without connection overrides') from None
    try:
        with _connect(host=url.host,port=url.port or 5432,user=url.username,password=url.password,
                      dbname=url.database,**dict(url.query)) as c:
            flags=c.execute('''SELECT r.rolcanlogin,r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls,
                pg_get_userbyid(d.datdba)=current_user,NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid)
                FROM pg_roles r JOIN pg_database d ON d.datname=current_database() WHERE r.rolname=current_user''').fetchone()
            if flags!=(True,False,False,False,False,False,True,True):
                raise NativeSetupError('Existing application role/database is not compatible with least-privilege ownership; no privileges were changed')
    except psycopg.Error:
        raise NativeSetupError('Local PostgreSQL application connection failed; check the running server and saved credentials. No data was reset') from None
    return True


def prepare_database(root,*,port=None,admin_user=None,admin_password=None,role=ROLE,database=DATABASE):
    ensure_local_environment()
    for name in (role,database):
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',name):raise NativeSetupError('Use ordinary project-specific role/database identifiers')
    data=_pending(root,port,role,database)
    if admin_user is None:admin_user=input('PostgreSQL administrator [postgres]: ').strip() or 'postgres'
    if admin_password is None:admin_password=getpass.getpass('PostgreSQL administrator password (not saved): ')
    if not admin_password:raise NativeSetupError('A PostgreSQL administrator password is required; no trust fallback')
    tag='mahjong-native-setup:'+data['token']
    try:
        with _connect(host='127.0.0.1',port=data['port'],user=admin_user,password=admin_password,dbname='postgres') as c:
            lock=int.from_bytes(hashlib.sha256((role+'\0'+database).encode()).digest()[:8],signed=True)
            if not c.execute('SELECT pg_try_advisory_lock(%s)',(lock,)).fetchone()[0]:
                raise NativeSetupError('Another native setup is provisioning this database; retry later')
            observed_role=c.execute("SELECT r.rolcanlogin,r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls,NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid),shobj_description(r.oid,'pg_authid') FROM pg_roles r WHERE r.rolname=%s",(role,)).fetchone()
            observed_db=c.execute("SELECT pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",(database,)).fetchone()
            if observed_role and observed_role!=(True,False,False,False,False,False,True,tag):
                raise NativeSetupError('Existing role has incompatible ownership/privileges; restore verified configuration or use separate project resources. Nothing was overwritten')
            if observed_db and observed_db!=(role,tag):
                raise NativeSetupError('Existing database ownership is ambiguous; inspect/restore verified configuration. No database was changed')
            if not observed_role:
                with c.transaction():
                    c.execute("SET LOCAL password_encryption='scram-sha-256'")
                    c.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(role),sql.Literal(data['password'])))
                    c.execute(sql.SQL('COMMENT ON ROLE {} IS {}').format(sql.Identifier(role),sql.Literal(tag)))
            if not observed_db:
                c.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(database),sql.Identifier(role)))
                c.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(database),sql.Literal(tag)))
    except psycopg.Error:
        raise NativeSetupError('PostgreSQL was not found, is not running, or administrator authentication/CREATE ROLE/CREATE DATABASE privileges failed. Install/start PostgreSQL and rerun setup-windows-native.cmd; pending credentials are preserved') from None
    finally:admin_password=None
    url=f'postgresql+psycopg://{role}:{quote(data["password"],safe="")}@127.0.0.1:{data["port"]}/{database}'
    validate_database(url)
    return {'database_url':url,'session_secret':data['session_secret']}
