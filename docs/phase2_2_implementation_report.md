# Laporan implementasi Mahjong Strategy AI Phase 2.2

Tanggal 2026-11-04, Asia/Jakarta. Semua hasil berasal dari eksekusi lokal; retrospective historical test diberi label secara eksplisit.

## 1. Final Verdict

**PHASE 2.2 PASS — PROMOTE_V3.** Delapan eksperimen nyata selesai, seleksi memakai development saja, checkpoint v3 terpisah tersimpan, verifikasi ulang inferensi berhasil, dan 279 tes lulus. 1624 file fase sebelumnya tetap identik.

Model yang direkomendasikan: `artifacts/models/mahjong_discard_mlp_v3.pt`. Keputusan ini berlaku untuk protokol internal yang didokumentasikan; **tidak tersedia blind test eksternal baru**. Hasil retrospektif tidak digunakan untuk memilih arsitektur, seed, epoch atau hyperparameter.

## 2. Environment and Preflight

CPython 3.12.10, PyTorch 2.15.0, NumPy 2.5.4, PyMahjongGB 1.4.0; `macOS-26.6.2-arm64-arm-64bit`, 8 CPU logis, RAM 16 GiB. Lingkungan `.venv` yang sudah ada digunakan; tidak ada dependency baru pada Phase 2.2.

MPS tersedia dan forward/backward masked optimizer benar-benar diuji. Microbenchmark CPU batch256 sekitar337k/256k/144k sampel/detik untuk64/128/256→128, dibanding MPS61k/58k/44k. Angka itu throughput microbenchmark, bukan epoch korpus. CPU satu thread dipilih. Satu epoch E0 nyata pada 1,400,549 train/350,917 validation memerlukan 12.2714 detik; state epoch1 dipakai ulang melalui resume. Free disk saat preflight 5.41 GB; pemeriksaan cadangan1 GiB dilakukan sebelum run. Checkpoint baru menyimpan dua generasi resume; generasi fase lama tidak dihapus.

Baseline sebelum perubahan: **218/218 lulus38.81 detik**. Audit korpus read-only PASS; kontrak lama tidak ditulis ulang, termasuk saat audit gagal. Branch `main`, HEAD `49ad7a2`; pekerjaan Phase2/2.1 yang sebelumnya belum di-stage dipertahankan. Bukti: [preflight.json](../artifacts/phase2_2/preflight.json), [data_integrity.json](../artifacts/phase2_2/data_integrity.json), [microbenchmark.json](../artifacts/phase2_2/microbenchmark.json), [epoch_benchmark.json](../artifacts/phase2_2/epoch_benchmark.json).

## 3. Data and Evaluation Lineage

Dataset `expanded_strict_v2`, run `ea198c8c8d504396964c9b9f0e939870`: **1,946,122 sampel /38,250 match /581 UID**,349 transaksi shard. Sumber Dannibal/ijcai-mahjong-round2, revision `c8435106623c106b9e03b980691bea24ba4ac240`; archive SHA-256 `68fe9a5613e523d65356ac5f3e3bc997be8a3ad08bc24035ae22aad17c1daa42`. Ada44,420 JSON game; angka historis44,421 juga menghitung `_sid.txt`. Tidak ada ekstraksi ulang atau filtering baru.

| Peran Phase2.1 | Match | Sampel |
| --- | --- | --- |
| train | 30589 | 1555412 |
| validation | 3840 | 196054 |
| test | 3816 | 194388 |
| historical_test | 5 | 268 |

Phase2 asli memiliki72 train/7 validation/5 test match. Kelima test asli dikeluarkan seluruh seat-nya sebagai `historical_test`; bersama3,816 test Phase2.1, total3,821 ID historis dilarang masuk fitting/seleksi. Pool development adalah train+validation lama: **1,751,466 sampel /34,429 match**. Semua ID, role dan checksum tercatat pada [evaluation_lineage.json](../artifacts/phase2_2/evaluation_lineage.json). [previous_experiment_lineage.json](../artifacts/phase2_2/previous_experiment_lineage.json) merekonstruksi empat prefix learning curve lama beserta3840 ID validation dan memeriksa hash subset metadata/history; seluruhnya development yang pernah dipakai, bukan holdout baru.

Sebelum protokol eksperimen dibekukan,190 grup berisi412 ID dengan seluruh trajectory input identik disatukan memakai hash `obs + legal_discard_mask + seat`, **tanpa target**. Representatif adalah ID terkecil. Bucket `sha256('phase2.2-dev-fold-v1:'+representatif)`, delapan byte awal unsigned big-endian modulo5. Match tunggal memakai ID sendiri. Tidak ada baris dibuang.

| Fold yang dijalankan | Train match | Train sampel | Validation match | Validation sampel |
| --- | --- | --- | --- | --- |
| 0 | 27515 | 1,400,549 | 6914 | 350,917 |
| 1 | 27717 | 1,408,964 | 6712 | 342,502 |

Hanya **dua dari lima bucket** dijalankan, dengan satu pengulangan seed di fold0; ini bukan full five-fold CV. Train/validation disjoint per run. Saved v2 pernah belajar pada sebagian fold baru, sehingga dilarang menjadi reference development; E0 dilatih dari acak dengan batas data yang sama. Tidak ada sumber kompatibel baru yang diberikan/tersedia lokal; dipakai Option B. Historical test baru dinilai setelah model dan keputusan dibekukan.

## 4. Baseline Error Analysis

Diagnostik v2 dilakukan **sebelum eksperimen kapasitas** pada validation Phase2.1 lama:196,054 keputusan /3840 match /336 UID, yang sebelumnya sudah dipakai untuk seleksi model. Top-1 57.4301%, Top-3 80.6819%, NLL 1.291864, macro F1 0.546666. Durasi91.36 detik, peak RSS713.6 MiB.

| Jumlah discard legal | Sampel | Top-1 | Top-3 |
| --- | --- | --- | --- |
| 1 | 57 | 100.0000% | 100.0000% |
| 2-3 | 2,722 | 72.2630% | 100.0000% |
| 4-6 | 20,472 | 67.9513% | 91.3296% |
| 7-10 | 85,156 | 58.4363% | 82.5779% |
| >10 | 87,647 | 53.5067% | 75.7402% |

Keputusan nontrivial (>1 discard legal):195,997 sampel, Top-1 57.4177%, Top-3 80.6762%.

| Konteks | Sampel | Top-1 |
| --- | --- | --- |
| draw | 179,191 | 57.7211% |
| post_meld | 16,863 | 54.3379% |

| Keluarga target | Sampel | Top-1 |
| --- | --- | --- |
| F | 32,504 | 78.5780% |
| J | 23,327 | 73.7343% |
| B | 46,106 | 48.4102% |
| T | 47,397 | 49.4398% |
| W | 46,720 | 51.5839% |

Terdapat112,594 target di rank1,29,925 di rank2 dan15,661 di rank3. Jadi45,586 dari83,460 kesalahan Top-1 (54.6%) masih berada di rank2–3. Confusion terbesar (target→prediksi): F3→F2 (355), F3→F1 (349), F4→F2 (330), J3→F1 (295), J1→F1 (254), F3→F4 (226). Honor lebih mudah daripada tile suited; post-meld juga lebih sulit. Model tidak otomatis menjadi strategi Mahjong yang optimal karena labelnya perilaku discard rekaman.

Distribusi UID tidak merata: dukungan5–9,232 keputusan per UID,156 UID memiliki≥100 sampel; sepuluh UID terbesar mencakup34.3839%. Per-UID rinci tersedia pada JSON; UID kecil ditandai insufficient support, bukan dibandingkan seolah estimasinya stabil. Ini bukan evaluasi unseen-player.

ECE15 bin=0.018390, Brier multiclass=0.553163, rerata confidence Top-1=0.570788. Tidak tampak overconfidence agregat yang kuat. Ada28,873 keputusan dengan margin Top1–Top2<0.05 dan21,708 di antaranya salah. Confidence adalah skor perilaku discard, bukan probabilitas menang.

Audit development1,751,466 observasi menemukan1,578,955 signature observable berbeda,172,511 observasi berulang;146,225 pengulangan juga berlabel sama. Sebanyak20,648 signature input memiliki label berbeda, mencakup95,844 observasi. Diagnostik bucket match-only awal menemukan33,065 overlap input,30,225 overlap input+label dan96,230 overlap coarse-hand. Angka overlap awal itu **mendahului pengelompokan trajectory** dan bukan hasil audit ulang fold final. Coarse-hand mengabaikan sebagian riwayat publik, jadi hanya indikator kemiripan.221 extra trajectory berlabel identik (175 lintas bucket awal) mendorong grouping input-only sebelum training; grouping final memiliki190 grup/412 ID. Ingestion duplicate yang terkonfirmasi=0. State berulang yang sah dan konflik perilaku tidak dihapus. Dependensi pada state individual/UID masih membatasi klaim generalisasi. Bukti lengkap: [error_analysis.json](../artifacts/phase2_2/error_analysis.json).

## 5. Experiment Matrix

| ID | Arsitektur | Parameter | Konfigurasi | Best/epoch | Val NLL | Val Top-1 | Val Top-3 | Macro F1 | Detik |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0_f0_s2026 | 1368→64→34 | 89,826 | WD=0.0001;dropout=0.2;f0;s2026 | 30/38 | 1.258961 | 58.7703% | 81.4751% | 0.561197 | 453.24 |
| E1_f0_s2026 | 1368→128→34 | 179,618 | WD=0.0001;dropout=0.2;f0;s2026 | 17/25 | 1.162112 | 61.7568% | 84.8089% | 0.594634 | 334.51 |
| E2_f0_s2026 | 1368→256→128→34 | 387,746 | WD=0.0001;dropout=0.2;f0;s2026 | 41/49 | 1.098598 | 63.7966% | 86.4031% | 0.615384 | 897.09 |
| E3_f0_s2026 | 1368→256→128→34 | 387,746 | WD=0.001;dropout=0.2;f0;s2026 | 41/49 | 1.092039 | 64.1174% | 86.5034% | 0.618880 | 1020.91 |
| E0_f1_s2026 | 1368→64→34 | 89,826 | WD=0.0001;dropout=0.2;f1;s2026 | 30/38 | 1.259399 | 58.6233% | 81.2924% | 0.559217 | 491.82 |
| E3_f1_s2026 | 1368→256→128→34 | 387,746 | WD=0.001;dropout=0.2;f1;s2026 | 60/60 | 1.091359 | 64.0621% | 86.4958% | 0.618930 | 1174.46 |
| E0_f0_s2027 | 1368→64→34 | 89,826 | WD=0.0001;dropout=0.2;f0;s2027 | 18/26 | 1.281392 | 58.0231% | 80.4375% | 0.550436 | 305.97 |
| E3_f0_s2027 | 1368→256→128→34 | 387,746 | WD=0.001;dropout=0.2;f0;s2027 | 58/60 | 1.088454 | 64.3266% | 86.6971% | 0.622343 | 1162.22 |

Semua run memakai AdamW, lr0.001, batch256, CPU1 thread, maksimal60 epoch, patience8, masked cross-entropy pada kelas discard legal. E0/E1/E2 memakai WD0.0001/dropout0.2. E3 dipilih dari E2 karena NLL lebih rendah daripada E1; gap Top-1 eval-train/validation≥3pp memicu **hanya WD menjadi0.001**, dropout tetap0.2. Aturan itu dibekukan sebelum E3. E4 normalization dan E5 lebih besar: **NOT RUN**, sesuai anggaran terbatas. Tidak ada pencarian hyperparameter tambahan setelah hasil test. [protocol.json](../artifacts/phase2_2/protocol.json), [experiment_registry.json](../artifacts/phase2_2/experiment_registry.json), [experiment_comparison.json](../artifacts/phase2_2/experiment_comparison.json).

## 6. Training Behavior

Kurva numerik per epoch untuk seluruh run tersedia pada [learning_curves.csv](../artifacts/phase2_2/learning_curves.csv); JSON lengkap tiap run berada di `experiments/<ID>/history.json`. [training_history.json](../artifacts/phase2_2/training_history.json) adalah history checkpoint terpilih.

| Epoch selected run | Train NLL online | Validation NLL | Validation Top-1 |
| --- | --- | --- | --- |
| 1 | 1.538976 | 1.422046 | 53.2391% |
| 5 | 1.252675 | 1.201459 | 60.3678% |
| 10 | 1.189554 | 1.156038 | 61.8340% |
| 20 | 1.142177 | 1.123789 | 62.8553% |
| 41 | 1.102829 | 1.092039 | 64.1174% |
| 49 | 1.095089 | 1.093992 | 63.9915% |

| Run | Eval-train Top-1 | Validation Top-1 | Gap pp | Stop |
| --- | --- | --- | --- | --- |
| E0_f0_s2026 | 60.5165% | 58.7703% | 1.746 | validation_patience |
| E1_f0_s2026 | 64.6047% | 61.7568% | 2.848 | validation_patience |
| E2_f0_s2026 | 68.8536% | 63.7966% | 5.057 | validation_patience |
| E3_f0_s2026 | 68.9290% | 64.1174% | 4.812 | validation_patience |
| E0_f1_s2026 | 60.5350% | 58.6233% | 1.912 | validation_patience |
| E3_f1_s2026 | 69.5980% | 64.0621% | 5.536 | max_epochs |
| E0_f0_s2027 | 59.5736% | 58.0231% | 1.551 | validation_patience |
| E3_f0_s2027 | 69.4921% | 64.3266% | 5.165 | max_epochs |

Training online dihitung saat dropout aktif dan sebelum setiap update; metrik itu tidak setara dengan eval-train akhir. Gap di atas memakai model terbaik dalam mode eval pada seluruh train fold. Model di-restore ke epoch dengan validation NLL minimum, bukan epoch terakhir atau Top-1 tertinggi. Semua bobot terpilih berbeda dari inisialisasi; finite loss/logits/gradient dan resume optimizer/RNG/best state diperiksa. Total waktu training tercatat97.34 menit; durasi itu tidak mencakup seluruh audit, testing, review dan evaluasi. Peak RSS per run tersedia pada history. Variasi seed/fold dinilai lewat tiga pasangan, bukan cherry-pick satu seed. Hasil E0→E1→E2 pada data/settings sama mengindikasikan kapasitas64 sebagai salah satu batas model lama; E3 menguji regularisasi terpisah. Ini mendukung perbaikan imitasi discard dalam protokol ini, bukan bukti bahwa kapasitas saja akan mencapai80–85% atau meningkatkan kemenangan.

## 7. Model Selection

Shortlist `E3_f0_s2026` adalah kandidat E1/E2/E3 dengan validation NLL fold0seed2026 minimum. Checkpoint publik tetap fold0seed2026 yang ditentukan di awal; run seed2027 hanya pemeriksaan robustness. Kandidat dibanding E0 pada fold0seed2026, fold1seed2026 dan fold0seed2027.

Promosi membutuhkan rata-rata perbaikan NLL≥0.01 dan setiap pasangan positif; rerata Top-1/Top-3/macro F1 tidak turun lebih dari0.002; legal rate1; tidak ada UID dengan≥1000 sampel yang turun Top-1>0.05; p95 inference≤50ms; compatibility/game/regression lulus. Keputusan aktual: **PROMOTE_V3**, mean perbaikan NLL=0.175966. Kriteria/arsitektur/seed/epoch/checksum/metadata dan bukti seleksi dibekukan di [model_freeze.json](../artifacts/phase2_2/model_freeze.json) **sebelum** historical test dibuka. [candidate_freeze.json](../artifacts/phase2_2/candidate_freeze.json) mengikat kandidat, reference, registry dan protokol.

## 8. Fair Model Comparison

| Pasangan | E0 NLL | V3 NLL | ΔNLL E0−V3 | E0 Top-1 | V3 Top-1 | ΔTop-1 pp |
| --- | --- | --- | --- | --- | --- | --- |
| E0_f0_s2026 / E3_f0_s2026 | 1.258961 | 1.092039 | 0.166921 | 58.7703% | 64.1174% | +5.3471 |
| E0_f1_s2026 / E3_f1_s2026 | 1.259399 | 1.091359 | 0.168039 | 58.6233% | 64.0621% | +5.4388 |
| E0_f0_s2027 / E3_f0_s2027 | 1.281392 | 1.088454 | 0.192938 | 58.0231% | 64.3266% | +6.3035 |

Setiap pasangan memakai match, preprocessing, legal mask, definisi metrik, seed dan budget yang sama; hanya konfigurasi model yang telah ditentukan berbeda. Rerata E0 Top-1=58.4722%; kandidat=64.1687%. Fold0seed2027 berbagi validation dengan seed2026, sehingga tiga hasil bukan tiga test independen.

Historical Phase2.1 yang telah dipublikasikan: v2 Top-1 **57.1738%**, Top-3 **80.6284%**, macro F1 **0.544619**, NLL **1.294869** pada194,388 keputusan/3816 match. Angka lama dihitung ulang secara read-only dari prediksi tersimpan ([historical_metric_verification.json](../artifacts/phase2_2/historical_metric_verification.json)). Itu konteks retrospektif. Saved v2 tidak dipakai sebagai reference out-of-sample pada fold development baru karena pernah dilatih pada sebagian input tersebut. Perbandingan saved v2 pada cohort historical yang sama disajikan terpisah di bawah.

## 9. Final Evaluation

| Cohort/model | Sampel | Top-1 | Top-3 | F1 34 | F1 supported | NLL | Legal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev fold0/reference_E0 | 350,917 | 58.7703% | 81.4751% | 0.561197 | 0.561197 | 1.258961 | 100.0000% |
| dev fold0/candidate_v3 | 350,917 | 64.1174% | 86.5034% | 0.618880 | 0.618880 | 1.092039 | 100.0000% |
| retrospektif/reference_E0 | 194,388 | 58.7588% | 81.4572% | 0.561602 | 0.561602 | 1.258421 | 100.0000% |
| retrospektif/candidate_v3 | 194,388 | 64.3466% | 86.5455% | 0.621944 | 0.621944 | 1.086453 | 100.0000% |
| retrospektif/saved_v2 | 194,388 | 57.1738% | 80.6284% | 0.544619 | 0.544619 | 1.294869 | 100.0000% |

| Cohort | Match | Cluster | UID | V3 Top-1 95% CI | ΔV3−E0 pp 95% CI |
| --- | --- | --- | --- | --- | --- |
| dev fold0 | 6914 | 6864 | 393 | 63.8448% – 64.3980% | +5.1781 – +5.5183 |
| retrospektif | 3816 | 3816 | 302 | 63.9681% – 64.6932% | +5.3494 – +5.8164 |

Bootstrap memakai 2,000 resample seed2026 pada **cluster match lengkap atau trajectory observable identik**, accuracy decision-weighted. Penggabungan trajectory mengikuti grouping development yang dibekukan; historical test memakai match sebagai cluster. CI di atas adalah Top-1 pada cohort tertentu; tidak ada klaim CI untuk NLL/F1 atau statistik independen atas seluruh keputusan. Tidak ada klaim signifikansi eksternal atau kemampuan menang.

Strata kandidat pada **historical test retrospektif**:

| Legal choice | Sampel | Top-1 | Top-3 |
| --- | --- | --- | --- |
| 1 | 63 | 100.0000% | 100.0000% |
| 2-3 | 2,753 | 75.1907% | 100.0000% |
| 4-6 | 20,437 | 72.1926% | 93.9766% |
| 7-10 | 84,770 | 64.9286% | 87.9391% |
| >10 | 86,365 | 61.5469% | 82.9804% |

Nontrivial (>1 legal):194,325 sampel, Top-1 64.3350%, Top-3 86.5411%.

| Konteks retrospektif | Sampel | Top-1 | Top-3 |
| --- | --- | --- | --- |
| draw | 177,657 | 64.6814% | 86.3006% |
| post_meld | 16,731 | 60.7913% | 89.1459% |

Per-class precision/recall/F1/support untuk34 kelas dan confusion matrix tersedia di [per_class_metrics.csv](../artifacts/phase2_2/per_class_metrics.csv) dan [confusion_matrix.csv](../artifacts/phase2_2/confusion_matrix.csv); tabel menyertakan identitas model. Prediksi Top-K, seluruh34 skor legal/illegal, log-probabilitas target dan identitas baris ada di `development/*_predictions.jsonl.gz` serta `retrospective/*_predictions.jsonl.gz`. Distribution confidence, rank, ECE/Brier, legal-choice, UID (support≥100), phase draw/post_meld dan tile family ada di masing-masing `*_analysis.json`. Ada 0 penurunan UID berat di development dan0 secara retrospektif; aturan promosi memakai development saja. Independent counter menghitung ulang NLL/Top-K/F1/confusion dari prediksi tersimpan; verifikasi akhir juga mengulangi inferensi **kedua cohort**, mencocokkan skor/rank/ID dan semua checksum leaf. [final_evaluation.json](../artifacts/phase2_2/final_evaluation.json), [reverification.json](../artifacts/phase2_2/reverification.json).

## 10. Accuracy Target Assessment

| Target Top-1 | Dev fold0 kandidat | Historical retrospektif kandidat |
| --- | --- | --- |
| >57.17% | YA | YA |
| >60% | YA | YA |
| >65% | TIDAK | TIDAK |
| >70% | TIDAK | TIDAK |
| ≥80% | TIDAK | TIDAK |
| ≥85% | TIDAK | TIDAK |

Angka kandidat adalah 64.1174% development dan 64.3466% historical retrospektif. Jawaban tabel **bukan capaian pada blind test baru**. Bukti perbaikan yang adil adalah E0 versus kandidat dengan cohort sama dan hasil tiga pasangan development; perbandingan terhadap57.17% lama harus menyebut protokol/cohort.80–85% tetap target stretch yang belum tercapai, bukan syarat PASS implementasi. UID dikenal, repeated states, penggunaan validation untuk seleksi dan hanya dua fold membatasi keandalan ekstrapolasi.

## 11. Checkpoint Evidence

| Model | Path | Bytes | SHA-256 |
| --- | --- | --- | --- |
| v1 | artifacts/models/mahjong_discard_mlp.pt | 361,733 | `e962b71b5bc031c2cfa307e9096fb763cb70e65240523a38e73254aa2563e855` |
| v2 | artifacts/models/mahjong_discard_mlp_v2.pt | 361,733 | `3a0356a66a81ba775291fdf38072d1c033299fa44e30328c7864addd95edcc8a` |
| v3 | artifacts/models/mahjong_discard_mlp_v3.pt | 1,553,925 | `ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720` |

Metadata v3: `artifacts/models/mahjong_discard_mlp_v3.metadata.json`; SHA-256 `84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e`. Weight-content SHA-256 `c7d693c0ce3d1a6d1107941ba52e3bd6d416ac2783df173399ca8a82285a1b92`. Arsitektur 1368→256→128→34, ReLU/dropout0.2, 387,746 parameter, version `discard_mlp_flexible_v1`. Encoder `ijcai2026_mcr_v1_strict`, input float32[1368] hasil flatten-C obs int8[38,4,9], output34 class, mapping `class=action_id−2`, legal mask slice[2:36].

Metadata menyimpan provenance/kontrak, hyperparameter lengkap, seed, best epoch, sejarah dan hash, ID/hash train-development serta pengecualian historical test, metrik validation, timestamp/environment/device, checksum file dan isi tensor. `test_evaluation` diberi jenis `retrospective_known_test`, bukan new blind. Semua model lama/baru benar-benar di-load CPU dengan `weights_only=True`; arsitektur dan metadata divalidasi sebelum deserialisasi, file/isi tensor diperiksa, tidak ada fallback model acak. Default arsitektur64 dan key state_dict lama tetap kompatibel.1624 file lama diperiksa byte-identik. Service tidak otomatis beralih ke v3.

## 12. Live Game Inference

| Seed | Human seat | Status | Prediksi | Normal | Post-meld | Turn akhir |
| --- | --- | --- | --- | --- | --- | --- |
| 42 | 1 | FINISHED | 8 | 5 | 3 | 132 |
| 43 | 1 | FINISHED | 22 | 18 | 4 | 344 |

| Seed | Phase | Tile legal | Rekomendasi | Top-3 skor |
| --- | --- | --- | --- | --- |
| 42 | SELF_TURN | W5, T1, T2, T3, B2, B4, B5, B6, B7, B9, J1, J2 | J1 | J1=0.82040, J2=0.06921, T1=0.02715 |
| 42 | POST_MELD_DISCARD | W5, T1, B2, B4, B5, B6, B7, B9, J1, J2 | T1 | T1=0.68996, J1=0.19105, W5=0.04040 |
| 43 | SELF_TURN | W1, W4, W7, W8, T1, T3, T6, B4, B5, B8, F4 | F4 | F4=0.85184, W8=0.03548, B4=0.03373 |
| 43 | POST_MELD_DISCARD | W1, W4, W7, T1, T3, T6, B4, B8, F4 | F4 | F4=0.87583, W1=0.04571, B8=0.02113 |

Semua Top-K legal; state game, array encoded dan bobot/file checkpoint tidak berubah karena predict. Dua round benar-benar selesai memakai kebijakan gameplay independen yang normal; AI bersifat advisory dan tidak otomatis mengirim aksinya. Ini menguji integrasi encoder/mask/service, bukan win-rate AI. Klaim-only/finished state tidak dipaksa menghasilkan discard.

Latency CPU service yang sudah di-load: warmup 20, 200 pengukuran; median 0.0632 ms, p95 0.0656 ms, max 0.0679 ms. Termasuk preprocessing/mask/ranking, tidak termasuk load model atau pembuatan game. Bukti: [live_demo.json](../artifacts/phase2_2/live_demo.json), [latency.json](../artifacts/phase2_2/latency.json).

## 13. Test Results

| Kelompok | Lulus |
| --- | --- |
| Phase1 | 90 |
| Phase2 | 69 |
| Phase2.1 | 59 |
| Phase2.2 | 61 |
| Full suite | 279 |

Perintah nyata:

```sh
.venv/bin/python -m pytest tests/test_phase2_2_*.py -q
.venv/bin/python -m pytest tests/test_phase2_2_evaluation.py -q -k 'regression_gate_rejects or test_test_evidence'
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase2_2/full_suite.xml
.venv/bin/python -m compileall -q app training scripts tests
git diff --check
```

Focused 61/61 lulus 47.23s; perbaikan filter-inventory2/2 lulus5.52s; full suite terakhir **279/279 lulus 73.65s**, 0 failure/error/skip. Koleksi lengkap 279 identitas cocok dengan XML; missing family11 kasus, duplicate case dan filter seleksi lingkungan benar-benar ditolak. Semua empat temuan review memiliki bukti RED→GREEN, tambahan15 test review Phase2.2. Syntax dan whitespace checks PASS. Bukti `docs/evidence/phase2_2/`, termasuk full_suite XML/TXT dan review red/green. Tidak diuji pada Windows, Linux, CUDA atau instalasi bersih baru; MPS hanya probe/microbenchmark, bukan training penuh. HTTP localhost dalam full suite memerlukan izin sandbox yang telah diberikan.

## 14. Problems and Fixes

Review independen fresh-context menemukan empat masalah Important dan tidak menemukan Critical: final verifier melewatkan leaf development; kegagalan awal menyisakan status verifikasi PASS lama; rerun diagnostik menimpa grouped lineage beku; gate regresi menerima suite yang kehilangan11 tes evaluasi. Seluruhnya direproduksi dengan10 failing targeted cases lalu diperbaiki. Pemeriksaan leaf juga diperluas ke model/metadata/history seluruh8 eksperimen dan XML JUnit asli; empat test corruption tambahan diamati RED→GREEN. Ditambah satu test yang menangkap wrapper yang merusak hasil beku saat pemanggilan duplikat ditolak; status attempt kini terpisah. Inventory koleksi juga mengabaikan filter `PYTEST_ADDOPTS`/configured addopts, sehingga baseline lengkap tidak ikut terpotong. Tes missing/duplicate inventory mencakup kasus itu.

Pengecekan negatif metadata awal juga diperkuat dengan pencatatan pemanggilan deserialisasi dan mutation check yang menonaktifkan gate sementara dalam proses uji; gate normal tetap aktif. Resume state baru dibatasi dua generasi untuk anggaran disk tanpa menghapus state fase lama. Semua perbaikan berkaitan dengan keselamatan/evidence; protokol/arsitektur/hyperparameter seleksi tidak diubah berdasarkan historical test. Review dan disposisi: [code_review.md](evidence/phase2_2/code_review.md). Tidak ada deferred Minor, tidak dilakukan re-review kedua.

Keterbatasan yang tersisa: tidak ada untouched external test; hanya dua bucket/dua seed; label merekam gaya pemain dan observable tidak menentukan satu keputusan unik; UID/state dependence tetap ada; CI bukan bukti kemampuan menang atau unseen-player. Checksum lokal menjamin konsistensi, bukan authenticity jika seluruh evidence chain sengaja diganti bersama-sama. Rerun diagnostik pada output protocol-bound/frozen kini ditolak sebelum menulis; gunakan output baru.

## 15. Model Promotion Decision

**PROMOTE_V3**. Keputusan dihitung sebelum retrospective test dari tiga paired development conditions, UID safety, legal predictions, p95 0.0656 ms, game/compatibility dan regresi. Semua detail dan nilai gate ada pada [model_selection.json](../artifacts/phase2_2/model_selection.json). Rekomendasi model: `artifacts/models/mahjong_discard_mlp_v3.pt`. v1/v2 tetap tersimpan dan dapat di-load; tidak ada perubahan otomatis pada default service. Promosi lokal ini tidak menyatakan generalisasi eksternal atau akurasi80–85%.

## 16. Reproduction Instructions

Jalankan dari root repo dengan Python3.12 dan korpus Phase2.1 yang sudah diverifikasi. Lingkungan yang dipakai tugas ini adalah `.venv` yang sudah ada. Untuk lingkungan baru, bootstrap standar adalah `python3.12 -m venv .venv` dan `.venv/bin/python -m pip install -r requirements-lock.txt`; bootstrap bersih itu **tidak diulang** pada Phase2.2. Dependency exact version ada pada lockfile, provenance source pada kontrak lama.

Audit ulang read-only dan lineage tanpa menulis kontrak lama:

```sh
.venv/bin/python - <<'PY'
from training.optimization_data import DevelopmentCorpus,evaluation_lineage
c=DevelopmentCorpus('datasets/expanded_strict_v2')
l=evaluation_lineage(c)
assert not set(l['historical_test_match_ids'])&set(l['permitted_development_match_ids'])
print(c.quality['status'],c.contract['accepted_samples'],c.contract['accepted_matches'])
PY
```

Untuk reproduksi training baru gunakan output **baru**, bukan mengubah protokol yang sudah selesai. Contoh berikut memakai direktori `artifacts/phase2_2/reproduction`; pastikan belum dipakai. Semua8 run, termasuk E0, dijalankan driver yang sama; tidak ada flag per-run yang harus ditebak.

```sh
.venv/bin/python -m training.optimization_analysis --output artifacts/phase2_2/reproduction
.venv/bin/python - <<'PY'
from pathlib import Path
from training.optimization_data import DevelopmentCorpus,build_trajectory_groups,evaluation_lineage
from training.reporting import write_json_report
out=Path('artifacts/phase2_2/reproduction')
c=DevelopmentCorpus('datasets/expanded_strict_v2')
write_json_report(out/'data_integrity.json',c.quality)
g=build_trajectory_groups(c)
write_json_report(out/'trajectory_groups.json',g)
c=DevelopmentCorpus('datasets/expanded_strict_v2',group_keys=g['group_keys'])
write_json_report(out/'evaluation_lineage.json',evaluation_lineage(c))
PY
.venv/bin/python -m training.optimization_runner --output artifacts/phase2_2/reproduction --benchmark-epoch
.venv/bin/python -m training.optimization_runner --output artifacts/phase2_2/reproduction --resume
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase2_2/reproduction_suite.xml
.venv/bin/python -m training.optimization_finalize --tests-xml docs/evidence/phase2_2/reproduction_suite.xml --output artifacts/phase2_2/reproduction --checkpoint artifacts/models/mahjong_discard_mlp_v3_reproduction.pt
.venv/bin/python -m training.optimization_finalize --output artifacts/phase2_2/reproduction --checkpoint artifacts/models/mahjong_discard_mlp_v3_reproduction.pt --verify-existing
```

Pertahankan XML JUnit asli yang terikat pada freeze. Untuk test run baru gunakan nama XML baru agar evidence beku tidak tertimpa. Untuk output utama yang sudah selesai, gunakan verifikasi, bukan training ulang:

```sh
.venv/bin/python -m training.optimization_finalize --verify-existing
.venv/bin/python -m scripts.demo_ai_prediction --checkpoint artifacts/models/mahjong_discard_mlp_v3.pt --contract datasets/expanded_strict_v2/data_contract.json --smoke --seed 42 --human-seat 1 --output artifacts/phase2_2/reproduced_demo_seed42.json
.venv/bin/python - <<'PY'
from pathlib import Path
from app.model_checkpoint import load_checkpoint
m,metadata=load_checkpoint(Path('artifacts/models/mahjong_discard_mlp_v3.pt'))
print(metadata['model_version'],sum(p.numel() for p in m.parameters()))
PY
```

`--resume` melanjutkan state completed-epoch dengan identitas sama. Sesudah model_freeze, training di output itu ditolak. `--verify-existing` mengulangi inferensi development+retrospective serta checksum/independent recalculation; ia tidak memilih ulang model. Setelah failure, finalizer `--resume` hanya diperbolehkan untuk model/protokol/data yang sama. Pertahankan registry/protocol/history/generation files untuk resume. Deployment cukup membutuhkan model, metadata, kontrak kecil dan runtime/source yang cocok; audit/train membutuhkan seluruh shard dan source provenance. Budget nyata tercatat per-run di tabel; mesin referensi RAM16 GiB, CPU1 thread dan disk bebas beberapa GB. Windows belum diuji.

## 17. Git Safety

Repository aktual adalah `mahjong-strategy-ai`, bukan Reallysick monorepo pada instruksi generik. Tidak ditemukan AGENTS.md di disk. Branch tetap `main`, HEAD tetap `49ad7a2`; tidak ada staging, commit, push, merge, reset, deployment atau publikasi. Perubahan Phase2/2.1 yang sudah ada tidak dibuang. Dataset, shard, arsip, old model/metadata/evidence/report dan core encoder/referee/replay yang dilindungi cocok dengan1624 hash preservation.

Source baru/ekstensi Phase2.2 dan dokumentasi tercantum pada [file inventory](phase2_2_file_inventory.md). Requirements tidak diubah pada phase ini. `git status --short` dan `git diff --check` terakhir disimpan sebagai evidence; Git diff biasa hanya menampilkan tracked files, sehingga inventory menyebut source/test yang sebelumnya untracked secara eksplisit. File bobot, dataset dan streaming predictions tetap di-ignore sesuai kebijakan lokal; tidak ada artifact dikirim ke remote.

## 18. Phase 3 Handoff

**Siap untuk integrasi Phase3 lokal yang tetap mempertahankan batas kualitas di atas**; Phase3 sendiri belum diimplementasikan. Gunakan checkpoint `artifacts/models/mahjong_discard_mlp_v3.pt` dan metadata dengan suffix `.metadata.json`, serta salinan `datasets/expanded_strict_v2/data_contract.json` jika ingin binding identitas dataset secara eksplisit. Distribusikan ketiga file itu beserta runtime/source Python yang cocok; jangan bergantung pada keberadaan archive/shard untuk inferensi. Pertahankan hash dan provenance saat menyalin, dan periksa load di platform target. Windows/Linux/CUDA belum tervalidasi.

Input: `EncodedTurnState` Phase1, obs int8[38,4,9], legal_mask bool[235], legal_discard_mask bool[34], encoder `ijcai2026_mcr_v1_strict`. Output rekomendasi discard legal dan Top-3 terbatas jumlah kelas legal, class0..33→action_id2..35. Import service: `app.services.ai_prediction_service.AIDiscardPredictionService`.

```python
import json
from pathlib import Path
from app.services.ai_prediction_service import AIDiscardPredictionService
from app.services.game_service import GameSessionService

contract=json.loads(Path('datasets/expanded_strict_v2/data_contract.json').read_text())
ai=AIDiscardPredictionService(Path('artifacts/models/mahjong_discard_mlp_v3.pt'),expected_contract=contract)
games=GameSessionService()
try:
    view=games.create_game(seed=42,human_seat=0)
    encoded=games.get_human_encoded_turn(view.game_id)
    prediction=ai.predict(encoded)
    print(prediction.recommended_tile,prediction.top3)
finally:
    games.shutdown()
```

Inisialisasi/load/predict dengan pola itu benar-benar dijalankan dalam latency/live verifier. `CheckpointValidationError` menolak metadata/architecture/hash/kontrak yang tidak cocok; `InvalidPredictionStateError` menolak input/encoder/mask tidak valid; `PredictionUnavailableError` dipakai bila tidak ada discard legal. Tidak ada fallback random atau state advancement dari predict. Scores meniru keputusan discard rekaman, bukan probabilitas menang. Saat integrasi consumer/API nanti, cache satu service, sampaikan keterbatasan kualitas dan tangani unavailable/error secara eksplisit. Readiness ini adalah kesiapan kontrak/checkpoint/inferensi yang sudah diuji, dengan validasi blind eksternal tetap pekerjaan lanjutan.
