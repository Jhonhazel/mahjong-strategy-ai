# Phase 2 execution ledger

## Preflight

- Current root: `mahjong-strategy-ai`; no local AGENTS.md; no existing Phase 2 code.
- Git now exists (unlike Phase 1): main / 49ad7a2. Tracked tree initially clean; pre-existing untracked datasets/ preserved. No Git mutations authorized.
- Existing `.venv`: CPython 3.12.10, NumPy 2.5.4, pytest 8.4.2, PyMahjongGB 1.4.0, macOS arm64. PyTorch initially absent.
- Fresh original Phase 1 suite: **90 passed in 15.85s**, separate `docs/evidence/phase2_phase1_baseline.{txt,xml}`. No Phase 1 report rewritten.
- Snapshot exact: READY/PASS run `84c2606383794fa8bc072d5edac7b252`; NPZ SHA `45303f98bd1d1bca4ac1dbc9228de398456644030bce8b6cb74945be21d86f4d`, manifest SHA `c496364986aba84efba65b19ae8c96e206bc7453d077ba7b0fc503e728687eb7`; all three recorded implementation hashes match.
- Actual arrays and sample groups match request: 1879 samples, 84 matches, train/validation/test 1564/213/102 samples and 72/7/5 matches, four player identities.
- PyTorch 2.15.0 has an official cp312 macOS arm64 wheel; minimal installation started in this `.venv` only.

## Interface ledger / rulings

- Data → training: flatten C-order obs only, direct float32; mask `[2:36]`; target `act - 2`. IDs and terminal scores are diagnostics only.
- Ruling: approved request supplies the design/permission; execute inline without repeated approvals or Git-dependent skill scripts. Cost: no separate design approval, but all choices and evidence recorded.
- Ruling: Phase 1 strict audit schema has no run ID. Verify contract/parity matching run IDs plus strict audit NPZ hash/count binding; never edit historical report to invent one.
- Ruling: use an app-level shared MLP/checkpoint module, so live inference does not depend on training loop code. Keep model weights out of the referee and bots.
- Ruling: class prior uses training-only Laplace smoothing (alpha=1) for finite NLL; deterministic prior tie-breaks; random baseline ranks a seeded legal permutation and uses uniform legal likelihood.
- Test split is only evaluated after configuration/checkpoint freeze; no architecture/seed search or test-driven changes.

## Progress

- Slice 1 complete: 17 integrity/alignment/preprocessing tests RED→GREEN. Approved snapshot unchanged; exact group sizes verified. Test split has no T3 examples, 33 supported classes.
- Slice 2 complete: 7 metric/baseline tests RED→GREEN with hand-calculated expectations. Validation prior Top-1 0.2253521127 / NLL 2.131096801; seeded random Top-1 0.1079812207. Test baselines deferred until primary freeze.
- Slice 3 complete: 9 model/loss tests and 5 trainer tests RED→GREEN; 11 checkpoint tests RED→GREEN. CPU state dictionaries and metadata fail-closed compatibility checks pass. CPU repeatability tested using tiny isolated fixtures; no performance claim from those fixtures.
- Actual primary training: one configuration, seed 2026, 1368→64→34 with dropout 0.2, AdamW lr .001 / weight decay .0001 / batch 32. MPS forward/backward probe passed. 18 epochs, 882 optimizer steps, 3.230458667s; selected epoch 8, stopped after 10 non-improving validation epochs. Best validation NLL 1.9891611879, Top-1 0.3192488263, Top-3 0.5915492958, Macro F1(34) 0.1829054073.
- Selected model reloaded on CPU: exact weight-content hash matches selected best state; validation NLL difference 2.200194937e-08. Primary test_evaluation remains None at this point; no primary test results used for implementation or selection.
- Slice 4 implementation complete: 12 inference tests and 2 evaluation tests RED→GREEN; evaluation unit runs use isolated temporary checkpoints, not the primary report directory. Advisory real-game demo finishes and validates legal suggestions / unchanged state, including post-meld turns.
- Awaiting one fresh read-only review before evaluating the primary frozen model on held-out test data.

## Final review / actual held-out evaluation

- Fresh review completed: 64 focused tests passed; no Critical/core training or inference issue. Two Important evaluation-report problems were reproduced independently, without reading primary test metrics.
- Final: fixed incomplete-evidence reverification — four missing/changed freeze/prediction cases RED→GREEN; checksums, row/score consistency and independent recalculation now required.
- Final: fixed PASS-before-metadata publication — injected write failure RED→GREEN; PASS published last, explicit same-frozen-model recovery tested. Seven evaluation tests PASS, then all 69 Phase 2 tests PASS.
- Primary model/configuration/weights stayed unchanged. Held-out evaluation occurred only after this fix pass: 102 samples / five matches, MLP Top-1 42/102 = 0.4117647059, Top-3 74/102 = 0.7254901961, NLL 1.6634954132, Macro F1(34) 0.2996361290, supported-class F1 0.3087160117, legal rate 1.0. Prior Top-1 34/102; seeded random Top-1 17/102. No tuning followed these results.
- Primary evaluation saved predictions were independently recalculated and `--verify-existing` passed with freeze, artifact and metadata checks. Checkpoint SHA e962b71b5bc031c2cfa307e9096fb763cb70e65240523a38e73254aa2563e855; weight-content hash matches selected state. Nine protected Phase 1 file hashes unchanged.
- Final suite: **159 passed in 19.87s**, including all 90 original tests and 69 Phase 2 tests; no failures/errors/skips. Compileall and git diff --check PASS. Git remains main / 49ad7a2; no staging/commit/publishing.
- Final: Ruling: preserve approved Phase 1 rules; hashes prove identity, not universal Mahjong correctness. Cost: Phase 1 limitations remain, explicitly disclosed.
- Final: Ruling: no alternate hyperparameter search or Phase 3/4 work. Cost: small-test uncertainty remains and later web/DB features are not implemented.
- Deferred minors: none. Windows NOT RUN. Phase 2 PASS / READY FOR PHASE 3 with the limited verified model-quality scope.
