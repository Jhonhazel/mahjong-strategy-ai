"""Native-Windows-only candidate builder; never downloads binaries or publishes."""
import argparse
import importlib.metadata
import json
from pathlib import Path,PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import zipfile

from scripts.lecturer_assets import file_hash,safe_path,verify_assets


def verify_pg_input(archive,metadata):
    url=urlsplit(metadata.get('download_url',''))
    if (url.scheme!='https' or url.hostname!='get.enterprisedb.com' or url.username or url.password or url.query or url.fragment
            or not url.path.startswith('/postgresql/') or not url.path.endswith('windows-x64-binaries.zip')
            or metadata.get('license_reviewed') is not True or not re.fullmatch(r'14\.\d+',metadata.get('version',''))):
        raise ValueError('Require the official EDB Windowsx64 source, PostgreSQL14 version and reviewed redistribution notices')
    digest=metadata.get('sha256','')
    if not re.fullmatch(r'[0-9a-f]{64}',digest) or Path(archive).is_symlink() or file_hash(archive)!=digest:
        raise ValueError('PostgreSQL archive does not match the separately verified provenance checksum')
    return {key:metadata[key] for key in ('download_url','version','sha256','license_reviewed')}


def extract_postgres(archive,destination):
    destination=Path(destination);verified=[];total=0
    with zipfile.ZipFile(archive) as source:
        names=set()
        for member in source.infolist():
            path=PurePosixPath(member.filename)
            if (not member.filename or path.is_absolute() or '..' in path.parts or '\\' in member.filename
                    or ':' in member.filename or stat.S_IFMT(member.external_attr>>16)==stat.S_IFLNK or member.filename in names):
                raise ValueError('Unsafe PostgreSQL ZIP member')
            names.add(member.filename);total+=member.file_size
            if total>2*1024**3:raise ValueError('PostgreSQL archive expansion exceeds the build bound')
            if len(path.parts)>=2 and path.parts[0]=='pgsql' and (path.parts[1] in ('bin','lib','share','doc') or path.parts[1].upper().startswith(('LICENSE','COPYRIGHT','NOTICE'))):
                if not member.is_dir():verified.append((member,'/'.join(path.parts[1:])))
        selected={p for _,p in verified}
        required={'bin/initdb.exe','bin/pg_ctl.exe','bin/psql.exe','bin/postgres.exe'}
        if not required.issubset(selected):raise ValueError('Incomplete PostgreSQL Windows runtime')
        if not any(p.startswith('doc/') or 'LICENSE' in p.upper() or 'COPYRIGHT' in p.upper() for p in selected):
            raise ValueError('Redistribution notices are missing; do not ship this archive')
        destination.mkdir(parents=True,exist_ok=False)
        for member,name in verified:
            target=safe_path(destination,name);target.parent.mkdir(parents=True,exist_ok=True)
            with source.open(member) as data,target.open('xb') as out:shutil.copyfileobj(data,out)


def build(root,output,pg_archive,provenance):
    root=Path(root).resolve();output=Path(output)
    if platform.system()!='Windows' or platform.machine().lower() not in ('amd64','x86_64') or sys.version_info[:2]!=(3,12):
        raise RuntimeError('Build on actual Windowsx64 CPython3.12; this is not a cross-compiler')
    if output.exists():raise FileExistsError('Choose a new build output; existing artifacts are preserved')
    verify_assets(root);provenance=verify_pg_input(pg_archive,provenance)
    import torch
    if torch.version.cuda is not None or torch.__version__.split('+')[0]!='2.15.0':raise ValueError('Use the exact official PyTorch2.15 CPU wheel')
    if importlib.metadata.version('pyinstaller')!='6.22.3':raise ValueError('Use the pinned Windows build environment')
    output.mkdir(parents=True,exist_ok=False);package=output/'mahjong-strategy-ai-windows-CANDIDATE';package.mkdir()
    extract_postgres(pg_archive,package/'postgres-runtime')
    version=subprocess.check_output([str(package/'postgres-runtime/bin/pg_ctl.exe'),'--version'],text=True)
    if (' '+provenance['version']) not in version:raise ValueError('Bundled PostgreSQL version disagrees with provenance')
    allowlist=json.loads((root/'packaging/runtime_allowlist.json').read_text())
    hidden=[];datas=[]
    for source,target in allowlist.items():
        path=safe_path(root,source)
        if path.suffix=='.py':
            if target!='main.py':hidden.append(target.removesuffix('.py').replace('/','.').removesuffix('.__init__'))
            readable=package/'source'/target;readable.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,readable)
        elif target.startswith(('app/static/','app/templates/','config/','artifacts/models/','datasets/','docs/ml_artifact_bundle_manifest')) or target=='THIRD_PARTY_NOTICES.md':
            datas.append((str(path),str(PurePosixPath(target).parent)))
    for source in ('scripts/windows_launcher.py','windows/entry.py'):
        readable=package/'source'/source;readable.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/source,readable)
    hidden+=['scripts.windows_launcher','sqlalchemy.dialects.postgresql.psycopg','psycopg_binary',
             'uvicorn.logging','uvicorn.protocols.http.h11_impl','uvicorn.lifespan.on']
    # Spec objects avoid Windows drive-letter / add-data separator ambiguity.
    with tempfile.TemporaryDirectory(prefix='mahjong-windows-build-') as work:
        work=Path(work);spec=work/'Mahjong.spec'
        spec.write_text("from PyInstaller.utils.hooks import collect_all\n"
            "td,tb,th=collect_all('torch')\n"
            +"a=Analysis("+repr([str(root/'windows/entry.py')])+",pathex="+repr([str(root)])+",binaries=tb,datas="+repr(datas)+"+td,hiddenimports="+repr(sorted(set(hidden)))+"+th,excludes=['pytest'],noarchive=False)\n"
            +"p=PYZ(a.pure)\ne=EXE(p,a.scripts,[],exclude_binaries=True,name='Mahjong',console=True,upx=False)\n"
            +"c=COLLECT(e,a.binaries,a.datas,name='Mahjong',upx=False)\n",encoding='utf-8')
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',str(work/'dist'),'--workpath',str(work/'work'),str(spec)],check=True,cwd=root)
        shutil.copytree(work/'dist/Mahjong',package/'app-runtime')
    verify_assets(package/'app-runtime/_internal')
    for name in ('Start Mahjong.bat','Stop Mahjong.bat','README_START_HERE.txt'):shutil.copyfile(root/'windows'/name,package/name)
    report={'status':'BUILT CANDIDATE; WINDOWS CLEAN-USER OFFLINE ACCEPTANCE STILL REQUIRED',
            'platform':platform.platform(),'python':platform.python_version(),'torch':torch.__version__,
            'postgres':provenance,'signed':False,'source':'Readable project Python source plus runtime HTML/JS/CSS/SVG under app-runtime/_internal'}
    (package/'BUILD_REPORT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    records={p.relative_to(package).as_posix():file_hash(p) for p in package.rglob('*') if p.is_file()}
    (package/'RUNTIME_MANIFEST.json').write_text(json.dumps({'files':records},indent=2,sort_keys=True)+'\n',encoding='utf-8')
    archive=output/'mahjong-strategy-ai-windows-CANDIDATE.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as zipout:
        for p in sorted(package.rglob('*')):
            if p.is_file():zipout.write(p,arcname='mahjong-strategy-ai-windows/'+p.relative_to(package).as_posix())
    summary={'status':report['status'],'zip_sha256':file_hash(archive),'zip_bytes':archive.stat().st_size,
             'extracted_bytes':sum(p.stat().st_size for p in package.rglob('*') if p.is_file()),'files':len(records)+1}
    (output/'candidate_manifest.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--postgres-archive',type=Path,required=True)
    parser.add_argument('--provenance',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[1],args.output,args.postgres_archive,
                                                json.loads(args.provenance.read_text(encoding='utf-8'))),indent=2))


if __name__=='__main__':main()
