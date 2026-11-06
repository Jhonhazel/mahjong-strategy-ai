# Phase 4 implementation plan

Spec: docs/phase4_design_spec.md. User supplies the design direction and explicitly
requires end-to-end implementation without stopping for a proposal. Execute
inline with TDD and one fresh final reviewer; preserve current main working tree.
No worktree/branch/Git mutations or approval ceremony can override that authority.

## Tasks

1. Preflight/baseline: inspect exact source/PDF/contracts, protect 1,999 old files,
   snapshot dev history read-only, run original 370 tests with real PG. Save all
   results under phase 4; do not claim the historical count as a new run.
2. Tile/assets RED→GREEN: new tile_catalog.py and original SVG/catalog generator;
   local sprite + safe tile renderer. Preserve W/T/B/F/J/H meanings and hidden
   backs; unknown/XSS-safe handling and accessible labels. Test all 42 codes,
   deterministic artifacts, no external assets and useful contrast.
3. Controller RED→GREEN: pure board/selection/settings/result projection and
   request coordinator with injected HTTP/render boundaries. Exact server IDs,
   duplicate tiles, all claims, uint 53 seed, busy guard, GET sequencing,
   uncertain-action reconciliation and errors. Test delayed responses and 409.
4. AI RED→GREEN: explicit predict, CSRF/payload, post-save GET verification,
   same-context advice only, saved-but-historical notice, no auto actions, no
   success on failed/uncertain saving. Use Top 3 order and actual phase/version.
5. Presentation RED→GREEN: shared CSS tokens/navigation, base/Jinja tile macros,
   Home/Contact/history/detail, game table/hand/actions/advisor/results. Keep
   stable phase 3 entrypoints and legal-action DOM/form/route contracts. Real PG
   page/history security tests; no fake identities.
6. Live verification: Python-hosted real FastAPI/Uvicorn+testPG and Node controller
   driver for actual model/round/CRD behavior. Then actual browser gameplay,
   full round, claims, keyboard, two-tab staleness, history detail/delete and
   session errors. Inspect1440/1280/1024/768/390/360 target layouts and reduced
   motion/zoom/overflow. Capture real screenshots; fix actual visual defects.
7. Final fresh review: scope all new UI code/templates/tests, known race/privacy/
   accessibility risks below; one focused fix pass RED→GREEN, then all old/new
   tests and JUnit identity reconciliation. No post-fix reviewer approval claim
   unless performed.
8. Finish: compare protected hashes/checkpoint/dev data/Git, syntax/pip checks,
   asset/performance observations, 25-section Indonesian implementation report,
   inventory/test matrix/UAS mapping and verification JSON. No final PDF/video,
   no staging/commit/push/deployment. Stop with actual remaining limitations.

## Shared interfaces

- Catalog → SVG/JS/Jinja renderers: one code/label/symbol map, fixed allowlist.
- HTTP client → controller: get/create/action/predict/session/owned-delete with
  structured status errors, CSRF and same-origin cookie semantics.
- Controller → view renderer: one current view, selected ID/index, pending
  operation, prediction, saved notice and message; renderer does not mutate view.
- Server actions → tile/action controls: member lookup only; no client decoding.
- Prediction → advisor/hand: server game/turn must equal latest verified view;
  stale committed results retain history identity only.
- History → progressively enhanced deletion: existing protected POST remains,
  JS confirms and awaits actual authorized deletion before refreshing the list.

## Review Focus

- A successful prediction followed by failed/late confirmation must retain its
  saved identity while never highlighting a stale/current-unverified hand.
- Old GETs, 409 and uncertain mutation outcomes must not restore old turn tokens,
  retry an action, clear a newer request's busy guard or double-submit.
- Duplicate tiles, competing Chi and hidden ANGANG must render correctly using
  only public fields; no calculated legality or fabricated chronology.
- Malformed/hostile labels/codes, owner isolation and delete/session failures
  must remain escaped/CSRF-protected and never imply a successful mutation.
- At 360 px/zoom/keyboard/reduced-motion, hand/claims/results/history remain
  operable without page overflow, focus loss or controls hidden behind panels.
