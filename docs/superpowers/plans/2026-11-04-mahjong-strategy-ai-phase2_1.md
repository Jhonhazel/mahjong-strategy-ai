# Phase 2.1 execution plan

Authority: user attachment `28817340-07b9-438c-b99b-5e2cb63b8f1b/Pasted text.txt` (Phase 2.1 master prompt). Execute inline, no Git mutations or publishing; preserve original artifacts and old tests.

1. **Baseline/preservation:** verify original corpus and checkpoint, hash protected artifacts, run all 159 existing tests, measure resources/archive. Expected: original pins match and fresh suite passes.
2. **Streaming expansion (TDD):** `training/expanded_dataset.py`, new expansion tests. Validate pinned archive before replay; deterministic bounded batches; strict observer/referee replay on all four roster seats; one transaction directory per batch, hashes and commit written last; per-game audit including exclusions; resume committed batches without replay/double ingestion. Stop safely on storage failure. Milestones at approximately 600, 5,000, 15,000, full corpus. Expected: all attempted games accounted, no accepted mismatches, valid provenance, immutable historical match roles.
3. **Dataset publication/quality (TDD):** stream validation of every shard and manifest; sample identities distinguish ingestion duplicates from repeated features; aggregate parity, bias and split reports; READY last only after full validation. Expected: full source coverage if resources permit, zero illegal targets, group intersections empty, protected original test never in training.
4. **Bounded training/learning curve (TDD):** `training/expanded_training.py`, new tests. Shuffle shard/batch order reproducibly; transfer only batches; stream metrics; train/validation-only API; validation NLL selection, early stopping, atomic resumable training state; CPU checkpoint using existing MLP loader. Freeze selection policy and configs before experiments. Original architecture/config first; nested match-complete learning-curve subsets; a small validation-justified regularization comparison only. Expected: real updates and portable selected checkpoint, no test input to training.
5. **Frozen evaluation (TDD):** `training/expanded_evaluation.py`, new tests. Lock selected and comparison checkpoints before new test; shared fresh cohort for old/new/prior/random; saved predictions, independent recalculation, match bootstrap intervals, subgroup/per-class/confusion, checksums and PASS written last. No tuning after test. Expected: honest measured common-cohort comparisons and tamper rejection.
6. **Live integration/review/report:** reuse current prediction service; demo accepts optional new contract path while default stays compatible. Real full-round SELF_TURN/post-meld prediction, no mutation. One fresh read-only final reviewer, fix Important/Critical by RED→GREEN; focused and full regression, syntax/whitespace/hash guard; Indonesian 15-section report and reproduction commands.

## Interfaces

- Expansion → training: versioned READY sharded contract, gzip CSV manifests with shard-local rows, split roles `train`, `validation`, fresh `test`, `historical_test`; obs unchanged int8[38,4,9], mask bool[235], action int16 2–35.
- Original 84 match roles remain fixed; newly seen matches use `phase2.1-match-split-v1:` SHA-256 first8 big-endian modulo100 (<80/<90/else). Every seat of a match shares its role.
- Training → inference: unchanged 1368→64→34 MLP, existing portable state_dict/metadata schema plus explicit expanded provenance; historical-test counts stored separately. Dataset sample hash is a canonical shard-inventory digest, documented as such (no claim of a single NPZ).
- Training → evaluation: selected model/config/dataset frozen; validation NLL primary; fresh test never returned to experiment API.

## Review focus

Interrupted commit/publication; missing/corrupt source/shards/manifests; duplicate/conflicting IDs including untracked seats; old historical-test protection; sample/manifest tampering; premature READY/PASS; training resume identity/RNG/best-state isolation; common-cohort baseline fairness; unchanged legacy loader/game behavior.
