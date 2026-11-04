# ML artifact transfer and restore

Commit packaging verified on 2026-11-05 (Asia/Jakarta). Phase 1 is already in
`49ad7a2`; the local commit for Phases 2–2.2 keeps the existing separation between
source/provenance in Git and trained weights/corpus outside Git. No Phase 3 code
is included. The new empty `datasets/.gitkeep` records the dataset directory;
it contains no training data.

## Promoted v3 inference bundle

The locally generated, Git-ignored bundle is:

`artifacts/transfer/mahjong_discard_mlp_v3_inference.tar.gz`

SHA-256: `96ea17fab9e13ae7061230a892cc302dfa74a7e765740f363cd7a27fa96119b2`

It contains exactly four regular files: the v3 weights, unchanged v3 metadata,
the expanded data contract, and a copy of the versioned
[`ml_artifact_bundle_manifest.json`](ml_artifact_bundle_manifest.json).
The manifest records each original file's size, SHA-256 and restore destination.
The original v3 weights have SHA-256
`ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`.

The bundle was restored into a temporary directory, all member bytes matched,
and `load_checkpoint(..., expected_contract=...)` loaded the restored 387,746
parameter model on CPU. See
[`bundle_verification.json`](evidence/commit_phases_2_2_2/bundle_verification.json).
No original model, metadata, contract or frozen evaluation record was rewritten.

To transfer it, copy the ignored archive separately through your chosen storage
channel and copy/checkout the source plus versioned manifest. No remote storage
location is assumed and no upload/push was performed. On the receiving machine,
verify the archive before restoring:

```sh
shasum -a 256 artifacts/transfer/mahjong_discard_mlp_v3_inference.tar.gz
```

The digest must match the archive digest above. The following restore command,
run from the repository root, additionally verifies the trusted Git manifest and
every member digest. It writes only missing destination files and refuses to
overwrite a different existing artifact. It does not use unrestricted extraction.

```sh
.venv/bin/python - <<'PY'
import hashlib
import json
import tarfile
from pathlib import Path

root = Path.cwd().resolve()
manifest_path = root / 'docs/ml_artifact_bundle_manifest.json'
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
archive = root / 'artifacts/transfer/mahjong_discard_mlp_v3_inference.tar.gz'
expected_archive = '96ea17fab9e13ae7061230a892cc302dfa74a7e765740f363cd7a27fa96119b2'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected_archive

with tarfile.open(archive, 'r:gz') as bundle:
    assert sorted(bundle.getnames()) == sorted([*manifest['files'], 'manifest.json'])
    copied_manifest = bundle.getmember('manifest.json')
    assert copied_manifest.isfile()
    assert bundle.extractfile(copied_manifest).read() == manifest_bytes
    verified = []
    for name, entry in manifest['files'].items():
        member = bundle.getmember(name)
        assert member.isfile() and member.size == entry['bytes']
        content = bundle.extractfile(member).read()
        assert hashlib.sha256(content).hexdigest() == entry['sha256']
        destination = (root / entry['restore_path']).resolve()
        assert destination.is_relative_to(root)
        if destination.exists():
            assert hashlib.sha256(destination.read_bytes()).hexdigest() == entry['sha256']
        verified.append((destination, content))
    for destination, content in verified:
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(content)

from app.model_checkpoint import load_checkpoint
model, metadata = load_checkpoint(
    root / 'artifacts/models/mahjong_discard_mlp_v3.pt',
    expected_contract=json.loads(
        (root / 'datasets/expanded_strict_v2/data_contract.json').read_text()
    ),
)
assert sum(p.numel() for p in model.parameters()) == 387746
print('Verified v3 restore and CPU load; existing identical artifacts retained')
PY
```

The exact restore command above was also exercised locally with the existing
valid files; they remained byte-identical. Installation uses the repository's
locked Python dependencies. Only macOS CPU restoration/loading was tested;
Windows/Linux/CUDA deployment remains unverified.

## Full evaluation and retraining

The inference bundle does not contain raw archives, expanded shards, historical
models or experiment weights, streaming predictions, optimizer state, or bulky
per-player diagnostic arrays. A checkout plus this bundle supports inference,
not a claim that the complete regression/audit pipeline can run without its
other local inputs.

For full replay/retraining, preserve/restore the Phase 1 and expanded Phase 2.1
dataset directories using their pinned source and contract checksums. The
versioned `artifacts/phase2_1/dataset_contract.json` is byte-identical to the
expanded dataset's contract. Follow the phase implementation reports for source
acquisition and a new training output directory; retraining does not recover the
exact already-frozen v3 checkpoint by assumption.

For reverification of the completed experiment, separately preserve the entire
local `artifacts/phase2*` trees and required dataset files, including ignored
prediction/diagnostic leaves and experiment weights. Frozen reports reference
these files by checksum and deliberately reject missing or changed evidence.
Resume additionally requires the matching ignored optimizer generations and
`training_resume*.json` pointers. Keep the original frozen JUnit XML; use a new
filename for later test runs.

Git contains source, tests, reports, bounded metadata/contracts/lineage, histories
and compact metrics/evidence. It excludes `.env*`, environments, raw corpus,
shards, trained `.pt` files, prediction streams, resume pointers, bulky analysis
JSON and transfer archives. Exclusion from Git does not delete the local files.
The original frozen verification certificates remain historical records; the
new README/ignore-policy documentation is not substituted into those records.

`.gitattributes` disables line-ending conversion for checksum-bound artifacts,
captured evidence and the bundle manifest. CSV exports retain their original
CRLF endings. Raw pytest evidence retains its emitted trailing spaces; only
those evidence paths receive relaxed trailing-space checks. Source code keeps
the normal whitespace rules. No frozen file was normalized to satisfy Git.

The pre-commit regression command used a separate evidence location:

```sh
.venv/bin/python -m pytest -q --junitxml=docs/evidence/commit_phases_2_2_2/regression.xml
```

Result: **279 passed in 64.29 seconds**, with zero failures/errors/skips.
The original documented Phase 2.2 result remains 279 passed in 73.65 seconds;
its frozen XML and SHA-256 are unchanged.
