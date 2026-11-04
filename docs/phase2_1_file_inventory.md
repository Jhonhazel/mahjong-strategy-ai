# Inventaris file Phase 2.1

Path relatif terhadap root `mahjong-strategy-ai`. Phase2 yang sudah unstaged sebelum pekerjaan ini dipertahankan. Tidak ada staging/commit/publishing.

## Shared files yang diperbarui

| File | Tujuan |
| --- | --- |
| `.gitignore` | Ignore checkpoint/resume generations dan prediksi besar, termasuk direktori reproduksi. |
| `README.md` | Pipeline full-corpus, command resume/train/eval/demo dan batasan. |
| `app/model_checkpoint.py` | Validasi backward-compatible parent/expanded identity, contract/shard digest dan metadata sebelum load. |
| `scripts/demo_ai_prediction.py` | Optional --contract untuk model expanded; default Phase2 dipertahankan. |

## Source baru

| File | Tujuan |
| --- | --- |
| `training/expanded_dataset.py` | Streaming strict replay seluruh corpus, commit shard/audit/manifest, progress/resume, integrity/quality/READY gate. |
| `training/expanded_training.py` | Sharded batch loader, streaming metrics, deterministic training/resume generations, learning curve/protocol dan selection freeze. |
| `training/expanded_evaluation.py` | Common locked test, baseline lama/prior/random, prediksi gzip JSONL, independent recalculation, subgroup/CI dan reverification. |

## Tes baru (59 total)

| File | Tujuan |
| --- | --- |
| `tests/test_phase2_1_expansion.py` | 23 tes sumber/replay/provenance/split/dedup/manifest/atomic recovery/disk/READY. |
| `tests/test_phase2_1_training.py` | 19 tes loader/metrics/learning curve/selection/epoch resume/contract gates. |
| `tests/test_phase2_1_checkpoint.py` | 6 tes provenance metadata, legacy compatibility dan full-round live model. |
| `tests/test_phase2_1_evaluation.py` | 11 tes common cohort, freeze/artifact tampering, fail-closed publication/recovery dan paired bootstrap. |

## Dokumentasi baru

| File | Tujuan |
| --- | --- |
| `docs/superpowers/plans/2026-11-04-mahjong-strategy-ai-phase2_1.md` | Rencana eksekusi dan review focus. |
| `docs/phase2_1_execution_ledger.md` | Preflight, interface/rulings, progress, review fixes dan hasil final. |
| `docs/phase2_1_implementation_report.md` | Laporan final 15 bagian berbahasa Indonesia. |
| `docs/phase2_1_file_inventory.md` | Inventaris ini. |
| `docs/evidence/phase2_1/code_review.md` | Satu review independen, tiga Important diperbaiki, ruling dan batasan. |

## Dataset dan model lokal

- `datasets/expanded_strict_v2/data_contract.json`, `progress.json`, `source_inventory.json`, `expansion_report.json`, `data_quality_report.json`, `partial_audit.json` / `revalidation.json`: dataset contract, cursor/inventory dan audit. READY contract adalah gate readiness; progress mencatat cursor source pass.
- `datasets/expanded_strict_v2/shards/*/{samples.npz,manifest.csv.gz,audit.jsonl,commit.json}`:349 transaksi, seluruh1.946.122 baris dan44.420 status sumber. Dataset diabaikan Git.
- `artifacts/models/mahjong_discard_mlp_v2.pt` dan `.metadata.json`: checkpoint final dan provenance/validation/test summary. Bobot .pt diabaikan Git.
- `artifacts/phase2_1/experiments/{curve_1000,curve_10000,curve_100000,full_original}/`: history, model, metadata, completed-epoch state dan generation pointer; bobot diabaikan Git.

## Ringkasan mesin baru

- `artifacts/phase2_1/baseline_metrics.json`
- `artifacts/phase2_1/confidence_intervals.json`
- `artifacts/phase2_1/confusion_matrix.csv`
- `artifacts/phase2_1/data_quality_report.json`
- `artifacts/phase2_1/dataset_contract.json`
- `artifacts/phase2_1/dataset_expansion_report.json`
- `artifacts/phase2_1/evaluation_metrics.json`
- `artifacts/phase2_1/experiment_comparison.json`
- `artifacts/phase2_1/final_data_audit.json`
- `artifacts/phase2_1/hardware_benchmark.json`
- `artifacts/phase2_1/independent_recalculation.json`
- `artifacts/phase2_1/learning_curve.csv`
- `artifacts/phase2_1/learning_curve.json`
- `artifacts/phase2_1/live_demo.json`
- `artifacts/phase2_1/loader_benchmark.json`
- `artifacts/phase2_1/milestone_15000.json`
- `artifacts/phase2_1/milestone_5000.json`
- `artifacts/phase2_1/milestone_600.json`
- `artifacts/phase2_1/model_freeze.json`
- `artifacts/phase2_1/original_data_validation.json`
- `artifacts/phase2_1/per_class_metrics.csv`
- `artifacts/phase2_1/preservation_after.json`
- `artifacts/phase2_1/preservation_before.json`
- `artifacts/phase2_1/protocol.json`
- `artifacts/phase2_1/reverification.json`
- `artifacts/phase2_1/selection_freeze.json`
- `artifacts/phase2_1/source_coverage.json`
- `artifacts/phase2_1/split_report.json`
- `artifacts/phase2_1/subgroup_metrics.json`
- `artifacts/phase2_1/test_predictions.jsonl.gz`
- `artifacts/phase2_1/training_history.json`
- `artifacts/phase2_1/verification_summary.json`

`test_predictions.jsonl.gz` besar diabaikan Git; JSON/CSV kecil tetap tersedia untuk review. Snapshot training .pt dan sementara juga diabaikan pada direktori reproduksi.

## Evidence baru

- `docs/evidence/phase2_1/archive_metadata_red.txt`
- `docs/evidence/phase2_1/audit_15000.txt`
- `docs/evidence/phase2_1/audit_5000.txt`
- `docs/evidence/phase2_1/audit_600.txt`
- `docs/evidence/phase2_1/baseline.txt`
- `docs/evidence/phase2_1/baseline.xml`
- `docs/evidence/phase2_1/checkpoint_green.txt`
- `docs/evidence/phase2_1/checkpoint_red.txt`
- `docs/evidence/phase2_1/evaluation.txt`
- `docs/evidence/phase2_1/evaluation_green.txt`
- `docs/evidence/phase2_1/evaluation_red.txt`
- `docs/evidence/phase2_1/evaluation_reverified.txt`
- `docs/evidence/phase2_1/expansion_15000.txt`
- `docs/evidence/phase2_1/expansion_5000.txt`
- `docs/evidence/phase2_1/expansion_600.txt`
- `docs/evidence/phase2_1/expansion_extended.txt`
- `docs/evidence/phase2_1/expansion_full.txt`
- `docs/evidence/phase2_1/expansion_green.txt`
- `docs/evidence/phase2_1/expansion_red.txt`
- `docs/evidence/phase2_1/experiment_red.txt`
- `docs/evidence/phase2_1/final_dataset_validation.txt`
- `docs/evidence/phase2_1/final_dataset_validation_plain.txt`
- `docs/evidence/phase2_1/focused.txt`
- `docs/evidence/phase2_1/frozen_metadata_red.txt`
- `docs/evidence/phase2_1/full_suite.txt`
- `docs/evidence/phase2_1/full_suite.xml`
- `docs/evidence/phase2_1/live_demo.txt`
- `docs/evidence/phase2_1/pre_review_full.txt`
- `docs/evidence/phase2_1/pre_review_full.xml`
- `docs/evidence/phase2_1/resume_generation_red.txt`
- `docs/evidence/phase2_1/review_green.txt`
- `docs/evidence/phase2_1/review_red.txt`
- `docs/evidence/phase2_1/training_checkpoint_green.txt`
- `docs/evidence/phase2_1/training_green.txt`
- `docs/evidence/phase2_1/training_red.txt`
- `docs/evidence/phase2_1/training_run.txt`

Log RED dan wrapper time yang gagal adalah bukti historis yang dipertahankan; hasil final218 passed /0 skipped dan audit Python/reverification PASS dicantumkan pada laporan.
