# Inventaris file Phase 2

Semua path relatif terhadap root `mahjong-strategy-ai`. Tidak ada staging/commit/publishing. `datasets/` adalah untracked yang sudah ada sebelum pekerjaan Phase 2; data dan laporan Phase 1 dipertahankan.

## Empat file tracked yang diubah

| File | Tujuan |
| --- | --- |
| `.gitignore` | Mengabaikan bobot/checkpoint sementara agar tidak ter-publish tanpa sengaja. |
| `README.md` | Reproduksi Phase 2, artefak, advisory inference dan batasan. |
| `requirements.txt` | Menambahkan PyTorch 2.15.0. |
| `requirements-lock.txt` | Versi dependency aktual setelah instalasi PyTorch; dependency Phase 1 dipertahankan. |

## Source dan tes baru

| File | Tujuan |
| --- | --- |
| `app/mlp.py` | MLP asli, preprocessing bersama, masked logits/loss dan ranking legal. |
| `app/model_checkpoint.py` | Penyimpanan CPU state_dict, metadata, checksum dan compatibility validation. |
| `app/services/ai_prediction_service.py` | Service prediksi read-only dan struktur output/error. |
| `training/phase2_dataset.py` | Integrity gate, provenance/alignment, split match tetap dan diagnostik. |
| `training/metrics.py` | Top-K, masked NLL, Macro F1, support dan confusion matrix. |
| `training/baselines.py` | Prior training-only dan seeded uniform-legal baseline. |
| `training/train_mlp.py` | Training masked Behavior Cloning, validation selection dan early stopping. |
| `training/evaluate_mlp.py` | Freeze, evaluasi held-out, artifact publication/reverification/recovery. |
| `scripts/demo_ai_prediction.py` | CLI prediksi checkpoint riil pada sesi game nyata sampai ronde selesai. |
| `tests/test_phase2_dataset.py` | 17 tes integritas, alignment dan preprocessing. |
| `tests/test_phase2_metrics.py` | 7 tes metrik/baseline dengan hasil yang dihitung manual. |
| `tests/test_phase2_model.py` | 9 tes arsitektur, masking, loss dan gradient. |
| `tests/test_phase2_training.py` | 5 tes training, validation selection, seed dan early stopping. |
| `tests/test_phase2_checkpoint.py` | 11 tes save/load, hash, metadata dan compatibility. |
| `tests/test_phase2_inference.py` | 12 tes legalitas, loading sekali, state/weight safety dan post-meld. |
| `tests/test_phase2_evaluation.py` | 7 tes evaluasi, evidence tampering dan publication failure/recovery. |
| `tests/test_phase2_demo.py` | 1 tes full-round demo dengan checkpoint utama nyata. |

## Artefak lokal baru

| File | Tujuan |
| --- | --- |
| `artifacts/models/mahjong_discard_mlp.pt` | Bobot utama terlatih; ignored oleh Git, tetap tersedia lokal. |
| `artifacts/models/mahjong_discard_mlp.metadata.json` | Metadata model dan ringkasan validation/test. |
| `artifacts/phase2/data_validation.json` | Hasil integrity gate dan distribusi/split/provenance. |
| `artifacts/phase2/baseline_metrics.json` | Metrik validation dan test kedua baseline. |
| `artifacts/phase2/training_history.json` | Konfigurasi, device dan seluruh epoch training. |
| `artifacts/phase2/model_freeze.json` | Identitas checkpoint/config/data sebelum evaluasi test. |
| `artifacts/phase2/evaluation_metrics.json` | Hasil test final dan checksum bukti pendukung. |
| `artifacts/phase2/test_predictions.json` | Prediksi per dataset_row untuk kalkulasi independen. |
| `artifacts/phase2/per_class_metrics.csv` | Support, precision, recall dan F1 seluruh 34 kelas. |
| `artifacts/phase2/confusion_matrix.csv` | Confusion matrix 34 x 34. |
| `artifacts/phase2/live_demo.json` | Delapan prediksi nyata dan penyelesaian ronde seed 42. |
| `artifacts/phase2/phase1_preservation_guard.json` | Sembilan hash sumber/artefak Phase 1 yang dilindungi. |
| `artifacts/phase2/verification_summary.json` | Ringkasan final hasil tes, model, demo dan batasan. |

## Dokumentasi baru

| File | Tujuan |
| --- | --- |
| `docs/phase2_implementation_report.md` | Laporan final berbahasa Indonesia dengan 14 bagian wajib. |
| `docs/phase2_file_inventory.md` | Inventaris ini. |
| `docs/phase2_execution_ledger.md` | Preflight, keputusan implementasi, progres dan penutupan review. |
| `docs/superpowers/plans/2026-11-04-mahjong-strategy-ai-phase2.md` | Rencana eksekusi Phase 2. |
| `docs/evidence/phase2_code_review.md` | Review independen, dua perbaikan Important dan ruling. |

## Bukti eksekusi baru

Log RED adalah bukti kegagalan yang disengaja sebelum implementasi/perbaikan; hasil final terdapat pada full suite dan reverification.

- `docs/evidence/phase2_baselines.txt`
- `docs/evidence/phase2_checkpoint_red.txt`
- `docs/evidence/phase2_dataset_red.txt`
- `docs/evidence/phase2_demo_red.txt`
- `docs/evidence/phase2_evaluation.txt`
- `docs/evidence/phase2_evaluation_red.txt`
- `docs/evidence/phase2_evaluation_reverified.txt`
- `docs/evidence/phase2_full_suite.txt`
- `docs/evidence/phase2_full_suite.xml`
- `docs/evidence/phase2_inference_red.txt`
- `docs/evidence/phase2_live_demo.txt`
- `docs/evidence/phase2_metrics_red.txt`
- `docs/evidence/phase2_model_red.txt`
- `docs/evidence/phase2_phase1_baseline.txt`
- `docs/evidence/phase2_phase1_baseline.xml`
- `docs/evidence/phase2_review_green.txt`
- `docs/evidence/phase2_review_red.txt`
- `docs/evidence/phase2_tests.txt`
- `docs/evidence/phase2_tests_before_review.txt`
- `docs/evidence/phase2_torch_install.txt`
- `docs/evidence/phase2_training_red.txt`
- `docs/evidence/phase2_training_run.txt`

Hasil final: 90 tes Phase 1 + 69 tes Phase 2 = **159 passed**, tanpa failure/error/skip. Windows **NOT RUN**.
