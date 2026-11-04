# Independent Phase 2.1 review

One fresh read-only `phase2_1_review` reviewer, 4 November 2026. No primary held-out evaluation performed by reviewer. Focused normal-path suite: 51 passed in28.36s. No repository edits, Git operations or primary artifact mutations.

No Critical findings. Three Important findings were independently reproduced with disposable real-game fixtures:

1. **Checkpoint and checksum were not one transaction.** Replacing the state before its checksum lost the prior recoverable epoch when checksum publication failed. Fixed using immutable SHA-named generations and an atomic checksum/generation pointer committed last. Legacy successfully completed checkpoint states remain readable. `test_interrupted_resume_pointer_retains_previous_complete_checkpoint` reproduced the old checksum mismatch (RED), then GREEN. CPU resumed training still equals uninterrupted history and selected weights.
2. **Published inventory was consumed without matching audited commits.** Duplicating the first contract shard was accepted by ShardCorpus and yielded1410 rows despite declaring1161. Fixed by comparing complete ordered inventory, roles, split statistics, dataset/source identity, algorithm and current core implementation hashes against audited state before loading. Six duplicate/omitted/substituted shard/role/count/source-hash regression cases RED→GREEN.
3. **Missing initial source inventory could not recover.** Interruption after progress publication but before inventory publication caused every resume to fail. Fixed by rebuilding only a missing inventory from the freshly revalidated pinned archive and checking existing inventory exactly. `test_missing_initial_inventory_is_rebuilt_from_pinned_archive_on_resume` RED→GREEN; committed shards remain unchanged.

Fix pass: all59 Phase2.1 tests passed in21.29s; parent full regression **218 passed in47.64s**, and complete real expanded-data/raw-source audit PASS. Primary experiments use the same correctly generated contract/data; these fixes change corruption/failure handling, not model inputs, architecture, selection criterion or labels. No test-performance-driven code changes.

## Declined judgments and rulings

- Pending real experiments, final accuracy and report: finish with actual evidence; no fabricated or prospective PASS.
- All-seat population / CPU / original roles: approved ledger choices; disclose these changes when interpreting data-scaling comparisons.
- MPS/CUDA/Windows reproducibility: reviewer exercised CPU only; root benchmark exercised MPS; Windows remains NOT RUN.
- Power-loss durability / same-output concurrent writers: ordinary process interruption is covered, not fsync/power-loss or concurrent extraction. Run one extractor per output directory.
- Coordinated malicious rewriting of every hash/provenance artifact: not an external signature/trust system; checks catch ordinary corruption and inconsistent artifacts.
- Full original regression / preservation audit: owned and independently rerun by parent.
- Winning strength / unseen-player generalization /80–85%: cannot be inferred from classification-code correctness; report measured behavior-imitation metrics with limitations.

No Minor findings deferred. No second review dispatched; verified fixes by failing regressions followed by focused/full suites.
