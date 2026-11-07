# Phase4.3 — bounded execution plan / ledger

Binding requirements: supplied1419-line Phase4.3 prompt. BaseHEAD
28623736f6ce9d90eeb86dea98908b182631aad1, main; preserve Phase4.2 working tree
(2trackedmodified/80untracked), historical ZIPs/evidence and all original data.
No disk AGENTS found. No Git mutation, paid resource, public deployment, model
upload, DNS change or external account action is authorized.

## Chosen design

Online: one always-running VM, existing web+realPG images, Caddy HTTPS, one app
worker/instance, persistent volumes/secretfiles. Use a small Compose override,
not another application. Default binds remain loopback for staging/handoff.
Public publishing requires a separate authorized host/domain/account step.
Free sleeping PaaS is unsuitable for in-memory games; Renderfree also expires
PG after30days. Provider-neutralVM handoff; current DO2GiB/2vCPU pricing example
$18/mo from official table (domain/tax/backups extra), not a purchase commitment.

One verified compatibility gap: backend currently disables forwarded headers;
CSRF expected origin uses request.url.scheme. HTTPS termination therefore needs
an explicit trusted proxy IP list, defaultempty, validated withoutwildcards/CIDRs.
No changes to gameplay/security contracts. Local TLS client trusts only the
new staging CA; no global CA installation or browser certificate bypass.

Windows: PyInstalleronedir on realWindowsx64, exact CPUtorch/PyMahjongGB, original
assets, bundled trustedPG binaries. Keep readable source, no offline fake. A
small per-user launcher owns state/ports/processes; no globalservice. Build
requires a Windows builder and separately verified PGarchive/provenance/licenses.
No Windows VM registered on this Mac, so no exe/WindowsPASS will be fabricated.
EmbeddedCPython was considered but adds pip/_pth/DLL assembly; Nuitka adds compiler
complexity without execution evidence. One chosen workflow only.

Ruling: execute inline from the explicit user spec without another approval or
worktree/commit ceremony — authorized scope already concrete; cost if wrong:
localized packaging rework. One fresh final reviewer is explicitly requested.
Ruling: no publicURL/noWindowsbinary can be delivered without external permission
and an actual Windows environment. Finish meaningful local staging/build inputs
and report separate statuses; cost: a Windows verification/publication follow-up.

## Sequence / gates

1. [x] Read all requirements, sources/Settings/CSRF, current Git, prior contracts;
   inspect Windows environment and official hosting/toolchain/license sources.
2. [x] Fresh437Python/91Node baseline; beforehashes/devrecords/archivechecksums.
3. [x] RED production proxy/config/release tests; minimal GREEN settings/runner,
   HTTPS Compose/Caddy, runtime-only export extension; preserve Phase4.2 default.
4. [x] Fresh production-like export/build, real isolatedPG/TLS verification,
   CSRF/Securecookie/host/spoofing, fullround/model/history/restart/expiry, metrics.
5. [x] RED launcher state/ownership/ports/timeout/process/asset/manifest tests;
   GREEN Windows launcher plus native build recipe/spec/provenance gates.
6. [x] Build only if Windows actually available; otherwise source-build package
   and precise clean-Windows checklist, no mislabeled offline executable.
7. [x] Full regression, historicalcase reconciliation, oldsource/model/data/ZIP
   preservation, no-secret manifests; retain all old audit capability.
8. [x] Fresh independent review, Critical/Important regressions+fixes, affected/full
   reruns. Document honest limitations and unresolved prerequisites.
9. [x] Final docs/evidence, ownedprocess cleanup, readonlyGitcheck,21part report.

## Review focus

Trustedproxy boundary/defaultfalse; no backend/DB publicports; no scale/sleep;
TLSverifiedclient+Securecookie+CSRF; oldmodel/engine/UI unchanged; offline state
ownership, reparsepaths, credentials/ACLs, idempotentPG lifecycle, race-safe cleanup,
boundedreadywait; no misleading WindowsPASS or hidden internet install; archive
integrity and explicitbinaryprovenance/licensing inputs; historicalZIPimmutability.

## Evidence ledger

- VBox metadata probe with required localIPC permission:0registered/0runningVMs.
- Fresh baseline437Python/91Node; final471Python/91Node, zero failures/skips.
- One read-only independent review:1Important config-loss issue and1Minor public
  port guide issue; both fixed, RED/GREEN/full verification executed. No re-review.
- Runtime-only source ZIP:102sourcefiles,1919823bytes; all members/source hashes and
  pinned assets verified.63staged application/config files match final sources.
- Actual stagingHTTPS/realCPUv3/privatePG, fullround/restart/expiry/proxy spoofing
  tested. BrowserHTTP loopback rendering explicitly separate from TLS evidence.
- Task containers stopped; volumes retained; preview port removed.2257original
  eligible files checked:2252identical,5targeted changes;44DEV rows and4old delivery
  files exact. No Git mutation or public action.
- Final channel verdicts:ONLINE DEPLOYMENT READY;WINDOWS BUILD READY/NOT VERIFIED.
  Windows binaries/provenance/licensing/native runtime and public publication
  remain explicit external gates. No overallPASS/liveURL/WindowsZIP claimed.
