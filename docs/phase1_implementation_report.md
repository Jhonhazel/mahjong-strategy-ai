# PHASE 1 IMPLEMENTATION REPORT

Status dokumen: FINAL — implementasi, review independen, perbaikan regresi, dan verifikasi selesai.
Tanggal: 4 November 2026. Proyek: `mahjong-strategy-ai`.

## 1. Final Verdict

**PHASE 1 PASS** pada lingkungan macOS arm64 yang diuji, menggunakan subset strict re-extraction terverifikasi. Suite final **90 passed in 16.06s**, tanpa failure/error/skip; tiga temuan Important dari reviewer sudah dibuktikan RED→GREEN dan ditutup. Tidak ada blocker Phase 1 yang diketahui dalam cakupan ini.

Phase 1 memakai jalur korektif **strict re-extraction** yang diizinkan R0–R4. NPZ historis ditolak untuk training: terdapat 13 label ilegal dan perbedaan representasi. Tidak ada klaim full parity terhadap seluruh NPZ atau 44.421 pertandingan. Windows x64 belum dijalankan. Tidak ada training MLP, web, PostgreSQL, atau deployment.

## 2. Implemented Features

| Task | Status implementasi | File utama | Fungsi dan bukti |
| --- | --- | --- | --- |
| 1 | Implemented | `requirements.txt`, `requirements-lock.txt`, `scripts/check_env.py`, `scripts/install_pymahjonggb.py` | CPython 3.12.10, native PyMahjongGB 1.4.0 tanpa patch; Nine Gates 92 fan, shanten 0; environment test RED→GREEN. |
| 2 | Implemented | `app/domain/tiles.py`, `actions.py`, `models.py`, `exceptions.py` | 34 tile, bunga, 136/144 wall, 235 action round-trip; konformansi semua aksi terhadap kode FeatureAgent publik. |
| 3 | Implemented | `app/engine/fan_calculator.py` | Minimum 8 fan tanpa bunga, Hu/Ron/Zimo, seluruh shanten khusus native, error eksplisit, skor zero-sum; tes exact 8-fan dan konteks khusus. |
| 4 | Implemented | `app/engine/feature_encoder.py` | Observer privat per kursi; tensor/mask sesuai kontrak; public event refresh, concealed Kong, fourth tile; regression tests. |
| 5 | Implemented | `app/engine/mcr_referee.py` | Lima fase, klaim prioritas, seluruh Kong, QiangGangHu, bunga, akhir ronde, validasi Hu; 200 ronde dan konservasi tiap langkah. |
| 6 | Implemented | `app/services/bot_service.py`, `game_service.py` | Tiga bot lokal, shanten policy, human pause, RLock per sesi, token giliran, TTL/capacity/shutdown; race 20 thread. |
| 7 | Implemented & verified | `training/dataset_loader.py`, `inspect_dataset.py`, `replay.py`, `verify_encoder_parity.py` | Arsip terverifikasi, audit asli, replay independen, manifest per keputusan, group contract; angka aktual di bagian 4. |
| 8 | Implemented | `scripts/play_cli_round.py` | Interaktif dan automated human; service/referee/bot nyata sampai FINISHED. Mode module dan file langsung diuji. |

## 3. Technical Architecture

```text
Raw Botzone JSON (protokol privat tiap kursi)
  -> training/replay.py: replay_observers
  -> PerSeatObserver / FeatureEncoder yang sama dengan runtime
  -> EncodedTurnState -> NPZ strict + manifest sumber

Raw display/actions -> consumed wall prefix -> MCRRefereeEngine
  -> independent legal action replay -> compare obs/mask/act + final fan/score

MCRRefereeEngine -> GameSessionService (lock + turn token)
  -> tiga ShantenHeuristicBot + manusia melalui CLI
```

Observer hanya menerima hand/draw milik kursinya dan event publik; tidak mempunyai referensi ke referee, wall, atau hand lawan. AnGang lawan memakai identitas tersembunyi. PublicPlayerView hanya mengungkap hand akhir setelah FINISHED. Bot mendapat hand/packs sendiri dan fitur publik.

- `obs`: `int8[38,4,9]`; 0 = seat wind, 1 = prevalent wind, 2–5 = hand unary, 6–21 = discard history unary, 22–37 = known meld unary, urutan relatif self/next/opposite/previous. Dua kolom padding honor selalu nol.
- `legal_mask`: `bool[235]`; `legal_discard_mask`: `bool[34]` = mask `[2:36]`.
- Target tersimpan: action 2–35 (`int16`); target kelas MLP nanti = `action_id - 2`, 0–33; input flat 1.368 nilai. Tidak ada model dalam Phase 1.
- Versi: `ijcai2026_mcr_v1_strict`; public events diperbarui segera, sehingga berbeda dari NPZ historis.
- Service menolak expected_turn_number yang hilang/stale. Signature lama masih mempunyai default None, tetapi None tidak boleh dieksekusi. Client fase berikut wajib membawa token view.
- Wall mengikuti varian Botzone yang dibuktikan dari log: tiap kursi mengambil segmennya sendiri dari belakang. Ronde berakhir ketika segmen kursi yang harus draw habis, meskipun segmen lain masih berisi tile.

## 4. Dataset and Parity Audit

Sumber: [Dannibal/ijcai-mahjong-round2](https://huggingface.co/datasets/Dannibal/ijcai-mahjong-round2), revisi `c8435106623c106b9e03b980691bea24ba4ac240`, CC BY 4.0. Kedua ukuran dan SHA-256 cocok dengan metadata LFS yang diambil dari sumber.

| Artefak | Hasil aktual |
| --- | --- |
| `finalist_decisions.tar.gz` | 40.599.733 byte; 30 file NPZ (28 individu, 2 agregat) |
| `finalist_games.tar.gz` | 165.209.428 byte; 44.421 JSON; 2.932.192.885 byte file tidak terkompresi |
| Individu historis | 576.868 keputusan, bukan hasil penjumlahan agregat |
| `_allfield.npz` | 576.868 baris; multiset seluruh fingerprint baris identik dengan file individu |
| `_top4.npz` | 48.476 baris; subset fingerprint individu yang terverifikasi |
| Array historis | obs `(N,38,4,9)` int8; mask `(N,235)` bool; act `(N,)` int16; score `(N,)` float32 |
| Validitas historis | **FAIL: 13 label mask[act] ilegal** pada 10 file individu; seluruh NPZ historis tidak disetujui untuk training |
| Scope strict | 100 JSON pertama dalam urutan arsip pinned; seluruh attempt dicatat |
| Match lengkap verified | 84; 336 seat dibandingkan |
| Dikecualikan | 16 terminal source RE/WA; tidak dihitung sebagai pass |
| Replay error / mismatch strict | 0 / 0 |
| Keputusan strict dibandingkan | 4.482; exact 4.482; obs/mask/act mismatch masing-masing 0 |
| Data diterima | 1.879 discard dari tracked seats pada 84 match; termasuk post-Chi/Peng |
| Provenance | 1.879/1.879 mempunyai file/row raw, match_id, UID, seat, urutan, action, versi, hash; score berasal dari log asli |
| Group contract | 72 train / 7 validation / 5 test match; overlap 0; tidak ada pipeline training Phase 2 |

Diagnosis NPZ historis terpisah: 138 tracked-seat checks; 85 `not_in_npz`, 48 `mismatch`, 5 `verified_exact`. Pada 653 keputusan normal-draw yang mempunyai kandidat urutan label dan skor lengkap: exact 208, obs berbeda 445, mask berbeda 224, action berbeda 0. Rate 208/653 = 31,852986%. Angka ini **bukan** full-round parity NPZ; sampel post-meld historis tidak tersedia dan tidak ada baris NPZ historis yang diterima untuk training. Kandidat diagnostik tidak menghasilkan provenance secara otomatis.

Strict NPZ: obs `(1879,38,4,9)` int8; mask `(1879,235)` bool; act int16; score float32 aktual; match_id unicode; seat int8. Audit strict **PASS**, 0 label ilegal. Data contract dan hash implementasi disimpan; sumber event training dan serving sama, tetapi replay diterjemahkan melalui dua jalur independen dan divalidasi hingga fan/skor akhir.

Bukti mencakup event sumber: 4.177 DRAW, 4.140 PLAY, 210 CHI, 132 PENG, 11 BUGANG, 9 GANG, 77 HU dan 7 HUANG. Ini cakupan 84 match legal, bukan semua arsip. Unknown unused wall suffix hanya filler deterministik pada fixture replay referee, tidak pernah masuk observasi/dataset dan tidak diklaim sebagai wall asli.

Artefak: `datasets/environment_report.json`, `acquisition_report.json`, `audit_report.json`, `strict_audit_report.json`, `parity_report.json`, `data_contract.json`, `decision_manifest.csv`, `strict_decisions/accepted.npz`, `cli_round_42.json`. Semuanya hasil eksekusi nyata dan diabaikan Git.

## 5. Test Results

| Check | Command | Hasil | Evidence |
| --- | --- | --- | --- |
| Environment | `.venv/bin/python -m scripts.check_env` | PASS | Python 3.12.10; PyMahjongGB 1.4.0; 92 fan / shanten 0 |
| Focused unit/integration | `.venv/bin/python -m pytest -m 'not slow and not integration' -q` | PASS pada run awal | 76 passed sebelum penambahan regresi akhir; suite lengkap di bawah mencakup tes baru |
| Full round/stress | `.venv/bin/python -m pytest tests/test_mcr_engine_playthrough.py -q` | PASS | 200 seed selesai, konservasi setiap langkah; `docs/evidence/engine-stress.txt` |
| Legacy audit | `.venv/bin/python -m training.inspect_dataset` | FAIL validasi sumber (expected/reported) | 13 label ilegal; report tetap tertulis; tidak disembunyikan |
| Strict parity | `.venv/bin/python -m training.verify_encoder_parity --max-games 100 --min-matches 50` | PASS | 84 match, 4.482 exact, 0 mismatch; `docs/evidence/encoder-parity.txt` |
| Strict audit | `audit_decisions_directory(datasets/strict_decisions, datasets/strict_audit_report.json)` | PASS | 1.879 baris, 0 ilegal |
| CLI | `.venv/bin/python -m scripts.play_cli_round --auto-human-demo --seed 42 --human-seat 1 --output datasets/cli_round_42.json` | PASS | FINISHED, 336 aksi, 26 keputusan manusia, HUANGZHUANG, delta [0,0,0,0] |
| Resilience | `.venv/bin/python -m pytest tests/test_dataset_resilience.py -q` | PASS | HTTP nyata: 503 dua kali, truncation sekali, sukses ke-4; permanent failure / traversal / symlink / truncated tar ditolak |
| Concurrency/shutdown | `.venv/bin/python -m pytest tests/test_game_service.py -q` | PASS | 20 worker, 1 diterima/19 stale; drain in-flight, kapasitas, TTL, delete |
| Complete suite final setelah perbaikan review | `.venv/bin/python -m pytest -q --junitxml=docs/evidence/pytest-results.xml` | PASS | **90 passed in 16.06s**, 0 failure/error/skip; `docs/evidence/full-suite.txt`, `pytest-results.xml` |
| Syntax | `.venv/bin/python -m compileall -q app training scripts tests` | PASS | exit 0 |
| Windows x64 | — | NOT RUN | Host hanya macOS arm64 |
| Git whitespace/status | `git diff --check`; `git status --short` | NOT AVAILABLE | Direktori sejak awal bukan Git repository |

Tes HTTP membutuhkan izin bind localhost; sandbox biasa menolaknya. Run lengkap dilakukan dengan eskalasi lokal yang diizinkan, tanpa menonaktifkan tes. Tidak ada hasil Windows yang diklaim.

## 6. Files Created or Modified

Semua file implementasi baru: folder awal kosong. Daftar lengkap path ada di `docs/file_inventory.md`.

- Domain: `app/domain/{exceptions,tiles,actions,models}.py` untuk kontrak bersama.
- Engine: `app/engine/{fan_calculator,feature_encoder,mcr_referee}.py` untuk rules, scoring, observer privat.
- Layanan: `app/services/{bot_service,game_service}.py` untuk policy dan lifecycle sesi.
- Data: `training/{dataset_loader,inspect_dataset,replay,verify_encoder_parity,reporting}.py` untuk akuisisi, audit, replay, provenance dan kontrak.
- CLI/environment: `scripts/{check_env,install_pymahjonggb,play_cli_round}.py`.
- Tests: `tests/test_env_bootstrap.py`, `test_tiles_and_actions.py`, `test_fan_calculator.py`, `test_feature_encoder.py`, `test_mcr_engine_playthrough.py`, `test_game_service.py`, `test_dataset_resilience.py`, `test_dataset_audit.py`, `test_encoder_parity.py`, `test_source_action_contract.py`, `test_cli.py`; fixtures `tests/helpers.py`, package markers `__init__.py`.
- Config/reproduksi: `.gitignore`, `requirements.txt`, `requirements-lock.txt`, `pytest.ini`, `README.md`, `THIRD_PARTY_NOTICES.md`.
- Dokumen asli: tiga dokumen revisi disalin verbatim ke `docs/superpowers/{plans,specs}/` dan `docs/MAHJONG_PHASE1_RINGKASAN_REVISI_DAN_GATE.md`.
- Dokumen baru: laporan ini, `docs/execution_ledger.md`, `docs/file_inventory.md`, serta evidence nyata di `docs/evidence/`.
- Dataset/report/arsip dan referensi eksternal di `datasets/` tidak ditambahkan ke tracking.

## 7. Problems Encountered and Fixes

1. Folder kosong dan tanpa Git: bootstrap project lokal, tanpa init/stage/commit/push.
2. Default python3 adalah 3.13: `.venv` dibuat eksplisit dengan Python 3.12.
3. Compiler workaround pada plan tidak diperlukan: pip build standar berhasil; sdist juga diverifikasi dengan metadata PyPI untuk inspeksi binding.
4. GitHub technical report/source mengembalikan 404: referensi FeatureAgent resmi penulis dari Hugging Face dipin ke revisi dan SHA-256; semua codec dikonfirmasi terhadap kode itu.
5. NPZ historis: 13 mask label ilegal dan drift setelah embedded Chi/Peng discard. Solusi: re-extraction strict, tidak menyalin bug ke serving dan tidak mengarang match_id untuk NPZ.
6. UID yang sama dapat menempati dua kursi: roster per-seat eksplisit dipertahankan, bukan dipaksa satu UID satu seat.
7. HUANG menyimpan skor pada output.content, tidak selalu display.score: parser diperbaiki menggunakan angka sumber eksplisit, dengan tes nyata RED→GREEN.
8. Flower setelah draw Kong tidak berhak fan Out with Replacement Tile: engine dan observer membersihkan konteks itu, diuji terhadap aturan WMO fan 46.
9. CLI file invocation awal tidak menemukan app: bootstrap path relatif project, tanpa path developer hardcoded.
10. Token giliran diwajibkan untuk mencegah dua aksi identik pada giliran selanjutnya; ini deviasi signature opsional plan yang terdokumentasi.
11. Review independen menemukan tiga celah: arsip hilang meninggalkan READY lama, entry duplikat menggandakan threshold match, dan scalar act melewati penulisan audit FAIL. Semuanya direproduksi RED→GREEN. Kontrak sekarang BLOCKED sebelum I/O, JSON atomik, READY ditulis terakhir setelah seluruh artefak, report/contract memakai run_id yang sama, manifest/sampel di-hash; duplicate match_id dikecualikan dan conflict memblokir gate; dimensi act diperiksa sebelum len(). Tes kegagalan penulisan artefak juga RED→GREEN. Lihat `docs/evidence/code-review.md` dan `final-review-red.txt`.

Rulings lengkap ada di `docs/execution_ledger.md`: tanpa Git/history (tidak ada diff); pip tanpa patch (Windows belum terbukti); wall segmented Botzone (bukan wall fisik kontinu); tiga respons klaim termasuk auto-Pass (turn menghitung Pass); encoder strict baru (NPZ historis tidak kompatibel); token giliran wajib (client mendatang harus mengirimkannya); subset eksplisit (tidak ada klaim full corpus); koreksi fourth-tile native dan bunga/Kong. Tidak ada Minor yang ditunda. Reviewer mengecualikan deployment dan Phase 2–4; ini sesuai scope pengguna, dengan konsekuensi kemampuan tersebut belum tersedia. Tidak ada perubahan terhadap teks plan historis.

## 8. Reproduction Instructions

Jalankan dari root proyek. macOS terverifikasi:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.check_env
.venv/bin/python -m training.dataset_loader
.venv/bin/python -m training.inspect_dataset
# Command audit historis di atas keluar nonzero karena 13 label sumber ilegal.
.venv/bin/python -m training.verify_encoder_parity --max-games 100 --min-matches 50
.venv/bin/python -m pytest -m 'not slow and not integration' -q
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.play_cli_round --seed 42 --human-seat 0
.venv/bin/python -m scripts.play_cli_round --auto-human-demo --seed 42 --human-seat 1 --output datasets/cli_round_42.json
```

Di PowerShell, ganti pembuatan venv dengan `py -3.12 -m venv .venv` dan interpreter setiap command dengan `.\.venv\Scripts\python.exe`; perintah ini didokumentasikan, **belum dijalankan**. Tidak ada Python global yang dimodifikasi. Native compiler diperlukan jika belum ada wheel kompatibel.

## 9. Git Safety

Branch: **N/A**. HEAD: **N/A**. Git sejak preflight mengembalikan `not a git repository`. Semua file project ini baru, tanpa daftar modified/untracked dari Git. `git diff --check` (exit 129) dan `git status --short` (exit 128) benar-benar dicoba. Tidak ada init, branch switch, fetch, pull, reset, restore, stash, clean, stage, commit, push, merge, PR, atau deployment. Tidak ada file sumber pengguna di luar project yang diubah; instalasi pip memakai cache package standar.

## 10. Phase 2 Handoff

**READY FOR PHASE 2** untuk subset terverifikasi yang dijelaskan di atas. Hanya `datasets/strict_decisions/accepted.npz` dengan manifest dan kontrak READY yang boleh dipakai, bukan 576.868 baris NPZ historis.

- Input: 1.368 nilai dari int8 `[38,4,9]`, konversi float saat training nanti.
- Output MLP nanti: 34 logits/discard classes; terapkan bool `[34]` legal mask dari action `[2:36]`.
- Target: label tindakan pemain asli, bukan strategi optimal atau peluang menang.
- Versi encoder: `ijcai2026_mcr_v1_strict`; seluruh match harus tetap pada satu split. Group contract dan source hashes wajib dibawa ke checkpoint.
- Skor dataset berasal dari source terminal asli dan tidak menggantikan label.
- Cakupan kecil (84 match/1.879 sampel) disetujui sebagai subset terverifikasi, tidak ada klaim kecukupan untuk akurasi tertentu. Untuk corpus lebih besar, rerun re-extraction dan inspeksi semua exclusion/error baru.
- Prasyarat minimum berikutnya: pilih hanya baris manifest, group split tanpa overlap, baseline terukur, kemudian training MLP dari bobot acak dan simpan kontrak encoder. Tidak ada langkah Phase 2 yang dijalankan dalam task ini.
