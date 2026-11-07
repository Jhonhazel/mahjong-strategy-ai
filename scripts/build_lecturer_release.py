"""Deterministic owner-local runtime/audit ZIPs; never moves original files."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile

from scripts.lecturer_assets import file_hash, safe_path, verify_assets

OMIT_DIRS={'.git','.venv','.local','.pytest_cache','__pycache__','.wheels_cache',
           'node_modules','delivery','.codex','.agents','.aws'}
OMIT_SUFFIXES={'.sql','.dump','.backup','.bak','.db','.sqlite','.sqlite3','.log','.pem','.key','.p12','.pfx','.pyc','.part','.zip'}
AUDIT_ROOTS={'app','config','scripts','training','tests','docs','artifacts','datasets','packaging','deploy','windows'}
AUDIT_TOP={'pytest.ini','requirements.txt','requirements-lock.txt','requirements-runtime.txt',
           'README.md','README_START_HERE.md','README_AUDIT.md','THIRD_PARTY_NOTICES.md',
           '.gitignore','.gitattributes','.env.example','main.py','Dockerfile','.dockerignore',
           'compose.yaml','setup-macos.sh','run-macos.sh','setup-windows.cmd','run-windows.cmd',
           'RELEASE_MANIFEST.json','pyproject.toml'}


def excluded(name):
    path=PurePosixPath(name)
    return (any(p in OMIT_DIRS for p in path.parts) or path.suffix.lower() in OMIT_SUFFIXES
            or path.name in ('.DS_Store','.pgpass','id_rsa','id_ed25519')
            or re.search(r'(?:^|[._-])(?:backup|credentials?|secrets?|production|staging)(?:[._-]|$)',path.name.lower())
            or any(path.name.lower().endswith(suffix+compression) for suffix in ('.sql','.dump','.backup') for compression in ('.gz','.bz2','.xz','.tar.gz'))
            or (path.name.startswith('.env') and path.name!='.env.example'))


def inventory(root):
    root=Path(root).resolve();result={}
    for base,dirs,names in os.walk(root,followlinks=False):
        for name in list(dirs):
            path=Path(base)/name
            if name in OMIT_DIRS:dirs.remove(name)
            elif path.is_symlink():raise ValueError('Audit directory symlink is unsafe')
        for name in names:
            path=Path(base)/name;relative=path.relative_to(root).as_posix()
            if excluded(relative) or (relative.split('/')[0] not in AUDIT_ROOTS and relative not in AUDIT_TOP):continue
            safe_path(root,relative)
            if not path.is_file():raise ValueError('Non-regular release source')
            result[relative]={'bytes':path.stat().st_size,'sha256':file_hash(path)}
    return result


def validate_imports(root,mapping):
    targets=set(mapping.values())
    for source,target in mapping.items():
        path=safe_path(root,source)
        if path.suffix=='.py':
            package=PurePosixPath(target).parent.parts
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'),filename=source)):
                names=[]
                if isinstance(node,ast.Import):names=[x.name for x in node.names]
                elif isinstance(node,ast.ImportFrom):
                    prefix=list(package[:len(package)-node.level+1]) if node.level else []
                    base='.'.join([*prefix,*((node.module or '').split('.') if node.module else [])])
                    names=[base]+[base+'.'+x.name for x in node.names if x.name!='*']
                for name in names:
                    if name.split('.')[0] not in ('app','training','scripts'):continue
                    candidate=name.replace('.','/')
                    options=[candidate+'.py',candidate+'/__init__.py']
                    existing=[p for p in options if (root/p).is_file()]
                    # The base module is mandatory; imported names may be attributes.
                    if not existing and name==names[0]:raise ValueError('Missing local runtime import: '+name)
                    if existing and not any(p in targets for p in existing):raise ValueError('Omitted local runtime import: '+name)
        elif path.suffix in ('.js','.mjs'):
            for name in re.findall(r"(?:from\s*|import\s*)['\"]([^'\"]+)['\"]",path.read_text()):
                if name.startswith('.'):
                    candidate=os.path.normpath(str(PurePosixPath(target).parent/name)).replace(os.sep,'/')
                    if candidate not in targets:raise ValueError('Missing local JavaScript import: '+name)


def check_no_secret(path):
    if path.suffix.lower() not in ('.py','.json','.md','.txt','.sh','.cmd','.yaml','.example'):return
    text=path.read_text(encoding='utf-8')
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}',text):
        raise ValueError('Potential secret found; refusing package inclusion')
    if path.suffix.lower()=='.json':
        sensitive={'mahjong_session_secret','mahjong_database_url','database_url','session_secret',
                   'password','api_key','access_token','refresh_token','private_key'}
        def contains_secret(value):
            if isinstance(value,dict):
                return any((str(key).lower() in sensitive and isinstance(item,str) and item and item not in ('**********','<redacted>'))
                           or contains_secret(item) for key,item in value.items())
            return isinstance(value,list) and any(contains_secret(item) for item in value)
        if contains_secret(json.loads(text)):raise ValueError('Potential secret in JSON; refusing package inclusion')


def write_zip(path,root,mapping,prefix):
    if len(set(mapping.values()))!=len(mapping) or 'RELEASE_MANIFEST.json' in mapping.values():
        raise ValueError('Reserved or duplicate archive destination')
    records={target:{'source':source,'bytes':safe_path(root,source).stat().st_size,
                      'sha256':file_hash(safe_path(root,source))} for source,target in mapping.items()}
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for source,target in sorted(mapping.items(),key=lambda x:x[1]):
            original=safe_path(root,source);check_no_secret(original)
            info=zipfile.ZipInfo(prefix+'/'+target,date_time=(2020,1,1,0,0,0))
            info.create_system=3;info.external_attr=(0o100755 if target.endswith('.sh') else 0o100644)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            digest=hashlib.sha256()
            with archive.open(info,'w',force_zip64=True) as dest,original.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(block);dest.write(block)
            if digest.hexdigest()!=records[target]['sha256']:raise ValueError('Source changed during archive copy')
        info=zipfile.ZipInfo(prefix+'/RELEASE_MANIFEST.json',date_time=(2020,1,1,0,0,0));info.external_attr=0o100644<<16
        archive.writestr(info,json.dumps({'format':1,'files':records},sort_keys=True,indent=2)+'\n')
    return {'files':len(records),'source_bytes':sum(x['bytes'] for x in records.values()),
            'zip_bytes':path.stat().st_size,'sha256':file_hash(path)}


def build_release(root,destination,runtime=None,*,include_audit=True):
    root=Path(root).resolve();destination=Path(destination)
    if destination.exists():raise FileExistsError('Choose a new release output directory')
    if destination.resolve().is_relative_to(root) and destination.resolve().relative_to(root).parts[0]!='delivery':
        raise ValueError('Repository output must be inside excluded delivery/')
    if runtime is None:runtime=json.loads((root/'packaging/runtime_allowlist.json').read_text())
    if len(set(runtime.values()))!=len(runtime):raise ValueError('Duplicate runtime target')
    if 'RELEASE_MANIFEST.json' in runtime.values():raise ValueError('Reserved generated manifest destination')
    for source,target in runtime.items():
        path=safe_path(root,source);safe_path(root,target)
        if excluded(source) or excluded(target) or not path.is_file():raise ValueError('Missing or prohibited runtime source')
        check_no_secret(path)
    verify_assets(root);validate_imports(root,runtime)
    # A valid model on the host is insufficient: every required asset must ship.
    from scripts.lecturer_assets import PINNED
    if any(runtime.get(name)!=name for name in PINNED):raise ValueError('Inference assets omitted or mapped to an incorrect destination')
    all_files=inventory(root) if include_audit else {
        source:{'bytes':safe_path(root,source).stat().st_size,'sha256':file_hash(safe_path(root,source))} for source in runtime}
    for name,record in all_files.items():
        record['category']=('runtime/setup' if name in runtime else 'tests' if name.startswith('tests/')
                            else 'research' if name.startswith(('training/','datasets/','artifacts/models/'))
                            else 'audit/evidence' if name.startswith(('docs/','artifacts/')) else 'development')
    audit={name:('manifests/source_RELEASE_MANIFEST.json' if name=='RELEASE_MANIFEST.json' else name) for name in all_files if name not in runtime} if include_audit else {}
    if 'packaging/README_AUDIT.md' in audit:audit['packaging/README_AUDIT.md']='README_AUDIT.md'
    if len(set(audit.values()))!=len(audit):raise ValueError('Preserved audit manifest destination collision')
    for source in audit:check_no_secret(safe_path(root,source))
    destination.mkdir(parents=True,exist_ok=False)
    result={'runtime':write_zip(destination/'mahjong-strategy-ai-lecturer-portable.zip',root,runtime,'mahjong-strategy-ai'),
            'inventory':all_files,'excluded_directories':sorted(OMIT_DIRS),
            'policy':'Local owner-generated packages only; no upload; original checkout and Git history retained'}
    if include_audit:result['audit']=write_zip(destination/'mahjong-strategy-ai-audit.zip',root,audit,'mahjong-strategy-ai-audit')
    (destination/'release_manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--runtime-only',action='store_true',help='Do not rearchive the preserved research/audit tree')
    parser.add_argument('--extra-files',type=Path,help='Additional trusted repository source-to-target mapping')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];runtime=None
    if args.extra_files:
        path=args.extra_files.resolve()
        if not path.is_relative_to(root) or path.is_symlink():raise ValueError('Extra mapping must belong to the trusted repository')
        runtime=json.loads((root/'packaging/runtime_allowlist.json').read_text())
        for source,target in json.loads(path.read_text()).items():
            if source in runtime and runtime[source]!=target:raise ValueError('Extra mapping cannot remap existing runtime files')
            runtime[source]=target
    result=build_release(root,args.output,runtime,include_audit=not args.runtime_only)
    print(json.dumps({k:v for k,v in result.items() if k!='inventory'},indent=2))


if __name__=='__main__':main()
