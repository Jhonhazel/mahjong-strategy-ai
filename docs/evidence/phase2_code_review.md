# Independent Phase 2 review and fix pass

Fresh read-only reviewer `phase2_review`, 4 November 2026. Review ran 64 focused Phase 2 tests successfully, verified primary CPU checkpoint reload and selected-state hash, and preserved primary `test_evaluation=None` until the review was finished. It did not evaluate or expose primary held-out metrics.

No Critical findings. Core data validation, masked training, metrics, portable checkpoint loading and advisory inference were assessed as sound. Two Important findings were reproduced on independent temporary checkpoint fixtures:

1. **Reverification could certify incomplete evidence.** Missing freeze or corrupt/empty predictions were not read before returning PASS. Regressions `test_reverification_rejects_missing_or_changed_saved_evidence` (four cases) were RED, then GREEN. Verification now requires the original freeze/configuration/data identity, checks all required artifact and metadata hashes, validates saved row identities/scores against actual inference, and independently recalculates saved metrics.
2. **PASS preceded metadata publication.** An injected metadata write failure left a successful evaluation report with incomplete model metadata. `test_metadata_write_failure_cannot_publish_pass_and_same_frozen_model_can_resume` was RED, then GREEN. PASS is now the final write; failures publish FAIL; explicit `--resume` accepts only the same frozen model/configuration/data. `--verify-existing` refuses incomplete metadata.

All seven evaluation tests passed after the fix. The full Phase 2 suite then passed 69 tests. Only after these fixes was the primary frozen checkpoint evaluated on the fixed held-out split. No model architecture, preprocessing, seed, weights or selection criterion changed in response to test performance. No second review was requested; the fixes were verified by regressions, the complete suite and real primary artifact reverification.

No Minor findings were deferred.

## Declined judgments and rulings

- Primary held-out quality was intentionally not reviewed before its first evaluation. Ruling: evaluate only after freeze/review, report actual metrics without an arbitrary accuracy gate.
- Phase 1 universal Mahjong correctness cannot be proved by Phase 2 hashes. Ruling: preserve the approved rules/encoder and verify all original regression tests; identity checks remain identity evidence.
- The reviewer did not independently rerun the entire Phase 1 suite. The root's final suite contains all 90 original tests.
- Alternative hyperparameters, production concurrency and Phases 3–4 were outside scope. Ruling: no extra search, infrastructure, website or database work; these capabilities remain future work.

No source, primary artifacts or historical reports were modified by the reviewer. No Git mutations or publishing occurred.
