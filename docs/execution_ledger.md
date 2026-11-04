# Phase 1 execution ledger

## Preflight (2026-11-04)

- Actual root: `mahjong-strategy-ai`, initially empty; no local AGENTS.md, README, code, tests, or Git metadata. No baseline tests exist.
- macOS arm64; CPython 3.12 available; default python3 is 3.13, so use `.venv/bin/python` explicitly.
- User's pasted request governs implementation and overrides unrelated monorepo instructions and example Git commands in the historical plan.
- Historical approved documents copied verbatim into `docs/superpowers/` and `docs/`.
- Ruling: no Git initialization, branch/worktree changes, staging, commits, or publishing; record progress here instead of Git-dependent skill scripts. Cost: no Git diff/history is available.
- Ruling: the approved design and implementation directive already authorize execution; no repeat design approval or planning-only stop. Implement Tasks 1–8 inline with focused RED/GREEN evidence.

## Interface preflight

| Producer → consumer | Contract / ruling |
| --- | --- |
| Task 1 → 3 | Actual module is `MahjongGB`, distribution `PyMahjongGB==1.4.0`; use supported pip path first. |
| Task 2 → 4,5,6,7 | Canonical 34 tiles and 235 actions shared; verify source ordering before encoder implementation. |
| Task 3 → 4,5,6 | Only `ERROR_NOT_WIN` becomes a normal negative result; invalid state and runtime errors remain visible. |
| Task 4 → 5,7 | Same strict observer for serving and log re-extraction. Historical NPZ parity and re-extraction parity must be reported separately. |
| Task 5 → 6,8 | Five engine phases; service pauses on every human discard and nontrivial human claim. |
| Task 6 → later API | Per-session lock plus expected turn token prevents duplicate submissions. No web/API implementation in Phase 1. |
| Task 7 → Phase 2 | Only accepted samples with explicit match identity; group contract prevents split leakage. No model training. |

## Progress

- Task 1 complete: CPython 3.12.10 `.venv`; unpatched pip build PyMahjongGB 1.4.0; environment test observed RED (missing module), then GREEN. Real Nine Gates=92, shanten=0; `datasets/environment_report.json`.
- Task 2 complete: 27 domain tests RED (missing implementation), then GREEN. All 235 actions independently conform to published FeatureAgent code (AST-isolated constants/codecs, no model execution).
- Task 3 complete: 9 fan tests RED, then GREEN; exact 8-fan Chicken Hand added. Source C++ confirms only ERROR_NOT_WIN is normal; MahjongShanten already covers all special forms. One proposed fixture omitted a real Kong; native source correctly cleared its flag, so fixture corrected, not library behavior.
- Task 4 complete: 10 observer tests RED, then GREEN; shapes/dtypes, public refresh, claim masks, hidden Kong, fourth-tile handling.
- Task 5 complete: 9 focused tests RED, then GREEN; `200 complete rounds` passed in 11.17s, checking physical tile counts at every action. Flower-after-Kong regression observed RED then GREEN against WMO rule 46.
- Task 6 complete: service/bot tests RED, then GREEN; real 20-thread race gives 1 accepted / 19 stale; capacity, TTL, delete, shutdown drain tested.
- Task 7: loader RED→GREEN with actual local HTTP (503 twice, truncated response once, success on fourth attempt); sandbox bind restriction resolved with authorized targeted escalation. Audit RED→GREEN; real legacy audit deliberately FAILS validation: 28 individual files / 576868 rows, 13 illegal mask labels. Both aggregates verified by full row-fingerprint multisets, excluded from sum.
- Task 7 parity: real source match observer/referee comparison RED→GREEN. Initial 60-game gate failed honestly (23 verified); fixed duplicated UID roster handling with real regression (one uid can occupy two explicit seats), reached 46; fixed HUANG score location via real RED→GREEN regression. Expanded explicit scope to first 100 archive entries (no success-only sampling): 84 verified complete matches, 16 source RE/WA exclusions, 0 failed replay, 4482 decisions compared, 0 differences; 1879 accepted tracked-seat samples. All original NPZ excluded for training; historical diagnosis is separate.
- Task 8 complete: real automated human-vs-three-bot CLI RED→GREEN; seed 42 evidence saved. Direct file invocation initially failed imports; regression RED→GREEN after project-relative bootstrap.

## Rulings and corrections

- Ruling: keep an empty workspace without Git, as authorized; do not run skill scripts that stage/commit/worktree. Cost: no version-control diff is available.
- Ruling: use standard unpatched PyPI installation, not the historical custom compiler patch. Cost: Windows build remains unverified here.
- Ruling: adopt verified Botzone segmented walls (seat draws its own segment backwards, round ends when the required drawer's segment is exhausted). This differs from a literal global-zero reading of the design and matches actual source games, including HUANG with tiles elsewhere. Cost: this is Botzone MCR wall scheduling, not a physical table wall simulation.
- Ruling: all three non-discarders respond to claim windows, including automatic Pass-only responses; the session still pauses exactly as specified. Cost: turn numbers count pass submissions as well as other actions.
- Ruling: distinguish `ijcai2026_mcr_v1_strict` from the historical encoder, refresh all public planes, and re-extract with the same runtime observer. Cost: original NPZ cannot be used with this serving representation.
- Ruling: require expected_turn_number even though the historical signature defaulted it to None. No existing clients exist; optional tokens cannot prevent repeated identical legal actions on later turns. Cost: later API clients must send the token returned in PublicPlayerView.
- Ruling: record every malformed/error source game, exclude the entire game, and verify a deterministic archive-order scope. Cost: acceptance applies only to the explicit strict subset; no full-corpus claim.
- Ruling: fourth-tile known count includes hand + public + incoming exactly once, but native scoring clears Last Tile for concealed duplicates and infers an exposed own pung. Cost: the flag alone is not proof of an awarded fan; tests assert actual native results.
- Ruling: replacing a flower after a Kong clears the replacement-Kong fan context, per WMO rules. Both engine and private observer updated; regression passed.

## Final review and fix pass

- Fresh read-only reviewer dispatched per executing-plans/requesting-code-review; 42 focused tests passed, 2 slow deselected. No gameplay/privacy/session blocker; three Important data-report/gate issues, no Critical or Minor findings.
- Final: fixed stale READY on absent archive — `test_missing_archive_invalidates_previous_ready_artifacts` RED→GREEN. BLOCKED before source I/O, matching run IDs, atomic JSON, READY last. Additional real filesystem publication failure regression also RED→GREEN.
- Final: fixed duplicate match identities inflating threshold — `test_duplicate_real_match_cannot_satisfy_distinct_match_gate` RED→GREEN. Deduplicate identical identity, block conflicting identity, gate distinct verified and accepted match groups.
- Final: fixed scalar action escaping audit report — `test_scalar_action_replaces_stale_audit_pass_with_failure` RED→GREEN. Validate dimensionality before len; always publish malformed-array FAIL.
- Final: Ruling: reviewer set aside production deployment and Phase 2–4 work — preserve user-authorized Phase 1 only. Cost: those later capabilities are intentionally unavailable.
- Deferred minors: none. No second review or Git operations; one fix pass verified by tests. Final complete-suite results recorded in `docs/evidence/full-suite.txt` and `pytest-results.xml`.

- Final verification complete: full suite 90/90 passed in 16.06s, 0 failures/errors/skips; 84 unique complete matches / 4482 exact decisions / 1879 accepted samples; strict audit PASS, original NPZ rejected with 13 illegal labels. Source/sample/manifest hashes and report/contract run identity checked. Phase 1 PASS for verified macOS arm64 scope; Windows NOT RUN.
