# Independent Phase 2.2 code review

Reviewer: fresh-context `phase2_2_final_review` agent, GPT-6 Astra, high reasoning. Scope: Phase 2.2 source, specification, implementation plan, ledger and focused temporary reproductions. No repository mutations, primary training, full audit or full-suite execution by the reviewer. The author's pre-review suite was264/264.

Verdict before fixes: **ready only after fixes**. No Critical findings; four Important findings; no deferred Minor findings.

1. **Frozen development evidence was not fully verified** (`training/optimization_finalize.py`, original line86). A tampered development prediction leaf still returned final PASS because the frozen branch only checked `development/metrics.json`, then repeated retrospective inference. Require development comparison/inventory verification on frozen resume and reverification.
2. **Early verification failure left stale PASS** (`training/optimization_evaluation.py`, original line105; finalizer original line78). Checksum/identity checks preceded the exception boundary. After a successful verification, corruption raised an error while `reverification.json` retained PASS. Every verification attempt must publish RUNNING then its own PASS/FAIL, including early failures.
3. **Diagnostics could overwrite frozen grouped lineage** (`training/optimization_analysis.py`, original line121). An ungrouped diagnostic rerun overwrote authoritative lineage before an injected model-load failure, even with protocol/freeze markers present. Reject protocol-bound outputs before any write and reject protected older artifact/dataset paths.
4. **Regression evidence accepted an incomplete actual suite** (`training/optimization_finalize.py`, original line24). Removing all11 `test_phase2_1_evaluation` cases from the real264-case report still passed the218-case/representative-family gate. Reconcile unique JUnit identities with a fresh complete test collection, rejecting missing or duplicate cases.

The reviewer inspected normal fold/seed pairing, bounded metadata architecture checks before deserialization, and training resume identities without finding another blocking defect in those paths.

Declined judgments and author dispositions:

- Final quality/promotion/pending reporting: reserved for completed actual experiments and final execution evidence.
- External generalization/full five-fold coverage: the approved protocol explicitly uses internal development and two folds of five; neither stronger claim is made.
- Coordinated malicious rewriting of all hashes/manifests: local checksums establish consistency, not cryptographic authorship or protection against a writer replacing the entire evidence chain.
- Standalone promotion-helper duplicate pairs: normal orchestration constructs the prescribed distinct three pairs; selection is based on that frozen matrix, not arbitrary helper input.

Author fix evidence: all four findings reproduced by10 failing targeted tests in `review_red.txt`. A further regression test caught a wrapper that could replace a valid frozen result on a rejected duplicate invocation (`review_wrapper_red.txt`); rejected attempts now have a separate status record. The fix pass is verified by the focused/full-suite evidence and final execution ledger. No second reviewer pass was requested.

The regression-inventory test also runs with a caller's `PYTEST_ADDOPTS` excluding the11 evaluation cases. This exposed a filtered expected inventory (`review_inventory_filter_red.txt`). Collection now removes that selection environment variable and overrides configured `addopts`; the same test confirms both the missing-family and duplicate-case rejections (`review_inventory_filter_green.txt`:2/2).

The same fix pass follows referenced evidence through all eight experiments' model/metadata/history files and the original JUnit XML. Four additional corruption cases were observed failing before the checks were added (`review_evidence_chain_red.txt`); the complete focused/full results after these checks are recorded separately. These extensions preserve the frozen experiment protocol and selection criterion.
