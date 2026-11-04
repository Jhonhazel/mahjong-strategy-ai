# Inventory file Phase 2.2

Source Phase2/2.1 yang sebelumnya untracked juga diperluas secara terbatas pada phase ini. Git status tidak dapat membedakan seluruh perubahan antar fase; tabel berikut menyatakan scope Phase2.2 secara eksplisit. Tidak ada ekstraksi/filtering/mutasi dataset lama.1,624 file dilindungi cocok dengan preservation manifest.

## Source, tests dan dokumentasi

| Path | Fungsi/perubahan |
| --- | --- |
| app/mlp.py | Factory MLP bounded; default/state_dict lama tetap |
| app/model_checkpoint.py | Metadata arsitektur/development dan hash tensor; portable CPU load |
| training/expanded_training.py | Remap train+validation opsional, spec/resume, finite gradient, retensi generasi baru |
| training/expanded_evaluation.py | Saved single-model recalculation dan bootstrap dengan nama actual |
| training/optimization_data.py | Audit read-only, role/lineage, grouping input-only dan protected output |
| training/optimization_analysis.py | Rank/calibration/UID/phase/legal-choice dan repetition diagnostics |
| training/optimization_runner.py | Frozen registry/matrix8 run, one-axis E3, paired development/promotion |
| training/optimization_evaluation.py | Candidate export/freeze, same-cohort prediction/recalculation/cluster bootstrap |
| training/optimization_finalize.py | Complete test inventory, live/latency, selection freeze, retro dan reverify |
| tests/test_phase2_2_data_analysis.py | Development filtering/grouping, diagnostics, preservation guards |
| tests/test_phase2_2_models.py | Architecture/gradient/compatibility/resume/retention |
| tests/test_phase2_2_registry.py | Registry/config/promotion/development metadata/cache corruption |
| tests/test_phase2_2_evaluation.py | Metric helper/orchestration/freeze/tampering/game/regression inventory |
| .gitignore | Ignore streaming Phase2.2 predictions; tidak menghapus file |
| README.md | Protokol dan CLI Phase2.2, tautan laporan/reproduksi |
| docs/phase2_2_execution_ledger.md | Keputusan/evidence/rulings/fix pass |
| docs/superpowers/plans/2026-11-04-mahjong-strategy-ai-phase2_2.md | Rencana/protokol implementasi dan review focus |
| docs/phase2_2_implementation_report.md | Laporan18 bagian dengan hasil aktual |
| docs/phase2_2_file_inventory.md | Inventory ini |

## Model terpisah

| Model | Path | Bytes | SHA-256 |
| --- | --- | --- | --- |
| v1 | artifacts/models/mahjong_discard_mlp.pt | 361,733 | `e962b71b5bc031c2cfa307e9096fb763cb70e65240523a38e73254aa2563e855` |
| v2 | artifacts/models/mahjong_discard_mlp_v2.pt | 361,733 | `3a0356a66a81ba775291fdf38072d1c033299fa44e30328c7864addd95edcc8a` |
| v3 | artifacts/models/mahjong_discard_mlp_v3.pt | 1,553,925 | `ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720` |

V3 metadata: `artifacts/models/mahjong_discard_mlp_v3.metadata.json`. V1/v2 hanya diverifikasi dan tetap byte-identik.

## Artifact Phase2.2 aktual

| Path | Bytes |
| --- | --- |
| artifacts/phase2_2/baseline_validation_predictions.jsonl.gz | 26147414 |
| artifacts/phase2_2/candidate_freeze.json | 1219 |
| artifacts/phase2_2/confusion_matrix.csv | 12828 |
| artifacts/phase2_2/data_integrity.json | 1504197 |
| artifacts/phase2_2/development/candidate_v3_analysis.json | 4663038 |
| artifacts/phase2_2/development/candidate_v3_predictions.jsonl.gz | 46882842 |
| artifacts/phase2_2/development/comparison_freeze.json | 814 |
| artifacts/phase2_2/development/confidence_intervals.json | 841 |
| artifacts/phase2_2/development/confusion_matrix.csv | 9646 |
| artifacts/phase2_2/development/independent_recalculation.json | 35839 |
| artifacts/phase2_2/development/metrics.json | 55363 |
| artifacts/phase2_2/development/per_class_metrics.csv | 5998 |
| artifacts/phase2_2/development/reference_E0_analysis.json | 4664206 |
| artifacts/phase2_2/development/reference_E0_predictions.jsonl.gz | 46511316 |
| artifacts/phase2_2/development/reverification.json | 102 |
| artifacts/phase2_2/epoch_benchmark.json | 247 |
| artifacts/phase2_2/error_analysis.json | 4116074 |
| artifacts/phase2_2/evaluation_lineage.json | 2830419 |
| artifacts/phase2_2/experiment_comparison.json | 423430 |
| artifacts/phase2_2/experiment_registry.json | 490856 |
| artifacts/phase2_2/experiments/E0_f0_s2026/history.json | 62993 |
| artifacts/phase2_2/experiments/E0_f0_s2026/model.metadata.json | 1514386 |
| artifacts/phase2_2/experiments/E0_f0_s2026/model.pt | 361733 |
| artifacts/phase2_2/experiments/E0_f0_s2026/training_resume.0037.37aa6417a8d07cf43b27c9923a93e12bb6034a957beff7fd01a6fb830e5a4bff.pt | 1460028 |
| artifacts/phase2_2/experiments/E0_f0_s2026/training_resume.0038.798618f362827afc6431dd2974bfb7a16b7ded7aeb9ce8d79e4aa55168191a7a.pt | 1460092 |
| artifacts/phase2_2/experiments/E0_f0_s2026/training_resume.sha256.json | 191 |
| artifacts/phase2_2/experiments/E0_f0_s2027/history.json | 58710 |
| artifacts/phase2_2/experiments/E0_f0_s2027/model.metadata.json | 1514421 |
| artifacts/phase2_2/experiments/E0_f0_s2027/model.pt | 361733 |
| artifacts/phase2_2/experiments/E0_f0_s2027/training_resume.0025.81398fea213943a65673f822273b3d3a2b52f35a6ac3aeaa34518aa80b4196d2.pt | 1458812 |
| artifacts/phase2_2/experiments/E0_f0_s2027/training_resume.0026.6ff6058bad7daa2cf6ab04ed86fe1a07ec22a4a2bf78bb4e296bddb3de4b3e7e.pt | 1458876 |
| artifacts/phase2_2/experiments/E0_f0_s2027/training_resume.sha256.json | 191 |
| artifacts/phase2_2/experiments/E0_f1_s2026/history.json | 63019 |
| artifacts/phase2_2/experiments/E0_f1_s2026/model.metadata.json | 1514394 |
| artifacts/phase2_2/experiments/E0_f1_s2026/model.pt | 361733 |
| artifacts/phase2_2/experiments/E0_f1_s2026/training_resume.0037.9bdbcd7847540e50e574efc8750a27332bf453e91212562e08e1c5266f937bb3.pt | 1459836 |
| artifacts/phase2_2/experiments/E0_f1_s2026/training_resume.0038.ef93ea466008fcab8b59a9ea041fdec58f9819214b8ebec5b8d8e61f83d9412f.pt | 1459900 |
| artifacts/phase2_2/experiments/E0_f1_s2026/training_resume.sha256.json | 191 |
| artifacts/phase2_2/experiments/E1_f0_s2026/history.json | 58293 |
| artifacts/phase2_2/experiments/E1_f0_s2026/model.metadata.json | 1514427 |
| artifacts/phase2_2/experiments/E1_f0_s2026/model.pt | 720901 |
| artifacts/phase2_2/experiments/E1_f0_s2026/training_resume.0024.84b2e1ee2a880d2ea8633985da39bf772551046a7ec5e3704377b9cf9e289e57.pt | 2895356 |
| artifacts/phase2_2/experiments/E1_f0_s2026/training_resume.0025.a7896339891e2af7d5474aed9a550026f9796caa25bcf1ad8347bc8284402c45.pt | 2895420 |
| artifacts/phase2_2/experiments/E1_f0_s2026/training_resume.sha256.json | 191 |
| artifacts/phase2_2/experiments/E2_f0_s2026/history.json | 66937 |
| artifacts/phase2_2/experiments/E2_f0_s2026/model.metadata.json | 1514364 |
| artifacts/phase2_2/experiments/E2_f0_s2026/model.pt | 1553925 |
| artifacts/phase2_2/experiments/E2_f0_s2026/training_resume.0048.036ea921fbec8a6ce7e6924b609eef9f29988c79cbba746be80be0dedadf01f4.pt | 6230382 |
| artifacts/phase2_2/experiments/E2_f0_s2026/training_resume.0049.f5e8ea3c76f0424958c64c1c3ac7e697e7eafe0eda17aa692896551f817fee76.pt | 6230446 |
| artifacts/phase2_2/experiments/E2_f0_s2026/training_resume.sha256.json | 191 |
| artifacts/phase2_2/experiments/E3_f0_s2026/history.json | 66919 |
| artifacts/phase2_2/experiments/E3_f0_s2026/model.metadata.json | 1514357 |
| artifacts/phase2_2/experiments/E3_f0_s2026/model.pt | 1553925 |
| artifacts/phase2_2/experiments/E3_f0_s2026/training_resume.0048.7405898473f990fb299e4167541d660f1049e7d844523ee4d604941b80bacf3e.pt | 6230382 |
| artifacts/phase2_2/experiments/E3_f0_s2026/training_resume.0049.b3fd504d2452001137eb7cfcecaaa811128622f8ad606aec3982d8b3f2a724f0.pt | 6230446 |
| artifacts/phase2_2/experiments/E3_f0_s2026/training_resume.sha256.json | 191 |
| artifacts/phase2_2/experiments/E3_f0_s2027/history.json | 70925 |
| artifacts/phase2_2/experiments/E3_f0_s2027/model.metadata.json | 1514360 |
| artifacts/phase2_2/experiments/E3_f0_s2027/model.pt | 1553925 |
| artifacts/phase2_2/experiments/E3_f0_s2027/training_resume.0059.48fa4bf187989a05c3d906874ecf14eecaeb05bfdd26e7e76bd57e59fdcb1977.pt | 6231342 |
| artifacts/phase2_2/experiments/E3_f0_s2027/training_resume.0060.4d42f93586589ea2cfbb3362e0d5231a32cc5adee93844494cd2774f17fbee8e.pt | 6231406 |
| artifacts/phase2_2/experiments/E3_f0_s2027/training_resume.sha256.json | 191 |
| artifacts/phase2_2/experiments/E3_f1_s2026/history.json | 70874 |
| artifacts/phase2_2/experiments/E3_f1_s2026/model.metadata.json | 1514312 |
| artifacts/phase2_2/experiments/E3_f1_s2026/model.pt | 1553925 |
| artifacts/phase2_2/experiments/E3_f1_s2026/training_resume.0059.fbeffe79bada93a6411206f171f0db12f7d66126c3b5a62c2bb4061ffe66de8a.pt | 6231342 |
| artifacts/phase2_2/experiments/E3_f1_s2026/training_resume.0060.b07be29471c082cc0d4df764e592ae12586bb26e59a8039eced9df473922681a.pt | 6231406 |
| artifacts/phase2_2/experiments/E3_f1_s2026/training_resume.sha256.json | 191 |
| artifacts/phase2_2/final_evaluation.json | 153956 |
| artifacts/phase2_2/historical_metric_verification.json | 87650 |
| artifacts/phase2_2/latency.json | 263 |
| artifacts/phase2_2/learning_curves.csv | 51083 |
| artifacts/phase2_2/live_demo.json | 95071 |
| artifacts/phase2_2/live_demo_seed_42.json | 22363 |
| artifacts/phase2_2/live_demo_seed_43.json | 56480 |
| artifacts/phase2_2/loader_benchmark.json | 318 |
| artifacts/phase2_2/microbenchmark.json | 2705 |
| artifacts/phase2_2/model_freeze.json | 1431 |
| artifacts/phase2_2/model_selection.json | 1259 |
| artifacts/phase2_2/per_class_metrics.csv | 8757 |
| artifacts/phase2_2/preflight.json | 611 |
| artifacts/phase2_2/preservation_manifest.json | 207883 |
| artifacts/phase2_2/preservation_verification.json | 149 |
| artifacts/phase2_2/previous_experiment_lineage.json | 3040053 |
| artifacts/phase2_2/protocol.json | 2202 |
| artifacts/phase2_2/regression_evidence.json | 377 |
| artifacts/phase2_2/regularization_choice.json | 622 |
| artifacts/phase2_2/retrospective/candidate_v3_analysis.json | 4016741 |
| artifacts/phase2_2/retrospective/candidate_v3_predictions.jsonl.gz | 26049807 |
| artifacts/phase2_2/retrospective/comparison_freeze.json | 1032 |
| artifacts/phase2_2/retrospective/confidence_intervals.json | 983 |
| artifacts/phase2_2/retrospective/confusion_matrix.csv | 12828 |
| artifacts/phase2_2/retrospective/independent_recalculation.json | 52285 |
| artifacts/phase2_2/retrospective/metrics.json | 80696 |
| artifacts/phase2_2/retrospective/per_class_metrics.csv | 8757 |
| artifacts/phase2_2/retrospective/reference_E0_analysis.json | 4015717 |
| artifacts/phase2_2/retrospective/reference_E0_predictions.jsonl.gz | 25839375 |
| artifacts/phase2_2/retrospective/reverification.json | 102 |
| artifacts/phase2_2/retrospective/saved_v2_analysis.json | 4015476 |
| artifacts/phase2_2/retrospective/saved_v2_predictions.jsonl.gz | 25905630 |
| artifacts/phase2_2/reverification.json | 142 |
| artifacts/phase2_2/training_complete.json | 243 |
| artifacts/phase2_2/training_history.json | 66919 |
| artifacts/phase2_2/trajectory_groups.json | 41440 |
| artifacts/phase2_2/verification_summary.json | 5378 |

## Evidence aktual

| Path | Bytes |
| --- | --- |
| docs/evidence/phase2_2/baseline.txt | 438 |
| docs/evidence/phase2_2/baseline.xml | 29460 |
| docs/evidence/phase2_2/code_review.md | 4129 |
| docs/evidence/phase2_2/data_analysis_green.txt | 98 |
| docs/evidence/phase2_2/data_analysis_red.txt | 4146 |
| docs/evidence/phase2_2/data_integrity.txt | 107 |
| docs/evidence/phase2_2/development_gate_mutation_red.txt | 15279 |
| docs/evidence/phase2_2/development_metadata_red.txt | 1303 |
| docs/evidence/phase2_2/document_checks.json | 201 |
| docs/evidence/phase2_2/epoch_benchmark.txt | 431 |
| docs/evidence/phase2_2/error_analysis.txt | 237 |
| docs/evidence/phase2_2/evaluation_green.txt | 99 |
| docs/evidence/phase2_2/evaluation_helpers_green.txt | 100 |
| docs/evidence/phase2_2/evaluation_helpers_red.txt | 2362 |
| docs/evidence/phase2_2/evaluation_red.txt | 26755 |
| docs/evidence/phase2_2/final_static_checks.json | 171 |
| docs/evidence/phase2_2/final_verification.txt | 524 |
| docs/evidence/phase2_2/finalization_green.txt | 100 |
| docs/evidence/phase2_2/finalization_pipeline.txt | 8462 |
| docs/evidence/phase2_2/finalization_red.txt | 4716 |
| docs/evidence/phase2_2/focused_before_training.txt | 99 |
| docs/evidence/phase2_2/focused_complete.txt | 100 |
| docs/evidence/phase2_2/focused_initial.txt | 99 |
| docs/evidence/phase2_2/focused_registered.txt | 99 |
| docs/evidence/phase2_2/full_suite.txt | 450 |
| docs/evidence/phase2_2/full_suite.xml | 38413 |
| docs/evidence/phase2_2/git_status_final.txt | 2710 |
| docs/evidence/phase2_2/grouping.txt | 548 |
| docs/evidence/phase2_2/grouping_red.txt | 1569 |
| docs/evidence/phase2_2/historical_metrics.txt | 101 |
| docs/evidence/phase2_2/microbenchmark.txt | 1808 |
| docs/evidence/phase2_2/models_green.txt | 99 |
| docs/evidence/phase2_2/models_red.txt | 13146 |
| docs/evidence/phase2_2/pre_review_full.txt | 445 |
| docs/evidence/phase2_2/pre_review_full.xml | 36190 |
| docs/evidence/phase2_2/reference_freeze_green.txt | 112 |
| docs/evidence/phase2_2/reference_freeze_red.txt | 4322 |
| docs/evidence/phase2_2/registry_green.txt | 98 |
| docs/evidence/phase2_2/registry_red.txt | 4031 |
| docs/evidence/phase2_2/review_evidence_chain_green.txt | 100 |
| docs/evidence/phase2_2/review_evidence_chain_red.txt | 14500 |
| docs/evidence/phase2_2/review_green.txt | 100 |
| docs/evidence/phase2_2/review_inventory_filter_green.txt | 113 |
| docs/evidence/phase2_2/review_inventory_filter_red.txt | 2217 |
| docs/evidence/phase2_2/review_red.txt | 21055 |
| docs/evidence/phase2_2/review_wrapper_red.txt | 1370 |
| docs/evidence/phase2_2/training_matrix.txt | 121664 |

Individual model/history/resume generations berada di `artifacts/phase2_2/experiments/<ID>/`. Delapan model eksperimen berbeda dari checkpoint v3 publik. Dua generasi completed-epoch per run dipertahankan; tidak ada generasi fase lama dihapus. Prediksi gzip dapat berukuran besar dan tetap lokal/ignored.

`final_evaluation.json` menyimpan checksum evidence root, masing-masing metrics report menyimpan checksum prediction/analysis/table/bootstrap leaf; candidate/model freeze mengikat identitas model/data/registry/protokol. `verification_summary.json` merekam hasil tests/loads/preservation/source checks. Learning curves CSV diturunkan dari seluruh history setelah training selesai. Inventory ini tidak mencoba meng-hash dirinya sendiri; hasil verifikasi akhir dapat menambah snapshot Git/evidence tanpa mengubah freeze model atau angka evaluasi.
