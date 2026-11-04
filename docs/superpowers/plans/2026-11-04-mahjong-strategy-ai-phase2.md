# Mahjong Strategy AI Phase 2 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline with focused TDD. User authorization forbids Git publishing/branch operations and any Phase 1 data regeneration; these override example skill Git steps.

**Goal:** Train and evaluate an original masked-discard MLP on the approved strict corpus, then expose advisory predictions from actual game states.

**Architecture:** Preserve Phase 1. Validate its pinned artifacts before preparing C-order float32 features and match groups. Train only on train/validation inputs; freeze the selected checkpoint before final test evaluation. Share the compact model/preprocessing/checkpoint boundary between training and the inference service.

**Tech stack:** Existing CPython 3.12 `.venv`, NumPy, pytest, native PyMahjongGB; add pinned PyTorch 2.15.0. No sklearn or web/DB framework needed.

**Spec:** User's full Phase 2 pasted request, 4 November 2026; current `datasets/data_contract.json` and `docs/phase1_implementation_report.md`.

## Constraints and decisions

- Snapshot: run `84c2606383794fa8bc072d5edac7b252`, 1879 samples / 84 matches, strict encoder `ijcai2026_mcr_v1_strict`; preserve all Phase 1 bytes.
- Splits reuse `partition_for_match`: train 72/1564, validation 7/213, test 5/102. Four known player identities; no unseen-player generalization claim.
- Input is only obs int8 `[38,4,9]` converted directly to float32 `[1368]` in C order; output 34 logits. Labels are `act - 2`, mask is `[2:36]`.
- One primary architecture: 1368 → 64 → 34, ReLU, dropout 0.2 (89,826 parameters). AdamW, lr 0.001, weight decay 0.0001, batch 32, max 80 epochs, patience 10, seed 2026. Select minimum validation NLL; no test tuning.
- Try real MPS operations first, then CUDA/CPU as available. Save cloned CPU state_dict; use weights_only=True for loading. Record actual environment/runtime/reproducibility limits.
- Phase 1 source/report/dataset files remain untouched. New reports under `artifacts/phase2/`, model artifacts under ignored `artifacts/models/`, new evidence files under `docs/evidence/phase2_*`.
- Git preflight: main / 49ad7a2, no tracked changes, pre-existing untracked datasets/. No stage/commit/push/branch operations.
- Strict audit has no run_id in its Phase 1 schema: bind it via the approved NPZ hash and sample count; require contract/parity run IDs to match. Do not invent a missing run ID.

## Review focus

1. Corrupted/self-consistent replacement artifacts must fail the approved snapshot gate; error reports must not leave stale PASS.
2. Manifest row permutation, duplicate semantic identity, and scalar arrays must not bypass alignment validation.
3. Empty masks, nonfinite logits, and fewer than three legal classes must be handled explicitly.
4. Training must not access test labels for selection; checkpoint weights must be cloned, metadata/hash mappings validated before deserialization.
5. Predictions from draw/post-meld states must leave game state/turn/weights unchanged and remain advisory.

## Execution slices

### 1. Approved data gate and preprocessing

- Create `training/phase2_dataset.py`, tests `tests/test_phase2_dataset.py`.
- `validate_dataset(root, report_path)` verifies hashes/contracts/provenance/alignment and returns a verified corpus. `prepare_split(corpus, name)` returns only features, labels, masks and row identities for one split.
- RED on malformed/copied real artifacts; GREEN on unchanged approved snapshot. Save data integrity and split/class/player/legality reports.

### 2. Metrics and baselines

- Create `training/metrics.py`, `training/baselines.py`, tests `tests/test_phase2_metrics.py`.
- Stable class-index tie breaks; Top-3 uses only available legal actions. Macro F1 across 34 and supported classes, 34x34 confusion matrix. Laplace-smoothed training-only class prior and seeded uniform legal ranking.
- RED with hand-calculated metrics / leakage / legality fixtures; GREEN then execute validation baselines. Final test baselines wait for model freeze.

### 3. Model, masked loss, training and checkpoint

- Create `app/mlp.py` for shared model/encoding/masking, `training/train_mlp.py` for training-only orchestration, `app/model_checkpoint.py` for validated portable artifact I/O.
- Tests `tests/test_phase2_model.py`, `test_phase2_training.py`, `test_phase2_checkpoint.py`: exact dimensions, loss/gradients, actual optimizer updates, early stop, copied best state, save/reload and incompatible/corrupt metadata rejection. Training API receives train/validation only.
- Execute the one primary real training run; save actual epoch history, best CPU checkpoint, metadata and validation evidence.

### 4. Frozen evaluation and live inference

- Create `training/evaluate_mlp.py`, `app/services/ai_prediction_service.py`, `scripts/demo_ai_prediction.py`.
- Tests `tests/test_phase2_inference.py`: masked Top-K, no legal action, model/version/dtype validation, actual draw/post-Chi/Peng game state, unchanged turn/view/weights, normal playthrough afterward.
- Freeze checkpoint/hash before held-out evaluation. Evaluate MLP and both baselines once on the fixed test split; independent metric recalculation verifies saved predictions.
- Demo actual saved model on a deterministic game and finish the round through normal session token protections.

### 5. Final verification and handoff

- Fresh read-only reviewer per executing-plans; fix Important/Critical findings with regressions, no broad extra features.
- Run focused Phase 2 tests, all Phase 1 regressions, full suite, compile checks, checkpoint reload and live demo; confirm original Phase 1 hashes and Git safety.
- Update README/dependency files minimally. Create `docs/phase2_implementation_report.md` with the user's 14 required sections and real metrics; declare readiness only from actual evidence.
