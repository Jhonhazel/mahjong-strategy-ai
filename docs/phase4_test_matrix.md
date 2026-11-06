# Phase 4 test matrix

Final: 399 pytest passed, 0 failed, 0 errors, 0 skipped;63.78 s (stdout), 63.770 s (JUnit).
Baseline 370 passed 59.98 s. Original 279 Phase 1–2.2 +91 Phase 3 preserved by exact
classname/name multiset comparison.29 new pytest cases include 6 wrappers executing
66 Node cases; do not double-count them as 465 independent cases.

| Area | Coverage | Actual evidence |
|---|---|---|
| Tiles |All 42 codes, back, unknown, labels, dupes, XSS, deterministic SVG/catalog |test_phase4_assets.py;tiles.test.mjs;contracts.py |
| Seats/public state |All 4 human seats, relative positions, hiddenANGANG, publicmelds/rivers/flowers |model.test.mjs;view.test.mjs |
| Settings |Seat/wind 0–3, flowersboolean, null/randomseed, uint 53 boundary/rejection |model.test.mjs;pages.pytests;actualbrowserunsafe seed |
| Actions |All 8 servertypes, exactIDs, duplicateindices, selection+confirm, doubleclick |controller.test.mjs;live_driver;browserChi/Peng |
| Request races |LateGET, oldfinally, busyguard, 409, uncertainaction/noPOSTretry |controller.test.mjs |
| AI |ExplicitPOST, realv 3, Top 3 order, legalmembership, noautomaticmove, state/weightimmutability |controller/http/viewtests;realTCP;oldASGIworkflow |
| Stale/save |Game/turnchange, repeatpending, manualrefresh 503, savednoticeafterfailedGET |controller 30 cases;review_advice_protocol_red→green |
| Bad success |Missing/mismatchedUUID/context/model/phase/score/Top 3;delete200/201/202 rejected |review_advice_protocol_red18 fail→GREEN 38 pass |
| Null/expired view |Winner/score/ID/public/handcleared |review_view_red→green;actualpostfixbrowser 404 |
| History |Realownedpaging/detail, Top 3, tables, completeclosedJSON, CSRF/delete |9 pagescases, 6 deletionNodecases, oldsecurity/PGtests, browser |
| Contact |Explicitunverified/empty, verifiedsynthetictextescaped, nofabrication |newpages+unchangedPhase 3 pages |
| Security |Sameorigin/cookie/CSRF, CSP, noinnerHTML/eval/storage, headers, ownerisolation |HTTP/contracttests;91 Phase 3 cases;browser401/404/409 |
| Responsive |5 pages×6 widths, nooverflow;44 pxtarget;14 tilesat705/768 edgeaccessible |browser_verification.json;browser_review_verification.json |
| Accessibility |Keyboardtile+Chi, explicitlabels, focus, 7 contrastpairs, reduced-motionrule |tests+actualCUA;contrast_verification.json |
| PostgreSQL |Actualsave/read/delete, reuse, concurrency, rollback, schema, export/restore, restart |regression_final.xml;postgres_integration_evidence.json |
| Model/data |1,999 protectedhashes, v3 SHA/metadata/runtimeweights, 11 devrecords |preservation_final.json;postgres_final.json;controller_acceptance_final.json |

Node breakdown: tiles 5, model 10, HTTP 8, controller 30, view 7, deletion 6 =66.
New Python breakdown: assets 3, contracts 10, pages 9, live 1, Nodewrappers 6 =29.

The live TCP acceptance is a real two-round request workflow using shipped JS,
Uvicorn, v3 CPU, testPostgreSQL. Seed 42/seat 1/withoutflowers: 23 actions, Zimo 25 fan.
Seed 43/seat 1/flowers: 23 actions, draw. Both save/reuse/CRD and post-meld inference
are verified. Browser is separately proven: seed 42/seat 1: 23 actions;seed 43/seat 3/
flowers: 26 actions;post-fixrepeat: 23 actions. Outputs and score vectors retained.

Unverified: actual 200%browserzoom (IABshortcutnoeffect), reduced-motionruntime
emulation(hostfalse, rulepresent), physicalmobile/otherbrowsers/OS, cleaninstall,
formalWCAGaudit. These are limitations, never reported as PASS.

Fresh independent review requested changes; author verified/fixed all findings
throughRED→GREEN and final suite. No second reviewer approval is claimed.
See independent_review.md for initial grades and author regradings.


## Audit minor remediation — 6 November 2026

| Finding | Added checks | Result |
|---|---|---|
| P4-A01 | Foreign/older/null/noninteger/structural success, failed reconciliation, valid forward/equal/finished/claim transition |10new cases;original game/URL authoritative;one POST;GET reconciliation |
| P4-A02 | Ascending ranking, coherent wrong class/action mapping, valid descending and ties |4new cases;reject without sort/mutation/false trusted save |

RED5fail/39pass → focusedGREEN44pass. AllNode80pass (66old +14new),
0fail/cancel/skip. Pytest399pass,0fail/error/skip,64.64s;all399identities preserved.
The six existing wrappers execute80Node cases; do not add80 again to399.
New final JUnit: `evidence/phase4/audit_minor_fix_regression.xml`.
Real TCP two-round acceptance ran inside that suite;additional actual browser
smoke passed. Fresh scoped reviewer found0issues and reran44controller tests.
All earlier results above remain historical evidence;all earlier caveats remain.
