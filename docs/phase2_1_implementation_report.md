# PHASE 2.1 IMPLEMENTATION REPORT

Tanggal: 4 November 2026. Status: FINAL. Proyek: `mahjong-strategy-ai`.

## 1. Final Verdict

**PHASE 2.1 PASS — READY FOR PHASE 3** pada macOS arm64 / CPU yang diuji. Seluruh **44.420 game JSON** pada arsip asli diproses; **1.946.122 keputusan dari 38.250 match** lolos replay strict. Dataset diperbesar, MLP asli dilatih ulang, checkpoint dipilih hanya dari validation NLL, dan model dibandingkan pada satu fresh locked test cohort.

Test baru: Top-1 **57.17%**, Top-3 **80.63%**, Macro F1(34) **0.544619**, legal rate **100%**. Model Phase 2 asli mendapat **31.04% Top-1 pada cohort yang sama**; peningkatan **26.14 poin persentase**. Target 80–85% **Top-1 belum tercapai**. Ini bukan alasan menggagalkan implementasi menurut acceptance criteria pengguna.

**218 tes passed**, 0 failure/error/skip; reverification prediksi tersimpan dan demo ronde penuh PASS. Seluruh **74 file sumber/artefak/evidence lama yang dilindungi** tetap identik. Windows NOT RUN. Tidak ada Phase 3–4, staging, commit, push atau deployment.

## 2. Dataset Expansion Summary

| Ukuran | Hasil aktual |
| --- | ---: |
| JSON game ditemukan / dicoba | 44.420 / 44.420 |
| JSON berhasil diparse | 44.420 |
| Match legal terverifikasi | 38.250 |
| Game dikecualikan | 6.170 |
| Keputusan strict lama | 1.879 /84 match, tracked seats |
| Keputusan expanded | 1.946.122, seluruh empat roster seats |
| Pemain/bot UID berbeda | 581 |
| Shard terkompresi | 349 |
| Waktu pemrosesan sumber | 819.918 detik, tidak termasuk audit terpisah |
| Coverage sumber | 100% dicoba, 0 tersisa |
| Proporsi match lolos | 86.11% |

Arsip berisi **44.420 JSON + satu `_sid.txt` (84 byte) + satu direktori**. Angka historis 44.421 menghitung file metadata sebagai game; koreksi ini berasal dari inventaris aktual, bukan pengurangan sumber secara diam-diam.

Eksklusi: **6.084 abnormal terminal**, **31 penolakan legalitas aksi sumber**, dan **55 JSON tanpa roster `players`**. Bucket teknis `invalid_label` pada audit31 kasus adalah penolakan aksi replay (termasuk Hu), bukan31 label discard yang diterima secara ilegal. Jumlah label ilegal pada dataset diterima: **0**. Rincian setiap percobaan ada di `datasets/expanded_strict_v2/shards/*/audit.jsonl`; alasan lengkap juga dirangkum di `artifacts/phase2_1/source_coverage.json`. Aturan referee tidak dilonggarkan untuk menerima kasus gagal.

Milestone600 →5.000 →15.000 →44.420 dilanjutkan dari commit sebelumnya. Pilot 600:554 match/27.299 keputusan;5.000:4.940/243.681;15.000:13.365/662.806. Tidak ada batas1.000-match. Arsip dibaca streaming tanpa mengekstrak3GB JSON atau menggabungkan seluruh fitur float32.

Ruang disk awal7,68GB, RAM16GiB,8 logical CPU. Shard dan manifest terkompresi memakai sekitar203.47MiB pada akhir source pass. Audit penuh ulang menggunakan puncak RSS **356.98MiB**, waktu **73.027s**. Sebuah microbenchmark masked optimizer100-step menunjukkan CPU batch 32 sekitar107k samples/s vs MPS10,7k; keduanya diuji, CPU dipilih karena lebih cepat untuk MLP kecil. Angka microbenchmark bukan throughput end-to-end corpus.

## 3. Integrity and Parity

- Dataset: `Dannibal/ijcai-mahjong-round2`, revisi `c8435106623c106b9e03b980691bea24ba4ac240`.
- Arsip: `finalist_games.tar.gz`,165.209.428 byte, SHA-256 `68fe9a5613e523d65356ac5f3e3bc997be8a3ad08bc24035ae22aad17c1daa42`.
- Parent Phase 1 run: `84c2606383794fa8bc072d5edac7b252`; expanded run: `ea198c8c8d504396964c9b9f0e939870`.
- Encoder tetap `ijcai2026_mcr_v1_strict`; encoder/referee/replay Phase 1 tidak diubah.
- **1.946.122 compared = 1.946.122 exact**; obs/mask/action mismatch0, unmatched decisions0 pada perbandingan yang berhasil dilakukan.
- Provenance100% pada accepted samples; label ilegal0; duplicate ingestion0. Tidak ada training dari NPZ historis yang ditolak.
- Sample inventory SHA-256: `bd1ea1f96304f64a607d6bca1270746315b3adfbdc7aa3a1c3465b5072ab6870`.
- Manifest inventory SHA-256: `3524f6d19b2d6aa31e627ae249448ea027b7e3c8a004322e03ebac7feb61a13f`.
- Contract file SHA-256: `95f21b15be55dbbe4b9cf001edbc8b52462e4461b9bbaf39431a0a482e73adbc`.

Dua inventory hash adalah hash kanonik daftar path/SHA shard dan manifest, **bukan hash satu NPZ besar**. Setiap shard mempunyai hash NPZ, manifest gzip CSV dan audit JSONL sendiri. Seluruh dataset_row, match/seat/UID, decision order, original source row, label, score, source hash, split, versi dan stable sample identity dibandingkan terhadap array dan audit. Source payload diperiksa kembali dari arsip yang dipin. Empat role split mempunyai intersection kosong.

Pisahkan sumber dicoba100%, match lolos86.11%, decision parity100% atas keputusan yang dibandingkan, dan accepted samples1.946.122. Kasus gagal tidak disebut berhasil diverifikasi. Hash membuktikan identitas/konsistensi; tidak membuktikan universal correctness semua aturan Mahjong.

Resume diuji untuk missing inventory, corrupt shard/manifest/audit, disk rendah, interupsi sebelum batch commit dan kegagalan publikasi. Batch committed tidak ditulis ulang. READY contract terbit terakhir setelah audit lengkap; missing initial inventory dipulihkan hanya dari arsip pinned yang divalidasi ulang. Jalankan satu extractor per output; tidak ada jaminan concurrent writers/fsync power-loss.

## 4. Dataset Distribution

| Split | Sampel | Match | UID |
| --- | ---: | ---: | ---: |
| train | 1.555.412 | 30.589 | 553 |
| validation | 196.054 | 3.840 | 336 |
| test | 194.388 | 3.816 | 302 |
| historical_test | 268 | 5 | 9 |

Original 84 match mempertahankan role lama. Seluruh seat dari lima original test matches menjadi `historical_test`; original 102 keputusan test tidak masuk training atau fresh test. Cohort historis expanded berisi268 keputusan karena seluruh seat disertakan, dan tidak dicampur dengan fresh test.

Match baru: SHA-256(`phase2.1-match-split-v1:` + match_id),8 byte pertama unsigned big-endian modulo100; <80 train,<90 validation, selainnya test. Salt/algoritma dikunci sebelum eksperimen. Data provenance/UID/score hanya untuk audit, tidak menjadi fitur model.

| Class / Tile | Train | Validation | Fresh test | Historical |
| --- | ---: | ---: | ---: | ---: |
| 0 / W1 | 52.413 | 6.552 | 6.542 | 7 |
| 1 / W2 | 44.745 | 5.580 | 5.635 | 9 |
| 2 / W3 | 36.480 | 4.577 | 4.589 | 4 |
| 3 / W4 | 35.966 | 4.529 | 4.463 | 6 |
| 4 / W5 | 35.471 | 4.387 | 4.423 | 4 |
| 5 / W6 | 34.724 | 4.375 | 4.361 | 8 |
| 6 / W7 | 35.449 | 4.479 | 4.509 | 7 |
| 7 / W8 | 44.769 | 5.617 | 5.585 | 7 |
| 8 / W9 | 52.467 | 6.624 | 6.575 | 5 |
| 9 / T1 | 53.262 | 6.675 | 6.652 | 5 |
| 10 / T2 | 44.247 | 5.664 | 5.557 | 4 |
| 11 / T3 | 37.513 | 4.767 | 4.685 | 2 |
| 12 / T4 | 35.122 | 4.468 | 4.423 | 3 |
| 13 / T5 | 34.934 | 4.444 | 4.437 | 7 |
| 14 / T6 | 36.519 | 4.527 | 4.513 | 6 |
| 15 / T7 | 35.673 | 4.483 | 4.544 | 4 |
| 16 / T8 | 44.397 | 5.512 | 5.599 | 7 |
| 17 / T9 | 54.394 | 6.857 | 6.713 | 11 |
| 18 / B1 | 52.121 | 6.602 | 6.364 | 11 |
| 19 / B2 | 42.832 | 5.388 | 5.371 | 10 |
| 20 / B3 | 34.371 | 4.425 | 4.336 | 11 |
| 21 / B4 | 34.484 | 4.354 | 4.344 | 8 |
| 22 / B5 | 35.848 | 4.571 | 4.409 | 10 |
| 23 / B6 | 33.701 | 4.250 | 4.220 | 4 |
| 24 / B7 | 34.765 | 4.405 | 4.297 | 5 |
| 25 / B8 | 43.146 | 5.470 | 5.416 | 6 |
| 26 / B9 | 52.081 | 6.641 | 6.570 | 9 |
| 27 / F1 | 63.855 | 7.982 | 7.879 | 14 |
| 28 / F2 | 64.678 | 8.207 | 8.104 | 13 |
| 29 / F3 | 63.729 | 8.028 | 7.942 | 12 |
| 30 / F4 | 65.657 | 8.287 | 8.161 | 15 |
| 31 / J1 | 61.521 | 7.811 | 7.692 | 15 |
| 32 / J2 | 61.170 | 7.580 | 7.691 | 8 |
| 33 / J3 | 62.908 | 7.936 | 7.787 | 11 |

Distribusi UID terbesar:

| UID publik | Sampel seluruh corpus | Proporsi |
| --- | ---: | ---: |
| `690d978db026646c5d0dd54f` | 93.870 | 4.82% |
| `68218edfd870d24732a2f196` | 85.633 | 4.40% |
| `6969e9e4ecf96d65cfeaa99c` | 80.168 | 4.12% |
| `62ff6f7c5f9ce709a6f5c58c` | 69.644 | 3.58% |
| `6960c70f37ecbd5c612d2532` | 66.326 | 3.41% |

UID berbeda bertambah4→581; UID terbesar4.82%. Namun 194.253 test decisions berasal dari UID yang muncul di training; hanya **135** dari UID unseen. Ini evaluasi match-disjoint, bukan desain unseen-player holdout.

Ada **170.955** pengulangan fitur-mask-label pada identitas sumber berbeda; dipertahankan sesuai kebijakan pengguna. Identitas ingestion tetap unik. Pengulangan tersebut tidak membuktikan semua observasi independen secara statistik. Post-meld samples seluruh corpus: **168.001**. Distribusi kelas/legal-choice/phase/UID/match dan player overlap lengkap ada pada `data_quality_report.json`.

Coverage archive-order aktual (bukan waktu kalender):

| Ordinal sumber | Dicoba | Verified | Samples |
| --- | ---: | ---: | ---: |
| 0–4441 | 4.442 | 4.382 | 216.310 |
| 4442–8883 | 4.442 | 4.440 | 214.057 |
| 8884–13325 | 4.442 | 3.308 | 167.088 |
| 13326–17767 | 4.442 | 3.355 | 178.844 |
| 17768–22209 | 4.442 | 3.055 | 161.378 |
| 22210–26651 | 4.442 | 3.647 | 191.577 |
| 26652–31093 | 4.442 | 3.816 | 197.864 |
| 31094–35535 | 4.442 | 4.098 | 209.914 |
| 35536–39977 | 4.442 | 4.048 | 202.410 |
| 39978–44419 | 4.442 | 4.101 | 206.680 |

## 5. Model Experiments

Semua eksperimen baru menggunakan MLP asli **1368→64→34**, ReLU, dropout 0,2, **89.826 parameter**, encoder/input/target mapping tetap. Obs int8[38,4,9] di-flatten C-order ke float32; mask legal[2:36]; target act−2. Objective masked CE sebelum normalisasi, AdamW lr 0,001/weight_decay0,0001, batch 32, max 80, patience 10, seed 2026, CPU 1 thread; hanya satu shard/batch diolah setiap waktu.

Empat eksperimen nyata tercantum di learning curve. Checkpoint full-data dieksekusi **24 epoch**, dipilih **epoch 14** dari minimum validation NLL, **1.170.648 optimizer steps**, **660.728s**. Best-state CPU reload cocok persis dengan selected weight-content hash. Train eval NLL **1.252649999**, train Top-1 **58.51%**. Validation NLL **1.291864163**, Top-1 **57.43%**, Top-3 **80.68%**, Macro F1 **0.546666365**. Early stopping10 epoch tanpa NLL lebih baik; epoch 24 bukan checkpoint terpilih.

Gap train-eval–validation **1.078pp**. Protocol yang ditulis sebelum training hanya mengizinkan satu tambahan weight_decay0,001 bila gap≥3pp; kondisi tidak terpenuhi, maka ExperimentB NOT RUN. Tidak ada capacity search, CNN/Transformer/RL/pretrained policy. Low accuracy sendiri tidak membuktikan penyebab kapasitas; tidak ada klaim perbaikan yang belum diukur.

Model lama menggunakan MPS/row-shuffle dan tracked-seat population. Model baru memakai CPU/shard shuffle dan seluruh roster; karena itu perbandingan lama-baru tidak mengisolasi volume sebagai satu-satunya penyebab. Learning curve baru memakai arsitektur/config/validation yang sama untuk mengukur scaling lebih terkontrol. Seluruh config, sejarah epoch dan selection policy tersimpan pada `protocol.json`, `experiments/*/history.json`, `experiment_comparison.json`.

## 6. Learning Curve

Nested whole-match subsets berasal dari **training partition saja**, diurutkan SHA `phase2.1-learning-curve-v1:`. Validation tetap196.054 keputusan/3.840 match. Budget aktual dapat sedikit melewati target karena match dipertahankan lengkap; prefix identik tidak digandakan.

| Train samples | Match | Best / executed epoch | Train Top-1 | Val Top-1 | Val Top-3 | Val Macro F1 | Val NLL | Detik |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.033 | 20 | 5 / 15 | 60.70% | 29.01% | 55.60% | 0.174869 | 2.078164 | 39.21 |
| 10.041 | 202 | 6 / 16 | 65.14% | 38.91% | 66.12% | 0.319606 | 1.811278 | 67.50 |
| 100.032 | 1.997 | 7 / 17 | 60.76% | 49.35% | 74.11% | 0.452283 | 1.537035 | 90.93 |
| 1.555.412 | 30.589 | 14 / 24 | 58.51% | 57.43% | 80.68% | 0.546666 | 1.291864 | 660.73 |

Validation meningkat pada keempat ukuran yang diukur; titik full lebih baik daripada100k. Kurva ini belum membuktikan bahwa tambahan data lain akan mencapai 80–85%. Seluruh corpus lokal sudah dicoba. JSON dan CSV numerik: `artifacts/phase2_1/learning_curve.json` / `learning_curve.csv`. Tidak ada titik buatan.

## 7. Final Frozen Test Evaluation

Cohort baru **194.388 keputusan /3.816 match**, seluruh34 kelas supported. Selected MLP:

- Top-1 **111.139/194.388 = 57.17%**.
- Top-3 **156.732/194.388 = 80.63%**.
- Macro F1 all34 **0.544619230**, supported34 **0.544619230**.
- NLL/cross-entropy **1.294868700**.
- Legal prediction rate **100%**, setelah verifikasi actual predicted classes terhadap mask.

Per-class precision/recall/F1/support lengkap pada `per_class_metrics.csv`; confusion matrix baris=true/kolom=predicted per model pada `confusion_matrix.csv`. Salah-label Top-1 sebanyak83.249. Confusion terbanyak: F3 → F2: 364; F4 → F2: 342; F3 → F1: 340; J3 → F1: 281; F3 → F4: 252; J1 → F1: 224. Ini kesalahan imitasi label yang tercatat, bukan pembuktian bahwa semua alternatif discard salah secara strategi.

Bootstrap **2.000** resample dari **3.816 match lengkap**, seed 2026, decision-weighted ratio per cohort: selected Top-1 CI95% **56.81–57.53%**. Selisih berpasangan terhadap model lama **26.14pp**, CI95% **25.78–26.50pp**. Tidak memperlakukan setiap keputusan sebagai independent bootstrap unit. Ketergantungan antar-UID/repeated states di luar cluster match belum sepenuhnya dimodelkan.

| Subgroup fresh test | Sampel | Top-1 baru | Top-3 baru |
| --- | ---: | ---: | ---: |
| Normal draw | 177.657 | 57.46% | 80.19% |
| Post Chi/Peng | 16.731 | 54.16% | 85.26% |
| Kelas di atas median frekuensi train | 117.048 | 65.53% | 86.63% |
| Kelas lainnya | 77.340 | 44.53% | 71.54% |
| UID pernah muncul di train | 194.253 | 57.18% | 80.63% |
| UID belum muncul di train | 135 | 53.33% | 78.52% |

`subgroup_metrics.json` juga memuat setiap legal-choice count,10 strata archive-order dan UID dengan≥100 keputusan; kelompok UID lebih kecil ditandai insufficient support. Counter Python/math.fsum secara independen menghitung ulang setiap metrik dari prediksi gzip JSONL. `--verify-existing` kemudian mengulang inference aktual dan membandingkan identitas/rank/skor serta seluruh checksum: PASS.

## 8. Comparison Against Phase 2

**Semua baris tabel berikut menggunakan fresh test yang sama**, bukan original 102 keputusan:

| Model | Top-1 | Top-3 | Macro F1(34) | NLL | Legal |
| --- | ---: | ---: | ---: | ---: | ---: |
| Checkpoint Phase 2 asli | 31.04% | 58.19% | 0.216529 | 2.041470 | 100.00% |
| Prior training-only | 29.11% | 55.09% | 0.166662 | 2.149189 | 100.00% |
| Uniform random legal | 11.34% | 33.91% | 0.113296 | 2.235459 | 100.00% |
| MLP expanded / terpilih | 57.17% | 80.63% | 0.544619 | 1.294869 | 100.00% |

`full_original` dan `selected_v2` di evaluation JSON adalah alias bobot yang sama, bukan dua eksperimen independen. Prior hanya memakai distribusi training dengan add-one smoothing; random adalah seeded uniform legal, rank tanpa pengulangan. Model lama tidak ditrain ulang dan metadata lamanya tidak diubah.

Konteks historis terpisah: checkpoint Phase 2 lama sebelumnya Top-1 **41,1765%**, Top-3 **72,5490%**, Macro F1≈0,299636 pada **102 decisions /5 match**. Angka tersebut bukan hasil baru dan tidak dibandingkan langsung sebagai populasi identik dengan57,17% di atas.

## 9. Accuracy Target Assessment

- Mencapai80% Top-1? **Belum**; aktual **57.17%**.
- Mencapai85% Top-1? **Belum**.
- Peningkatan terhadap old model di fresh cohort? **26.14pp**, dengan paired-match interval di atas.
- Generalisasi beyond known players? **Belum terbukti**; hanya135 keputusan unseen-UID, mayoritas test known-UID.
- Batasan: label satu perilaku pemain, MLP/encoder tetap, variasi kebijakan/UID, repeated states, skor tidak dikalibrasi, dan tidak ada evaluasi kekuatan bermain.
- Apakah data tambahan membantu? Empat titik learning curve memperlihatkan manfaat sampai full available training; tidak ada jaminan extrapolation atau cukup data lokal tersisa. Tidak dapat menetapkan penyebab tunggal gap terhadap 80% tanpa eksperimen lanjutan.

Tidak ada tuning setelah hasil fresh test dilihat, perubahan definisi Top-1, pemilihan hanya easy decisions, atau perpindahan match antar-split. Penelitian model berikutnya memerlukan protocol dan holdout baru.

## 10. Checkpoint and Inference

- Baru: `artifacts/models/mahjong_discard_mlp_v2.pt`, **361733 byte**.
- SHA-256: `3a0356a66a81ba775291fdf38072d1c033299fa44e30328c7864addd95edcc8a`.
- Metadata: `artifacts/models/mahjong_discard_mlp_v2.metadata.json`.
- Architecture version tetap `discard_mlp_v1`; model version **discard_mlp_v1:3a0356a66a81**. Expanded dataset version `expanded_strict_v2` berbeda dari versi arsitektur.
- Metadata mencatat parent/expanded run, contract file/content hashes, shard/manifest hashes, role counts, actual training subset, seed/config, epoch, CPU device, initial/selected weight hashes, validation/test metrics dan Torch version.
- Safe CPU `state_dict`, metadata/encoder/mapping/provenance validation sebelum `torch.load(weights_only=True)`. Dataset besar/arsip mentah tidak diperlukan untuk inference.

Real demo: seed42, human seat1, **8 prediksi**, SELF_TURN dan POST_MELD_DISCARD, seluruhnya legal dan state/turn/obs/mask tetap. Ronde **FINISHED**, turn132, ron9 fan, delta[-17,-8,33,-8]. Normal human helper terpisah memilih aksi; rekomendasi MLP tidak dieksekusi otomatis. Hasil ron membuktikan gameplay berlanjut, bukan kekuatan bermain MLP.

Prediksi pertama turn4, visible hand `W5 T1 T2 T2 T3 B2 B4 B5 B6 B7 B7 B9 J1 J2`. Legal class IDs `[4,9,10,11,19,21,22,23,24,26,31,32]`; mask lengkap tersimpan pada `live_demo.json`.

| Tile | Class | Action | Skor masked |
| --- | ---: | ---: | ---: |
| J1 | 31 | 33 | 0.782136500 |
| J2 | 32 | 34 | 0.130154833 |
| W5 | 4 | 6 | 0.020683117 |

## 11. Automated Test Results

| Test / command | Status | Actual result |
| --- | --- | --- |
| Baseline `.venv/bin/python -m pytest -q` | PASS | 159 passed in20,15s sebelum perubahan |
| New focused pre-review suite | PASS | 51 passed in22,89s; independent reviewer51 in28,36s |
| Review fault/tamper regressions | PASS | 8 kasus RED→GREEN; new suite59 passed in21,29s |
| `.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase2_1/full_suite.xml` | PASS | **218 passed in47,64s**, 90 Phase 1+69 Phase 2+59 Phase 2.1,0 skipped/failure/error |
| Full source/manifest/shard/contract audit | PASS | 1.946.122 legal aligned rows, raw source hashes, zero split intersections;73,0269s |
| `.venv/bin/python -m training.expanded_training --device cpu` | PASS | Empat learning-curve runs nyata, full24/best14, selected CPU reload |
| `.venv/bin/python -m training.expanded_evaluation` | PASS | Frozen test194.388/3.816, old/new/baselines, CI, independent recalculation |
| `.venv/bin/python -m training.expanded_evaluation --verify-existing` | PASS | Actual inference vs saved identities/ranks/scores, evidence/metadata hashes |
| Actual new checkpoint full-round demo | PASS | 8 legal/read-only predictions, FINISHED |
| Actual four restart state generations | PASS | Reloaded history/best-state hashes identical after pointer migration |
| `.venv/bin/python -m compileall -q app training scripts tests` | PASS | exit0 |
| `git diff --check` | PASS | exit0 |
| Old74 protected file hashes | PASS | Before/after identical |
| MPS masked optimizer probe/benchmark | PASS | Available, tested; CPU selected for throughput |
| Windows / CUDA | NOT RUN | Host macOS arm64; new CLI resource instrumentation uses Unix `resource` |

Evidence disimpan terpisah di `docs/evidence/phase2_1/`. RED logs menyimpan kegagalan yang disengaja sebelum perbaikan. Tes fixture memakai subset/temporary artifacts dan tidak menjadi angka performa primary model. Wrapper `/usr/bin/time -l` pernah exit1 setelah validation PASS karena sysctl sandbox; pengukuran/audit diulang sukses lewat Python `resource`, kegagalan wrapper tidak disembunyikan.

## 12. Problems and Fixes

1. Metadata `_sid.txt` menyebabkan inventory pertama menolak arsip. Inventaris aktual dikoreksi dan interleaved-metadata regression membuktikan ordinal game/resume tetap benar.
2. Validator Phase 1 hanya menerima enam key dasar. Reuse validator pada enam array dan validasi typed expanded provenance secara terpisah; tidak mengubah validator/evidence Phase 1.
3. Reviewer: checkpoint bytes diganti sebelum checksum. Immutable generation + satu atomic pointer mempertahankan generation sebelumnya jika publikasi gagal; actual completed states dimigrasi dan direload.
4. Reviewer: published contract dapat menduplikasi/mengganti inventory tanpa audit loader. Sekarang seluruh inventory/roles/split statistics/source/encoder identity dibandingkan terhadap commit terverifikasi sebelum training.
5. Reviewer: interupsi initial inventory tidak bisa resume. Missing inventory direkonstruksi dari pinned archive yang diperiksa ulang; inventory existing yang berubah ditolak.
6. Kasus roster/terminal/legality yang gagal tetap dieksklusi dengan alasan; tidak ada perubahan rules demi volume.

Tidak ada Critical/Important yang tersisa; tidak ada Minor yang ditunda. Review/rulings lengkap: `docs/evidence/phase2_1/code_review.md` dan `docs/phase2_1_execution_ledger.md`. Batasan model/platform/independensi di atas tetap berlaku.

## 13. Reproduction Instructions

Dari root, gunakan `.venv` Python 3.12 proyek dan dependency Phase 2 yang sudah dipin; tidak ada dependency tambahan Phase 2.1. Jangan menimpa snapshot/model/report Phase 1–2.

```sh
.venv/bin/python -m training.expanded_dataset --max-games 600 --workers 2
.venv/bin/python -m training.expanded_dataset --audit-partial
.venv/bin/python -m training.expanded_dataset --max-games 5000 --workers 2
.venv/bin/python -m training.expanded_dataset --max-games 15000 --workers 2
.venv/bin/python -m training.expanded_dataset --workers 2
.venv/bin/python -m training.expanded_dataset --validate
.venv/bin/python -m training.expanded_training --device cpu
# Jika eksperimen terinterupsi, sebelum selection_freeze ada:
.venv/bin/python -m training.expanded_training --device cpu --resume
.venv/bin/python -m training.expanded_evaluation
# Hasil yang sudah ada hanya diverifikasi, bukan diganti/tune ulang:
.venv/bin/python -m training.expanded_evaluation --verify-existing
# Hanya bila publikasi evaluation FAIL/RUNNING, frozen data/model harus sama:
.venv/bin/python -m training.expanded_evaluation --resume
.venv/bin/python -m scripts.demo_ai_prediction --checkpoint artifacts/models/mahjong_discard_mlp_v2.pt --contract datasets/expanded_strict_v2/data_contract.json --smoke --seed 42 --human-seat 1 --output artifacts/phase2_1/live_demo.json
.venv/bin/python -m pytest tests/test_phase2_1_*.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app training scripts tests
```

Command training awal berlaku pada report directory baru. Sesudah `selection_freeze.json`, training menolak perubahan selection di direktori tersebut. Untuk reproduksi independen, gunakan `--output artifacts/phase2_1_reproduction --checkpoint artifacts/models/mahjong_discard_mlp_v2_reproduction.pt`; berikan path sama ke evaluator, dengan protocol/holdout yang ditetapkan sebelum tuning. Mengulang training bukan izin mengoptimalkan fresh test yang sudah diketahui. Dataset expansion tanpa `--max-games` melanjutkan sampai akhir; counter cursor pada progress dan commit adalah sumber resume, contract READY adalah gate readiness akhir.

Checkpoint verification:

```python
import json
from pathlib import Path
from app.model_checkpoint import load_checkpoint
contract = json.loads(Path('artifacts/phase2_1/dataset_contract.json').read_text())
model, metadata = load_checkpoint(Path('artifacts/models/mahjong_discard_mlp_v2.pt'), expected_contract=contract)
print(metadata['checkpoint_sha256'])
```

Snapshot state epoch yang lengkap memuat optimizer/RNG/best weights dan menggunakan atomic pointer; partial epoch diulang dari epoch committed terakhir. Tidak perlu raw JSON extraction, database atau distributed framework. Windows commands belum diuji.

## 14. Git Safety

Branch **main**, HEAD **49ad7a2** sejak preflight sampai penutupan. Tidak ada reset/stash/clean/rebase/switch/stage/commit/push/merge/PR/deployment. Worktree berisi perubahan Phase 2 yang sudah ada ditambah Phase 2.1; perubahan requirements berasal dari Phase 2 dan tidak disentuh lagi. `datasets/` sudah untracked sebelum Phase 2.1. Large data/shards/checkpoints/prediction gzip diabaikan Git; `git check-ignore` dikonfirmasi.

Shared files Phase 2.1: `.gitignore`, `README.md`, `app/model_checkpoint.py`, `scripts/demo_ai_prediction.py`; tiga module training baru dan empat test modules, dokumentasi serta evidence baru. Inventaris lengkap: `docs/phase2_1_file_inventory.md`. Seluruh74 file original yang dilindungi mempunyai hash sama pada `preservation_before.json` / `preservation_after.json`. Checkpoint lama tetap tersedia dengan SHA `e962b71b5bc031c2cfa307e9096fb763cb70e65240523a38e73254aa2563e855`.

## 15. Phase 3 Handoff

**READY FOR PHASE 3**, dengan batasan kualitas model yang telah diukur. Rekomendasi model: `mahjong_discard_mlp_v2.pt`, karena validation selection dan common-cohort evidence lebih baik. Model lama tetap tersedia; default service/CLI lama dipertahankan demi compatibility, sehingga Phase 3 harus memilih path baru secara eksplisit.

```python
import json
from pathlib import Path
from app.services.ai_prediction_service import AIDiscardPredictionService
contract = json.loads(Path('artifacts/phase2_1/dataset_contract.json').read_text())
ai = AIDiscardPredictionService(Path('artifacts/models/mahjong_discard_mlp_v2.pt'), expected_contract=contract)
state = game_service.get_human_encoded_turn(game_id)
prediction = ai.predict(state)
# Aksi pilihan pengguna dikirim terpisah dengan state.turn_number.
```

Load sekali per aplikasi; bundle checkpoint + metadata + optional small contract JSON, tanpa training shards/arsip. Input tetap `EncodedTurnState`: int8[38,4,9], bool[235], bool[34] sama dengan[2:36], encoder/seat/turn valid. Output `DiscardPrediction`: tile/class/action rekomendasi, tuple Top-3 legal dengan skor,34 masked scores, model/encoder version, seat/turn. Service tidak membaca hidden wall/hand lawan, menulis state, atau mengeksekusi discard.

`CheckpointValidationError` untuk artifact tidak kompatibel/korup, `InvalidPredictionStateError` untuk state/mask salah, `PredictionUnavailableError` jika tidak ada legal discard. Tidak ada silent fallback/random policy. Client tetap membawa turn token dan bebas memilih aksi legal lain. Dependency inference tetap PyTorch 2.15.0/NumPy serta engine Phase 1; metadata CPU-compatible. FastAPI/Jinja2/PostgreSQL belum diimplementasikan dan tetap pekerjaan Phase 3–4.
