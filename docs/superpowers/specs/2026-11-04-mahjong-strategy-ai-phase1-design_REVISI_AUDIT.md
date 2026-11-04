# Spesifikasi Desain Teknis — Mahjong Strategy AI (Kontrak Global & Tahap 1: Core MCR Engine, Bot, Dataset, dan Feature Encoder `38×4×9`)

- **Tanggal:** 4 November 2026
- **Proyek:** Mahjong Strategy AI — *Play, Predict & Learn* (UAS Pemrograman Web Framework)
- **Cakupan Dokumen:** Dekomposisi Lintas-Tahap (Tahap 1–4) + Spesifikasi Desain Penuh **Tahap 1**
- **Status:** REVISI AUDIT — siap memulai implementasi Phase 1 dengan koreksi R0–R4; belum lulus Phase 1

---


## 0. REVISI AUDIT 4 NOVEMBER 2026 — BACA SEBELUM IMPLEMENTASI

> **Status keputusan:** *APPROVED TO START PHASE 1 WITH CORRECTIVE GATES*, **bukan** Phase 1 lulus. Dokumen ini adalah desain/rencana, bukan bukti kode telah dieksekusi. Target UAS tetap game web playable satu ronde + prediksi MLP hasil training sendiri + PostgreSQL CRD; tidak ada klaim model optimal.
>
> **Prioritas 21 hari:** bukti state game → encoder → data berlabel harus lolos lebih dulu, baru memperluas sistem. Jangan menghabiskan minggu pertama pada retry jaringan, 256 sesi, dan stress test sebelum satu ronde playable.

### R0. Kewajiban koreksi dan urutan gerbang

| ID | Temuan audit | Tindakan wajib | Bukti kelulusan |
|---|---|---|---|
| R0-01 | `obs` dataset belum mengandung `match_id` per baris; metadata file/daftar pertandingan tidak sama dengan pemetaan sampel | Bangun manifest **setiap sampel** `(source_file, row_index, match_id, seat, decision_index, encoder_version)` lewat rekonstruksi log yang terverifikasi. Jika pencocokan NPZ ambigu/tidak lengkap, **buat ulang dataset keputusan dari log JSON** dengan encoder sama seperti serving; jangan mengira baris NPZ dapat dipisah per pertandingan | Tidak ada `match_id` kosong/ambigu dalam data yang dipakai training; semua `match_id` hanya berada pada **satu** split train/validation/test |
| R0-02 | Script parity berpotensi `continue` saat error dan mengklaim 100% dari subset yang lolos | Rekam semua log yang dibaca, dikecualikan, gagal replay, kandidat ambigu, dan mismatch; tulis laporan **sebelum** fail. Parity 100% hanya dinyatakan untuk seluruh keputusan dalam **cakupan eksplisit** yang benar-benar telah dibandingkan. `mask` dan `act` wajib ikut dibandingkan | `parity_report.json` menunjukkan `attempted/verified/unmatched/failed`, penyebab dan contoh error, jumlah keputusan, rate dari denominator jujur; 0 mismatch pada set yang dinyatakan lulus |
| R0-03 | Data asal memiliki kemungkinan ketidaksamaan penanganan buangan sesudah Chi/Peng; 'parity subset' bukan 'full parity' | Audit dua jalur: (a) encoder live yang memproses semua event MCR; (b) perilaku ekstraksi data asli. Bila berbeda, gunakan **re-extracted strict corpus** untuk training atau perbaiki encoder; tidak boleh melatih dari NPZ lama lalu serving dengan encoder yang tidak identik | E2E test mengambil state game nyata, encoder yang sama dengan training menghasilkan shape/dtype/mask benar dan prediksi sah |
| R0-04 | Pembaruan fitur publik lawan pada contoh `PerSeatObserver` belum konsisten | Pastikan setiap `Play`, `Chi`, `Peng`, `Gang`, `BuGang` yang mengubah keadaan publik memperbarui `obs` **sebelum** pengambilan fitur berikutnya; tambah regression test | Event lawan mengubah planes discard/meld sesuai expected; tidak mengungkap hidden hand |
| R0-05 | Perhitungan *fourth tile* hanya menghitung keping tampak, dan exception fan calculator ditelan luas | Uji salinan dalam tangan sendiri + area publik + ubin menang tanpa double-count; bedakan *non-winning hand* yang memang tidak memenuhi syarat dengan error perangkat lunak. Jangan `except Exception: return False` untuk semua error | Test untuk 8 fan, self draw, Ron, 4th-tile, kong, corrupted input, dan exception tak terduga lulus |
| R0-06 | Instalasi `PyMahjongGB==1.4.0` memakai patch source dan asumsi nama folder tar, lintas OS belum dibuktikan | Uji instalasi di **macOS arm64 dan Windows x64** sedini mungkin. Gunakan paket sumber `sdist` yang dipilih eksplisit dan diverifikasi hash; ekstraksi aman. Jangan menganggap `rtk` command baku | `scripts/check_env.py` lulus di lingkungan target; dokumentasikan perintah standar tanpa `rtk` |
| R0-07 | Full Mahjong MCR dan hardening production-grade tidak sebanding deadline 3 minggu jika diprioritaskan bersamaan | **MVP gate**: CLI satu ronde legal, bot sederhana, encoder teruji, model checkpoint, endpoint inferensi, browser game + DB CRD. Stress test lanjut setelah MVP | Demo end-to-end pada lingkungan lokal dan laporan pengujian aktual |

### R1. Aturan manifest dan pemisahan dataset (kontrak wajib Tahap 1 → Tahap 2)

- File `datasets/decision_manifest.csv` atau `.parquet` harus memiliki minimal `source_file`, `source_row`, `match_id`, `player_uid`, `seat`, `decision_order`, `target_action_id`, `encoder_version`, `replay_status`, dan `source_hash`.
- Satu baris manifest = satu sampel *Play/Discard* yang benar-benar dapat dilacak ke satu game. Tidak boleh ada dua penetapan `match_id` berbeda untuk indeks data yang sama; setiap kasus ambigu masuk laporan dan **tidak digunakan untuk training**.
- Bila ada kecocokan NPZ ↔ replay yang tidak satu-ke-satu, **jangan membuat provenance dari dugaan**. Bangun ulang data `(obs, mask, act, match_id)` langsung dari log JSON menggunakan `FeatureEncoder` yang sama dengan runtime game; evaluasi ketidakcocokan ini secara eksplisit.
- Split training/validation/testing berdasar **`match_id`**, bukan acak baris. Contoh target proporsi 80/10/10 *berdasarkan group*; cek `set(train.match_id).isdisjoint(set(val.match_id))`, dan pasangan split lainnya.
- Arsip `_allfield.npz` dan `_top4.npz` adalah agregat; jangan dijumlahkan lagi sebagai sampel baru bersama file individu. Bilangan 576.868 dari rencana asal adalah **nilai yang harus diaudit**, bukan bukti yang sudah dihasilkan kelompok.
- Label BC adalah *tindakan yang dilakukan pemain/bot pada dataset*, **bukan** label strategi optimal maupun peluang kemenangan.

### R2. Definisi hasil parity yang boleh dilaporkan

- `full_parity`: kecocokan `obs`, `mask`, dan `act` untuk seluruh keputusan dalam **pertandingan/sesi yang diakui sebagai verified**; tampilkan `n_matches_verified`, `n_decisions_compared`, `n_mismatches`, `n_matches_unmatched`, `n_matches_failed_replay`, dan contoh alasan.
- `partial_parity`: kecocokan pada subset terbatas, misalnya sebelum event `Chi/Peng`; tidak boleh dinamai `full_round_parity`.
- Jika sumber `.npz` terdokumentasi memiliki perbedaan dari state live, dua jalan sah: **(A)** adaptasi encoder runtime sehingga cocok betul dengan fitur training tanpa melanggar informasi publik, atau **(B)** train ulang di dataset yang diekstraksi dari log mentah menggunakan encoder runtime; pilihan wajib tertulis dalam `datasets/data_contract.json`.
- Tidak boleh hardcode `parity_rate: 1.0`; hasil dihitung dari nilai perbandingan aktual. Error parsing dan hilang provenance **tidak dihitung sebagai pass**.

### R3. Gerbang waktu 21 hari (MVP dulu)

1. **Hari 1–3:** environment, data sample, game CLI minimal; uji 1 ronde legal yang selesai.
2. **Hari 4–5:** replay dan feature encoder; bukti parity yang dapat diaudit atau pilih jalur *re-extraction* yang sah.
3. **Hari 6–10:** corpus dengan `match_id` valid, group split, baseline, training MLP, checkpoint, inferensi dari state game.
4. **Hari 11–16:** FastAPI + Jinja2/JS board + sesi game + PostgreSQL riwayat Create/Read/Delete.
5. **Hari 17–21:** pengujian integrasi, bugfix, dokumentasi, video, ekspor SQL, dan presentasi. Hardening (stress 200 ronde/race/HTTP retry) setelah fitur inti stabil; jangan mengklaim lulus test yang belum dijalankan.

### R4. Bukti yang wajib disertakan saat menyatakan Phase 1 lulus

`environment_report.json`, `audit_report.json`, `parity_report.json`, `decision_manifest.*`, bukti kelompok split tanpa overlap, hasil `pytest` nyata, serta log satu game CLI end-to-end. **Tidak ada nilai akurasi AI** dalam Phase 1 karena training adalah Tahap 2.

**Sumber pembanding publik:** [Corpus IJCAI 2026](https://huggingface.co/datasets/Dannibal/ijcai-mahjong-round2), [PyMahjongGB 1.4.0](https://pypi.org/project/PyMahjongGB/), [laporan teknis asal](https://github.com/SuuTTT/IJCAI-mahjong/blob/master/doc/TECHNICAL_REPORT_IJCAI2026_MCR.md). Ketersediaan sumber tidak berarti implementasi sudah diuji.

---

## 1. Tujuan & Peta Dekomposisi Proyek

Proyek **Mahjong Strategy AI** bertujuan membangun aplikasi web terintegrasi berbasis **FastAPI + Jinja2 + PostgreSQL + PyTorch** yang memungkinkan pengguna memainkan satu ronde **Chinese Standard Mahjong / Mahjong Competition Rules (MCR)** melawan tiga bot lokal, memperoleh rekomendasi pembuangan keping (*Play/Discard*) dari model **Multilayer Perceptron (MLP)** berbasis *Behavior Cloning* pada dataset **IJCAI-2026 Chinese Standard Mahjong (`Dannibal/ijcai-mahjong-round2`)**, serta mengelola riwayat prediksi (*Create, Read, Delete*) di PostgreSQL.

Untuk memitigasi risiko teknis tertinggi sejak awal (kesetaraan representasi fitur antara *game engine* dan *dataset training*), keseluruhan proyek didekomposisi menjadi **4 sub-proyek berurutan** dengan kontrak antarmuka yang dikunci di dokumen ini:

| Tahap | Nama Sub-Proyek | Fokus & Gerbang Kelulusan (*Exit Gate*) |
|---|---|---|
| **Tahap 1 (Dokumen Ini)** | **Core MCR Engine, Heuristic Bot, Audit Dataset, & *Bit-Exact Encoder Parity*** | Ronde MCR 1 manusia vs 3 bot dapat dimainkan tuntas via layanan Python/CLI tanpa kebocoran kartu lawan, dan kontrak encoder dibuktikan dengan audit parity `obs`/`mask`/`act` yang **dilaporkan lengkap**, tanpa silent skip. Jika parity NPZ historis tidak tercapai, dataset training direkonstruksi dari log JSON dengan encoder yang sama dengan serving dan provenance `match_id` eksplisit. |
| **Tahap 2** | **Pipeline Training, Evaluasi Riil, & Serving Artefak MLP** | Pemisahan dataset berbasis `match_id` (anti-*leakage*), *baseline* pembanding, pelatihan MLP dari bobot acak di PyTorch, perhitungan metrik aktual (Top-1, Top-3, Macro F1, Valid-Action Rate), dan `AIService` siap inferensi. |
| **Tahap 3** | **Backend FastAPI, Orkestrasi Sesi Web, & PostgreSQL CRUD** | Integrasi `GameSessionService` + `AIService` + PostgreSQL nyata (dengan *retry/backoff*, *connection pooling*, *graceful shutdown*, dan *integration test* tanpa *fake mock*) untuk endpoint permainan serta CRD histori prediksi. |
| **Tahap 4** | **Frontend Interaktif Jinja2 + CSS + JavaScript & Pengemasan UAS** | Antarmuka papan Mahjong MCR interaktif, panel *AI Prediction*, halaman *Home* (metrik nyata), *History* (Read/Delete), *Contact Us*, ekspor `.sql`, dan dokumentasi akhir. |

---

## 2. Keputusan Desain Kunci yang Telah Dikunci

1. **Arsitektur *Botzone Protocol-Native* + `PyMahjongGB`:** Komunikasi internal antara wasit meja (`MCRRefereeEngine`) dan pengamat per kursi (`PerSeatObserver` / `FeatureEncoder`) menggunakan protokol pesan standar **Botzone Chinese Standard Mahjong**, selaras dengan sumber data kompetisi IJCAI-2026 (`SuuTTT/IJCAI-mahjong`). Kalkulasi syarat menang minimal **8-fan** dan *shanten* menggunakan pustaka resmi PyPI `PyMahjongGB`.
2. **Interaksi MCR Penuh untuk Kursi Manusia:** Pemain manusia memegang kendali penuh atas seluruh aksi legal yang ditawarkan aturan MCR—baik saat giliran sendiri (`Play/Discard`, `AnGang`, `BuGang`, `Hu/Zimo`) maupun saat merespons keping buangan lawan (`Chi`, `Peng`, `MingGang`, `Hu/Ron`, `Pass`). Fitur prediksi MLP secara spesifik terikat pada fase giliran `Play/Discard` manusia.
3. **Standar Pembuktian *Bit-Exact Replay Parity*:** Tahap 1 mengunduh kedua arsip dataset (`finalist_decisions.tar.gz` dan `finalist_games.tar.gz`), memutar ulang log pertandingan JSON asli melalui `PerSeatObserver`, dan menargetkan kecocokan `100%` (`np.array_equal`) terhadap `obs (38, 4, 9)` dan `mask (235,)` **pada cakupan rekaman yang diverifikasi**, serta label `act`. Seluruh replay gagal, sampel ambigu, dan mismatch harus tercatat; bila representasi `.npz` lama berbeda, digunakan re-ekstraksi data dari log mentah menggunakan encoder runtime yang sama.
4. **Dukungan Lintas Sistem Operasi Tim:** Seluruh komponen dirancang berjalan konsisten pada **Windows (x64)** dan **macOS Apple Silicon (`arm64`)** menggunakan CPython `3.11` atau `3.12`.
5. **Tanpa Data Palsu & *Context-First Wiring*:** Dilarang menggunakan tensor *dummy*, angka akurasi rekayasa, ataupun *fake mock* yang memotong jalur logika. Seluruh komponen Tahap 1 langsung dihubungkan dari hulu ke hilir melalui `GameSessionService`, skrip CLI interaktif, dan *suite* pengujian otomatis berbasis data riil.

---

## 3. Kontrak Antarmuka Global Lintas-Tahap

Kontrak tipe data berikut bersifat tetap dan menjadi jembatan antara Tahap 1, Tahap 2, Tahap 3, dan Tahap 4:

### 3.1 Keping (*Tile*) dan Ruang Aksi (`235` Aksi ↔ `34` Kelas *Discard*)
- **34 Jenis Keping Utama (`tile_index: 0..33`):**
  - `0..8`: `W1..W9` (*Wan / Characters* 1–9)
  - `9..17`: `T1..T9` (*Tiao / Bamboo* 1–9)
  - `18..26`: `B1..B9` (*Bing / Dots* 1–9)
  - `27..30`: `F1..F4` (*Feng / Winds*: East, South, West, North)
  - `31..33`: `J1..J3` (*Jian / Dragons*: Red/Zhong, Green/Fa, White/Bai)
- **8 Keping Bunga Opsional Protokol (`H1..H8`):** Ditangani sebagai transaksi penggantian bunga otomatis (`BuHua`) pada level meja jika dimuat di tembok 144 ubin, dan tidak pernah menjadi pilihan *discard* maupun bagian dari 34 kelas target MLP.
- **Ruang Aksi `235` (`action_id: 0..234`):**
  - Rincian blok aksi standar MCR IJCAI-2026 (`1 + 1 + 34 + 63 + 34 + 34 + 34 + 34 = 235`):
    - `0`: `Pass` (1 aksi)
    - `1`: `Hu` (1 aksi)
    - `2..35`: `Play` / *Discard* (34 jenis keping)
    - `36..98`: `Chi` (63 kombinasi: 3 suit angka × 7 keping tengah `2..8` × 3 posisi keping klaim)
    - `99..132`: `Peng` (34 jenis keping)
    - `133..166`: `MingGang` / Kong Terbuka dari buangan lawan (34 jenis keping)
    - `167..200`: `AnGang` / Kong Tertutup dari tangan sendiri (34 jenis keping)
    - `201..234`: `BuGang` / Promosi `Peng` menjadi Kong (34 jenis keping)
  - Urutan di dalam setiap blok diverifikasi secara otomatis terhadap berkas `.npz` dan log JSON asli pada `training/verify_encoder_parity.py`, serta diekspos sebagai konstanta terpusat (`PLAY_ACTION_OFFSET = 2`, `NUM_TILE_TYPES = 34`, `ACTION_SPACE_SIZE = 235`) di `app/domain/actions.py`.
  - Konversi label model MLP (Tahap 2): `class_idx = action_id - PLAY_ACTION_OFFSET` (`0..33`) dan `discard_legal_mask = legal_mask[PLAY_ACTION_OFFSET : PLAY_ACTION_OFFSET + 34]`.

### 3.2 Struktur Data Pertukaran Antar-Lapisan
- **`EncodedTurnState` (Output Tahap 1 → Input Tahap 2 `AIService`):**
  - `obs: np.ndarray` dengan `shape=(38, 4, 9)` dan `dtype=np.int8`
  - `legal_mask: np.ndarray` dengan `shape=(235,)` dan `dtype=np.bool_`
  - `legal_discard_mask: np.ndarray` dengan `shape=(34,)` dan `dtype=np.bool_`
  - `seat: int` (`0..3`), `turn_number: int`, `encoder_version: str` (`"ijcai2026_mcr_v1"`)
- **`PublicPlayerView` (Output Tahap 1 → Input Tahap 3 API & Tahap 4 UI):**
  - `game_id: str`
  - `status: Literal["WAITING_HUMAN_DISCARD", "WAITING_HUMAN_CLAIM", "FINISHED"]`
  - `human_seat: int`, `prevalent_wind: int`, `active_seat: int`, `turn_number: int`
  - `wall_tiles_remaining: int`
  - `own_hand: list[str]` (hanya milik kursi manusia, terurut kanonik)
  - `own_flowers: list[str]`
  - `seat_public_states: list[SeatPublicState]` (untuk kursi `0..3`: jumlah kartu tertutup sebagai angka bulat saja tanpa isi kartu, daftar *melds* terbuka beserta sumber klaim, daftar keping bunga, dan daftar riwayat *discard* berurutan)
  - `legal_actions: list[LegalActionOption]` (setiap opsi berisi `action_id: int`, `action_type: str`, `tile: str | None`, `meld_tiles: list[str] | None`, `label: str`)
  - `can_request_ai_prediction: bool` (bernilai `True` hanya jika `status == "WAITING_HUMAN_DISCARD"`)
  - `round_result: RoundResult | None` (diisi saat `FINISHED`: tipe akhir `HU` atau `HUANGZHUANG`, kursi pemenang, kursi pemberi ubin jika *Ron*, total *fan*, rincian daftar nama *fan* MCR beserta poinnya, perubahan skor 4 kursi, dan pengungkapan tangan akhir ke-4 pemain setelah ronde resmi berakhir).

---

## 4. Arsitektur Modul & Struktur Direktori Tahap 1

```text
mahjong/
├── app/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── exceptions.py        # Hierarki error eksplisit domain, sesi, & dataset
│   │   ├── models.py            # Dataclass/Pydantic kontrak: PublicPlayerView, EncodedTurnState, RoundResult
│   │   ├── tiles.py             # Codec kanonik 34 jenis ubin, grid (4,9), & bunga H1..H8
│   │   └── actions.py           # Codec dua arah 235 ruang aksi <-> aksi MCR & 34 kelas Play
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── fan_calculator.py    # Adapter terisolasi PyMahjongGB (8-fan Hu check & Shanten)
│   │   ├── feature_encoder.py   # PerSeatObserver: stream event Botzone -> obs(38,4,9) + mask(235)
│   │   └── mcr_referee.py       # Wasit meja MCR 4 pemain (wall, klaim prioritas, QiangGangHu, hasil ronde)
│   └── services/
│       ├── __init__.py
│       ├── bot_service.py       # Antarmuka BotPolicy + ShantenHeuristicBot & RandomLegalBot
│       └── game_service.py      # GameSessionService (per-game lock, bounded store, pause-on-human, shutdown)
├── training/
│   ├── __init__.py
│   ├── dataset_loader.py        # Downloader Hugging Face (retry+backoff, validasi arsip, safe extract)
│   ├── inspect_dataset.py       # Audit kuantitatif seluruh .npz -> datasets/audit_report.json
│   └── verify_encoder_parity.py # Replay log JSON vs .npz -> bukti np.array_equal 100% + indeks match_id
├── scripts/
│   ├── check_env.py             # Diagnostik lingkungan lintas-OS (Windows x64 & macOS arm64) + PyMahjongGB
│   └── play_cli_round.py        # Runner CLI interaktif 1 ronde penuh (wiring hulu-hilir Tahap 1)
├── tests/
│   ├── test_tiles_and_actions.py
│   ├── test_fan_calculator.py
│   ├── test_mcr_engine_playthrough.py
│   ├── test_encoder_parity.py
│   └── test_edge_cases_and_resilience.py
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-11-04-mahjong-strategy-ai-phase1-design.md
├── datasets/                    # Diabaikan Git (.gitignore), menyimpan raw archive & laporan audit JSON
├── requirements.txt
├── .gitignore
└── THIRD_PARTY_NOTICES.md       # Atribusi lisensi dataset CC-BY-4.0 & pustaka pihak ketiga
```

---

## 5. Spesifikasi Teknis Komponen Inti

### 5.1 `FanCalculatorAdapter` (`app/engine/fan_calculator.py`)
- Membungkus `MahjongFanCalculator` dan `MahjongShanten` dari `PyMahjongGB`.
- Menyediakan fungsi murni `evaluate_hu(packs, hand_tiles, win_tile, is_zimo, is_fourth_tile, is_kong_replacement, is_robbing_kong, is_last_tile, seat_wind, prevalent_wind) -> tuple[int, list[tuple[int, str]]]`.
- Syarat sah `Hu`: total *fan* dari elemen non-bunga wajib `>= 8` (sesuai aturan resmi MCR dan Botzone, ubin bunga `H1..H8` menambah poin akhir bila sudah memenuhi syarat dasar 8-fan, tetapi **tidak** dihitung untuk menembus ambang minimum 8-fan).
- Menyediakan fungsi `calculate_shanten(packs, hand_tiles) -> int` untuk dipakai oleh `ShantenHeuristicBot`.

### 5.2 `MCRRefereeEngine` (`app/engine/mcr_referee.py`)
- Mengelola siklus hidup satu ronde penuh secara deterministik berdasarkan `seed: int`.
- Mendukung konfigurasi tembok standar MCR (136 ubin utama maupun 144 ubin dengan bunga `BuHua`, mengikuti persis mode pertandingan Botzone MCR).
- **Aturan Transisi & Prioritas Klaim:**
  1. **Pembagian Awal (`Deal`):** 13 ubin utama untuk tiap kursi (`0..3`), diikuti penggantian bunga beruntun bila mode 144 ubin aktif, lalu kursi `0` (*East*) melakukan `Draw` pertama.
  2. **Fase Pasca-`Draw` (atau Pasca-`Peng`/`Chi`):**
     - Pasca-`Draw` (atau `Draw` pengganti Kong): mengevaluasi legalitas `Hu` (*Zimo* ≥ 8 fan), `AnGang` (4 ubin identik di tangan, selama sisa tembok `> 0`), `BuGang` (memiliki 1 ubin tangan yang cocok dengan *meld* `Peng` terbuka sendiri, selama sisa tembok `> 0`), dan `Play` (seluruh ubin di tangan tertutup).
     - Pasca-`Peng` atau `Chi`: hanya aksi `Play` yang diizinkan (sesuai aturan MCR, tidak boleh langsung deklarasi Kong pada giliran klaim `Peng`/`Chi` sebelum gilirannya berikutnya, dan tidak boleh menang langsung tanpa `Draw`).
  3. **Jendela Interupsi `BuGang` (*QiangGangHu / Robbing the Kong*):** Ketika pemain mendeklarasikan `BuGang`, 3 pemain lain diperiksa apakah dapat memenangkan ubin tersebut (`>= 8 fan` dengan flag `is_robbing_kong=True`) dan ditawarkan opsi `[Hu, Pass]` sebelum `Draw` pengganti Kong dijalankan.
  4. **Fase Klaim Pasca-`Play`:** Ketika kursi `d` membuang ubin `t`, 3 kursi lainnya diperiksa hak klaimnya:
     - `Hu` (*Ron* ≥ 8 fan pada ubin `t`).
     - `MingGang` (memiliki 3 ubin `t` di tangan tertutup dan sisa tembok `> 0`).
     - `Peng` (memiliki `>= 2` ubin `t` di tangan tertutup).
     - `Chi` (hanya untuk kursi `(d + 1) % 4`, memiliki 2 ubin berurutan se-suit di tangan yang membentuk *chow* dengan `t`).
     - Resolusi keputusan klaim setelah semua kursi yang berhak merespons: **`Hu` > (`MingGang` / `Peng`) > `Chi` > Semua `Pass`**. Jika lebih dari satu kursi memilih `Hu` bersamaan, pemenang tunggal dipilih berdasarkan urutan kursi terdekat berlawanan arah jarum jam dari pembuang `d` (`(d + 1) % 4`, lalu `(d + 2) % 4`, lalu `(d + 3) % 4`), sesuai protokol resmi Botzone MCR.
  5. **Kondisi Berakhir Ronde (`FINISHED`) & Perhitungan Skor MCR Resmi:**
     - Ronde berakhir seketika saat satu `Hu` tereksekusi, atau berakhir seri (`HUANGZHUANG`) ketika pemain perlu melakukan `Draw` tetapi sisa ubin di tembok sudah `0`.
     - Rumus perubahan skor 4 kursi (`score_deltas`) mengikuti standar resmi MCR:
       - **Menang *Zimo* (*Self-Draw*):** Tiga pemain lawan masing-masing membayar `(8 + total_fan)` kepada pemenang; pemenang memperoleh `+3 × (8 + total_fan)`.
       - **Menang *Ron* (Klaim Buangan / *QiangGangHu*):** Pemain pemberi ubin membayar `(8 + total_fan)` sedangkan dua pemain lainnya masing-masing membayar poin dasar `8`; pemenang memperoleh `+(24 + total_fan)`.
       - **Seri (`HUANGZHUANG`):** Perubahan skor `[0, 0, 0, 0]`.
  6. **Pengaman Struktural (*Hard Step Ceiling*):** Engine membatasi jumlah transisi langkah maksimum dalam satu ronde pada `MAX_ROUND_STEPS = 600` (jauh di atas batas matematis maksimum 144 ubin + seluruh klaim), melempar `EngineInvariantError` bila terlampaui agar mustahil terjadi perulangan tak berujung.

### 5.3 `PerSeatObserver` / `FeatureEncoder` (`app/engine/feature_encoder.py`)
- Satu instans `PerSeatObserver` hanya memelihara pengetahuan satu kursi (`seat_id`). Ia tidak memiliki referensi ke `MCRRefereeEngine` maupun ke daftar kartu kursi lain.
- Setiap kali menerima pesan event protokol Botzone untuk kursinya, `PerSeatObserver` memperbarui struktur internalnya (angin meja, angin kursi, hitungan ubin di tangan tertutup sendiri, daftar *packs/melds* ke-4 kursi dalam koordinat relatif `[self, next, opposite, prev]`, riwayat buangan ke-4 kursi, dan penghitung ubin yang belum terlihat) serta menyusun `obs: int8[38, 4, 9]` dan `legal_mask: bool[235]`.
- Definisi eksak setiap *channel* `0..37` pada `obs` dan setiap indeks `0..234` pada `legal_mask` diselaraskan 1-ke-1 dengan implementasi sumber dataset IJCAI-2026 (`SuuTTT/IJCAI-mahjong`) dan dikunci menggunakan pengujian paritas biner (`np.array_equal`).

### 5.4 `ShantenHeuristicBot` (`app/services/bot_service.py`)
- Mengimplementasikan antarmuka `BotPolicy.select_action(encoded_state: EncodedTurnState, view: SeatPrivateBotView, rng: random.Random) -> int`.
- Urutan aturan keputusan:
  1. Jika aksi `Hu` bernilai `True` pada `legal_mask`, langsung pilih `Hu`.
  2. Jika berada di jendela klaim (`AnGang`, `BuGang`, `MingGang`, `Peng`, `Chi` tersedia bersama `Pass`): hitung `shanten_before` vs `shanten_after` menggunakan `FanCalculatorAdapter.calculate_shanten`. Ambil klaim hanya bila `shanten_after < shanten_before` (atau `shanten_after == shanten_before` khusus untuk `AnGang`/`BuGang` yang tidak mempersempit fleksibilitas tangan); selain itu pilih `Pass`.
  3. Jika berada di fase wajib `Play/Discard`: evaluasi semua keping `c` dengan `legal_discard_mask[c] == True`. Pilih keping yang meminimalkan `shanten` dari 13/N-1 keping tersisa; bila seri, prioritaskan membuang keping yang jumlah salinan tersisanya di meja/tangan paling sedikit (ubin terisolasi, *honor* tunggal, atau terminal `1`/`9`).

### 5.5 `GameSessionService` (`app/services/game_service.py`)
- Mengelola kumpulan sesi permainan aktif di memori dengan kuota terukur (`max_active_sessions: int = 256`, `session_ttl_seconds: int = 3600`).
- **Pause-on-Human Loop:** Saat `create_game()` maupun `submit_human_action()` dipanggil, layanan otomatis menjalankan langkah ke-3 kursi bot menggunakan `ShantenHeuristicBot`. Pada jendela klaim lawan di mana satu-satunya aksi legal kursi manusia hanyalah `Pass` (`legal_mask` hanya bernilai `True` pada `action_id == 0`), sistem otomatis mengirimkan `Pass` tanpa menghentikan permainan. Sebaliknya, loop **selalu berhenti** dan mengembalikan kontrol ke pengguna apabila:
  1. Kursi manusia sedang berada pada giliran sendiri pasca-`Draw` / pasca-klaim (`WAITING_HUMAN_DISCARD`, termasuk kasus tepi ketika seluruh ubin tersisa di tangan manusia berjenis kembar sehingga hanya ada 1 opsi `Play` unik), atau
  2. Kursi manusia berada pada jendela klaim dan memiliki minimal satu opsi klaim sah selain `Pass` (`WAITING_HUMAN_CLAIM`), atau
  3. Ronde telah mencapai status `FINISHED`.

---

## 6. Penanganan Kegagalan (*Anti Happy-Path*), Concurrency, & Backpressure

| Area Risiko | Mekanisme Penanganan Eksplisit |
|---|---|
| **Kegagalan Jaringan / Koneksi Putus saat Unduh Dataset** | `dataset_loader.py` menerapkan *retry* hingga 4 percobaan dengan *exponential backoff + jitter* (`1s, 2s, 4s, 8s`) pada kegagalan jaringan/HTTP `429`/`5xx`, *timeout* eksplisit per *socket read* (`30s`), serta unduhan ke berkas sementara `*.part`. Jika seluruh percobaan gagal, berkas parsial tidak pernah dianggap valid dan sistem melempar `DatasetDownloadError` berisi penyebab teknis terperinci. |
| **Arsip Korup atau *Path Traversal*** | Sebelum ekstraksi, arsip `.tar.gz` divalidasi integritas *gzip/tar* dan ukuran minimumnya. Ekstraksi memvalidasi setiap path anggota arsip agar berada ketat di bawah direktori tujuan (`os.path.commonpath`), menolak *symlink* keluar maupun `..` dengan `CorruptedDatasetError`. |
| **Input Tidak Valid pada Permainan** | `game_id` kosong/asing melempar `GameNotFoundError`; mengirim aksi ke ronde tamat melempar `GameAlreadyFinishedError`; mengirim `action_id` di luar `0..234` atau aksi dengan `legal_mask[action_id] == False` melempar `IllegalActionError` **sebelum** menyentuh state `MCRRefereeEngine`. |
| **Race Condition / Klik Ganda Serentak** | Setiap sesi game memiliki `threading.RLock` dedikasi, ditambah `store_lock` terpisah untuk manajemen kamus sesi. Jika dua *request* mengirim aksi bersamaan untuk `game_id` yang sama pada `turn_number` yang sama, *request* kedua baru masuk setelah *request* pertama memajukan state sehingga pasti tertolak aman oleh pemeriksaan nomor giliran / legalitas aksi tanpa korupsi memori. |
| **Backpressure Memori Sesi & *Graceful Shutdown*** | Saat membuat game baru ketika jumlah sesi aktif mencapai `max_active_sessions`, sistem terlebih dahulu menyapu sesi yang sudah melewati `session_ttl_seconds` atau sudah `FINISHED` lebih dari batas retensi singkat; bila seluruh slot benar-benar sedang dipakai sesi aktif, sistem menerapkan *backpressure* tegas dengan melempar `SessionCapacityExceededError` (tidak pernah menghapus paksa game pemain lain yang sedang berlangsung). Metode `shutdown(timeout_sec)` menghentikan penerimaan game baru dan menunggu seluruh *per-game lock* yang sedang memproses langkah selesai (*drain in-flight steps*) secara bersih. |

---

## 7. Strategi Verifikasi & Kriteria Penerimaan Tahap 1 (*No Fake Mocks*)

Tahap 1 baru dinyatakan **LULUS** untuk lanjut ke Tahap 2 apabila seluruh pembuktian otomatis dan terukur berikut terpenuhi:

1. **Diagnostik Lingkungan (`scripts/check_env.py`):** Berhasil mengimpor `numpy`, `PyMahjongGB`, dan pustaka inti tanpa galat, serta lulus uji hitung cepat 8-fan dan *shanten*.
2. **Audit Kuantitatif Dataset Riil (`training/inspect_dataset.py`):** Menghasilkan `datasets/audit_report.json` dari berkas `.npz` asli `Dannibal/ijcai-mahjong-round2` yang melaporkan jumlah berkas pemain, total baris keputusan riil, dimensi terverifikasi `(N, 38, 4, 9)` & `(N, 235)`, bukti `100%` `mask[act] == True`, serta distribusi kelas 34 ubin.
3. **Bukti *Bit-Exact Replay Parity* (`tests/test_encoder_parity.py`):** Memutar ulang minimal **50 pertandingan lengkap** (mencakup ratusan hingga ribuan titik keputusan `Play`) dari log JSON `finalist_games.tar.gz` melalui `PerSeatObserver` kita dan melaporkan hasil `np.array_equal` untuk `obs (38, 4, 9)`, `legal_mask (235,)`, dan `act` dengan denominator jelas (`attempted/verified/failed/unmatched/mismatched`) serta menghasilkan manifest per-keputusan dengan `match_id`. Kecocokan 100% **hanya boleh dinyatakan jika benar-benar dicapai pada seluruh sampel cakupan valid**; jika tidak, re-ekstraksi dan pengujian ulang wajib dilakukan.
4. **Ketahanan Ronde Penuh & Isolasi Informasi (`tests/test_mcr_engine_playthrough.py`):** Menjalankan **200 ronde penuh** otomatis dengan `seed` berbeda tanpa *crash* maupun *stuck*, membuktikan jumlah total keping selalu kekal di setiap langkah, membuktikan pemenang `Hu` selalu memiliki `>= 8 fan` sah, serta memastikan objek `PublicPlayerView` selama permainan aktif tidak mengandung kartu tertutup milik kursi lawan.
5. **Pembuktian *Edge-Cases*, *Race Condition*, & Kegagalan I/O (`tests/test_edge_cases_and_resilience.py`):**
   - Uji **input invalid**: penolakan `IllegalActionError`, `GameNotFoundError`, dan `GameAlreadyFinishedError` tanpa mutasi state.
   - Uji **race condition nyata**: 20 *worker thread* mengeksekusi `submit_human_action` serentak pada satu `game_id` yang sama → tepat 1 berhasil memajukan giliran, 19 gagal terkendali dengan exception domain, dan integritas state tetap utuh.
   - Uji **backpressure & graceful shutdown**: pengisian slot hingga `max_active_sessions` memicu `SessionCapacityExceededError` tanpa menghapus sesi aktif, serta pemanggilan `shutdown()` menolak sesi baru dan menuntaskan langkah yang sedang berjalan.
   - Uji **koneksi terputus & arsip rusak**: menggunakan *local HTTP test server* sungguhan yang menyimulasikan putus koneksi / `HTTP 503` pada 2 percobaan awal sebelum pulih di percobaan ke-3 (membuktikan *retry + backoff* bekerja nyata), serta menguji penolakan arsip `.tar.gz` terpotong (*truncated*) dan arsip berbahaya (*path traversal*).
6. **Keterhubungan Hulu-Hilir via CLI (`scripts/play_cli_round.py`):** Satu ronde MCR penuh (1 manusia vs 3 `ShantenHeuristicBot`) dapat dijalankan end-to-end melalui terminal menggunakan `GameSessionService` dan `PerSeatObserver` yang sama persis dengan yang akan dipakai FastAPI di Tahap 3.
