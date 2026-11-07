# Phase4.2 execution plan and ledger

Baseline: main, HEAD28623736f6ce9d90eeb86dea98908b182631aad1, clean tree.
User explicitly authorizes implementation/local packaging/testing, not Git mutation
or publishing. The supplied Phase4.2 prompt is the binding specification.

## Design and decisions

Primary: Docker Desktop/Compose, using real PostgreSQL and CPU PyTorch, since a
working Linux/arm64 Docker engine is available and avoids host C++/Postgres setup.
Secondary: native CPython3.12 setup with existing project-owned macOS PG helper
or explicitly supplied local TCP database (Windows). Preserve all application
source/semantics. Keep the small existing training.dataset_loader runtime import.
Generate a runtime ZIP from exact source-to-destination mappings, and a separate
audit ZIP of non-runtime source/data/evidence. No original files moved/deleted.
Include the owner's checksum-bound inference assets locally, with attribution;
no public publication or assertion of a new blanket redistribution license.

Ruling: execute inline from the detailed user spec without a new approval gate
or worktree/commit ceremonies — these conflict with explicit continuous execution
and no Git changes. Cost if wrong: localized packaging/script rework.
Ruling: native Windows and Windows Docker Desktop cannot be certified from this
Mac; implement launchers, test what is available, label the Windows matrix NOT
YET VERIFIED. Cost if wrong: Windows-specific defects need a Windows follow-up.

## Tasks / verification

1. [x] Read requirements/instructions, runtime sources, current state; inspect
   Docker, dependency metadata, bundle manifest, storage and licensing notices.
2. [x] Fresh baseline405Python/91Node; real PG/v3, new evidence paths.
3. [x] Inventory hashes/categories and fingerprint dev records before changes.
4. [x] RED tests: allowlist/import closure, deterministic ZIP/hash manifest,
   traversal/symlinks/missing assets/secret exclusions/output collisions;
   asset tampering/import refusal; persistent private native/Compose config.
5. [x] GREEN minimal builder/assets/setup, platform launchers/runtime dependency
   lock, Dockerfile/Compose/init script; no application changes.
6. [x] Build independent runtime and audit ZIP; verify correspondence/checksums.
7. [x] Fresh extraction/new venv/native PG: install own requirements and launch,
   actual health/pages, no original repo paths, idempotent setup/secret/history.
8. [x] Fresh Compose build actual Linux/arm64, isolated persistent PG and secrets,
   actual engine/v3/history/CSRF/ownership/deletion/complete rounds/browser UX.
9. [x] Full original Node/Python regressions plus new tests; exact identity
   reconciliation, source/model/dev-record integrity and package sizes/timings.
10. [x] One fresh independent review (authorized by user section29); confirmed
    Important/Critical fixes RED→GREEN, then affected/full verification.
11. [x] Final README/report/manifests/Git state, stop task-owned services only.

## Review focus

No secret/config/SQL/cluster/venv/Git inclusion; exact import/file closure;
Windows CMD quoting/exit statuses; localhost exposure and non-superuser app DB;
native repeated setup must preserve env/secret/history; deterministic archives
must reject unsafe paths/symlinks and output collisions; mandatory asset hashes;
fresh package must not import/read original repo; honest platform claims.

## Evidence / ledger

- Fresh Python baseline:405passed,0failed/errors/skipped,65.45s, existing warning1.
- Node baseline91passed; exact log under docs/evidence/phase4_2/.
- Docker Desktop4.43.2, engine28.3.2 Linux/arm64, Compose2.38.2 available.
- Existing checkout3.3GiB allocated; venv872MiB, datasets447MiB, artifacts427MiB.
- Runtime import analysis: app.web.runtime imports training.dataset_loader;
  that module imports stdlib + app.domain.exceptions only. Retain it unchanged.
- Initial18RED→18GREEN; extra asset-map/copy-race/launcher-port RED→GREEN.
- Compose actualRED: bind-init execution/psql14 meta-command; baked init image
  and compatible command GREEN on a new disposable project/volume.
- Independent reviewer found3Important; synthetic11RED→32focusedGREEN total.
  Engineering437Python/91Node; restored audit437Python/91Node;0fail/error/skip.
- Final runtime ZIP hash2d57ce03d6cc34d5c4103d3f75b95a8384f26e35aa96df25b43c3fa2d6da996b;
  exact tested payload79files. Native and Compose setup/repeat/persistence PASS.
- Original2177files:2175identical,README/.gitignore authorized;44devrecords stable.
- Owned services stopped; original cluster/three unrelated containers retained.
- Final delivery uses a new output directory; post-build member hashes and
  correspondence recorded in delivery/phase4_2/release_verification.json.
