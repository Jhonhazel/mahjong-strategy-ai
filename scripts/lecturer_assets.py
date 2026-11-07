"""Standard-library verification/import of the owner's frozen inference bundle."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

PINNED = {
    'artifacts/models/mahjong_discard_mlp_v3.pt': 'ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720',
    'artifacts/models/mahjong_discard_mlp_v3.metadata.json': '84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e',
    'datasets/expanded_strict_v2/data_contract.json': '95f21b15be55dbbe4b9cf001edbc8b52462e4461b9bbaf39431a0a482e73adbc',
}
BUNDLE_SHA = '96ea17fab9e13ae7061230a892cc302dfa74a7e765740f363cd7a27fa96119b2'


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def safe_path(root,name):
    name=str(name);relative=PurePosixPath(name)
    if not name or relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe package path')
    root=Path(root).resolve();path=root
    for part in relative.parts:
        path=path/part
        if path.is_symlink():raise ValueError('Symlinks are not allowed in release paths')
    if not path.resolve().is_relative_to(root):raise ValueError('Path escaped release root')
    return path


def asset_manifest(root):
    path=safe_path(root,'docs/ml_artifact_bundle_manifest.json')
    if path.stat().st_size>65536:raise ValueError('Invalid asset manifest size')
    manifest=json.loads(path.read_text(encoding='utf-8'))
    entries=manifest['files']
    if len(entries)!=3 or {x['restore_path'] for x in entries.values()}!=set(PINNED):
        raise ValueError('Unexpected inference asset set')
    for name,entry in entries.items():
        if '/' in name or entry['sha256']!=PINNED[entry['restore_path']] or not 0<entry['bytes']<4*1024*1024:
            raise ValueError('Untrusted inference asset manifest')
    return manifest


def verify_assets(root):
    manifest=asset_manifest(root)
    for entry in manifest['files'].values():
        path=safe_path(root,entry['restore_path'])
        if not path.is_file() or path.stat().st_size!=entry['bytes'] or file_hash(path)!=entry['sha256']:
            raise ValueError('Required inference asset missing/mismatched: '+entry['restore_path'])
    return {'status':'PASS','sha256':dict(PINNED)}


def restore_assets(root,archive):
    manifest=asset_manifest(root);archive=Path(archive)
    if archive.is_symlink() or archive.stat().st_size>8*1024*1024 or file_hash(archive)!=BUNDLE_SHA:
        raise ValueError('Untrusted inference bundle checksum')
    verified=[]
    with tarfile.open(archive,'r:gz') as bundle:
        if sorted(bundle.getnames())!=sorted([*manifest['files'],'manifest.json']):raise ValueError('Unexpected bundle members')
        for member in bundle.getmembers():
            if not member.isfile() or member.size>4*1024*1024:raise ValueError('Unsafe bundle member')
        if bundle.extractfile('manifest.json').read()!=safe_path(root,'docs/ml_artifact_bundle_manifest.json').read_bytes():
            raise ValueError('Bundle manifest differs from trusted repository manifest')
        for name,entry in manifest['files'].items():
            data=bundle.extractfile(name).read();destination=safe_path(root,entry['restore_path'])
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Corrupt bundle asset')
            if destination.exists() and (not destination.is_file() or file_hash(destination)!=entry['sha256']):
                raise ValueError('Refusing to overwrite a different existing artifact')
            verified.append((destination,data))
    for destination,data in verified:
        if not destination.exists():
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as stream:stream.write(data)
    return verify_assets(root)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    print(json.dumps(restore_assets(root,args.bundle) if args.bundle else verify_assets(root),indent=2))
