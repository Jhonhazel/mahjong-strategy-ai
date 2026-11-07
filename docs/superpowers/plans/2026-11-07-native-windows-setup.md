# Native Windows setup implementation plan

Goal: extend the existing native installer so a lecturer with CPython3.12x64 and
running local PostgreSQL uses setup-windows-native.cmd then fastapi dev main.py,
without Docker or manual SQL provisioning. Preserve the existing application.

Spec: user attachment 30cbb136-b376-4cee-8469-35b67b1f6393/Pasted text.txt.
Execute inline; one fresh read-only security review at the end.

## Design and constraints

Use scripts/lecturer_setup.py and one small scripts/native_postgres.py helper.
The helper stages immutable application credentials privately before privileged
DDL, creates a least-privilege role and owned database, and tags both with a
random project ownership token. Existing untagged resources are never claimed.
Retries reuse the staged credentials and validate ownership; ambiguous state fails
closed. PostgreSQL advisory locking serializes this explicit provisioning stage.
CREATE DATABASE runs in autocommit; role+role-comment creation is transactional.
No DROP, password reset, owner rewrite, global PG configuration or service action.

First-run uses127.0.0.1/5432, admin postgres, app mahjong_app/mahjong_phase3_dev by
default; prompt for local port/admin and hidden password only when provisioning.
Existing valid configuration needs no admin. All effective database targets must
be loopback. Use existing initialize_schema and actual application lifespan probe.
Persist .env only after validation; publish a privately staged complete file with
exclusive creation, never overwrite existing configuration. Native Windows ACLs
are applied before secret bytes, not inferred from chmod. POSIX permissions support
the disposable real-PG tests on this host.

Alternatives considered: write .env before DDL (makes incomplete setup look like
an existing valid configuration); regenerate on collision (breaks stable secrets);
reuse a server service/global policy (outside scope). The private immutable pending
record is the implementer's smallest recoverable choice, not a user-selected design.

Ruling: the user supplied the complete execution directive and no-Git policy;
proceed without new approval, worktree, commit or skill-generated Git ceremonies.
Cost if wrong: local implementation rework only. Native Windows cannot be certified
from Mac tests; ship a candidate source package with explicit unverified gates.

## Review focus

- No catalog-name collision may rotate passwords or take over another database.
- Failed .env publication/schema/auth must preserve staged app credentials and data.
- No administrator credential may reach config, CLI arguments or exception output.
- Same-CMD activation needs actual Windows testing; static review cannot certify it.
- Symlinks/junctions, concurrent provisioning and existing user files fail safely.

## Tasks

### 1. Preflight and fresh baseline

- [x] Record read-only Git/source/model/old-release hashes, P43-IA01 and DEV hashes.
- [x] Run existing full Python suite against established dedicated testPG and Node.
- [x] Inspect the native setup, requirements, assets/schema and release allowlists.

### 2. Provisioning and installer, RED to GREEN

Files: scripts/lecturer_setup.py; new scripts/native_postgres.py;
new tests/test_native_windows_setup.py (isolated real TCP PG + deterministic faults).

- [x] RED tests for real role/database creation, least privileges, schema/probe,
  persistence/repeat, wrong auth/unavailable PG, foreign resources, pending-state
  recovery and missing .env without privileged recurring startup.
- [x] Implement prepare_database(root, ...) returning stable URL/session secret;
  private staging/publication and local/owner validation. No application changes.
- [x] Integrate Windows-only setup, existing-config reuse, --check without DDL,
  dependency/CPU/import checks; preserve Mac/Compose and original launchers.
- [x] GREEN real PostgreSQL tests including insert/read/history after recreation
  of app resources, and deterministic disk/provisioning/permissions failures.

### 3. CMD, package and final verification

Files: new setup-windows-native.cmd/run-windows-native.cmd;
packaging/runtime_allowlist.json; README_START_HERE.md; append implementation report.

- [x] Setup CMD calls project Python setup and activate.bat without setlocal, checks
  project fastapi resolution; recurring CMD validates existing config then runs
  the original fastapi dev main.py, with no admin/provisioning/install path.
- [x] Add two launchers/helper and required shared helper to runtime allowlist;
  verify a new versioned runtime-only ZIP, preserving all historical ZIPs.
- [x] Run focused/full Python/Node suites, reconcile all489/91 identities, verify
  frozen assets/P43/engine/schema/UI/DEV and historical evidence unchanged.
- [x] One independent read-only security review; TDD-fix real Critical/Important
  findings once, rerun affected/full checks. No independent re-review.
- [x] Final beginner quick-start, minimal evidence/manifest, exact Git status and
  Indonesian18-part report. Windows native stays NOT YET VERIFIED absent host.

## Execution ledger

- Inspected current main/HEAD28623736f6ce9d90eeb86dea98908b182631aad1;
  uncommitted Phase4.2/4.3/P43-IA01 work preserved. No disk AGENTS found.
- Baseline489Python/91Node;32new cases. Final521Python/91Node, zero failures/skips.
  Focused101passed. ProperRED17failed; initial socket-path fixture error retained.
- Final: fixed inherited connection overrides and incomplete DACL restriction —
  eight review regressions RED→GREEN plus full suite. Native ACL not certified.
- Final: Ruling: cached external marker with newly created venv regraded from Minor
  to an installer blocker under the stated auto-install contract; reinstall only
  for a new venv. Cost if wrong: one extra first-run install, no data mutation.
- Final: Ruling: process DB/session overrides are rejected rather than silently
  changing the caller CMD or application settings. Cost: advanced users must clear
  conflicting variables before using this file-based native workflow.
- Final: Ruling: database creation without its ownership comment is ambiguous;
  fail closed retaining immutable pending credentials. Cost: operator inspection
  for that interruption window, never password reset/drop.
- Final: Ruling: actual Windows CMD/ACL/hardlink/dependency and hostile same-user
  filesystem guarantees cannot be certified on Mac; native verification gate remains.
  Server policy/logging stay unchanged. Cost: Windows candidate needs native acceptance.
- No independent re-review after fixes; no deferred minor remains. One review only.
- Task3 final:521Python passed72.55s;91Node passed125.249333ms;101focused passed.
  New versioned runtime-only ZIP105sourcefiles,1931947bytes; audit not rebuilt.
- External gates remain NOT RUN: actual Windows CMD environment inheritance,
  fresh-session launcher, native DACL/hardlink/junction/dependency/browser checks.
  Candidate source ready for controlled Windows acceptance, not certified release.
