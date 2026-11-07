# Audit/development archive — preserve before publishing

This separate owner-local archive preserves non-runtime tests, training source,
datasets, historical model candidates/reports, JUnit/browser evidence, experiment
contracts, plans and release-builder source. Original engineering files/Git history
remain in the original repository. No originals were moved or deleted.

Private `.env`, credentials/key files, SQL dumps/logs, the local database cluster,
Git internals, virtualenvs and generated caches are excluded. Do not treat this
research archive as an automatically approved public dataset release; respect
the attribution in THIRD_PARTY_NOTICES and the owner's publication decisions.

Runtime-required bytes are in the companion lecturer ZIP, including only the
promoted v3 weights, metadata and contract. Historical candidates remain here;
the v3 model is not duplicated. Each ZIP has RELEASE_MANIFEST.json with source
paths, byte sizes and SHA-256. The external release_manifest.json identifies both
ZIP hashes and the source correspondence. Verify before copying/restoring.
Existing root RELEASE_MANIFEST.json is preserved on rebuild under
manifests/source_RELEASE_MANIFEST.json; generated manifest destinations are
reserved and duplicate ZIP names are rejected. Audit inputs are restricted to
known development roots/top-level files, with backup/credential/config exclusions
and structured JSON secret checks. Unknown private root files are not distributed.

## Restore a development workspace

Extract both ZIPs into a new directory. Keep both manifests separately. Copy the
contents of the clean `mahjong-strategy-ai/` tree into the separate
`mahjong-strategy-ai-audit/` tree, excluding its RELEASE_MANIFEST.json. Runtime
paths and audit paths complement each other; do not overlay an existing checkout.
For example in macOS Terminal (after extraction):

```sh
# Use a new workspace; preserve the audit manifest before copying runtime files.
cp mahjong-strategy-ai-audit/RELEASE_MANIFEST.json audit-manifest-reference.json
cp -R mahjong-strategy-ai/. mahjong-strategy-ai-audit/
cd mahjong-strategy-ai-audit
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
```

The original archives plus manifests retain the reference bytes. Windows native development install
of the historical macOS lock is not verified (uvloop is platform-specific);
use the runtime lock for operation. Full regression is verified in the original
engineering environment, not claimed from every restored platform.

Tests use their unchanged root-relative paths. Set MAHJONG_TEST_DATABASE_URL to
an explicitly provisioned, disposable PostgreSQL database ending `_test`.
Marker-protected admin/export tests additionally require the existing project
helper's isolated cluster. Missing integration prerequisites produce explicit
skips and cannot establish full PASS. Never point tests at production/dev data.

```sh
node --test tests/frontend/*.test.mjs
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase4_2/my_reproduction.xml
```

Use a new evidence filename. Historical corpus, original feature reference,
frozen model/evaluation/optimizer artifacts are preserved where available and
must match their manifests; do not regenerate frozen evidence to obtain green.
This archive is a snapshot, not a claim that historical external services remain
available forever. For provenance consult the phase reports and original Git log.

Rebuild from the restored engineering layout:

```sh
.venv/bin/python -m scripts.build_lecturer_release --output delivery/new-release
```

The builder refuses existing output paths, verifies all v3 hashes, checks local
Python/JS imports, uses the explicit packaging/runtime_allowlist.json, and creates
fixed-timestamp ZIPs. It never copies `.git`/secrets or edits the source tree.
Rebuilding the same snapshot yields identical ZIP bytes; adding new evidence
intentionally changes the audit snapshot. Distribution metadata/publishing still
requires separate authorization. See docs/phase4_2_implementation_report.md and
artifacts/phase4_2/verification_summary.json for actual platform results/caveats.
