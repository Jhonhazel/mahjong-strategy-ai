# Independent Phase 1 review

Read-only reviewer: fresh-context `phase1_review`, 4 November 2026.

The reviewer found no Critical issue and no concrete gameplay, hidden-information, claim-resolution or session-locking blocker. Its focused verification ran 42 tests successfully, with two slow tests deselected. The root implementer separately ran the full suite, HTTP tests and 200-round stress test.

## Important findings and disposition

1. **Stale READY after missing replay archive.** Reviewer reproduced a missing source archive leaving prior PASS/READY reports unchanged. Root regression `test_missing_archive_invalidates_previous_ready_artifacts` reproduced RED, then GREEN. The verifier now publishes BLOCKED/RUNNING before source I/O, records archive hash errors, associates report/contract with a run ID, writes JSON atomically, and publishes READY last. Additional `test_artifact_write_failure_publishes_fail_and_blocked_contract` reproduced RED→GREEN using a real filesystem obstruction and preserved the obstructing file.
2. **Duplicate archive entries inflated complete-match gate.** Reviewer used one real source game under two filenames to satisfy a two-match threshold. Root regression `test_duplicate_real_match_cannot_satisfy_distinct_match_gate` reproduced RED→GREEN. Duplicate match identities are now excluded, conflicting payload identities block acceptance, and the gate counts distinct verified match IDs plus distinct accepted match groups. The real final scope remains 84 distinct complete matches.
3. **Scalar NPZ action preserved an old audit PASS.** Reviewer reproduced `len()` on a scalar action array escaping report publication. Root regression `test_scalar_action_replaces_stale_audit_pass_with_failure` reproduced RED→GREEN. Shape validation now rejects scalar actions with a domain error, then publishes the FAIL report atomically.

No Minor findings were deferred. No second review was requested; the fixes were verified through regressions and a fresh full-suite run, per the execution workflow.

## Review limitations / rulings

- The reviewer did not independently rerun the whole raw corpus audit, 200-round stress, HTTP suite, or Windows build. The root's actual commands cover the first three; Windows remains NOT RUN.
- Production deployment hardening and later-phase web/ML work were outside review. Ruling: preserve the user's Phase 1 scope; these are future work, not incomplete Phase 1 implementation.
- There is no Git base/head/diff because the workspace began without Git metadata. The review inspected the current new implementation without creating Git state.
