# UAS feedback revision implementation plan

Goal: extend the existing Mahjong Home/Contact/shared footer with accurate academic
content and local accessible charts, preserving the game/model/PostgreSQL systems.
Spec: user attachment abd829e2-8cb3-4862-a05c-046143162e14/Pasted text.txt.
Execute inline with TDD and one fresh final read-only review; no Git mutations.

## Design

Preserve hero, How It Works, CTA, jade/ivory/gold design, navigation and game JS.
Reuse the already verified runtime metadata for model/evaluation/training facts.
Generate one small config/home_research.public.json from frozen contract, quality
report and selected training history; verify provenance/checksums and34 support
counts against the training confusion matrix. Do not scan or change shards.

Actual promoted v3 uses fold0 E3_f0_s2026:1,400,549train/350,917validation. Its class
histogram is selected_train_metrics.per_class.support, not predicted_count. Original
corpus partitions1555412/196054/194388/268 sum1946122; label those Phase2.1, not the
v3 training fold. Metrics194388 are known retrospective evaluation, not a new blind
test or all1946122 corpus decisions. UID581 includes player/bot identities.

Charts: local server-rendered SVG donut for original partitions,34-row horizontal
bar chart and family donut for actual v3 train. Text legends/tables, controlled
rounding and scroll only within chart/table panels on narrow screens. No CDN/JS
dependency/inline styles. One bounded cached summary read with validation and safe
informative fallback; never load training data or another model per request.

Set equal role fields on five official roster members; preserve identity fields.
Hide the stale role notice only when configured roles are complete. Unverified or
partial alternate rosters keep truthful fallback. Shared normal-flow footer:
©2026Kelompok1, project and Universitas Bunda Mulia. Minimal body flex layout.

Ruling: user's detailed execution directive chooses implementation in the main
working tree; no new approval, worktree/branch/commit/deployment ceremony. Cost if
wrong: bounded frontend rework. Separate SQLite branch/worktree is untouched.

## Files / tasks

- [x] Preflight snapshot mainHEAD/source/model/DEV/old ZIPs and fresh fullPython/Node
  baseline in docs/evidence/uas_feedback_2026_11_10; check roster/source contracts.
- [x] RED tests: factual Home/cohorts/chart counts/provenance/malformed summary,
  equal verified roles and preserved fallback, one shared footer on5page types.
  Existing obsolete no-role assertions change to the newly authorized behavior;
  preserve test names/identities and strengthen assertions.
- [x] Add reproducible offline generator scripts/build_home_research_summary.py and
  small public artifact; validate sources and exclusive/check output. Runtime
  summary loading/validation/context stays in app/web/pages.py, no new service/API.
- [x] Minimal templates/CSS/config changes. If needed update smoke_online contact
  assertion, runtime allowlist and .dockerignore for the new required artifact.
- [x] GREEN affected tests; fullPython/Node; actual PostgreSQL/v3/game/History/CSRF
  smoke and browser1440/768/390 with screenshots. Verify no request-time corpus I/O.
- [x] Fresh independent review academic provenance/accuracy/UI/fallback/security;
  one focused RED→GREEN fix pass for real Important/Critical, no re-review.
- [x] New runtime-only candidate ZIP with source+model/member hash checks; no large
  audit rebuild. Final small report/evidence, source/model/DEV/old archive integrity,
  owned-preview cleanup and read-only Git check. Indonesian20-section final report.

## Review focus

- Corpus partition vs actual fold0 training, and268 vs194388 historical naming.
- Ground-truth support vs predictions; all34 canonical tile classes/family totals.
- CSP-compatible local charts, accessible numbers and page overflow at390px.
- Complete vs unverified/partial contact configurations, no invented contributions.
- Corrupt/missing summary must degrade truthfully without breaking game startup.

## Ledger

- Main d0a0168f578b5c00e83f45013972f4088d94dedd, initially clean. No disk AGENTS.
- Read-only evidence audit verified387746params, fold0 training histogram and source
  historySHA bacdb2dbc813c500d6bd36351652342a293966d4dc4a319837cc8bf7aaf9ea9d.
- PostgreSQL owned cluster running; no service or database change required.

## Final ledger

- Fresh baseline521Python/91Node; final543Python/91Node,0failure/error/skip.
  All521previous Python identities remain,+22new;91Nodeidentities unchanged.
- RED20failed/17passed; focusedfinal41passed. Fresh read-onlyreview found2Important
  (DockerCOPYmissing,alternateContactscopeclaim) and1Minor(rejectionwording); fixed
  with additionalRED1+3cases and finalfullregression. No secondreview.
- Realbrowser5pagetypes1440/768/390 without pageoverflow; realv3predict/save/detail.
  Realprocessrestartsmoke retained savedTESTHistory;task-ownedserversstopped.
- ReadonlyUTCcanonicalDEV comparison44/44identical;3frozenSHAunchanged.
  883preflightfileschecked,870identical,13intendedexistingchanges,0missing.
- Newruntime-onlycandidate106files/1941024bytes,allmemberhashes/sourceverified,
  extractedpackagedHomeandassetsverified; oldZIPs/auditevidenceuntouched.
- NativeWindowsandDockerimagebuildNOTRUN;nodeploymentorGitmutation.
