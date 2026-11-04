# PHASE 2 IMPLEMENTATION REPORT

Tanggal: 4 November 2026. Status: FINAL. Proyek: `mahjong-strategy-ai`.

## 1. Final Verdict

**PHASE 2 PASS — READY FOR PHASE 3** pada macOS arm64 yang diuji. Model MLP asli telah dilatih dari inisialisasi acak, dipilih hanya dengan validation loss, disimpan/reload di CPU, dievaluasi pada split test tetap, dan dipakai untuk prediksi legal pada game nyata tanpa mutasi state.

Bukti final: **159 tes passed**, 0 failure/error/skip; 69 tes Phase 2 dan seluruh 90 tes Phase 1. Test MLP: Top-1 **41.18%**, Top-3 **72.55%**, Macro F1(34) **0.299636**, legal rate **100%**. Hasil terbatas pada **102 keputusan dari lima match**, bukan bukti generalisasi luas atau peluang menang. Windows x64 **NOT RUN**.

## 2. Implementation Summary

| Task | Status | File aktual | Fungsi / bukti |
| --- | --- | --- | --- |
| 1 Integrity gate | PASS | `training/phase2_dataset.py`, `tests/test_phase2_dataset.py` | Snapshot/hash/source/report dan seluruh alignment baris diverifikasi; malformed/tampered inputs ditolak. |
| 2 Match splitting | PASS | `training/phase2_dataset.py` | Group Phase 1 dipertahankan; 72/7/5 match, overlap nol. |
| 3 Preprocessing | PASS | `app/mlp.py`, `training/phase2_dataset.py` | Obs saja, C-order float32[1368], mask [2:36], target act−2. |
| 4 Baselines | PASS | `training/baselines.py`, `training/metrics.py`, `tests/test_phase2_metrics.py` | Prior train-only + seeded uniform legal; metrik yang sama dengan MLP. |
| 5 MLP | PASS | `app/mlp.py`, `tests/test_phase2_model.py` | 1368→64→34, ReLU/dropout, 89.826 parameter, random initialization. |
| 6 Masked BC | PASS | `app/mlp.py` | Illegal logits di-mask sebelum CE; target legal, finite loss, gradient dan perubahan bobot nyata diuji. |
| 7 Training | PASS | `training/train_mlp.py`, `tests/test_phase2_training.py` | Train/validation-only API, seeded DataLoader, AdamW, minimum validation loss, early stopping. |
| 8 Training metrics | PASS | `training/metrics.py`, `training/train_mlp.py` | Riwayat tiap epoch dan definisi Top-K/F1/NLL eksplisit. |
| 9 Held-out evaluation | PASS | `training/evaluate_mlp.py`, `tests/test_phase2_evaluation.py` | Freeze sebelum test, final checkpoint, baselines, class CSV/confusion, kalkulasi independen dan reverification. |
| 10 Checkpoint | PASS | `app/model_checkpoint.py`, `tests/test_phase2_checkpoint.py` | CPU state_dict, metadata/hash/mapping checks sebelum weights_only deserialization. |
| 11 Prediction service | PASS | `app/services/ai_prediction_service.py`, `tests/test_phase2_inference.py` | Load sekali, Top-3 legal, normalized scores, unavailable/error eksplisit, tanpa game/model mutation. |
| 12 Live integration | PASS | `app/services/ai_prediction_service.py`, `tests/test_phase2_inference.py` | GameSessionService nyata, termasuk sesudah Chi/Peng; normal gameplay selesai dengan turn token. |
| 13 CLI demo | PASS | `scripts/demo_ai_prediction.py`, `tests/test_phase2_demo.py` | Checkpoint utama nyata, seed 42, human seat 1, delapan prediksi, ronde FINISHED. |
| 14 Tests/documentation | PASS | `tests/test_phase2_*.py`, `README.md`, laporan ini | RED→GREEN terarah, review independen, 159 tes dan dokumentasi reproduksi. |

File lama yang diubah hanya `.gitignore`, `README.md`, `requirements.txt`, `requirements-lock.txt`. Daftar exact path lengkap: `docs/phase2_file_inventory.md`. Tidak ada source/referee/observer/service Phase 1 yang diubah dan tidak ada data Phase 1 yang diregenerasi.

## 3. Dataset and Provenance

- Dataset: `Dannibal/ijcai-mahjong-round2`.
- Revision: `c8435106623c106b9e03b980691bea24ba4ac240`.
- Phase 1 run ID: `84c2606383794fa8bc072d5edac7b252`.
- Encoder: `ijcai2026_mcr_v1_strict`.
- Sampel/match: **1879/84**.
- NPZ SHA-256: `45303f98bd1d1bca4ac1dbc9228de398456644030bce8b6cb74945be21d86f4d`.
- Manifest SHA-256: `c496364986aba84efba65b19ae8c96e206bc7453d077ba7b0fc503e728687eb7`.
- Seluruh hash implementasi Phase 1 cocok. Sembilan file sumber/artefak Phase 1 yang dilindungi tetap identik. NPZ historis sekitar 576.868 baris tidak dipakai.
- Contract READY dan parity PASS mempunyai run ID yang sama. Strict audit Phase 1 tidak mempunyai field run_id dalam skemanya; identitasnya dibuktikan dengan hash NPZ dan jumlah baris. Laporan lama tidak diedit untuk menambahkan run ID.
- Semua 1.879 dataset_row unik/lengkap, match/seat/action/score sesuai NPZ, source_file/log row/hash/UID/decision_order valid. Duplikat identitas: 0; repeated feature-mask-label signatures: 0.
- Hash membuktikan identitas artefak, bukan pembuktian independen setiap aturan Mahjong.

| Split | Match | Sampel | Kelas tanpa support |
| --- | ---: | ---: | --- |
| Train | 72 | 1564 | Tidak ada |
| Validation | 7 | 213 | Tidak ada |
| Test | 5 | 102 | T3 |

Algoritma tetap: SHA-256(`phase1-match-groups-v1:` + match_id), 8 byte awal unsigned big-endian modulo 100; <80 train, <90 validation, lainnya test. Seluruh intersection match kosong. Tidak ada random row split, rebalance berdasarkan held-out labels, atau pemindahan match.

Distribusi kelas aktual:

| Class | Tile | Semua | Train | Validation | Test |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | W1 | 68 | 58 | 7 | 3 |
| 1 | W2 | 59 | 53 | 2 | 4 |
| 2 | W3 | 37 | 30 | 5 | 2 |
| 3 | W4 | 45 | 36 | 6 | 3 |
| 4 | W5 | 49 | 41 | 6 | 2 |
| 5 | W6 | 41 | 34 | 3 | 4 |
| 6 | W7 | 46 | 38 | 7 | 1 |
| 7 | W8 | 58 | 49 | 5 | 4 |
| 8 | W9 | 59 | 48 | 8 | 3 |
| 9 | T1 | 68 | 59 | 8 | 1 |
| 10 | T2 | 55 | 48 | 5 | 2 |
| 11 | T3 | 45 | 39 | 6 | 0 |
| 12 | T4 | 41 | 37 | 1 | 3 |
| 13 | T5 | 37 | 27 | 6 | 4 |
| 14 | T6 | 34 | 24 | 8 | 2 |
| 15 | T7 | 45 | 40 | 3 | 2 |
| 16 | T8 | 46 | 39 | 6 | 1 |
| 17 | T9 | 64 | 55 | 5 | 4 |
| 18 | B1 | 57 | 52 | 4 | 1 |
| 19 | B2 | 58 | 46 | 8 | 4 |
| 20 | B3 | 42 | 36 | 4 | 2 |
| 21 | B4 | 40 | 35 | 4 | 1 |
| 22 | B5 | 50 | 44 | 2 | 4 |
| 23 | B6 | 46 | 40 | 5 | 1 |
| 24 | B7 | 36 | 29 | 5 | 2 |
| 25 | B8 | 65 | 55 | 7 | 3 |
| 26 | B9 | 65 | 51 | 10 | 4 |
| 27 | F1 | 69 | 51 | 11 | 7 |
| 28 | F2 | 68 | 52 | 11 | 5 |
| 29 | F3 | 91 | 78 | 9 | 4 |
| 30 | F4 | 76 | 63 | 7 | 6 |
| 31 | J1 | 85 | 66 | 12 | 7 |
| 32 | J2 | 63 | 53 | 6 | 4 |
| 33 | J3 | 71 | 58 | 11 | 2 |

Distribusi empat identitas pemain/bot (UID publik sumber, jumlah sampel):

| UID | Train | Validation | Test |
| --- | ---: | ---: | ---: |
| `64479d3637d38a1cc585553e` | 58 | 0 | 0 |
| `6641a0a35a5a94783d8831ba` | 108 | 11 | 14 |
| `690d978db026646c5d0dd54f` | 156 | 56 | 0 |
| `692e88f12ab5c344942824ef` | 1242 | 146 | 88 |

Identitas pemain dapat muncul lintas split; evaluasi ini match-disjoint, bukan unseen-player. Distribusi legal-action count tersimpan lengkap per split di `artifacts/phase2/data_validation.json`.

## 4. Model Architecture

`int8[38,4,9] → C-order float32[1368] → Linear(1368,64) → ReLU → Dropout(0.2) → Linear(64,34)`.

- Parameter: **89.826**, bobot awal acak, seed **2026**.
- Output: 34 logits; class 0–33 ↔ action 2–35, urutan tile kanonik Phase 1.
- Objective: masked cross-entropy, illegal logits −inf sebelum normalisasi/loss; setiap target diverifikasi legal. Tidak ada scaling/normalization tambahan.
- Optimizer: AdamW, lr 0.001, weight decay 0.0001, batch 32, maksimum 80 epoch, patience 10, num_workers 0.
- Checkpoint dipilih berdasarkan **minimum validation NLL**, bukan test atau Top-1 tertinggi.
- Device training: **mps**, setelah forward/backward probe nyata. Runtime: Python 3.12.10, PyTorch 2.15.0, NumPy 2.5.4, macOS arm64.
- Checkpoint/inference CPU. Perbedaan NLL validation MPS vs CPU reload **2.20019493735e-08**; hash isi bobot best-state cocok persis.
- CPU fixture repeatability diuji. MPS best-effort; tidak ada klaim bit-for-bit lintas device/OS.
- Tidak ada pretrained policy, RL, CNN/Transformer, fitur score/outcome/UID/match_id, maupun penggantian bot lawan.

## 5. Training Results

- Satu konfigurasi utama, **18 epoch**, **882 optimizer step**.
- Best epoch **8**, waktu training terukur **3.230459 detik**.
- Best epoch training loss (dropout aktif): **1.061225355**; train eval NLL **0.928478026**, train Top-1 **75.70%**.
- Validation NLL **1.989161188**, Top-1 **31.92%**, Top-3 **59.15%**, Macro F1(34) **0.182905407**.
- Early stopping setelah 10 epoch tanpa penurunan validation NLL. Pada epoch terakhir, train Top-1 mencapai 91.43%, tetapi validation NLL naik menjadi 2.204118360; ini menunjukkan overfitting pada data kecil. Bobot epoch 8 dipulihkan dan disimpan.
- Test tidak diberikan ke `train_model`; primary evaluation baru dijalankan setelah checkpoint/configuration freeze dan perbaikan review. Tidak ada perubahan hyperparameter atau bobot setelah melihat hasil test.
- Riwayat lengkap: `artifacts/phase2/training_history.json`.

## 6. Baseline Comparison

| Model | Validation Top-1 | Test Top-1 | Test Top-3 | Test Macro F1(34) | Legal Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Prior kelas training | 22.54% | 33.33% | 59.80% | 0.201879 | 100.00% |
| Uniform random legal | 10.80% | 16.67% | 39.22% | 0.160943 | 100.00% |
| MLP epoch 8 | 31.92% | 41.18% | 72.55% | 0.299636 | 100.00% |

Prior memakai frekuensi training saja, add-one smoothing alpha=1, dan tie-break class ID terkecil. Random memakai seed 2026 dan permutasi kelas legal tanpa pengulangan; NLL-nya dari distribusi uniform legal. Baseline test dinilai pada split yang sama sesudah freeze. Perbedaan yang terukur bukan klaim signifikansi statistik atau kemenangan game.

## 7. Final Test Evaluation

**102 sampel / lima match**, 33 kelas dengan support. MLP:

- Top-1 **42/102 = 41.18%**.
- Top-3 **74/102 = 72.55%**.
- Macro F1 seluruh 34 kelas **0.299636129**.
- Macro F1 kelas dengan support **0.308716012**.
- Cross-entropy/NLL **1.663495413**.
- Legal prediction rate **100%**.

Macro F1 menetapkan precision/recall/F1 dengan denominator nol menjadi nol. Mean seluruh 34 kelas tetap memasukkan T3 dengan F1=0; mean supported-class mengecualikan kelas tanpa target. Top-3 memakai maksimal tiga kelas legal; jika hanya satu/dua legal, semua yang tersedia dipakai.

Per-class support/precision/recall/F1 lengkap: `artifacts/phase2/per_class_metrics.csv`. Confusion matrix 34×34 (baris=true, kolom=predicted): `artifacts/phase2/confusion_matrix.csv`. Detail JSON dan prediksi setiap dataset_row: `evaluation_metrics.json` / `test_predictions.json`.

Contoh confusion terbanyak: B9 → F2: 2; B5 → F2: 2; B2 → F2: 2; W9 → J1: 1; W9 → F2: 1; W8 → W1: 1; W8 → T9: 1; W8 → T2: 1. Model masih salah pada 60/102 Top-1 keputusan dan beberapa kelas mempunyai recall rendah. Test lebih baik daripada validation pada sampel ini; ukuran lima match tidak cukup untuk klaim generalisasi luas. Tidak ada bootstrap CI atau kalibrasi yang diklaim. Akurasi klasifikasi perilaku bukan peluang memenangkan Mahjong.

## 8. Checkpoint Evidence

- File: `artifacts/models/mahjong_discard_mlp.pt` (361733 byte), state_dict tensor CPU float32.
- Metadata: `artifacts/models/mahjong_discard_mlp.metadata.json`.
- SHA-256: `e962b71b5bc031c2cfa307e9096fb763cb70e65240523a38e73254aa2563e855`.
- Model version: `discard_mlp_v1:e962b71b5bc0`.
- Encoder/dataset/revision/run/hash/split/architecture/epoch/configuration/validation/test summary dicatat lengkap.
- Load menggunakan `torch.load(..., map_location='cpu', weights_only=True)` setelah pemeriksaan metadata, encoder, input/output, preprocessing, tile/action map dan checksum. Corrupt/missing/incompatible artifacts ditolak.
- CPU reload terverifikasi, selected weight-content hash cocok, dan file checkpoint tidak berubah saat evaluasi/inferensi.
- Freeze record: `artifacts/phase2/model_freeze.json`. Final evaluation PASS dipublikasikan terakhir setelah metadata dan seluruh artefak berhasil; checksum masing-masing disimpan. `--verify-existing` berhasil setelah membaca kembali bukti tersimpan dan menghitung ulang metrik.

## 9. Real Game Inference

Demo nyata: seed **42**, human seat **1**, model checkpoint utama, **8** prediksi. Ronde selesai pada turn **132**, ending `ron`, 9 fan, score deltas `[-17, -8, 33, -8]`.

Prediksi pertama, turn 4 / `SELF_TURN`:

- Own visible hand: `W5 T1 T2 T2 T3 B2 B4 B5 B6 B7 B7 B9 J1 J2`.
- Legal discard mask bool[34]: `[False, False, False, False, True, False, False, False, False, True, True, True, False, False, False, False, False, False, False, True, False, True, True, True, True, False, True, False, False, False, False, True, True, False]`.
- True class IDs: `[4, 9, 10, 11, 19, 21, 22, 23, 24, 26, 31, 32]`.
- Rekomendasi: **J1**, class 31, action 33.

| Tile | Class | Action | Skor model |
| --- | ---: | ---: | ---: |
| J1 | 31 | 33 | 0.397954017 |
| J2 | 32 | 34 | 0.250010610 |
| T1 | 9 | 11 | 0.078117251 |

Skor adalah softmax terbatas aksi legal untuk perilaku discard, tidak terkalibrasi sebagai peluang menang. Setiap permintaan mempertahankan view, turn, obs dan mask; semua rekomendasi legal. Demo meliputi SELF_TURN dan POST_MELD_DISCARD. Tes integrasi juga mencakup kedua Chi dan Peng. Normal gameplay memakai policy terpisah dan `expected_turn_number`, sehingga rekomendasi tidak melakukan discard otomatis. Detail: `artifacts/phase2/live_demo.json`; log `docs/evidence/phase2_live_demo.txt`.

## 10. Testing Results

| Test / Command | Status | Actual Result |
| --- | --- | --- |
| Fresh Phase 1 baseline sebelum perubahan | PASS | 90 passed in 15.85s; `phase2_phase1_baseline.txt/xml` |
| `.venv/bin/python -m training.phase2_dataset` | PASS | Snapshot 1879/84, hashes, full row alignment, original groups |
| `.venv/bin/python -m training.baselines` | PASS | Validation baseline nyata; test ditunda sampai freeze |
| `.venv/bin/python -m training.train_mlp --device auto --seed 2026 --max-epochs 80 --patience 10` | PASS | MPS, 18 epoch/best8, 882 step, 3.230459s |
| `.venv/bin/python -m training.evaluate_mlp` | PASS | Frozen checkpoint, 102/5, metrics/baselines/per-class/confusion/predictions |
| `.venv/bin/python -m training.evaluate_mlp --verify-existing` | PASS | Saved artifacts, metadata, hashes dan independent recalculation cocok |
| `.venv/bin/python -m scripts.demo_ai_prediction --smoke --seed 42 --human-seat 1` | PASS | FINISHED, 8 prediksi legal/unchanged |
| `.venv/bin/python -m pytest tests/test_phase2_*.py -q` | PASS | 69 passed in 3.92s |
| `.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase2_full_suite.xml` | PASS | **159 passed in 19.87s**, seluruh 90 Phase 1 + 69 Phase 2, 0 skips/errors/failures |
| `.venv/bin/python -m compileall -q app training scripts tests` | PASS | exit 0 |
| `git diff --check` | PASS | exit 0 |
| Primary checkpoint/selected state + 9 protected Phase 1 hashes | PASS | Reload CPU, SHA-256 dan source bytes cocok |
| macOS arm64 / MPS / CPU inference | PASS | Dijalankan nyata pada host ini |
| Windows x64 | NOT RUN | Tidak tersedia pada host ini |

RED→GREEN evidence tersedia pada `docs/evidence/phase2_*_red.txt`. Beberapa unit test memakai fixture kecil/temp checkpoint untuk menguji mekanisme, bukan bukti performa model utama. Seluruh training/evaluation utama memakai snapshot riil yang diverifikasi.

## 11. Problems and Fixes

1. PyTorch belum tersedia: instal hanya wheel resmi 2.15.0 di `.venv`; dependency Phase 1 tetap versinya. Forward/backward MPS dan CPU diuji sebelum training.
2. Strict audit lama tidak mempunyai run ID: gunakan ikatan hash NPZ/jumlah baris yang terverifikasi, tidak mengubah report Phase 1.
3. Reviewer menemukan reverification bisa memberi PASS ketika freeze/predictions hilang/rusak. Empat regresi RED→GREEN; sekarang seluruh bukti/hash/identity/predictions dicek dan saved metrics dihitung ulang.
4. Reviewer menemukan PASS ditulis sebelum metadata. Fault injection RED→GREEN; PASS sekarang penulisan terakhir, kegagalan menjadi FAIL, recovery hanya model/config/data frozen yang sama melalui `--resume`.
5. Overfitting: train accuracy bertambah ketika validation NLL memburuk; early stopping/minimum validation loss mempertahankan epoch 8. Tidak ada tuning menggunakan test.

Tidak ada temuan Critical/Minor yang tertunda. Rulings lengkap: `docs/phase2_execution_ledger.md`; review: `docs/evidence/phase2_code_review.md`. Batasan yang tetap ada: test kecil/known-player overlap, skor belum dikalibrasi, MPS tidak dijanjikan bit-exact lintas hardware, Windows belum diuji. Phase 1 Mahjong correctness tidak diklaim terbukti ulang hanya dari hash.

## 12. Reproduction Instructions

Gunakan `.venv` proyek yang ada. Dari root, pada lingkungan macOS yang diuji:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m training.phase2_dataset
.venv/bin/python -m training.baselines
# Pada checkout/artifact directory yang baru:
.venv/bin/python -m training.train_mlp --device auto --seed 2026 --max-epochs 80 --patience 10
.venv/bin/python -m training.evaluate_mlp
# Untuk memeriksa hasil yang sudah ada tanpa mengganti held-out record:
.venv/bin/python -m training.evaluate_mlp --verify-existing
.venv/bin/python -m scripts.demo_ai_prediction --smoke --seed 42 --human-seat 1 --output artifacts/phase2/live_demo.json
.venv/bin/python -m pytest tests/test_phase2_*.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app training scripts tests
```

Semua jalur utama di atas telah dijalankan; tidak perlu venv baru. `requirements-lock.txt` menyimpan versi aktual. Untuk mengulang training tanpa mengganti model yang telah dievaluasi, gunakan `--checkpoint artifacts/models/reproduction.pt --report-dir artifacts/phase2/reproduction` dan berikan path sama ke evaluator. Recovery penulisan artefak memakai `--resume`, tidak mengizinkan perubahan checkpoint/config/data. Lihat README untuk opsi tersebut. Tidak ada alternate hyperparameter search yang dijalankan.

Metadata dapat dibaca dengan `python -m json.tool artifacts/models/mahjong_discard_mlp.metadata.json`. PowerShell memakai `.\.venv\Scripts\python.exe`; Windows **NOT RUN**. Jangan menjalankan extractor/audit Phase 1 yang menulis ulang snapshot hanya untuk training Phase 2.

## 13. Git Safety

Branch tetap **main**, HEAD tetap **49ad7a2**. Empat tracked files berubah: `.gitignore`, `README.md`, `requirements.txt`, `requirements-lock.txt`; source/test/dokumen/artifact summary Phase 2 baru belum di-stage. Untracked `datasets/` sudah ada sejak preflight dan dipertahankan. Checkpoint `.pt` terbukti diabaikan Git; metadata/evaluation summaries kecil tersedia untuk review. `git diff --check` PASS. Tidak ada staging, commit, push, merge, branch switch, PR atau deployment. Tidak ada source/tes/data/evidence historis Phase 1 yang diubah.

## 14. Phase 3 Handoff

**READY FOR PHASE 3** dengan cakupan kualitas model yang terbatas di atas. Tidak ada FastAPI/Jinja2/PostgreSQL/browser game yang dibangun dalam task ini.

```python
import json
from pathlib import Path
from app.services.ai_prediction_service import AIDiscardPredictionService

contract = json.loads(Path('datasets/data_contract.json').read_text())
ai = AIDiscardPredictionService(
    Path('artifacts/models/mahjong_discard_mlp.pt'),
    expected_contract=contract,
)
state = game_service.get_human_encoded_turn(game_id)
prediction = ai.predict(state)
# Pilihan aksi pengguna dikirim terpisah:
# game_service.submit_human_action(game_id, chosen_action_id, state.turn_number)
```

- Inisialisasi satu service per aplikasi; model tervalidasi dimuat sekali pada CPU. Dataset training besar tidak dibutuhkan untuk inference; expected contract JSON kecil dapat dibundel untuk ikatan provenance.
- Input: `EncodedTurnState` Phase 1, obs int8[38,4,9], full mask bool[235], discard mask bool[34] identik dengan [2:36], encoder version/seat/turn valid.
- Output `DiscardPrediction`: recommended tile/class/action, tuple `top3` dengan tile/class/action/score, tuple 34 masked scores, model/encoder version, seat dan turn. Model tidak memilih Hu/Kong atau menjalankan aksi.
- `PredictionUnavailableError`: tidak ada legal discard. `InvalidPredictionStateError`: state/mask/encoder tidak sesuai. `CheckpointValidationError`: model/metadata hilang, korup atau tidak kompatibel. Tidak ada fallback ke model random atau unduhan checkpoint remote.
- Prediksi hanya membaca snapshot, tidak mengubah sesi, wall, hand, turn, bobot atau DB; tidak menerima hand lawan tersembunyi. Client harus tetap membawa token giliran saat aksi dipilih, dan dapat memilih aksi legal lain.
- Artefak: `artifacts/models/mahjong_discard_mlp.pt` + sidecar metadata; dependency PyTorch 2.15.0 serta dependency Phase 1. Inference CPU telah diverifikasi; Windows belum.
- Keterbatasan ilmiah: 1.564 sampel training, 102 test dari lima match, empat identitas pemain yang sudah dikenal, tanpa kalibrasi/unseen-player proof. Model meniru discard behavior, bukan strategi optimal atau probabilitas kemenangan.

Referensi API primer: [PyTorch state_dict / weights_only / CPU loading](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html), [MPS backend](https://docs.pytorch.org/docs/2.15/notes/mps.html). Hasil performa di atas berasal dari eksekusi lokal, bukan angka sumber eksternal.
