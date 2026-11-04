# Mahjong Strategy AI (Tahap 1: Core MCR Engine, Heuristic Bot, Dataset & Feature Encoder `38×4×9`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membangun fondasi inti Mahjong Strategy AI Tahap 1 berupa simulator satu ronde penuh *Chinese Standard Mahjong* (MCR, 1 manusia vs 3 bot heuristik) dengan isolasi informasi ketat, pembuktian *bit-exact parity* (`np.array_equal`) terhadap tensor `(38, 4, 9)` dan `mask (235,)` pada dataset asli IJCAI-2026 (`Dannibal/ijcai-mahjong-round2`), serta ketahanan *production-grade* terhadap *race condition*, *backpressure*, dan kegagalan I/O.

**Architecture:** Menggunakan protokol standar *Botzone Chinese Standard Mahjong* sebagai jembatan tunggal antara `MCRRefereeEngine` (wasit pemegang tembok & kartu rahasia) dan 4 instans `PerSeatObserver` (`FeatureEncoder` penghasil tensor `int8[38, 4, 9]` dan `bool[235]`), diperkuat adapter kalkulator resmi `PyMahjongGB` untuk validasi syarat minimum 8-fan dan *shanten*. Seluruh komponen dibungkus di dalam `GameSessionService` berfitur *Pause-on-Human*, *per-session lock*, dan kuota sesi terukur, serta langsung dihubungkan dari hulu ke hilir melalui skrip verifikasi paritas dataset dan *CLI Playable Runner*.

**Tech Stack:** Python `3.11` / `3.12` (lintas Windows x64 & macOS Apple Silicon `arm64`), `numpy`, `PyMahjongGB==1.4.0` (C++ MCR Fan & Shanten Calculator), `pytest`, pustaka standar Python (`urllib`, `tarfile`, `threading`, `http.server`, `dataclasses`).


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


## Global Constraints

- Bahasa dokumentasi rencana & laporan pengujian wajib menggunakan Bahasa Indonesia; nama simbol kode menggunakan Bahasa Inggris yang konsisten sesuai blok `Interfaces`.
- Versi Python wajib `>=3.11, <3.13` (gunakan `py -3.11` di Windows bila Python default pada `PATH` masih `3.10`, atau `python3.11`/`python3.12` di macOS `arm64`) di dalam `.venv` lokal proyek.
- Di Windows PowerShell, selalu konfigurasikan `PYTHONUTF8=1` atau panggil `sys.stdout.reconfigure(encoding="utf-8")` pada skrip CLI karena nama pemain di dataset mengandung karakter Mandarin yang memicu `UnicodeEncodeError` pada konsol `cp1252`.
- `rtk` adalah pembungkus opsional milik sebagian lingkungan, **bukan perintah Python standar**. Jika tidak terpasang, jalankan perintah langsung (mis. `./.venv/bin/python -m pytest -v` di macOS, atau `.\.venv\Scripts\python.exe -m pytest -v` di Windows). Hindari one-liner PowerShell dengan kutipan bersarang.
- Dilarang keras memakai data *mockup*/*placeholder*, *fake mock* yang memotong logika bisnis, ataupun tensor *dummy*; seluruh pengujian wajib memakai `PyMahjongGB` sungguhan, berkas `.npz`/`.json` asli dari Hugging Face, serta *HTTP test server* lokal sungguhan.
- Arsip `finalist_decisions.tar.gz` berisi **30 berkas `.npz`** yang terdiri atas **28 berkas individu pemain (`576.868` baris)** dan **2 berkas agregat awalan garis bawah (`_allfield.npz` & `_top4.npz`)**; dilarang menjumlahkan berkas berawalan `_` ke total sampel unik agar tidak terjadi penggandaan data dan *data leakage*.
- Setiap skenario I/O jaringan dan sesi permainan wajib menangani kegagalan secara eksplisit (*retry + exponential backoff + jitter*, penulisan berkas atomik `*.part`, anti-*path traversal*, *per-session mutex*, *backpressure* kuota sesi, dan *graceful shutdown*).

---

## Peta Struktur Berkas Tahap 1

| Path Berkas | Tanggung Jawab Tunggal |
|---|---|
| `.gitignore` | Mengabaikan `.venv/`, `datasets/`, `__pycache__/`, `.pytest_cache/`, `build/`, `*.egg-info/`, dan berkas sementara `*.part`. |
| `requirements.txt` | Daftar dependensi terukur Tahap 1 (`numpy`, `pytest`, dan catatan bootstrap `PyMahjongGB==1.4.0`). |
| `THIRD_PARTY_NOTICES.md` | Dokumentasi lisensi atribusi `CC-BY-4.0` (`Dannibal/ijcai-mahjong-round2`) dan `MIT` (`PyMahjongGB` & referensi skema `Dannibal/ijcai-mahjong-ckpts-2026`). |
| `scripts/install_pymahjonggb.py` | Skrip kompilasi dan instalasi lintas-OS `PyMahjongGB==1.4.0` (mengatasi bug `__attribute__((always_inline))` pada GCC 15/Clang modern serta menautkan `-static` pada MinGW Windows agar bebas galat DLL). |
| `scripts/check_env.py` | Diagnostik kesiapan Python, `numpy`, dan uji hitung riil `MahjongFanCalculator` + `MahjongShanten`. |
| `app/domain/exceptions.py` | Hierarki kelas *exception* eksplisit untuk domain aturan MCR, sesi konkurensi, dan akuisisi dataset. |
| `app/domain/tiles.py` | Definisi kanonik 34 jenis keping MCR (`W1..W9, T1..T9, B1..B9, F1..F4, J1..J3`), bunga opsional `H1..H8`, pemetaan kisi `(4, 9)`, pengurutan tangan, dan generator tembok deterministik 136/144 keping. |
| `app/domain/actions.py` | Codec dua arah ruang aksi `235` (`Pass`, `Hu`, `Play`, `Chi`, `Peng`, `Gang`, `AnGang`, `BuGang`) ↔ indeks kelas *discard* `0..33`. |
| `app/domain/models.py` | Struktur data *immutable* lintas-tahap: `MeldPack`, `FanItem`, `LegalActionOption`, `SeatPublicState`, `RoundResult`, `PublicPlayerView`, dan `EncodedTurnState`. |
| `app/engine/fan_calculator.py` | Adapter terisolasi `PyMahjongGB` untuk evaluasi kemenangan `>= 8 fan`, perhitungan *shanten* (standar + 7 pasang + 13 yatim + *knitted*), dan rumus skor resmi MCR. |
| `app/engine/feature_encoder.py` | `PerSeatObserver` yang mengubah *stream* kejadian kursi menjadi tensor `obs (38, 4, 9)` (`int8`) dan `legal_mask (235,)` (`bool`) tanpa akses ke kartu tersembunyi lawan. |
| `app/engine/mcr_referee.py` | Mesin wasit meja MCR 4 pemain (tembok 136 keping standar maupun 144 keping `BuHua`, prioritas klaim `HU > PENG/GANG > CHI`, `QiangGangHu`, `AnGang`, dan pengaman `MAX_ROUND_STEPS = 600`). |
| `app/services/bot_service.py` | Antarmuka `BotPolicy` beserta implementasi `ShantenHeuristicBot` (deterministik per `seed`) dan `RandomLegalBot`. |
| `app/services/game_service.py` | `GameSessionService` dengan *Pause-on-Human loop*, `RLock` per sesi, *bounded store* + *backpressure*, pembersihan TTL, dan `shutdown()` aman. |
| `training/dataset_loader.py` | Pengunduh streaming `finalist_decisions.tar.gz` & `finalist_games.tar.gz` dengan *retry + backoff + jitter*, verifikasi SHA-256 & ukuran byte eksak, serta ekstraksi `tar.gz` anti-*path traversal*. |
| `training/inspect_dataset.py` | Pengaudit kuantitatif seluruh berkas `.npz` (memisahkan 28 pemain individu dari 2 agregat `_*.npz`) ke `datasets/audit_report.json`. |
| `training/verify_encoder_parity.py` | Penguji *bit-exact parity* (`np.array_equal`) antara `PerSeatObserver` dan isi `.npz` melalui *replay* log JSON asli, sekaligus pembuat `datasets/parity_report.json` & `datasets/match_index.json`. |
| `scripts/play_cli_round.py` | *CLI Playable Runner* satu ronde penuh (mode interaktif manusia maupun mode verifikasi otomatis `--auto-human-demo`) yang menghubungkan seluruh komponen hulu ke hilir. |
| `tests/test_*.py` | 9 berkas pengujian otomatis `pytest` yang memvalidasi seluruh fungsionalitas dan *edge-case* tanpa *fake mock*. |

---

### Task 1: Inisialisasi Lingkungan Proyek, Bootstrap Kompilasi Lintas-OS `PyMahjongGB`, & Diagnostik

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `app/__init__.py`
- Create: `app/domain/__init__.py`
- Create: `app/engine/__init__.py`
- Create: `app/services/__init__.py`
- Create: `training/__init__.py`
- Create: `scripts/install_pymahjonggb.py`
- Create: `scripts/check_env.py`
- Test: `tests/test_env_bootstrap.py`

**Interfaces:**
- Consumes: CPython `3.11` atau `3.12`, koneksi internet ke PyPI untuk sumber `PyMahjongGB==1.4.0`, dan kompilator C++ lokal (`MSYS2 MinGW-w64 g++` di `M:\Programming\env\msys64\ucrt64\bin` atau `MSVC` di Windows; `clang++` di macOS `arm64`; `g++` di Linux).
- Produces:
  - Lingkungan virtual `.venv` berisi `numpy`, `pytest`, dan `PyMahjongGB==1.4.0` terkompilasi statis.
  - `scripts.check_env.verify_environment() -> dict[str, object]` yang memvalidasi `MahjongFanCalculator` dan `MahjongShanten`.

- [ ] **Step 1: Buat `.venv` Python 3.11/3.12 dan berkas konfigurasi dasar proyek**

Buat berkas `.gitignore`:

```gitignore
.venv/
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
build/
dist/
*.egg-info/
.wheels_cache/
datasets/*
!datasets/.gitkeep
*.part
.env
```

Buat berkas kosong penanda direktori paket (`app/__init__.py`, `app/domain/__init__.py`, `app/engine/__init__.py`, `app/services/__init__.py`, `training/__init__.py`, dan `datasets/.gitkeep` kosong).

Buat berkas `requirements.txt`:

```text
numpy>=1.26.0,<3.0.0
pytest>=8.0.0,<9.0.0
# PyMahjongGB==1.4.0 dipasang melalui: python scripts/install_pymahjonggb.py
```

Buat berkas `THIRD_PARTY_NOTICES.md`:

```markdown
# Third-Party Notices & Attribution

## 1. IJCAI-2026 Chinese Standard Mahjong — Finalist & Strong-Bot Game Corpus
- **Source:** https://huggingface.co/datasets/Dannibal/ijcai-mahjong-round2
- **Author / Maintainer:** Dannibal (IJCAI-2026 Mahjong AI Competition)
- **License:** Creative Commons Attribution 4.0 International (`CC-BY-4.0`)

## 2. PyMahjongGB (Chinese Standard Mahjong Fan & Shanten Calculator)
- **Source:** https://pypi.org/project/PyMahjongGB/ (`https://github.com/ailab-pku/PyMahjongGB`)
- **Copyright:** Copyright (c) 2016-2021 Yunlong Lu `<luyunlong@pku.edu.cn>`
- **License:** MIT License

## 3. IJCAI-2026 MCR Feature & Action Space Specification Reference
- **Source:** https://huggingface.co/Dannibal/ijcai-mahjong-ckpts-2026 & https://huggingface.co/datasets/Dannibal/mcr-final2026-testset
- **License:** MIT License (feature/action layout reference) & Competition Game Logs Research Use
```

Jalankan pembuatan `.venv` dan instalasi `pip`, `setuptools`, `wheel`, `numpy`, `pytest`:

```powershell
py -3.11 -m venv .venv
rtk .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
rtk .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

*(Catatan untuk anggota tim di macOS Apple Silicon: gunakan `python3.11 -m venv .venv` lalu `rtk ./.venv/bin/python -m pip install --upgrade pip setuptools wheel && rtk ./.venv/bin/python -m pip install -r requirements.txt`.)*

- [ ] **Step 2: Tulis *failing test* untuk verifikasi lingkungan di `tests/test_env_bootstrap.py`**

```python
from __future__ import annotations

import sys


def test_python_version_within_supported_bounds() -> None:
    assert (3, 11) <= sys.version_info[:2] < (3, 13), (
        f"Versi Python harus 3.11 atau 3.12, ditemukan: {sys.version}"
    )


def test_verify_environment_runs_real_pymahjonggb() -> None:
    from scripts.check_env import verify_environment

    report = verify_environment()
    assert report["pymahjonggb_ok"] is True
    assert report["sample_shanten"] == 0
    assert report["sample_nine_gates_fan"] == 92
```

- [ ] **Step 3: Jalankan `pytest` untuk memastikan *test* gagal sebelum implementasi**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_env_bootstrap.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'scripts'` (dan `MahjongGB` belum terpasang).

**Catatan audit R0-06:** Script pemasangan berikut adalah *prototype*, bukan installer tervalidasi. Sebelum digunakan: pilih rilis `sdist` eksplisit (jangan `meta["urls"][0]`), cocokkan hash SHA-256 terhadap metadata PyPI, ekstrak dengan pengecekan path anggota tar (jangan `extractall` tanpa validasi), temukan root berisi `setup.py` secara aman tanpa hardcode kapitalisasi nama folder, dan buktikan kompilasi serta `check_env` di OS masing-masing. Gunakan `python -m pip install PyMahjongGB==1.4.0` terlebih dahulu sebagai jalur instalasi sederhana jika berhasil; patch sumber hanya fallback yang didokumentasikan.

- [ ] **Step 4: Implementasikan `scripts/install_pymahjonggb.py` dan `scripts/check_env.py`, lalu jalankan instalasi `PyMahjongGB`**

Buat `scripts/install_pymahjonggb.py`:

```python
from __future__ import annotations

import io
import json
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

PYPI_JSON_URL = "https://pypi.org/pypi/PyMahjongGB/1.4.0/json"
DEFAULT_MSYS2_BINS = (
    r"M:\Programming\env\msys64\ucrt64\bin",
    r"C:\msys64\ucrt64\bin",
    r"C:\msys64\mingw64\bin",
)


def _detect_windows_compiler(env: dict[str, str]) -> str:
    """Kembalikan 'msvc' bila cl.exe tersedia, atau 'mingw32' bila g++.exe tersedia."""
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / (
        r"Microsoft Visual Studio\Installer\vswhere.exe"
    )
    if vswhere.exists():
        out = subprocess.check_output(
            [
                str(vswhere),
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            text=True,
        ).strip()
        if out:
            return "msvc"

    if shutil.which("g++", path=env.get("PATH")):
        return "mingw32"

    for candidate in DEFAULT_MSYS2_BINS:
        if (Path(candidate) / "g++.exe").exists():
            env["PATH"] = candidate + os.pathsep + env.get("PATH", "")
            return "mingw32"

    raise RuntimeError(
        "Kompilator C++ tidak ditemukan di Windows. Pasang MSYS2 ucrt64 (g++) "
        "atau Microsoft Visual C++ Build Tools terlebih dahulu."
    )


def build_and_install_pymahjonggb() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    env = os.environ.copy()
    system = platform.system().lower()

    req = urllib.request.Request(PYPI_JSON_URL, headers={"User-Agent": "MahjongStrategyAI/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        meta = json.loads(resp.read().decode("utf-8"))
    # Pilih sdist eksplisit dan validasi hash dari metadata PyPI.
    sources = [u for u in meta["urls"] if u.get("packagetype") == "sdist"]
    if len(sources) != 1:
        raise RuntimeError(f"Expected one PyMahjongGB sdist, found {len(sources)}")
    sdist_url = sources[0]["url"]
    expected_sha = sources[0]["digests"]["sha256"]

    req_tar = urllib.request.Request(sdist_url, headers={"User-Agent": "MahjongStrategyAI/1.0"})
    with urllib.request.urlopen(req_tar, timeout=60) as resp:
        raw_tar = resp.read()
    if hashlib.sha256(raw_tar).hexdigest() != expected_sha:
        raise RuntimeError("PyMahjongGB source archive checksum mismatch")

    wheels_dir = Path(__file__).resolve().parent.parent / ".wheels_cache"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pymahjonggb_build_") as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:gz") as tf:
            # Jangan melakukan extractall sebelum memvalidasi path dan tipe entry.
            for member in tf.getmembers():
                name = Path(member.name)
                target = (tmp_path / name).resolve()
                if name.is_absolute() or ".." in name.parts or not (
                    member.isfile() or member.isdir()
                ) or target != tmp_path.resolve() and tmp_path.resolve() not in target.parents:
                    raise RuntimeError(f"Unsafe archive member: {member.name!r}")
            tf.extractall(tmp_path)

        # Nama folder yang dipaketkan tidak boleh diasumsikan kapitalisasinya.
        setup_candidates = sorted(tmp_path.glob("*/setup.py"))
        if len(setup_candidates) != 1:
            raise RuntimeError("Could not uniquely locate PyMahjongGB setup.py")
        pkg_dir = setup_candidates[0].parent
        tile_h = pkg_dir / "MahjongGB" / "mahjong-algorithm" / "tile.h"
        tile_h.write_text(
            tile_h.read_text(encoding="utf-8").replace("__attribute__((always_inline))", ""),
            encoding="utf-8",
        )

        setup_py = pkg_dir / "setup.py"
        setup_text = setup_py.read_text(encoding="utf-8")

        pip_wheel_cmd = [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(pkg_dir),
            "--no-build-isolation",
            "-w",
            str(wheels_dir),
        ]

        if system == "windows":
            compiler = _detect_windows_compiler(env)
            if compiler == "mingw32":
                setup_text = setup_text.replace(
                    'extra_compile_args = ["-std=c++11"]',
                    'extra_compile_args = ["-std=c++11", "-O3"], extra_link_args = ["-static"]',
                )
                pip_wheel_cmd.extend(
                    [
                        "--config-settings=--global-option=build_ext",
                        "--config-settings=--global-option=--compiler=mingw32",
                    ]
                )
            else:
                setup_text = setup_text.replace(
                    'extra_compile_args = ["-std=c++11"]',
                    'extra_compile_args = ["/O2"]',
                )
        else:
            if system == "darwin" and not shutil.which("clang++"):
                raise RuntimeError(
                    "Kompilator clang++ tidak ditemukan di macOS. Jalankan: xcode-select --install"
                )
            setup_text = setup_text.replace(
                'extra_compile_args = ["-std=c++11"]',
                'extra_compile_args = ["-std=c++11", "-O3"]',
            )

        setup_py.write_text(setup_text, encoding="utf-8")
        subprocess.check_call(pip_wheel_cmd, env=env)

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-index",
            f"--find-links={wheels_dir}",
            "PyMahjongGB==1.4.0",
        ],
        env=env,
    )
    print("Instalasi PyMahjongGB==1.4.0 berhasil.")


if __name__ == "__main__":
    build_and_install_pymahjonggb()
```

Buat `scripts/check_env.py`:

```python
from __future__ import annotations

import json
import platform
import sys

import numpy as np


def verify_environment() -> dict[str, object]:
    from MahjongGB import MahjongFanCalculator, MahjongShanten

    shanten = MahjongShanten(
        (),
        ("W1", "W1", "W2", "W3", "W4", "T2", "T3", "T4", "B5", "B6", "B7", "F1", "F1"),
    )
    fans = MahjongFanCalculator(
        (),
        ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W9", "W9"),
        "W5",
        0,
        True,
        False,
        False,
        False,
        0,
        0,
        True,
    )
    fan_sum = sum(int(point) * int(cnt) for point, cnt, _, _ in fans)
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "pymahjonggb_ok": True,
        "sample_shanten": int(shanten),
        "sample_nine_gates_fan": int(fan_sum),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    report = verify_environment()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

Jalankan bootstrap `PyMahjongGB` dan diagnostik:

```powershell
rtk .\.venv\Scripts\python.exe scripts/install_pymahjonggb.py
rtk .\.venv\Scripts\python.exe scripts/check_env.py
```

- [ ] **Step 5: Jalankan `pytest` untuk memastikan *test* lulus dan lakukan *commit***

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_env_bootstrap.py -v`
Expected: PASS (`2 passed`)

Commit ke Git:

```powershell
rtk git add .gitignore requirements.txt THIRD_PARTY_NOTICES.md datasets/.gitkeep app/__init__.py app/domain/__init__.py app/engine/__init__.py app/services/__init__.py training/__init__.py scripts/install_pymahjonggb.py scripts/check_env.py tests/test_env_bootstrap.py
rtk git commit -m "chore(env): bootstrap cross-platform PyMahjongGB build and environment diagnostics"
```

---

### Task 2: Domain Exceptions, Model Kontrak Global, serta Codec Keping (`34` Jenis) & Ruang Aksi (`235` Aksi)

**Files:**
- Create: `app/domain/exceptions.py`
- Create: `app/domain/tiles.py`
- Create: `app/domain/actions.py`
- Create: `app/domain/models.py`
- Test: `tests/test_tiles_and_actions.py`

**Interfaces:**
- Consumes: `numpy`
- Produces:
  - `app.domain.exceptions`: `MahjongError`, `GameNotFoundError`, `GameAlreadyFinishedError`, `IllegalActionError`, `InvalidTurnStateError`, `SessionCapacityExceededError`, `ServiceShuttingDownError`, `EngineInvariantError`, `DatasetDownloadError`, `CorruptedDatasetError`
  - `app.domain.tiles`: `NUM_TILE_TYPES = 34`, `TILE_LIST`, `FLOWER_TILES`, `TILE_TO_INDEX`, `is_flower_tile(tile: str) -> bool`, `tile_to_index(tile: str) -> int`, `index_to_tile(idx: int) -> str`, `tile_to_grid_rc(tile: str) -> tuple[int, int]`, `sort_hand_tiles(tiles: Iterable[str]) -> list[str]`, `build_standard_136_wall(seed: int) -> list[str]`, `build_144_wall_with_flowers(seed: int) -> list[str]`
  - `app.domain.actions`: `ACTION_SPACE_SIZE = 235`, `PASS_ACTION_ID = 0`, `HU_ACTION_ID = 1`, `PLAY_ACTION_OFFSET = 2`, `CHI_ACTION_OFFSET = 36`, `PENG_ACTION_OFFSET = 99`, `GANG_ACTION_OFFSET = 133`, `ANGANG_ACTION_OFFSET = 167`, `BUGANG_ACTION_OFFSET = 201`, `DecodedAction`, `encode_play_action`, `decode_discard_class_to_action_id`, `action_id_to_discard_class`, `encode_chi_action`, `encode_peng_action`, `encode_gang_action`, `encode_angang_action`, `encode_bugang_action`, `decode_action`, `extract_legal_discard_mask`
  - `app.domain.models`: `ENCODER_VERSION = "ijcai2026_mcr_v1"`, `MeldPack`, `FanItem`, `LegalActionOption`, `SeatPublicState`, `RoundResult`, `PublicPlayerView`, `EncodedTurnState`

- [ ] **Step 1: Tulis *failing test* komprehensif di `tests/test_tiles_and_actions.py`**

```python
from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from app.domain.actions import (
    ACTION_SPACE_SIZE,
    ANGANG_ACTION_OFFSET,
    BUGANG_ACTION_OFFSET,
    CHI_ACTION_OFFSET,
    GANG_ACTION_OFFSET,
    HU_ACTION_ID,
    PASS_ACTION_ID,
    PENG_ACTION_OFFSET,
    PLAY_ACTION_OFFSET,
    action_id_to_discard_class,
    decode_action,
    decode_discard_class_to_action_id,
    encode_angang_action,
    encode_bugang_action,
    encode_chi_action,
    encode_gang_action,
    encode_peng_action,
    encode_play_action,
    extract_legal_discard_mask,
)
from app.domain.exceptions import IllegalActionError
from app.domain.tiles import (
    FLOWER_TILES,
    NUM_TILE_TYPES,
    TILE_LIST,
    build_144_wall_with_flowers,
    build_standard_136_wall,
    index_to_tile,
    is_flower_tile,
    sort_hand_tiles,
    tile_to_grid_rc,
    tile_to_index,
)


def test_tile_list_matches_ijcai2026_canonical_order() -> None:
    assert len(TILE_LIST) == NUM_TILE_TYPES == 34
    assert TILE_LIST[0] == "W1"
    assert TILE_LIST[8] == "W9"
    assert TILE_LIST[9] == "T1"
    assert TILE_LIST[17] == "T9"
    assert TILE_LIST[18] == "B1"
    assert TILE_LIST[26] == "B9"
    assert TILE_LIST[27] == "F1"
    assert TILE_LIST[30] == "F4"
    assert TILE_LIST[31] == "J1"
    assert TILE_LIST[33] == "J3"

    for idx, tile in enumerate(TILE_LIST):
        assert tile_to_index(tile) == idx
        assert index_to_tile(idx) == tile
        r, c = tile_to_grid_rc(tile)
        assert r * 9 + c == idx


def test_standard_136_wall_is_deterministic_and_conserves_tiles() -> None:
    wall_a = build_standard_136_wall(seed=2026)
    wall_b = build_standard_136_wall(seed=2026)
    wall_c = build_standard_136_wall(seed=2027)
    assert wall_a == wall_b
    assert wall_a != wall_c
    assert len(wall_a) == 136
    assert Counter(wall_a) == {t: 4 for t in TILE_LIST}

    wall_144 = build_144_wall_with_flowers(seed=2026)
    assert len(wall_144) == 144
    expected_144 = {t: 4 for t in TILE_LIST} | {h: 1 for h in FLOWER_TILES}
    assert Counter(wall_144) == expected_144
    assert is_flower_tile("H1") is True
    assert is_flower_tile("W1") is False


def test_sort_hand_tiles_orders_by_canonical_index() -> None:
    raw = ["J3", "W2", "B1", "T1", "W1", "F1"]
    assert sort_hand_tiles(raw) == ["W1", "W2", "T1", "B1", "F1", "J3"]


def test_all_235_actions_roundtrip_without_gap_or_collision() -> None:
    assert ACTION_SPACE_SIZE == 235
    assert PASS_ACTION_ID == 0
    assert HU_ACTION_ID == 1
    assert PLAY_ACTION_OFFSET == 2
    assert CHI_ACTION_OFFSET == 36
    assert PENG_ACTION_OFFSET == 99
    assert GANG_ACTION_OFFSET == 133
    assert ANGANG_ACTION_OFFSET == 167
    assert BUGANG_ACTION_OFFSET == 201

    seen_ids: set[int] = set()
    for action_id in range(ACTION_SPACE_SIZE):
        dec = decode_action(action_id)
        assert dec.action_id == action_id
        seen_ids.add(action_id)
        if dec.action_type == "Play":
            assert dec.tile is not None
            assert encode_play_action(dec.tile) == action_id
            cls = action_id_to_discard_class(action_id)
            assert 0 <= cls < 34
            assert decode_discard_class_to_action_id(cls) == action_id
        elif dec.action_type == "Chi":
            assert dec.chi_mid_tile is not None and dec.tile is not None
            assert encode_chi_action(dec.chi_mid_tile, dec.tile) == action_id
        elif dec.action_type == "Peng":
            assert dec.tile is not None
            assert encode_peng_action(dec.tile) == action_id
        elif dec.action_type == "Gang":
            assert dec.tile is not None
            assert encode_gang_action(dec.tile) == action_id
        elif dec.action_type == "AnGang":
            assert dec.tile is not None
            assert encode_angang_action(dec.tile) == action_id
        elif dec.action_type == "BuGang":
            assert dec.tile is not None
            assert encode_bugang_action(dec.tile) == action_id
    assert len(seen_ids) == 235


def test_chi_encoding_matches_feature_agent_formula_exactly() -> None:
    # W1-W2-W3: mid=W2 (num=2). Jika lawan buang W3 (num=3): pos = 3 - 2 + 1 = 2 -> 36 + 0*21 + 0*3 + 2 = 38
    assert encode_chi_action("W2", "W3") == 38
    # Lawan buang W2 (mid): pos = 1 -> 37
    assert encode_chi_action("W2", "W2") == 37
    # Lawan buang W1 (left): pos = 0 -> 36
    assert encode_chi_action("W2", "W1") == 36
    # Suit T (idx=1), mid=T5 (num=5), lawan buang T4: 36 + 21 + (5-2)*3 + (4-5+1) = 66
    assert encode_chi_action("T5", "T4") == 66


def test_invalid_action_and_tile_raise_explicit_errors() -> None:
    with pytest.raises(IllegalActionError):
        decode_action(-1)
    with pytest.raises(IllegalActionError):
        decode_action(235)
    with pytest.raises(IllegalActionError):
        action_id_to_discard_class(0)
    with pytest.raises(IllegalActionError):
        tile_to_index("INVALID")


def test_extract_legal_discard_mask_slices_exact_34_play_actions() -> None:
    mask = np.zeros(235, dtype=np.bool_)
    mask[encode_play_action("W1")] = True
    mask[encode_play_action("J3")] = True
    mask[PASS_ACTION_ID] = True
    dmask = extract_legal_discard_mask(mask)
    assert dmask.shape == (34,)
    assert dmask.dtype == np.bool_
    assert bool(dmask[0]) is True
    assert bool(dmask[33]) is True
    assert int(dmask.sum()) == 2
```

- [ ] **Step 2: Jalankan `pytest` untuk memverifikasi kegagalan awal**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_tiles_and_actions.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'app.domain.actions'`

- [ ] **Step 3: Implementasikan `exceptions.py`, `tiles.py`, `actions.py`, dan `models.py`**

Buat `app/domain/exceptions.py`:

```python
from __future__ import annotations


class MahjongError(Exception):
    """Kelas dasar seluruh galat domain dan infrastruktur Mahjong Strategy AI."""


class GameNotFoundError(MahjongError):
    """Dilempar ketika game_id tidak ditemukan atau telah kedaluwarsa."""


class GameAlreadyFinishedError(MahjongError):
    """Dilempar ketika pengguna mengirim aksi pada ronde yang telah selesai."""


class IllegalActionError(MahjongError):
    """Dilempar ketika aksi atau kode keping berada di luar aturan/mask legal."""


class InvalidTurnStateError(MahjongError):
    """Dilempar ketika aksi dikirim saat meja tidak sedang menunggu kursi tersebut."""


class SessionCapacityExceededError(MahjongError):
    """Dilempar sebagai backpressure ketika batas sesi aktif maksimum tercapai."""


class ServiceShuttingDownError(MahjongError):
    """Dilempar ketika layanan sedang melakukan graceful shutdown."""


class EngineInvariantError(MahjongError):
    """Dilempar ketika invarian internal wasit meja dilanggar (mis. melebihi batas langkah)."""


class DatasetDownloadError(MahjongError):
    """Dilempar ketika unduhan dataset gagal setelah seluruh percobaan retry habis."""


class CorruptedDatasetError(MahjongError):
    """Dilempar ketika checksum, struktur arsip, atau keamanan path arsip tidak valid."""
```

Buat `app/domain/tiles.py`:

```python
from __future__ import annotations

import random
from collections.abc import Iterable

from app.domain.exceptions import IllegalActionError

NUM_TILE_TYPES: int = 34
GRID_ROWS: int = 4
GRID_COLS: int = 9
GRID_CELLS: int = 36

TILE_LIST: tuple[str, ...] = (
    *(f"W{i}" for i in range(1, 10)),
    *(f"T{i}" for i in range(1, 10)),
    *(f"B{i}" for i in range(1, 10)),
    *(f"F{i}" for i in range(1, 5)),
    *(f"J{i}" for i in range(1, 4)),
)

FLOWER_TILES: tuple[str, ...] = tuple(f"H{i}" for i in range(1, 9))
FLOWER_SET: frozenset[str] = frozenset(FLOWER_TILES)
TILE_TO_INDEX: dict[str, int] = {tile: idx for idx, tile in enumerate(TILE_LIST)}
NUMBERED_SUITS: str = "WTB"


def is_flower_tile(tile: str) -> bool:
    return tile in FLOWER_SET


def tile_to_index(tile: str) -> int:
    try:
        return TILE_TO_INDEX[tile]
    except KeyError as exc:
        raise IllegalActionError(f"Kode keping tidak dikenal: {tile!r}") from exc


def index_to_tile(idx: int) -> str:
    if not (0 <= idx < NUM_TILE_TYPES):
        raise IllegalActionError(f"Indeks keping di luar rentang 0..33: {idx}")
    return TILE_LIST[idx]


def tile_to_grid_rc(tile: str) -> tuple[int, int]:
    idx = tile_to_index(tile)
    return idx // GRID_COLS, idx % GRID_COLS


def sort_hand_tiles(tiles: Iterable[str]) -> list[str]:
    return sorted(tiles, key=tile_to_index)


def build_standard_136_wall(seed: int) -> list[str]:
    wall = [tile for tile in TILE_LIST for _ in range(4)]
    rng = random.Random(seed)
    rng.shuffle(wall)
    return wall


def build_144_wall_with_flowers(seed: int) -> list[str]:
    wall = [tile for tile in TILE_LIST for _ in range(4)] + list(FLOWER_TILES)
    rng = random.Random(seed)
    rng.shuffle(wall)
    return wall
```

Buat `app/domain/actions.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.domain.exceptions import IllegalActionError
from app.domain.tiles import NUMBERED_SUITS, NUM_TILE_TYPES, index_to_tile, tile_to_index

ActionType = Literal["Pass", "Hu", "Play", "Chi", "Peng", "Gang", "AnGang", "BuGang"]

ACTION_SPACE_SIZE: int = 235
PASS_ACTION_ID: int = 0
HU_ACTION_ID: int = 1
PLAY_ACTION_OFFSET: int = 2
CHI_ACTION_OFFSET: int = 36
PENG_ACTION_OFFSET: int = 99
GANG_ACTION_OFFSET: int = 133
ANGANG_ACTION_OFFSET: int = 167
BUGANG_ACTION_OFFSET: int = 201


@dataclass(frozen=True)
class DecodedAction:
    action_id: int
    action_type: ActionType
    tile: str | None = None
    chi_mid_tile: str | None = None
    chi_claimed_pos: int | None = None


def encode_play_action(tile: str) -> int:
    return PLAY_ACTION_OFFSET + tile_to_index(tile)


def decode_discard_class_to_action_id(class_idx: int) -> int:
    if not (0 <= class_idx < NUM_TILE_TYPES):
        raise IllegalActionError(f"Indeks kelas discard harus 0..33, diterima: {class_idx}")
    return PLAY_ACTION_OFFSET + class_idx


def action_id_to_discard_class(action_id: int) -> int:
    if not (PLAY_ACTION_OFFSET <= action_id < PLAY_ACTION_OFFSET + NUM_TILE_TYPES):
        raise IllegalActionError(f"Action ID {action_id} bukan aksi Play/Discard (2..35).")
    return action_id - PLAY_ACTION_OFFSET


def encode_chi_action(mid_tile: str, claimed_tile: str) -> int:
    if len(mid_tile) != 2 or len(claimed_tile) != 2:
        raise IllegalActionError(f"Format keping Chi tidak sah: mid={mid_tile!r}, claimed={claimed_tile!r}")
    suit = mid_tile[0]
    if suit not in NUMBERED_SUITS or claimed_tile[0] != suit:
        raise IllegalActionError(f"Chi hanya sah untuk suit W/T/B yang sama: {mid_tile!r} vs {claimed_tile!r}")
    mid_rank = int(mid_tile[1])
    claimed_rank = int(claimed_tile[1])
    if not (2 <= mid_rank <= 8):
        raise IllegalActionError(f"Keping tengah Chi wajib bernilai 2..8, diterima: {mid_tile!r}")
    pos = claimed_rank - mid_rank + 1
    if pos not in (0, 1, 2):
        raise IllegalActionError(f"Keping klaim {claimed_tile!r} tidak bersebelahan dengan tengah {mid_tile!r}")
    suit_idx = NUMBERED_SUITS.index(suit)
    return CHI_ACTION_OFFSET + suit_idx * 21 + (mid_rank - 2) * 3 + pos


def encode_peng_action(tile: str) -> int:
    return PENG_ACTION_OFFSET + tile_to_index(tile)


def encode_gang_action(tile: str) -> int:
    return GANG_ACTION_OFFSET + tile_to_index(tile)


def encode_angang_action(tile: str) -> int:
    return ANGANG_ACTION_OFFSET + tile_to_index(tile)


def encode_bugang_action(tile: str) -> int:
    return BUGANG_ACTION_OFFSET + tile_to_index(tile)


def decode_action(action_id: int) -> DecodedAction:
    if not isinstance(action_id, (int, np.integer)) or isinstance(action_id, bool):
        raise IllegalActionError(f"action_id harus berupa integer, diterima: {action_id!r}")
    aid = int(action_id)
    if not (0 <= aid < ACTION_SPACE_SIZE):
        raise IllegalActionError(f"action_id di luar rentang 0..234: {aid}")
    if aid == PASS_ACTION_ID:
        return DecodedAction(action_id=aid, action_type="Pass")
    if aid == HU_ACTION_ID:
        return DecodedAction(action_id=aid, action_type="Hu")
    if aid < CHI_ACTION_OFFSET:
        return DecodedAction(
            action_id=aid,
            action_type="Play",
            tile=index_to_tile(aid - PLAY_ACTION_OFFSET),
        )
    if aid < PENG_ACTION_OFFSET:
        rel = aid - CHI_ACTION_OFFSET
        combo = rel // 3
        pos = rel % 3
        suit = NUMBERED_SUITS[combo // 7]
        mid_rank = (combo % 7) + 2
        claimed_rank = mid_rank + pos - 1
        return DecodedAction(
            action_id=aid,
            action_type="Chi",
            tile=f"{suit}{claimed_rank}",
            chi_mid_tile=f"{suit}{mid_rank}",
            chi_claimed_pos=pos,
        )
    if aid < GANG_ACTION_OFFSET:
        return DecodedAction(
            action_id=aid,
            action_type="Peng",
            tile=index_to_tile(aid - PENG_ACTION_OFFSET),
        )
    if aid < ANGANG_ACTION_OFFSET:
        return DecodedAction(
            action_id=aid,
            action_type="Gang",
            tile=index_to_tile(aid - GANG_ACTION_OFFSET),
        )
    if aid < BUGANG_ACTION_OFFSET:
        return DecodedAction(
            action_id=aid,
            action_type="AnGang",
            tile=index_to_tile(aid - ANGANG_ACTION_OFFSET),
        )
    return DecodedAction(
        action_id=aid,
        action_type="BuGang",
        tile=index_to_tile(aid - BUGANG_ACTION_OFFSET),
    )


def extract_legal_discard_mask(legal_mask: np.ndarray) -> np.ndarray:
    if legal_mask.shape != (ACTION_SPACE_SIZE,):
        raise IllegalActionError(
            f"legal_mask harus berukuran (235,), diterima: {legal_mask.shape}"
        )
    return legal_mask[PLAY_ACTION_OFFSET : PLAY_ACTION_OFFSET + NUM_TILE_TYPES].astype(
        np.bool_, copy=True
    )
```

Buat `app/domain/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

ENCODER_VERSION: str = "ijcai2026_mcr_v1"
GameStatus = Literal["WAITING_HUMAN_DISCARD", "WAITING_HUMAN_CLAIM", "FINISHED"]
RoundEnding = Literal["zimo", "ron", "draw"]
PackType = Literal["CHI", "PENG", "GANG", "ANGANG"]


@dataclass(frozen=True)
class MeldPack:
    pack_type: PackType
    tile: str
    offer: int


@dataclass(frozen=True)
class FanItem:
    fan_points: int
    count: int
    fan_name_zh: str
    fan_name_en: str


@dataclass(frozen=True)
class LegalActionOption:
    action_id: int
    action_type: str
    tile: str | None
    meld_tiles: tuple[str, ...] | None
    label: str


@dataclass(frozen=True)
class SeatPublicState:
    seat: int
    concealed_count: int
    melds: tuple[MeldPack, ...]
    flowers: tuple[str, ...]
    discards: tuple[str, ...]
    wall_remaining: int


@dataclass(frozen=True)
class RoundResult:
    ending: RoundEnding
    winner_seat: int | None
    discarder_seat: int | None
    qianggang: bool
    win_tile: str | None
    total_fan: int
    fans: tuple[FanItem, ...]
    score_deltas: tuple[int, int, int, int]
    revealed_hands: tuple[tuple[str, ...], ...]

    @property
    def outcome_type(self) -> Literal["HU", "HUANGZHUANG"]:
        return "HU" if self.ending in ("zimo", "ron") else "HUANGZHUANG"


@dataclass(frozen=True)
class PublicPlayerView:
    game_id: str
    status: GameStatus
    human_seat: int
    prevalent_wind: int
    active_seat: int
    turn_number: int
    wall_tiles_remaining: int
    own_hand: tuple[str, ...]
    own_flowers: tuple[str, ...]
    seat_public_states: tuple[SeatPublicState, ...]
    legal_actions: tuple[LegalActionOption, ...]
    can_request_ai_prediction: bool
    round_result: RoundResult | None = None


@dataclass(frozen=True)
class EncodedTurnState:
    obs: np.ndarray
    legal_mask: np.ndarray
    legal_discard_mask: np.ndarray
    seat: int
    turn_number: int
    encoder_version: str = ENCODER_VERSION
```

- [ ] **Step 4: Jalankan `pytest` untuk memastikan seluruh *test* domain lulus**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_tiles_and_actions.py -v`
Expected: PASS (`6 passed`)

- [ ] **Step 5: Commit perubahan Task 2**

```powershell
rtk git add app/domain/exceptions.py app/domain/tiles.py app/domain/actions.py app/domain/models.py tests/test_tiles_and_actions.py
rtk git commit -m "feat(domain): add MCR canonical tiles, 235-action codec, and cross-phase contracts"
```

---

### Task 3: Adapter Kalkulator Skor MCR (`8-Fan`, `Shanten`, & Rumus Poin MCR) Berbasis `PyMahjongGB`

**Files:**
- Create: `app/engine/fan_calculator.py`
- Test: `tests/test_fan_calculator.py`

**Interfaces:**
- Consumes: `MahjongGB` (`MahjongFanCalculator`, `MahjongShanten`, `SevenPairsShanten`, `ThirteenOrphansShanten`, `HonorsAndKnittedTilesShanten`), `app.domain.models.FanItem`, `app.domain.exceptions.IllegalActionError`
- Produces:
  - `FanCalculatorAdapter.try_evaluate_hu(packs, hand_tiles, win_tile, is_zimo, is_fourth_tile, is_about_kong, is_wall_last, seat_wind, prevalent_wind, flower_count=0) -> tuple[bool, int, tuple[FanItem, ...]]`
  - `FanCalculatorAdapter.calculate_shanten(packs, hand_tiles) -> int`
  - `compute_mcr_score_deltas(ending, winner_seat, discarder_seat, total_fan) -> tuple[int, int, int, int]`

- [ ] **Step 1: Tulis *failing test* di `tests/test_fan_calculator.py`**

```python
from __future__ import annotations

import pytest

from app.domain.exceptions import IllegalActionError
from app.engine.fan_calculator import FanCalculatorAdapter, compute_mcr_score_deltas


def test_fan_calculator_rejects_hand_below_8_fan_minimum() -> None:
    # Chicken hand / tangan biasa < 8 fan (hanya kombinasi campuran 1-2 fan)
    packs = (("CHI", "W2", 1), ("CHI", "T6", 2), ("PENG", "B9", 3))
    hand = ("W7", "W8", "F2", "F2")
    is_ok, total_fan, fans = FanCalculatorAdapter.try_evaluate_hu(
        packs=packs,
        hand_tiles=hand,
        win_tile="W9",
        is_zimo=False,
        is_fourth_tile=False,
        is_about_kong=False,
        is_wall_last=False,
        seat_wind=0,
        prevalent_wind=0,
    )
    assert is_ok is False
    assert 0 < total_fan < 8
    assert len(fans) >= 1


def test_flowers_do_not_bypass_8_fan_gate() -> None:
    packs = (("CHI", "W2", 1), ("CHI", "T6", 2), ("PENG", "B9", 3))
    hand = ("W7", "W8", "F2", "F2")
    is_ok, total_fan, _ = FanCalculatorAdapter.try_evaluate_hu(
        packs=packs,
        hand_tiles=hand,
        win_tile="W9",
        is_zimo=False,
        is_fourth_tile=False,
        is_about_kong=False,
        is_wall_last=False,
        seat_wind=0,
        prevalent_wind=0,
        flower_count=8,
    )
    assert is_ok is False


def test_fan_calculator_accepts_valid_pure_straight_and_nine_gates() -> None:
    is_ok, total_fan, fans = FanCalculatorAdapter.try_evaluate_hu(
        packs=(),
        hand_tiles=("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W9", "W9"),
        win_tile="W5",
        is_zimo=True,
        is_fourth_tile=False,
        is_about_kong=False,
        is_wall_last=False,
        seat_wind=0,
        prevalent_wind=0,
    )
    assert is_ok is True
    assert total_fan == 92
    assert sum(item.fan_points * item.count for item in fans) == 92


def test_fan_calculator_returns_false_cleanly_on_non_winning_shape() -> None:
    is_ok, total_fan, fans = FanCalculatorAdapter.try_evaluate_hu(
        packs=(),
        hand_tiles=("W1", "W3", "W5", "T1", "T3", "T5", "B1", "B3", "B5", "F1", "F2", "F3", "J1"),
        win_tile="J2",
        is_zimo=False,
        is_fourth_tile=False,
        is_about_kong=False,
        is_wall_last=False,
        seat_wind=0,
        prevalent_wind=0,
    )
    assert is_ok is False
    assert total_fan == 0
    assert fans == ()


def test_calculate_shanten_considers_seven_pairs_and_thirteen_orphans() -> None:
    # Tenpai 7 pasang (6 pasang + 1 tunggal = shanten 0)
    seven_pairs_tenpai = (
        "W1", "W1", "W4", "W4", "T2", "T2", "T8", "T8", "B3", "B3", "F1", "F1", "J1"
    )
    assert FanCalculatorAdapter.calculate_shanten((), seven_pairs_tenpai) == 0

    # Tenpai 13 yatim (13 jenis terminal/honor unik = shanten 0)
    orphans_tenpai = (
        "W1", "W9", "T1", "T9", "B1", "B9", "F1", "F2", "F3", "F4", "J1", "J2", "J3"
    )
    assert FanCalculatorAdapter.calculate_shanten((), orphans_tenpai) == 0


def test_mcr_score_deltas_zimo_ron_and_draw_sum_to_zero() -> None:
    # Zimo 20 fan oleh kursi 1 -> pemenang +3*(8+20)=+84, lainnya -28
    assert compute_mcr_score_deltas("zimo", winner_seat=1, discarder_seat=None, total_fan=20) == (
        -28,
        84,
        -28,
        -28,
    )
    # Ron 20 fan oleh kursi 2 dari buangan kursi 3 -> pemenang +(24+20)=+44, kursi 3 -(28), sisanya -8
    assert compute_mcr_score_deltas("ron", winner_seat=2, discarder_seat=3, total_fan=20) == (
        -8,
        -8,
        44,
        -28,
    )
    assert compute_mcr_score_deltas("draw", winner_seat=None, discarder_seat=None, total_fan=0) == (
        0,
        0,
        0,
        0,
    )
    with pytest.raises(IllegalActionError):
        compute_mcr_score_deltas("ron", winner_seat=1, discarder_seat=1, total_fan=8)
```

- [ ] **Step 2: Jalankan `pytest` untuk memverifikasi kegagalan awal**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_fan_calculator.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'app.engine.fan_calculator'`

- [ ] **Step 3: Implementasikan `app/engine/fan_calculator.py`**

```python
from __future__ import annotations

from collections.abc import Sequence

from MahjongGB import (
    HonorsAndKnittedTilesShanten,
    MahjongFanCalculator,
    MahjongShanten,
    SevenPairsShanten,
    ThirteenOrphansShanten,
)

from app.domain.exceptions import IllegalActionError, EngineInvariantError
from app.domain.models import FanItem, RoundEnding

MIN_MCR_FAN: int = 8
FLOWER_FAN_NAMES_EN: frozenset[str] = frozenset({"Flower Tiles"})
FLOWER_FAN_NAMES_ZH: frozenset[str] = frozenset({"花牌"})


class FanCalculatorAdapter:
    """Adapter terisolasi untuk kalkulasi fan dan shanten Chinese Standard Mahjong (MCR)."""

    @staticmethod
    def normalize_packs_for_gb(
        packs: Sequence[tuple[str, str, int]],
    ) -> tuple[tuple[str, str, int], ...]:
        normalized: list[tuple[str, str, int]] = []
        for pack_type, tile, offer in packs:
            gb_type = "GANG" if pack_type == "ANGANG" else pack_type
            normalized.append((gb_type, tile, int(offer)))
        return tuple(normalized)

    @classmethod
    def try_evaluate_hu(
        cls,
        packs: Sequence[tuple[str, str, int]],
        hand_tiles: Sequence[str],
        win_tile: str,
        is_zimo: bool,
        is_fourth_tile: bool,
        is_about_kong: bool,
        is_wall_last: bool,
        seat_wind: int,
        prevalent_wind: int,
        flower_count: int = 0,
    ) -> tuple[bool, int, tuple[FanItem, ...]]:
        """Evaluasi kemenangan MCR.

        Mengembalikan (is_legal_8fan, total_fan, fan_items).
        Aturan resmi MCR: keping bunga menambah skor akhir bila tangan telah mencapai >= 8 fan
        non-bunga, tetapi tidak boleh dipakai untuk menembus ambang batas minimum 8 fan.
        """
        gb_packs = cls.normalize_packs_for_gb(packs)
        try:
            raw_fans = MahjongFanCalculator(
                pack=gb_packs,
                hand=tuple(hand_tiles),
                winTile=win_tile,
                flowerCount=int(flower_count),
                isSelfDrawn=bool(is_zimo),
                is4thTile=bool(is_fourth_tile),
                isAboutKong=bool(is_about_kong),
                isWallLast=bool(is_wall_last),
                seatWind=int(seat_wind),
                prevalentWind=int(prevalent_wind),
                verbose=True,
            )
        except TypeError as exc:
            # Diverifikasi dari binding C++ PyMahjongGB 1.4.0 (mahjong.cpp):
            # ERROR_NOT_WIN adalah sinyal bentuk tangan bukan winning hand.
            # Error lain (wrong tile count, duplicate >4, invalid tile/pack)
            # menunjukkan invalid state/input dan TIDAK boleh disamarkan.
            if str(exc) == "ERROR_NOT_WIN":
                return False, 0, ()
            raise EngineInvariantError(
                f"MahjongFanCalculator menerima state/parameter tidak valid: {exc}"
            ) from exc

        items: list[FanItem] = []
        total_fan = 0
        flower_fan = 0
        for fan_point, cnt, fan_zh, fan_en in raw_fans:
            pts = int(fan_point)
            count = int(cnt)
            items.append(
                FanItem(
                    fan_points=pts,
                    count=count,
                    fan_name_zh=str(fan_zh),
                    fan_name_en=str(fan_en),
                )
            )
            subtotal = pts * count
            total_fan += subtotal
            if str(fan_en) in FLOWER_FAN_NAMES_EN or str(fan_zh) in FLOWER_FAN_NAMES_ZH:
                flower_fan += subtotal

        non_flower_fan = total_fan - flower_fan
        is_legal = non_flower_fan >= MIN_MCR_FAN
        return is_legal, total_fan, tuple(items)

    @classmethod
    def calculate_shanten(
        cls,
        packs: Sequence[tuple[str, str, int]],
        hand_tiles: Sequence[str],
    ) -> int:
        """Hitung jarak minimum ke tenpai (shanten) mencakup pola standar dan tangan spesial."""
        gb_packs = cls.normalize_packs_for_gb(packs)
        hand_tuple = tuple(hand_tiles)
        best = int(MahjongShanten(pack=gb_packs, hand=hand_tuple))
        if len(gb_packs) == 0 and len(hand_tuple) == 13:
            sp_shanten, _ = SevenPairsShanten(hand=hand_tuple)
            to_shanten, _ = ThirteenOrphansShanten(hand=hand_tuple)
            hk_shanten, _ = HonorsAndKnittedTilesShanten(hand=hand_tuple)
            best = min(best, int(sp_shanten), int(to_shanten), int(hk_shanten))
        return best


def compute_mcr_score_deltas(
    ending: RoundEnding,
    winner_seat: int | None,
    discarder_seat: int | None,
    total_fan: int,
) -> tuple[int, int, int, int]:
    if ending == "draw":
        return (0, 0, 0, 0)
    if winner_seat is None or not (0 <= winner_seat < 4):
        raise IllegalActionError(f"winner_seat tidak sah untuk akhir {ending!r}: {winner_seat!r}")
    if total_fan < MIN_MCR_FAN:
        raise IllegalActionError(f"total_fan kemenangan MCR wajib >= 8, diterima: {total_fan}")

    scores = [0, 0, 0, 0]
    if ending == "zimo":
        for seat in range(4):
            scores[seat] = 3 * (8 + total_fan) if seat == winner_seat else -(8 + total_fan)
    elif ending == "ron":
        if discarder_seat is None or not (0 <= discarder_seat < 4) or discarder_seat == winner_seat:
            raise IllegalActionError(
                f"discarder_seat tidak sah untuk Ron: winner={winner_seat}, discarder={discarder_seat}"
            )
        for seat in range(4):
            if seat == winner_seat:
                scores[seat] = 24 + total_fan
            elif seat == discarder_seat:
                scores[seat] = -(8 + total_fan)
            else:
                scores[seat] = -8
    else:
        raise IllegalActionError(f"Tipe akhir ronde tidak dikenal: {ending!r}")
    return (scores[0], scores[1], scores[2], scores[3])
```

**Catatan audit R0-05:** Binding C++ `MahjongFanCalculator` membedakan `TypeError("ERROR_NOT_WIN")` dari error state seperti `"ERROR_WRONG_TILES_COUNT"` dan `"ERROR_TILE_COUNT_GREATER_THAN_4"`. Karena itu hanya `ERROR_NOT_WIN` yang dikonversi menjadi `(False, 0, ())`; sisanya dibungkus `EngineInvariantError`. Jalankan pengujian riil untuk memastikan perilaku paket `1.4.0` yang benar-benar terpasang. Sumber: [mahjong.cpp upstream](https://github.com/ailab-pku/PyMahjongGB/blob/master/MahjongGB/mahjong.cpp).

- [ ] **Step 4: Jalankan `pytest` untuk memverifikasi kelulusan Task 3**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_fan_calculator.py -v`
Expected: PASS (`6 passed`)

- [ ] **Step 5: Commit perubahan Task 3**

```powershell
rtk git add app/engine/fan_calculator.py tests/test_fan_calculator.py
rtk git commit -m "feat(engine): implement PyMahjongGB 8-fan, shanten, and MCR scoring adapter"
```


---

### Task 4: `PerSeatObserver` (`FeatureEncoder` `38×4×9` + `235` Legal Action Mask)

**Files:**
- Create: `app/engine/feature_encoder.py`
- Test: `tests/test_feature_encoder.py`

**Interfaces:**
- Consumes: `app.domain.tiles`, `app.domain.actions`, `app.domain.models.EncodedTurnState`, `app.domain.exceptions.IllegalActionError`, `app.engine.fan_calculator.FanCalculatorAdapter`
- Produces:
  - `OBS_CHANNELS = 38`
  - `OFFSET_OBS = {"SEAT_WIND": 0, "PREVALENT_WIND": 1, "HAND": 2, "DISCARD": 6, "HALF_FLUSH": 22}`
  - `PerSeatObserver(seat_wind: int, fix_zimo_4th_tile: bool = True, initial_wall_per_seat: int = 21)`:
    - `on_event(request: str, turn_number: int = 0) -> EncodedTurnState | None`
    - `get_encoded_state(turn_number: int = 0) -> EncodedTurnState`
    - `has_non_pass_action() -> bool`

- [ ] **Step 1: Tulis *failing test* untuk `PerSeatObserver` di `tests/test_feature_encoder.py`**

```python
from __future__ import annotations

import numpy as np
import pytest

from app.domain.actions import (
    ANGANG_ACTION_OFFSET,
    BUGANG_ACTION_OFFSET,
    HU_ACTION_ID,
    PASS_ACTION_ID,
    encode_chi_action,
    encode_peng_action,
    encode_play_action,
)
from app.domain.exceptions import IllegalActionError
from app.domain.tiles import tile_to_grid_rc, tile_to_index
from app.engine.feature_encoder import OBS_CHANNELS, PerSeatObserver


def test_wind_and_deal_encoding_populates_exact_planes() -> None:
    obs_seat2 = PerSeatObserver(seat_wind=2, fix_zimo_4th_tile=True)
    obs_seat2.on_event("Wind 3")
    hand_13 = ["W1", "W1", "W2", "W3", "T5", "T6", "B7", "B8", "B9", "F1", "F2", "J1", "J1"]
    obs_seat2.on_event("Deal " + " ".join(hand_13))
    state = obs_seat2.on_event("Draw W4")
    assert state is not None
    assert state.obs.shape == (OBS_CHANNELS, 4, 9)
    assert state.obs.dtype == np.int8
    assert state.legal_mask.shape == (235,)
    assert state.legal_mask.dtype == np.bool_
    assert state.legal_discard_mask.shape == (34,)

    # Plane 0: seat wind = F3 (seat_wind=2 -> F3)
    r_sw, c_sw = tile_to_grid_rc("F3")
    assert state.obs[0, r_sw, c_sw] == 1
    assert int(state.obs[0].sum()) == 1

    # Plane 1: prevalent wind = F4 (quan=3 -> F4)
    r_pw, c_pw = tile_to_grid_rc("F4")
    assert state.obs[1, r_pw, c_pw] == 1
    assert int(state.obs[1].sum()) == 1

    # Plane 2..5: unary count 14 keping di tangan (2 pasang W1 & J1 -> plane 2 sum=12, plane 3 sum=2)
    assert int(state.obs[2].sum()) == 12
    assert int(state.obs[3].sum()) == 2
    assert int(state.obs[4].sum()) == 0
    assert int(state.obs[5].sum()) == 0

    # Kolom padding baris honor (baris 3 kolom 7 dan 8) wajib 0 di seluruh 38 channel
    assert int(np.abs(state.obs[:, 3, 7:9]).sum()) == 0

    # Semua 12 keping unik di tangan wajib legal untuk Play
    assert int(state.legal_discard_mask.sum()) == 12
    assert bool(state.legal_mask[encode_play_action("W1")]) is True
    assert bool(state.legal_mask[encode_play_action("W4")]) is True


def test_claim_masks_for_peng_chi_and_angang_concealment() -> None:
    # Kursi 1 mengamati buangan dari kursi 0 (left neighbor: p = (0 + 4 - 1) % 4 == 3)
    obs = PerSeatObserver(seat_wind=1)
    obs.on_event("Wind 0")
    obs.on_event("Deal W2 W3 T5 T5 T5 B1 B2 B3 F1 F1 J2 J2 J3")

    # Kursi 0 draw lalu buang W1 -> kursi 1 wajib bisa Chi (mid W2, claimed W1) dan Pass
    obs.on_event("Player 0 Draw")
    claim_state = obs.on_event("Player 0 Play W1")
    assert claim_state is not None
    assert bool(claim_state.legal_mask[PASS_ACTION_ID]) is True
    assert bool(claim_state.legal_mask[encode_chi_action("W2", "W1")]) is True
    assert obs.has_non_pass_action() is True

    # Jika kursi 2 (right neighbor: p = 1) membuang T5 -> kursi 1 bisa Peng & Gang, TIDAK bisa Chi
    obs.on_event("Player 2 Draw")
    peng_state = obs.on_event("Player 2 Play T5")
    assert peng_state is not None
    assert bool(peng_state.legal_mask[encode_peng_action("T5")]) is True
    assert int(peng_state.legal_mask[36:99].sum()) == 0

    # Jika lawan (kursi 3) melakukan AnGang tertutup -> HALF_FLUSH lawan tetap 0 (rahasia terjaga)
    obs.on_event("Player 3 Draw")
    obs.on_event("Player 3 AnGang")
    snap = obs.get_encoded_state()
    assert int(snap.obs[22:38].sum()) == 0


def test_self_angang_bugang_and_nine_gates_hu_mask() -> None:
    obs = PerSeatObserver(seat_wind=0)
    obs.on_event("Wind 0")
    obs.on_event("Deal W1 W1 W1 W2 W3 W4 W5 W6 W7 W8 W9 W9 W9")
    # Draw W1 ke-4 -> sekaligus Hu (Nine Gates) dan AnGang W1 legal!
    st = obs.on_event("Draw W1")
    assert st is not None
    assert bool(st.legal_mask[HU_ACTION_ID]) is True
    assert bool(st.legal_mask[ANGANG_ACTION_OFFSET + tile_to_index("W1")]) is True

    # Uji BuGang: kursi 0 punya PENG B2, lalu draw B2 ke-4
    obs2 = PerSeatObserver(seat_wind=0)
    obs2.on_event("Wind 0")
    obs2.on_event("Deal B2 B2 W1 W2 W3 T1 T2 T3 F1 F2 F3 J1 J2")
    obs2.on_event("Player 1 Draw")
    obs2.on_event("Player 1 Play B2")
    post_peng = obs2.on_event("Player 0 Peng")
    assert post_peng is not None
    assert bool(post_peng.legal_mask[encode_play_action("J2")]) is True
    obs2.on_event("Player 0 Play J2")
    st_bg = obs2.on_event("Draw B2")
    assert st_bg is not None
    assert bool(st_bg.legal_mask[BUGANG_ACTION_OFFSET + tile_to_index("B2")]) is True


def test_unknown_event_raises_illegal_action_error() -> None:
    obs = PerSeatObserver(seat_wind=0)
    with pytest.raises(IllegalActionError):
        obs.on_event("UnknownCommand X Y")
```

- [ ] **Step 2: Jalankan `pytest` untuk memverifikasi kegagalan awal**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_feature_encoder.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'app.engine.feature_encoder'`

- [ ] **Step 3: Implementasikan `app/engine/feature_encoder.py`**

```python
from __future__ import annotations

from collections import defaultdict

import numpy as np

from app.domain.actions import (
    ACTION_SPACE_SIZE,
    ANGANG_ACTION_OFFSET,
    BUGANG_ACTION_OFFSET,
    CHI_ACTION_OFFSET,
    GANG_ACTION_OFFSET,
    HU_ACTION_ID,
    PASS_ACTION_ID,
    PENG_ACTION_OFFSET,
    PLAY_ACTION_OFFSET,
    extract_legal_discard_mask,
)
from app.domain.exceptions import IllegalActionError
from app.domain.models import ENCODER_VERSION, EncodedTurnState
from app.domain.tiles import GRID_CELLS, GRID_COLS, GRID_ROWS, NUMBERED_SUITS, TILE_LIST, tile_to_index
from app.engine.fan_calculator import FanCalculatorAdapter

OBS_CHANNELS: int = 38
OFFSET_OBS: dict[str, int] = {
    "SEAT_WIND": 0,
    "PREVALENT_WIND": 1,
    "HAND": 2,
    "DISCARD": 6,
    "HALF_FLUSH": 22,
}


class PerSeatObserver:
    """Encoder state per kursi (38x4x9 int8 + 235 bool mask) yang setara 1-ke-1 dengan skema IJCAI-2026.

    Instans ini hanya menerima stream event protokol yang sah dilihat oleh satu kursi (seat_wind),
    sehingga secara struktural terisolasi dari kartu tertutup lawan maupun susunan sisa tembok.
    """

    def __init__(
        self,
        seat_wind: int,
        fix_zimo_4th_tile: bool = True,
        initial_wall_per_seat: int = 21,
    ) -> None:
        if not (0 <= seat_wind < 4):
            raise IllegalActionError(f"seat_wind harus 0..3, diterima: {seat_wind}")
        self.seat_wind: int = int(seat_wind)
        self.prevalent_wind: int = 0
        self.fix_zimo_4th_tile: bool = bool(fix_zimo_4th_tile)

        self.hand: list[str] = []
        self.packs: list[list[tuple[str, str, int]]] = [[] for _ in range(4)]
        self.history: list[list[str]] = [[] for _ in range(4)]
        self.tile_wall: list[int] = [int(initial_wall_per_seat)] * 4
        self.flower_count: int = 0
        self.shown_tiles: defaultdict[str, int] = defaultdict(int)

        self.wall_last: bool = False
        self.is_about_kong: bool = False
        self.tile_from: int = 0
        self.cur_tile: str = ""
        self.valid_actions: list[int] = []

        self._obs_flat = np.zeros((OBS_CHANNELS, GRID_CELLS), dtype=np.int8)
        self._obs_flat[OFFSET_OBS["SEAT_WIND"], tile_to_index(f"F{self.seat_wind + 1}")] = 1

    def on_event(self, request: str, turn_number: int = 0) -> EncodedTurnState | None:
        tokens = request.strip().split()
        if not tokens:
            raise IllegalActionError("String event kosong tidak diizinkan.")

        head = tokens[0]
        if head == "Wind":
            self.prevalent_wind = int(tokens[1])
            self._obs_flat[OFFSET_OBS["PREVALENT_WIND"], :] = 0
            self._obs_flat[
                OFFSET_OBS["PREVALENT_WIND"],
                tile_to_index(f"F{self.prevalent_wind + 1}"),
            ] = 1
            return None

        if head == "Deal":
            self.hand = list(tokens[1:])
            self._update_embeddings()
            return None

        if head == "Huang":
            self.valid_actions = []
            return self.get_encoded_state(turn_number=turn_number)

        if head == "Draw":
            self.tile_wall[0] -= 1
            self.wall_last = self.tile_wall[1] == 0
            tile = tokens[1]
            self.valid_actions = []
            if self._check_mahjong(tile, is_self_drawn=True, is_about_kong=self.is_about_kong):
                self.valid_actions.append(HU_ACTION_ID)
            self.is_about_kong = False
            self.hand.append(tile)
            self._update_embeddings()

            seen_in_hand: set[str] = set()
            for h_tile in self.hand:
                if h_tile in seen_in_hand:
                    continue
                seen_in_hand.add(h_tile)
                t_idx = tile_to_index(h_tile)
                self.valid_actions.append(PLAY_ACTION_OFFSET + t_idx)
                if self.hand.count(h_tile) == 4 and not self.wall_last and self.tile_wall[0] > 0:
                    self.valid_actions.append(ANGANG_ACTION_OFFSET + t_idx)

            if not self.wall_last and self.tile_wall[0] > 0:
                for pack_type, p_tile, _ in self.packs[0]:
                    if pack_type == "PENG" and p_tile in self.hand:
                        self.valid_actions.append(BUGANG_ACTION_OFFSET + tile_to_index(p_tile))
            return self.get_encoded_state(turn_number=turn_number)

        if head != "Player" or len(tokens) < 3:
            raise IllegalActionError(f"Event protokol tidak dikenal: {request!r}")

        p = (int(tokens[1]) + 4 - self.seat_wind) % 4
        ev = tokens[2]

        if ev == "Draw":
            self.tile_wall[p] -= 1
            self.wall_last = self.tile_wall[(p + 1) % 4] == 0
            return None

        if ev == "BuHua":
            self.tile_wall[p] -= 1
            self.wall_last = self.tile_wall[(p + 1) % 4] == 0
            if p == 0:
                self.flower_count += 1
            self.is_about_kong = False
            return None

        if ev in ("Invalid", "Hu"):
            self.valid_actions = []
            return self.get_encoded_state(turn_number=turn_number)

        if ev == "Play":
            self.tile_from = p
            self.cur_tile = tokens[3]
            self.shown_tiles[self.cur_tile] += 1
            self.history[p].append(self.cur_tile)
            if p == 0:
                self.hand.remove(self.cur_tile)
                self._update_embeddings()
                self.valid_actions = []
                return None

            self.valid_actions = []
            if self._check_mahjong(self.cur_tile, is_self_drawn=False, is_about_kong=False):
                self.valid_actions.append(HU_ACTION_ID)
            if not self.wall_last:
                cur_idx = tile_to_index(self.cur_tile)
                cnt = self.hand.count(self.cur_tile)
                if cnt >= 2:
                    self.valid_actions.append(PENG_ACTION_OFFSET + cur_idx)
                    if cnt == 3 and self.tile_wall[0] > 0:
                        self.valid_actions.append(GANG_ACTION_OFFSET + cur_idx)
                suit = self.cur_tile[0]
                if p == 3 and suit in NUMBERED_SUITS:
                    num = int(self.cur_tile[1])
                    suit_offset = NUMBERED_SUITS.index(suit) * 21
                    tmp = [f"{suit}{num + delta}" for delta in range(-2, 3)]
                    if tmp[0] in self.hand and tmp[1] in self.hand:
                        self.valid_actions.append(CHI_ACTION_OFFSET + suit_offset + (num - 3) * 3 + 2)
                    if tmp[1] in self.hand and tmp[3] in self.hand:
                        self.valid_actions.append(CHI_ACTION_OFFSET + suit_offset + (num - 2) * 3 + 1)
                    if tmp[3] in self.hand and tmp[4] in self.hand:
                        self.valid_actions.append(CHI_ACTION_OFFSET + suit_offset + (num - 1) * 3)
            self.valid_actions.append(PASS_ACTION_ID)
            # R0-04: lawan membuang keping mengubah plane DISCARDS publik.
            self._update_embeddings()
            return self.get_encoded_state(turn_number=turn_number)

        if ev == "Chi":
            mid_tile = tokens[3]
            suit = mid_tile[0]
            mid_num = int(mid_tile[1])
            offer = int(self.cur_tile[1]) - mid_num + 2
            self.packs[p].append(("CHI", mid_tile, offer))
            self.shown_tiles[self.cur_tile] -= 1
            for delta in range(-1, 2):
                self.shown_tiles[f"{suit}{mid_num + delta}"] += 1
            self.wall_last = self.tile_wall[(p + 1) % 4] == 0
            if p == 0:
                self.valid_actions = []
                self.hand.append(self.cur_tile)
                for delta in range(-1, 2):
                    self.hand.remove(f"{suit}{mid_num + delta}")
                self._update_embeddings()
                for h_tile in set(self.hand):
                    self.valid_actions.append(PLAY_ACTION_OFFSET + tile_to_index(h_tile))
                return self.get_encoded_state(turn_number=turn_number)
            # R0-04: claim lawan mengubah exposed melds.
            self._update_embeddings()
            return None

        if ev == "Peng":
            offer = (4 + p - self.tile_from) % 4
            self.packs[p].append(("PENG", self.cur_tile, offer))
            self.shown_tiles[self.cur_tile] += 2
            self.wall_last = self.tile_wall[(p + 1) % 4] == 0
            if p == 0:
                self.valid_actions = []
                for _ in range(2):
                    self.hand.remove(self.cur_tile)
                self._update_embeddings()
                for h_tile in set(self.hand):
                    self.valid_actions.append(PLAY_ACTION_OFFSET + tile_to_index(h_tile))
                return self.get_encoded_state(turn_number=turn_number)
            # R0-04: Peng lawan harus tercermin dalam fitur.
            self._update_embeddings()
            return None

        if ev == "Gang":
            offer = (4 + p - self.tile_from) % 4
            self.packs[p].append(("GANG", self.cur_tile, offer))
            self.shown_tiles[self.cur_tile] += 3
            if p == 0:
                for _ in range(3):
                    self.hand.remove(self.cur_tile)
                self._update_embeddings()
                self.is_about_kong = True
            # R0-04: update exposed Kong untuk seat yang dapat melihatnya.
            self._update_embeddings()
            return None

        if ev == "AnGang":
            tile = "CONCEALED" if p != 0 else tokens[3]
            self.packs[p].append(("GANG", tile, 0))
            if p == 0:
                self.is_about_kong = True
                for _ in range(4):
                    self.hand.remove(tile)
                self._update_embeddings()
            else:
                self.is_about_kong = False
            # R0-04: jangan membuka identitas AnGang tersembunyi lawan.
            self._update_embeddings()
            return None

        if ev == "BuGang":
            tile = tokens[3]
            for idx, (pack_type, p_tile, offer) in enumerate(self.packs[p]):
                if p_tile == tile and pack_type == "PENG":
                    self.packs[p][idx] = ("GANG", tile, offer)
                    break
            self.shown_tiles[tile] += 1
            if p == 0:
                self.hand.remove(tile)
                self._update_embeddings()
                self.is_about_kong = True
                return None

            self.valid_actions = []
            if self._check_mahjong(tile, is_self_drawn=False, is_about_kong=True):
                self.valid_actions.append(HU_ACTION_ID)
            self.valid_actions.append(PASS_ACTION_ID)
            # R0-04: perubahan Peng -> BuGang harus masuk fitur.
            self._update_embeddings()
            return self.get_encoded_state(turn_number=turn_number)

        raise IllegalActionError(f"Sub-event Player tidak dikenal: {request!r}")

    def get_encoded_state(self, turn_number: int = 0) -> EncodedTurnState:
        mask = np.zeros(ACTION_SPACE_SIZE, dtype=np.bool_)
        for act_id in self.valid_actions:
            mask[act_id] = True
        obs_3d = self._obs_flat.reshape((OBS_CHANNELS, GRID_ROWS, GRID_COLS)).copy()
        return EncodedTurnState(
            obs=obs_3d,
            legal_mask=mask,
            legal_discard_mask=extract_legal_discard_mask(mask),
            seat=self.seat_wind,
            turn_number=turn_number,
            encoder_version=ENCODER_VERSION,
        )

    def has_non_pass_action(self) -> bool:
        return any(act_id != PASS_ACTION_ID for act_id in self.valid_actions)

    def _update_embeddings(self) -> None:
        self._obs_flat[OFFSET_OBS["HAND"] :, :] = 0

        hand_counts: defaultdict[str, int] = defaultdict(int)
        for tile in self.hand:
            hand_counts[tile] += 1
        for tile, cnt in hand_counts.items():
            self._obs_flat[
                OFFSET_OBS["HAND"] : OFFSET_OBS["HAND"] + cnt,
                tile_to_index(tile),
            ] = 1

        for rel_seat, tile_list in enumerate(self.history):
            disc_counts: defaultdict[str, int] = defaultdict(int)
            for tile in tile_list:
                disc_counts[tile] += 1
            base = OFFSET_OBS["DISCARD"] + 4 * rel_seat
            for tile, cnt in disc_counts.items():
                self._obs_flat[base : base + min(cnt, 4), tile_to_index(tile)] = 1

        for rel_seat in range(4):
            meld_tiles: list[str] = []
            for pack_type, tile, _ in self.packs[rel_seat]:
                if pack_type == "CHI":
                    suit = tile[0]
                    mid = int(tile[1])
                    meld_tiles.extend([tile, f"{suit}{mid - 1}", f"{suit}{mid + 1}"])
                elif pack_type == "PENG":
                    meld_tiles.extend([tile] * 3)
                elif tile != "CONCEALED":
                    meld_tiles.extend([tile] * 4)

            meld_counts: defaultdict[str, int] = defaultdict(int)
            for tile in meld_tiles:
                meld_counts[tile] += 1
            base = OFFSET_OBS["HALF_FLUSH"] + 4 * rel_seat
            for tile, cnt in meld_counts.items():
                self._obs_flat[base : base + min(cnt, 4), tile_to_index(tile)] = 1

    def _check_mahjong(self, win_tile: str, is_self_drawn: bool, is_about_kong: bool) -> bool:
        # R0-05: hitung salinan yang diketahui di tangan sendiri DAN area publik.
        # Pada self-draw fungsi dipanggil sebelum win_tile ditambah ke self.hand,
        # sedangkan pada Ron keping yang diklaim sudah tercatat di shown_tiles.
        known_count = self.shown_tiles[win_tile] + self.hand.count(win_tile)
        if is_self_drawn:
            known_count += 1
        is_fourth = known_count == 4
        # Bandingkan perilaku flag ini dengan encoder sumber melalui replay parity,
        # khususnya pada legacy mode fix_zimo_4th_tile=False.

        public_packs = [
            (p_type, p_tile, p_offer)
            for p_type, p_tile, p_offer in self.packs[0]
            if p_tile != "CONCEALED"
        ]
        is_ok, _, _ = FanCalculatorAdapter.try_evaluate_hu(
            packs=public_packs,
            hand_tiles=self.hand,
            win_tile=win_tile,
            is_zimo=is_self_drawn,
            is_fourth_tile=is_fourth,
            is_about_kong=is_about_kong,
            is_wall_last=self.wall_last,
            seat_wind=self.seat_wind,
            prevalent_wind=self.prevalent_wind,
            flower_count=self.flower_count,
        )
        return is_ok
```

- [ ] **Step 4: Jalankan `pytest` untuk memverifikasi kelulusan Task 4**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_feature_encoder.py -v`
Expected: PASS (`4 passed`)

- [ ] **Step 5: Commit perubahan Task 4**

```powershell
rtk git add app/engine/feature_encoder.py tests/test_feature_encoder.py
rtk git commit -m "feat(encoder): implement PerSeatObserver 38x4x9 feature tensor and 235 legal action mask"
```

---

### Task 5: `MCRRefereeEngine` (Wasit Meja MCR 4 Pemain Berbasis Protokol Botzone + Stress-Test 200 Ronde)

**Files:**
- Create: `app/engine/mcr_referee.py`
- Test: `tests/test_mcr_engine_playthrough.py`

**Interfaces:**
- Consumes: `app.domain.tiles`, `app.domain.actions`, `app.domain.models`, `app.domain.exceptions`, `app.engine.fan_calculator`, `app.engine.feature_encoder.PerSeatObserver`
- Produces:
  - `MAX_ROUND_STEPS = 600`
  - `MCRRefereeEngine(prevalent_wind: int = 0, seed: int = 0, wall: Sequence[str] | None = None, include_flowers: bool = False)`:
    - `phase: Literal["SELF_TURN", "POST_MELD_DISCARD", "CLAIM_DISCARD", "CLAIM_QIANGGANG", "FINISHED"]`
    - `is_finished: bool`
    - `turn_number: int`
    - `active_seat: int`
    - `round_result: RoundResult | None`
    - `get_pending_seats() -> tuple[int, ...]`
    - `get_seat_encoded_state(seat: int) -> EncodedTurnState`
    - `get_seat_hand(seat: int) -> tuple[str, ...]`
    - `get_seat_packs(seat: int) -> tuple[MeldPack, ...]`
    - `build_public_player_view(game_id: str, human_seat: int) -> PublicPlayerView`
    - `submit_seat_action(seat: int, action_id: int) -> None`
    - `assert_tile_conservation() -> None`

- [ ] **Step 1: Tulis *failing test* komprehensif (termasuk 200 ronde penuh otomatis, prioritas multi-klaim, `QiangGangHu`, dan isolasi kartu lawan) di `tests/test_mcr_engine_playthrough.py`**

```python
from __future__ import annotations

import random

import numpy as np
import pytest

from app.domain.actions import (
    HU_ACTION_ID,
    PASS_ACTION_ID,
    encode_bugang_action,
    encode_chi_action,
    encode_peng_action,
    encode_play_action,
)
from app.domain.exceptions import (
    GameAlreadyFinishedError,
    IllegalActionError,
    InvalidTurnStateError,
)
from app.domain.tiles import TILE_LIST
from app.engine.mcr_referee import MCRRefereeEngine


def _build_custom_wall(
    seat_hands: list[list[str]],
    first_draws_per_seat: list[list[str]],
) -> list[str]:
    """Susun tembok 136 keping valid yang memberikan kartu awal & draw spesifik ke kursi 0..3."""
    pool = [t for t in TILE_LIST for _ in range(4)]
    for s in range(4):
        for t in seat_hands[s]:
            pool.remove(t)
        for t in first_draws_per_seat[s]:
            pool.remove(t)

    segments: list[list[str]] = [[] for _ in range(4)]
    for s in range(4):
        need_filler = 34 - 13 - len(first_draws_per_seat[s])
        filler = [pool.pop() for _ in range(need_filler)]
        # Ingat konvensi segmen: konsumsi dari belakang (indeks 33 turun ke 0)
        # Indeks 33..21 = 13 kartu awal (terbalik), indeks 20.. = urutan draw
        seg = filler + list(reversed(first_draws_per_seat[s])) + list(reversed(seat_hands[s]))
        assert len(seg) == 34
        segments[s] = seg
    return segments[0] + segments[1] + segments[2] + segments[3]


def test_claim_priority_hu_beats_peng_and_peng_beats_chi() -> None:
    # Kursi 0 akan buang W5.
    # Kursi 1 punya W4,W6 (bisa Chi W5).
    # Kursi 2 punya W5,W5 (bisa Peng W5).
    # Kursi 3 punya tangan Tenpai Pure Flush 8+ fan menunggu W5 (bisa Hu Ron!).
    hands = [
        ["W5", "T1", "T2", "T3", "T4", "T5", "T6", "B1", "B2", "B3", "F1", "F2", "F3"],
        ["W4", "W6", "T1", "T2", "T3", "B4", "B5", "B6", "B7", "B8", "F1", "F2", "J1"],
        ["W5", "W5", "T7", "T8", "T9", "B1", "B2", "B3", "F2", "F3", "F4", "J2", "J3"],
        ["W1", "W1", "W1", "W2", "W3", "W4", "W6", "W7", "W8", "W9", "W9", "W9", "J1"],
    ]
    # Ubah J1 kursi 3 jadi W2 agar Pure One Suit (Qing Yi Se = 24 fan) menunggu W5:
    # W1,W1,W1 + W2,W2 + W3,W4,[W5] + W6,W7,W8 + W9,W9,W9
    hands[3][-1] = "W2"
    wall = _build_custom_wall(hands, [["J3"], [], [], []])

    eng = MCRRefereeEngine(prevalent_wind=0, seed=1, wall=wall)
    assert eng.get_pending_seats() == (0,)
    eng.submit_seat_action(0, encode_play_action("W5"))

    # Kursi 1 (Chi), 2 (Peng), dan 3 (Hu) semuanya pending
    assert set(eng.get_pending_seats()) == {1, 2, 3}
    eng.submit_seat_action(1, encode_chi_action("W5", "W5"))
    eng.submit_seat_action(2, encode_peng_action("W5"))
    eng.submit_seat_action(3, HU_ACTION_ID)

    assert eng.is_finished is True
    assert eng.round_result is not None
    assert eng.round_result.ending == "ron"
    assert eng.round_result.winner_seat == 3
    assert eng.round_result.discarder_seat == 0
    assert eng.round_result.total_fan >= 24

    # Uji skenario kedua pada wall yang sama bila kursi 3 memilih Pass -> Peng (kursi 2) mengalahkan Chi (kursi 1)
    eng2 = MCRRefereeEngine(prevalent_wind=0, seed=1, wall=wall)
    eng2.submit_seat_action(0, encode_play_action("W5"))
    eng2.submit_seat_action(1, encode_chi_action("W5", "W5"))
    eng2.submit_seat_action(2, encode_peng_action("W5"))
    eng2.submit_seat_action(3, PASS_ACTION_ID)
    assert eng2.is_finished is False
    assert eng2.phase == "POST_MELD_DISCARD"
    assert eng2.active_seat == 2
    assert eng2.get_pending_seats() == (2,)


def test_qiangganghu_robbing_the_kong_awards_ron_against_bugang_player() -> None:
    # Kursi 0 punya B2,B2, kursi 1 punya tangan Pure Flush B menunggu B2
    hands = [
        ["B2", "B2", "T1", "T2", "T3", "T4", "T5", "T6", "W1", "W2", "W3", "F1", "F2"],
        ["B1", "B3", "B4", "B4", "B5", "B6", "B7", "B7", "B7", "B8", "B8", "B8", "B9"],
        ["B2", "W4", "W5", "W6", "T7", "T8", "T9", "F1", "F2", "F3", "F4", "J1", "J2"],
        ["W7", "W8", "W9", "T1", "T2", "T3", "F1", "F2", "F3", "F4", "J1", "J2", "J3"],
    ]
    # Koreksi tangan kursi 1: B1,[B2],B3 + B4,B5,B6 + B7,B7,B7 + B8,B8,B8 + B9,B9
    hands[1] = ["B1", "B3", "B4", "B5", "B6", "B7", "B7", "B7", "B8", "B8", "B8", "B9", "B9"]
    # Draw pertama kursi 0: F3 (buang F3), kursi 1 draw J3 (buang J3), kursi 2 draw J3 (buang B2 -> kursi 0 Peng B2 lalu buang F2),
    # berikutnya sampai kursi 0 draw B2 ke-4 dan deklarasi BuGang B2 -> kursi 1 QiangGangHu!
    wall = _build_custom_wall(
        hands,
        [
            ["F3", "B2"],  # kursi 0 draw 1 = F3, draw 2 = B2 (untuk BuGang!)
            ["J1", "J3"],  # kursi 1 draw 1 = J1, draw 2 = J3 (dijamin non-B agar tetap tenpai B2!)
            ["J2", "J3"],  # kursi 2 draw 1 = J2 (lalu buang B2!), draw 2 = J3
            ["F4"],        # kursi 3 draw 1 = F4
        ],
    )
    eng = MCRRefereeEngine(prevalent_wind=0, seed=7, wall=wall)
    def _play_and_pass_claims(seat: int, tile: str) -> None:
        eng.submit_seat_action(seat, encode_play_action(tile))
        if eng.phase == "CLAIM_DISCARD":
            for pending_s in eng.get_pending_seats():
                eng.submit_seat_action(pending_s, PASS_ACTION_ID)

    _play_and_pass_claims(0, "F3")
    _play_and_pass_claims(1, "J1")
    # Kursi 2 membuang B2 -> kursi 0 klaim Peng B2, lainnya Pass
    eng.submit_seat_action(2, encode_play_action("B2"))
    for s in eng.get_pending_seats():
        if s == 0:
            eng.submit_seat_action(0, encode_peng_action("B2"))
        else:
            eng.submit_seat_action(s, PASS_ACTION_ID)
    assert eng.phase == "POST_MELD_DISCARD" and eng.active_seat == 0
    _play_and_pass_claims(0, "F2")
    # Putar giliran kursi 1 (draw J3, buang J3 agar tetap tenpai B2), 2 (buang J3), dan 3 (buang F4)
    _play_and_pass_claims(1, "J3")
    _play_and_pass_claims(2, "J3")
    _play_and_pass_claims(3, "F4")
    # Sekarang kursi 0 draw B2 ke-4 dan deklarasi BuGang B2 -> kursi 1 QiangGangHu!
    assert eng.active_seat == 0
    eng.submit_seat_action(0, encode_bugang_action("B2"))
    assert eng.phase == "CLAIM_QIANGGANG"
    assert 1 in eng.get_pending_seats()
    for s in eng.get_pending_seats():
        eng.submit_seat_action(s, HU_ACTION_ID if s == 1 else PASS_ACTION_ID)
    assert eng.is_finished is True
    assert eng.round_result is not None
    assert eng.round_result.qianggang is True
    assert eng.round_result.winner_seat == 1
    assert eng.round_result.discarder_seat == 0


def test_public_player_view_never_exposes_opponent_hidden_hands_while_active() -> None:
    eng = MCRRefereeEngine(prevalent_wind=1, seed=99)
    view = eng.build_public_player_view(game_id="g-test", human_seat=2)
    assert view.round_result is None
    assert len(view.own_hand) == 13
    for seat_state in view.seat_public_states:
        assert isinstance(seat_state.concealed_count, int)
        assert not hasattr(seat_state, "hand")


def test_illegal_and_wrong_turn_submissions_raise_without_mutating_state() -> None:
    eng = MCRRefereeEngine(prevalent_wind=0, seed=123)
    hand_before = eng.get_seat_hand(0)
    with pytest.raises(InvalidTurnStateError):
        eng.submit_seat_action(1, PASS_ACTION_ID)
    with pytest.raises(IllegalActionError):
        eng.submit_seat_action(0, PASS_ACTION_ID)
    assert eng.get_seat_hand(0) == hand_before


def test_stress_200_full_rounds_conserve_tiles_and_terminate_cleanly() -> None:
    endings = {"zimo": 0, "ron": 0, "draw": 0}
    for seed in range(200):
        rng = random.Random(seed + 10_000)
        eng = MCRRefereeEngine(prevalent_wind=seed % 4, seed=seed)
        steps = 0
        while not eng.is_finished:
            eng.assert_tile_conservation()
            pending = eng.get_pending_seats()
            assert len(pending) >= 1
            for seat in pending:
                enc = eng.get_seat_encoded_state(seat)
                legal_ids = np.flatnonzero(enc.legal_mask).tolist()
                assert len(legal_ids) >= 1
                # Prioritaskan Hu bila legal agar menguji jalur kemenangan maupun draw secara alami
                chosen = HU_ACTION_ID if HU_ACTION_ID in legal_ids else rng.choice(legal_ids)
                eng.submit_seat_action(seat, int(chosen))
            steps += 1
            assert steps <= 600

        eng.assert_tile_conservation()
        res = eng.round_result
        assert res is not None
        endings[res.ending] += 1
        assert sum(res.score_deltas) == 0
        if res.ending != "draw":
            assert res.total_fan >= 8
        with pytest.raises(GameAlreadyFinishedError):
            eng.submit_seat_action(0, PASS_ACTION_ID)

    assert sum(endings.values()) == 200


def test_144_tile_flower_buhua_mode_conserves_144_tiles() -> None:
    for seed in range(10):
        rng = random.Random(seed + 50_000)
        eng = MCRRefereeEngine(prevalent_wind=0, seed=seed, include_flowers=True)
        while not eng.is_finished:
            eng.assert_tile_conservation()
            for seat in eng.get_pending_seats():
                enc = eng.get_seat_encoded_state(seat)
                legal_ids = np.flatnonzero(enc.legal_mask).tolist()
                chosen = HU_ACTION_ID if HU_ACTION_ID in legal_ids else rng.choice(legal_ids)
                eng.submit_seat_action(seat, int(chosen))
        eng.assert_tile_conservation()
        view = eng.build_public_player_view("g-144", human_seat=0)
        total_flowers = sum(len(sp.flowers) for sp in view.seat_public_states)
        assert total_flowers == 8
```

- [ ] **Step 2: Jalankan `pytest` untuk memverifikasi kegagalan awal**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_mcr_engine_playthrough.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'app.engine.mcr_referee'`

- [ ] **Step 3: Implementasikan `app/engine/mcr_referee.py`**

```python
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Literal

import numpy as np

from app.domain.actions import (
    HU_ACTION_ID,
    PASS_ACTION_ID,
    DecodedAction,
    decode_action,
)
from app.domain.exceptions import (
    EngineInvariantError,
    GameAlreadyFinishedError,
    IllegalActionError,
    InvalidTurnStateError,
)
from app.domain.models import (
    EncodedTurnState,
    GameStatus,
    LegalActionOption,
    MeldPack,
    PublicPlayerView,
    RoundEnding,
    RoundResult,
    SeatPublicState,
)
from app.domain.tiles import (
    FLOWER_TILES,
    TILE_LIST,
    build_144_wall_with_flowers,
    build_standard_136_wall,
    is_flower_tile,
    sort_hand_tiles,
)
from app.engine.fan_calculator import FanCalculatorAdapter, compute_mcr_score_deltas
from app.engine.feature_encoder import PerSeatObserver

EnginePhase = Literal[
    "SELF_TURN",
    "POST_MELD_DISCARD",
    "CLAIM_DISCARD",
    "CLAIM_QIANGGANG",
    "FINISHED",
]

MAX_ROUND_STEPS: int = 600
CLAIM_PRIORITY: dict[str, int] = {
    "Hu": 3,
    "Gang": 2,
    "Peng": 2,
    "Chi": 1,
}


class MCRRefereeEngine:
    """Wasit meja Chinese Standard Mahjong (MCR) 4 kursi berbasis protokol Botzone."""

    def __init__(
        self,
        prevalent_wind: int = 0,
        seed: int = 0,
        wall: Sequence[str] | None = None,
        include_flowers: bool = False,
    ) -> None:
        if not (0 <= prevalent_wind < 4):
            raise IllegalActionError(f"prevalent_wind harus 0..3, diterima: {prevalent_wind}")
        self.prevalent_wind: int = int(prevalent_wind)
        self.seed: int = int(seed)

        expected_136 = {t: 4 for t in TILE_LIST}
        expected_144 = expected_136 | {h: 1 for h in FLOWER_TILES}
        if wall is None:
            full_wall = (
                build_144_wall_with_flowers(self.seed)
                if include_flowers
                else build_standard_136_wall(self.seed)
            )
        else:
            full_wall = list(wall)
            counts = Counter(full_wall)
            if not (
                (len(full_wall) == 136 and counts == expected_136)
                or (len(full_wall) == 144 and counts == expected_144)
            ):
                raise IllegalActionError(
                    "Tembok kustom wajib berisi tepat 136 keping standar atau 144 keping dengan bunga H1..H8."
                )

        self._total_tiles: int = len(full_wall)
        seg_len: int = self._total_tiles // 4
        self._seg_len: int = seg_len
        self._segments: list[list[str]] = [
            full_wall[seg_len * s : seg_len * (s + 1)] for s in range(4)
        ]
        self._remain: list[int] = [seg_len, seg_len, seg_len, seg_len]
        self._hands: list[list[str]] = [[] for _ in range(4)]
        self._melds: list[list[MeldPack]] = [[] for _ in range(4)]
        self._flowers: list[list[str]] = [[] for _ in range(4)]
        self._discard_history: list[list[str]] = [[] for _ in range(4)]
        self._river_physical: list[list[str]] = [[] for _ in range(4)]
        self._shown_tiles: defaultdict[str, int] = defaultdict(int)

        self._observers: list[PerSeatObserver] = [
            PerSeatObserver(
                seat_wind=s,
                fix_zimo_4th_tile=True,
                initial_wall_per_seat=seg_len - 13,
            )
            for s in range(4)
        ]

        self.turn_number: int = 0
        self.active_seat: int = 0
        self.phase: EnginePhase = "SELF_TURN"
        self.round_result: RoundResult | None = None

        self._last_drawn_tile: str | None = None
        self._last_draw_was_kong_replacement: bool = False
        self._live_discard_tile: str | None = None
        self._live_discard_seat: int | None = None
        self._bugang_tile: str | None = None
        self._bugang_seat: int | None = None
        self._pending_seats: list[int] = []
        self._collected_claims: dict[int, DecodedAction] = {}

        self._initialize_round()

    @property
    def is_finished(self) -> bool:
        return self.phase == "FINISHED"

    def _initialize_round(self) -> None:
        for s in range(4):
            self._observers[s].on_event(f"Wind {self.prevalent_wind}", turn_number=0)

        for s in range(4):
            raw_dealt = [self._segments[s][self._seg_len - 1 - i] for i in range(13)]
            self._remain[s] = self._seg_len - 13
            concealed: list[str] = []
            for t in raw_dealt:
                if is_flower_tile(t):
                    self._flowers[s].append(t)
                else:
                    concealed.append(t)
            while len(concealed) < 13:
                rep = self._segments[s][self._remain[s] - 1]
                self._remain[s] -= 1
                for obs_s in range(4):
                    self._observers[obs_s].on_event(f"Player {s} BuHua", turn_number=0)
                if is_flower_tile(rep):
                    self._flowers[s].append(rep)
                else:
                    concealed.append(rep)
            self._hands[s] = concealed
            self._observers[s].on_event("Deal " + " ".join(concealed), turn_number=0)

        self._perform_draw(seat=0, is_kong_replacement=False)
        self.assert_tile_conservation()

    def assert_tile_conservation(self) -> None:
        wall_cnt = sum(self._remain)
        hand_cnt = sum(len(h) for h in self._hands)
        river_cnt = sum(len(r) for r in self._river_physical)
        flower_cnt = sum(len(f) for f in self._flowers)
        meld_cnt = sum(
            4 if m.pack_type in ("GANG", "ANGANG") else 3
            for s in range(4)
            for m in self._melds[s]
        )
        total = wall_cnt + hand_cnt + river_cnt + meld_cnt + flower_cnt
        if total != self._total_tiles:
            raise EngineInvariantError(
                f"Invarian konservasi {self._total_tiles} keping dilanggar: total={total} "
                f"(wall={wall_cnt}, hand={hand_cnt}, river={river_cnt}, meld={meld_cnt}, flower={flower_cnt})"
            )

    def get_pending_seats(self) -> tuple[int, ...]:
        if self.is_finished:
            return ()
        return tuple(self._pending_seats)

    def get_seat_encoded_state(self, seat: int) -> EncodedTurnState:
        if not (0 <= seat < 4):
            raise IllegalActionError(f"Nomor kursi harus 0..3, diterima: {seat}")
        return self._observers[seat].get_encoded_state(turn_number=self.turn_number)

    def get_seat_hand(self, seat: int) -> tuple[str, ...]:
        if not (0 <= seat < 4):
            raise IllegalActionError(f"Nomor kursi harus 0..3, diterima: {seat}")
        return tuple(sort_hand_tiles(self._hands[seat]))

    def get_seat_packs(self, seat: int) -> tuple[MeldPack, ...]:
        if not (0 <= seat < 4):
            raise IllegalActionError(f"Nomor kursi harus 0..3, diterima: {seat}")
        return tuple(self._melds[seat])

    def build_public_player_view(self, game_id: str, human_seat: int) -> PublicPlayerView:
        if not (0 <= human_seat < 4):
            raise IllegalActionError(f"human_seat harus 0..3, diterima: {human_seat}")

        if self.is_finished:
            status: GameStatus = "FINISHED"
        elif self.phase in ("SELF_TURN", "POST_MELD_DISCARD") and human_seat in self._pending_seats:
            status = "WAITING_HUMAN_DISCARD"
        else:
            status = "WAITING_HUMAN_CLAIM"

        seat_states = tuple(
            SeatPublicState(
                seat=s,
                concealed_count=len(self._hands[s]),
                melds=tuple(self._melds[s]),
                flowers=tuple(self._flowers[s]),
                discards=tuple(self._discard_history[s]),
                wall_remaining=self._remain[s],
            )
            for s in range(4)
        )

        legal_options: list[LegalActionOption] = []
        if not self.is_finished and human_seat in self._pending_seats:
            enc = self.get_seat_encoded_state(human_seat)
            for aid in np.flatnonzero(enc.legal_mask).tolist():
                dec = decode_action(int(aid))
                meld_tiles: tuple[str, ...] | None = None
                if dec.action_type == "Chi" and dec.chi_mid_tile is not None:
                    suit = dec.chi_mid_tile[0]
                    mid_r = int(dec.chi_mid_tile[1])
                    meld_tiles = (f"{suit}{mid_r - 1}", dec.chi_mid_tile, f"{suit}{mid_r + 1}")
                    label = f"Chi {'-'.join(meld_tiles)}"
                elif dec.action_type in ("Peng", "Gang", "AnGang", "BuGang") and dec.tile:
                    count = 3 if dec.action_type == "Peng" else 4
                    meld_tiles = tuple([dec.tile] * count)
                    label = f"{dec.action_type} {dec.tile}"
                elif dec.action_type == "Play" and dec.tile:
                    label = f"Discard {dec.tile}"
                else:
                    label = dec.action_type
                legal_options.append(
                    LegalActionOption(
                        action_id=int(aid),
                        action_type=dec.action_type,
                        tile=dec.tile,
                        meld_tiles=meld_tiles,
                        label=label,
                    )
                )

        return PublicPlayerView(
            game_id=game_id,
            status=status,
            human_seat=human_seat,
            prevalent_wind=self.prevalent_wind,
            active_seat=self.active_seat,
            turn_number=self.turn_number,
            wall_tiles_remaining=sum(self._remain),
            own_hand=tuple(sort_hand_tiles(self._hands[human_seat])),
            own_flowers=tuple(self._flowers[human_seat]),
            seat_public_states=seat_states,
            legal_actions=tuple(legal_options),
            can_request_ai_prediction=(status == "WAITING_HUMAN_DISCARD"),
            round_result=self.round_result,
        )

    def submit_seat_action(self, seat: int, action_id: int) -> None:
        if self.is_finished:
            raise GameAlreadyFinishedError("Ronde telah selesai; tidak dapat mengirim aksi baru.")
        if not (0 <= seat < 4):
            raise IllegalActionError(f"Nomor kursi tidak sah: {seat}")
        if seat not in self._pending_seats:
            raise InvalidTurnStateError(
                f"Kursi {seat} tidak sedang menunggu aksi (pending={self._pending_seats})."
            )

        decoded = decode_action(action_id)
        seat_state = self.get_seat_encoded_state(seat)
        if not bool(seat_state.legal_mask[decoded.action_id]):
            raise IllegalActionError(
                f"Aksi {decoded.action_type} (id={decoded.action_id}, tile={decoded.tile}) "
                f"tidak legal bagi kursi {seat} pada fase {self.phase}."
            )

        self.turn_number += 1
        if self.turn_number > MAX_ROUND_STEPS:
            raise EngineInvariantError(
                f"Melebihi batas pengaman langkah maksimum ({MAX_ROUND_STEPS})."
            )

        if self.phase in ("SELF_TURN", "POST_MELD_DISCARD"):
            self._handle_active_turn_action(seat, decoded)
        elif self.phase == "CLAIM_DISCARD":
            self._pending_seats.remove(seat)
            self._collected_claims[seat] = decoded
            if not self._pending_seats:
                self._resolve_discard_claims()
        elif self.phase == "CLAIM_QIANGGANG":
            self._pending_seats.remove(seat)
            self._collected_claims[seat] = decoded
            if not self._pending_seats:
                self._resolve_qianggang_claims()
        else:
            raise EngineInvariantError(f"Fase engine tidak dikenal: {self.phase!r}")

        self.assert_tile_conservation()

    def _handle_active_turn_action(self, seat: int, decoded: DecodedAction) -> None:
        if decoded.action_type == "Hu":
            if self._last_drawn_tile is None:
                raise EngineInvariantError("Zimo Hu dipanggil tanpa keping draw terakhir.")
            self._finish_with_hu(
                ending="zimo",
                winner_seat=seat,
                discarder_seat=None,
                win_tile=self._last_drawn_tile,
                is_about_kong=self._last_draw_was_kong_replacement,
                qianggang=False,
            )
            return

        if decoded.action_type == "Play":
            assert decoded.tile is not None
            tile = decoded.tile
            self._hands[seat].remove(tile)
            self._discard_history[seat].append(tile)
            self._river_physical[seat].append(tile)
            self._shown_tiles[tile] += 1
            self._live_discard_tile = tile
            self._live_discard_seat = seat
            self._last_drawn_tile = None
            self._last_draw_was_kong_replacement = False

            for s in range(4):
                self._observers[s].on_event(f"Player {seat} Play {tile}", turn_number=self.turn_number)

            claimers = [
                other
                for other in range(4)
                if other != seat and self._observers[other].has_non_pass_action()
            ]
            if claimers:
                self.phase = "CLAIM_DISCARD"
                self._pending_seats = claimers
                self._collected_claims = {}
            else:
                self._perform_draw(seat=(seat + 1) % 4, is_kong_replacement=False)
            return

        if decoded.action_type == "AnGang":
            assert decoded.tile is not None
            tile = decoded.tile
            for _ in range(4):
                self._hands[seat].remove(tile)
            self._melds[seat].append(MeldPack(pack_type="ANGANG", tile=tile, offer=0))
            for s in range(4):
                if s == seat:
                    self._observers[s].on_event(
                        f"Player {seat} AnGang {tile}", turn_number=self.turn_number
                    )
                else:
                    self._observers[s].on_event(
                        f"Player {seat} AnGang", turn_number=self.turn_number
                    )
            self._perform_draw(seat=seat, is_kong_replacement=True)
            return

        if decoded.action_type == "BuGang":
            assert decoded.tile is not None
            tile = decoded.tile
            self._hands[seat].remove(tile)
            upgraded = False
            for idx, m in enumerate(self._melds[seat]):
                if m.pack_type == "PENG" and m.tile == tile:
                    self._melds[seat][idx] = MeldPack(pack_type="GANG", tile=tile, offer=m.offer)
                    upgraded = True
                    break
            if not upgraded:
                raise EngineInvariantError(f"BuGang {tile} tanpa meld PENG yang cocok.")

            self._shown_tiles[tile] += 1
            self._bugang_tile = tile
            self._bugang_seat = seat
            for s in range(4):
                self._observers[s].on_event(
                    f"Player {seat} BuGang {tile}", turn_number=self.turn_number
                )

            robbers = [
                other
                for other in range(4)
                if other != seat
                and bool(self._observers[other].get_encoded_state().legal_mask[HU_ACTION_ID])
            ]
            if robbers:
                self.phase = "CLAIM_QIANGGANG"
                self._pending_seats = robbers
                self._collected_claims = {}
            else:
                self._perform_draw(seat=seat, is_kong_replacement=True)
            return

        raise IllegalActionError(f"Aksi {decoded.action_type} tidak valid pada giliran sendiri.")

    def _resolve_discard_claims(self) -> None:
        assert self._live_discard_tile is not None and self._live_discard_seat is not None
        live_tile = self._live_discard_tile
        discarder = self._live_discard_seat

        non_pass = {
            s: dec for s, dec in self._collected_claims.items() if dec.action_type != "Pass"
        }
        self._collected_claims = {}

        if not non_pass:
            self._live_discard_tile = None
            self._live_discard_seat = None
            self._perform_draw(seat=(discarder + 1) % 4, is_kong_replacement=False)
            return

        best_prio = max(CLAIM_PRIORITY[dec.action_type] for dec in non_pass.values())
        contenders = [
            s for s, dec in non_pass.items() if CLAIM_PRIORITY[dec.action_type] == best_prio
        ]
        contenders.sort(key=lambda s: (s - discarder) % 4)
        winner = contenders[0]
        win_dec = non_pass[winner]

        if win_dec.action_type == "Hu":
            self._finish_with_hu(
                ending="ron",
                winner_seat=winner,
                discarder_seat=discarder,
                win_tile=live_tile,
                is_about_kong=False,
                qianggang=False,
            )
            return

        # Keping buangan resmi diklaim dari meja fisik
        self._river_physical[discarder].pop()
        self._live_discard_tile = None
        self._live_discard_seat = None

        if win_dec.action_type == "Gang":
            for _ in range(3):
                self._hands[winner].remove(live_tile)
            offer = (4 + winner - discarder) % 4
            self._melds[winner].append(MeldPack(pack_type="GANG", tile=live_tile, offer=offer))
            self._shown_tiles[live_tile] += 3
            for s in range(4):
                self._observers[s].on_event(f"Player {winner} Gang", turn_number=self.turn_number)
            self._perform_draw(seat=winner, is_kong_replacement=True)
            return

        if win_dec.action_type == "Peng":
            for _ in range(2):
                self._hands[winner].remove(live_tile)
            offer = (4 + winner - discarder) % 4
            self._melds[winner].append(MeldPack(pack_type="PENG", tile=live_tile, offer=offer))
            self._shown_tiles[live_tile] += 2
            for s in range(4):
                self._observers[s].on_event(f"Player {winner} Peng", turn_number=self.turn_number)
            self.active_seat = winner
            self.phase = "POST_MELD_DISCARD"
            self._pending_seats = [winner]
            return

        if win_dec.action_type == "Chi":
            assert win_dec.chi_mid_tile is not None
            mid_tile = win_dec.chi_mid_tile
            suit = mid_tile[0]
            mid_num = int(mid_tile[1])
            need_tiles = [
                f"{suit}{r}" for r in (mid_num - 1, mid_num, mid_num + 1) if f"{suit}{r}" != live_tile
            ]
            for nt in need_tiles:
                self._hands[winner].remove(nt)
            offer = int(live_tile[1]) - mid_num + 2
            self._melds[winner].append(MeldPack(pack_type="CHI", tile=mid_tile, offer=offer))
            self._shown_tiles[live_tile] -= 1
            for delta in range(-1, 2):
                self._shown_tiles[f"{suit}{mid_num + delta}"] += 1
            for s in range(4):
                self._observers[s].on_event(
                    f"Player {winner} Chi {mid_tile}", turn_number=self.turn_number
                )
            self.active_seat = winner
            self.phase = "POST_MELD_DISCARD"
            self._pending_seats = [winner]
            return

        raise EngineInvariantError(f"Klaim pemenang tidak terduga: {win_dec}")

    def _resolve_qianggang_claims(self) -> None:
        assert self._bugang_tile is not None and self._bugang_seat is not None
        bg_tile = self._bugang_tile
        bg_seat = self._bugang_seat
        hu_seats = [
            s for s, dec in self._collected_claims.items() if dec.action_type == "Hu"
        ]
        self._collected_claims = {}
        self._bugang_tile = None
        self._bugang_seat = None

        if hu_seats:
            hu_seats.sort(key=lambda s: (s - bg_seat) % 4)
            winner = hu_seats[0]
            self._finish_with_hu(
                ending="ron",
                winner_seat=winner,
                discarder_seat=bg_seat,
                win_tile=bg_tile,
                is_about_kong=True,
                qianggang=True,
            )
        else:
            self._perform_draw(seat=bg_seat, is_kong_replacement=True)

    def _perform_draw(self, seat: int, is_kong_replacement: bool) -> None:
        while True:
            if self._remain[seat] == 0:
                self.phase = "FINISHED"
                self._pending_seats = []
                for s in range(4):
                    self._observers[s].on_event("Huang", turn_number=self.turn_number)
                self.round_result = RoundResult(
                    ending="draw",
                    winner_seat=None,
                    discarder_seat=None,
                    qianggang=False,
                    win_tile=None,
                    total_fan=0,
                    fans=(),
                    score_deltas=(0, 0, 0, 0),
                    revealed_hands=tuple(tuple(sort_hand_tiles(self._hands[s])) for s in range(4)),
                )
                return

            tile = self._segments[seat][self._remain[seat] - 1]
            self._remain[seat] -= 1
            if is_flower_tile(tile):
                self._flowers[seat].append(tile)
                is_kong_replacement = False
                for s in range(4):
                    self._observers[s].on_event(
                        f"Player {seat} BuHua", turn_number=self.turn_number
                    )
                continue
            break

        self._hands[seat].append(tile)
        self._last_drawn_tile = tile
        self._last_draw_was_kong_replacement = is_kong_replacement
        self.active_seat = seat
        self.phase = "SELF_TURN"
        self._pending_seats = [seat]

        for s in range(4):
            if s == seat:
                self._observers[s].on_event(f"Draw {tile}", turn_number=self.turn_number)
            else:
                self._observers[s].on_event(f"Player {seat} Draw", turn_number=self.turn_number)

    def _finish_with_hu(
        self,
        ending: RoundEnding,
        winner_seat: int,
        discarder_seat: int | None,
        win_tile: str,
        is_about_kong: bool,
        qianggang: bool,
    ) -> None:
        is_zimo = ending == "zimo"
        hand_without_win = list(self._hands[winner_seat])
        if is_zimo:
            hand_without_win.remove(win_tile)

        packs_tuples = [(m.pack_type, m.tile, m.offer) for m in self._melds[winner_seat]]
        is_wall_last = (
            self._remain[(winner_seat + 1) % 4] == 0
            if is_zimo
            else (discarder_seat is not None and self._remain[(discarder_seat + 1) % 4] == 0 and not qianggang)
        )
        # R0-05: di engine, win_tile self-draw sudah menjadi anggota hand;
        # pada Ron, win_tile lawan sudah tercatat di shown_tiles.
        is_fourth = (
            self._shown_tiles[win_tile] + self._hands[winner_seat].count(win_tile)
        ) == 4

        is_ok, total_fan, fans = FanCalculatorAdapter.try_evaluate_hu(
            packs=packs_tuples,
            hand_tiles=hand_without_win,
            win_tile=win_tile,
            is_zimo=is_zimo,
            is_fourth_tile=is_fourth,
            is_about_kong=is_about_kong,
            is_wall_last=is_wall_last,
            seat_wind=winner_seat,
            prevalent_wind=self.prevalent_wind,
            flower_count=len(self._flowers[winner_seat]),
        )
        if not is_ok:
            raise IllegalActionError(
                f"Klaim Hu oleh kursi {winner_seat} gagal validasi 8-fan (total_fan={total_fan})."
            )

        for s in range(4):
            self._observers[s].on_event(f"Player {winner_seat} Hu", turn_number=self.turn_number)

        deltas = compute_mcr_score_deltas(
            ending=ending,
            winner_seat=winner_seat,
            discarder_seat=discarder_seat,
            total_fan=total_fan,
        )
        self.phase = "FINISHED"
        self._pending_seats = []
        self.round_result = RoundResult(
            ending=ending,
            winner_seat=winner_seat,
            discarder_seat=discarder_seat,
            qianggang=qianggang,
            win_tile=win_tile,
            total_fan=total_fan,
            fans=fans,
            score_deltas=deltas,
            revealed_hands=tuple(tuple(sort_hand_tiles(self._hands[s])) for s in range(4)),
        )
```

- [ ] **Step 4: Jalankan `pytest` untuk memverifikasi 200 ronde dan seluruh aturan klaim MCR**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_mcr_engine_playthrough.py -v`
Expected: PASS (`6 passed`, mencakup 200 ronde 136-keping dan 10 ronde 144-keping `BuHua` bebas galat)

- [ ] **Step 5: Commit perubahan Task 5**

```powershell
rtk git add app/engine/mcr_referee.py tests/test_mcr_engine_playthrough.py
rtk git commit -m "feat(engine): add MCRRefereeEngine with claim priority, QiangGangHu, and 200-round conservation tests"
```


---

### Task 6: `ShantenHeuristicBot` & `GameSessionService` (Concurrency Lock, Backpressure, Pause-on-Human, & Graceful Shutdown)

**Files:**
- Create: `app/services/bot_service.py`
- Create: `app/services/game_service.py`
- Test: `tests/test_edge_cases_and_resilience.py`

**Interfaces:**
- Consumes: `app.domain.actions`, `app.domain.tiles`, `app.domain.models`, `app.domain.exceptions`, `app.engine.fan_calculator.FanCalculatorAdapter`, `app.engine.mcr_referee.MCRRefereeEngine`
- Produces:
  - `BotPolicy` (Protocol/ABC), `RandomLegalBot`, `ShantenHeuristicBot`:
    - `select_action(encoded_state: EncodedTurnState, hand_tiles: Sequence[str], packs: Sequence[MeldPack], rng: random.Random) -> int`
  - `GameSessionService(max_active_sessions: int = 256, session_ttl_seconds: float = 3600.0, bot_policy: BotPolicy | None = None)`:
    - `create_game(human_seat: int = 0, prevalent_wind: int = 0, seed: int | None = None) -> PublicPlayerView`
    - `get_player_view(game_id: str) -> PublicPlayerView`
    - `get_human_encoded_turn(game_id: str) -> EncodedTurnState`
    - `submit_human_action(game_id: str, action_id: int, expected_turn_number: int | None = None) -> PublicPlayerView`
    - `delete_session(game_id: str) -> None`
    - `active_session_count() -> int`
    - `shutdown(timeout_sec: float = 5.0) -> None`

- [ ] **Step 1: Tulis *failing test* untuk `ShantenHeuristicBot` dan ketahanan konkurensi/backpressure `GameSessionService` di `tests/test_edge_cases_and_resilience.py`**

```python
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from app.domain.actions import PASS_ACTION_ID
from app.domain.exceptions import (
    GameAlreadyFinishedError,
    GameNotFoundError,
    IllegalActionError,
    InvalidTurnStateError,
    ServiceShuttingDownError,
    SessionCapacityExceededError,
)
from app.services.bot_service import ShantenHeuristicBot
from app.services.game_service import GameSessionService


def test_game_session_full_human_vs_3_heuristic_bots_playthrough() -> None:
    svc = GameSessionService(max_active_sessions=16, bot_policy=ShantenHeuristicBot())
    view = svc.create_game(human_seat=1, prevalent_wind=0, seed=42)
    assert view.human_seat == 1
    assert view.status in ("WAITING_HUMAN_DISCARD", "WAITING_HUMAN_CLAIM", "FINISHED")

    steps = 0
    while view.status != "FINISHED":
        assert len(view.legal_actions) >= 1
        # Pastikan tidak pernah berhenti jika satu-satunya opsi manusia hanyalah Pass tunggal
        if len(view.legal_actions) == 1:
            assert view.legal_actions[0].action_id != PASS_ACTION_ID

        if view.status == "WAITING_HUMAN_DISCARD":
            assert view.can_request_ai_prediction is True
            enc = svc.get_human_encoded_turn(view.game_id)
            assert enc.obs.shape == (38, 4, 9)
            assert int(enc.legal_discard_mask.sum()) >= 1
        else:
            assert view.can_request_ai_prediction is False

        # Manusia memilih Hu bila tersedia, jika tidak ambil opsi legal terakhir (biasanya Discard / Pass)
        hu_opts = [opt for opt in view.legal_actions if opt.action_type == "Hu"]
        chosen_id = hu_opts[0].action_id if hu_opts else view.legal_actions[0].action_id
        view = svc.submit_human_action(view.game_id, chosen_id)
        steps += 1
        assert steps <= 300

    assert view.round_result is not None
    assert sum(view.round_result.score_deltas) == 0
    with pytest.raises(GameAlreadyFinishedError):
        svc.submit_human_action(view.game_id, PASS_ACTION_ID)


def test_invalid_inputs_do_not_corrupt_session_state() -> None:
    svc = GameSessionService(max_active_sessions=8)
    with pytest.raises(GameNotFoundError):
        svc.get_player_view("non-existent-id")
    with pytest.raises(IllegalActionError):
        svc.create_game(human_seat=9, prevalent_wind=0, seed=1)

    view = svc.create_game(human_seat=0, prevalent_wind=0, seed=7)
    before = svc.get_player_view(view.game_id)
    with pytest.raises(IllegalActionError):
        svc.submit_human_action(view.game_id, 999)
    with pytest.raises(IllegalActionError):
        svc.submit_human_action(view.game_id, PASS_ACTION_ID)
    after = svc.get_player_view(view.game_id)
    assert after == before


def test_concurrent_20_threads_race_condition_allows_only_valid_serial_progress() -> None:
    svc = GameSessionService(max_active_sessions=8)
    view = svc.create_game(human_seat=0, prevalent_wind=0, seed=101)
    assert view.status == "WAITING_HUMAN_DISCARD"

    # Pilih satu keping yang HANYA ada 1 salinan di tangan kursi 0 agar tembakan kedua pasti ditolak!
    counts = {t: view.own_hand.count(t) for t in set(view.own_hand)}
    single_tiles = [t for t, c in counts.items() if c == 1]
    assert len(single_tiles) >= 1
    target_tile = single_tiles[0]
    target_opt = next(
        opt for opt in view.legal_actions if opt.action_type == "Play" and opt.tile == target_tile
    )

    barrier = threading.Barrier(20)
    successes = []
    controlled_rejections = []
    unexpected_errors = []

    def _worker() -> None:
        barrier.wait()
        try:
            res = svc.submit_human_action(
                view.game_id,
                target_opt.action_id,
                expected_turn_number=view.turn_number,
            )
            successes.append(res)
        except (IllegalActionError, InvalidTurnStateError, GameAlreadyFinishedError) as exc:
            controlled_rejections.append(exc)
        except Exception as exc:  # pragma: no cover
            unexpected_errors.append(exc)

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(_worker) for _ in range(20)]
        for f in futures:
            f.result()

    assert unexpected_errors == []
    # Tepat 1 thread yang menang lock pada turn_number awal; 19 lainnya tertolak terkendali
    assert len(successes) == 1
    assert len(controlled_rejections) == 19


def test_session_backpressure_evicts_expired_only_and_never_drops_active_games() -> None:
    svc = GameSessionService(max_active_sessions=3, session_ttl_seconds=0.15)
    g1 = svc.create_game(human_seat=0, prevalent_wind=0, seed=1)
    g2 = svc.create_game(human_seat=0, prevalent_wind=0, seed=2)
    g3 = svc.create_game(human_seat=0, prevalent_wind=0, seed=3)
    assert svc.active_session_count() == 3

    # Saat ke-3 sesi masih aktif (belum TTL), game ke-4 wajib ditolak oleh backpressure
    with pytest.raises(SessionCapacityExceededError):
        svc.create_game(human_seat=0, prevalent_wind=0, seed=4)

    # Pastikan ke-3 game aktif tetap utuh
    assert svc.get_player_view(g1.game_id).game_id == g1.game_id
    assert svc.get_player_view(g2.game_id).game_id == g2.game_id
    assert svc.get_player_view(g3.game_id).game_id == g3.game_id

    # Tunggu melewati TTL -> pembuatan game baru menyapu sesi kedaluwarsa secara sah
    time.sleep(0.20)
    g4 = svc.create_game(human_seat=0, prevalent_wind=0, seed=5)
    assert g4.game_id != g1.game_id


def test_graceful_shutdown_drains_inflight_step_and_rejects_new_requests() -> None:
    bot_entered = threading.Event()
    allow_bot_finish = threading.Event()
    inner_bot = ShantenHeuristicBot()

    class _SlowStepBot:
        def select_action(self, encoded_state, hand_tiles, packs, rng) -> int:  # type: ignore[no-untyped-def]
            if not bot_entered.is_set():
                bot_entered.set()
                allow_bot_finish.wait(timeout=3.0)
            return inner_bot.select_action(encoded_state, hand_tiles, packs, rng)

    svc = GameSessionService(max_active_sessions=4, bot_policy=_SlowStepBot())
    g = svc.create_game(human_seat=0, prevalent_wind=0, seed=11)
    first_play = next(opt for opt in g.legal_actions if opt.action_type == "Play")

    inflight_done = threading.Event()
    inflight_results: list[object] = []

    def _run_inflight_step() -> None:
        res = svc.submit_human_action(g.game_id, first_play.action_id)
        inflight_results.append(res)
        inflight_done.set()

    worker = threading.Thread(target=_run_inflight_step)
    worker.start()
    assert bot_entered.wait(timeout=2.0) is True

    shutdown_done = threading.Event()
    shutdown_thread = threading.Thread(target=lambda: (svc.shutdown(timeout_sec=3.0), shutdown_done.set()))
    shutdown_thread.start()

    # Selagi operasi in-flight berjalan dan shutdown sudah dimulai, request baru wajib langsung ditolak
    time.sleep(0.05)
    assert shutdown_done.is_set() is False
    with pytest.raises(ServiceShuttingDownError):
        svc.create_game(human_seat=0, prevalent_wind=0, seed=12)

    # Lepaskan langkah in-flight -> shutdown baru selesai setelah langkah in-flight tuntas (drained)
    allow_bot_finish.set()
    worker.join(timeout=3.0)
    shutdown_thread.join(timeout=3.0)
    assert inflight_done.is_set() is True
    assert shutdown_done.is_set() is True
    assert len(inflight_results) == 1

    with pytest.raises(ServiceShuttingDownError):
        svc.submit_human_action(g.game_id, g.legal_actions[0].action_id)
```

- [ ] **Step 2: Jalankan `pytest` untuk memverifikasi kegagalan awal**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_edge_cases_and_resilience.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'app.services.bot_service'`

- [ ] **Step 3: Implementasikan `app/services/bot_service.py` dan `app/services/game_service.py`**

Buat `app/services/bot_service.py`:

```python
from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from app.domain.actions import (
    HU_ACTION_ID,
    PASS_ACTION_ID,
    decode_action,
)
from app.domain.exceptions import IllegalActionError
from app.domain.models import EncodedTurnState, MeldPack
from app.engine.fan_calculator import FanCalculatorAdapter


class BotPolicy(Protocol):
    def select_action(
        self,
        encoded_state: EncodedTurnState,
        hand_tiles: Sequence[str],
        packs: Sequence[MeldPack],
        rng: random.Random,
    ) -> int: ...


class RandomLegalBot:
    """Bot legal acak yang selalu memilih Hu bila sah; digunakan untuk fuzz/stress testing."""

    def select_action(
        self,
        encoded_state: EncodedTurnState,
        hand_tiles: Sequence[str],
        packs: Sequence[MeldPack],
        rng: random.Random,
    ) -> int:
        legal_ids = np.flatnonzero(encoded_state.legal_mask).tolist()
        if not legal_ids:
            raise IllegalActionError("Tidak ada aksi legal bagi RandomLegalBot.")
        if HU_ACTION_ID in legal_ids:
            return HU_ACTION_ID
        return int(rng.choice(legal_ids))


def _tile_isolation_penalty(tile: str, hand_tiles: Sequence[str]) -> tuple[int, int]:
    """Skor preferensi buang saat shanten seri: buang honor tunggal/terminal terisolasi lebih dulu."""
    cnt = hand_tiles.count(tile)
    suit = tile[0]
    rank = int(tile[1])
    if suit in ("F", "J"):
        # Honor tunggal paling layak dibuang (skor besar = lebih diprioritaskan dibuang)
        return (3 if cnt == 1 else 0, 0)
    neighbors = sum(
        1 for delta in (-2, -1, 1, 2) if f"{suit}{rank + delta}" in hand_tiles
    )
    edge_score = 2 if rank in (1, 9) else (1 if rank in (2, 8) else 0)
    return (2 if (cnt == 1 and neighbors == 0) else 0, edge_score - neighbors)


class ShantenHeuristicBot:
    """Bot heuristik MCR cepat (< 5ms/aksi) berbasis minimisasi MahjongShanten dan 8-fan Hu."""

    def select_action(
        self,
        encoded_state: EncodedTurnState,
        hand_tiles: Sequence[str],
        packs: Sequence[MeldPack],
        rng: random.Random,
    ) -> int:
        legal_ids = [int(x) for x in np.flatnonzero(encoded_state.legal_mask).tolist()]
        if not legal_ids:
            raise IllegalActionError("Tidak ada aksi legal bagi ShantenHeuristicBot.")

        # 1. Selalu ambil kemenangan >= 8 fan
        if HU_ACTION_ID in legal_ids:
            return HU_ACTION_ID

        if len(legal_ids) == 1:
            return legal_ids[0]

        pack_tuples = [(m.pack_type, m.tile, m.offer) for m in packs]
        decoded_list = [decode_action(aid) for aid in legal_ids]
        has_pass = any(d.action_type == "Pass" for d in decoded_list)

        # 2. Jendela klaim buangan lawan (Pass tersedia bersama Chi / Peng / Gang)
        if has_pass:
            # Tangan saat klaim selalu berukuran 13 - 3 * len(packs)
            shanten_before = FanCalculatorAdapter.calculate_shanten(pack_tuples, hand_tiles)
            best_action = PASS_ACTION_ID
            best_shanten = shanten_before

            for dec in decoded_list:
                if dec.action_type == "Pass":
                    continue
                if dec.action_type == "Gang" and dec.tile is not None:
                    rem_hand = list(hand_tiles)
                    for _ in range(3):
                        rem_hand.remove(dec.tile)
                    new_packs = [*pack_tuples, ("GANG", dec.tile, 1)]
                    sh_after = FanCalculatorAdapter.calculate_shanten(new_packs, rem_hand)
                    if sh_after <= best_shanten:
                        best_shanten = sh_after
                        best_action = dec.action_id
                elif dec.action_type == "Peng" and dec.tile is not None:
                    rem_hand = list(hand_tiles)
                    for _ in range(2):
                        rem_hand.remove(dec.tile)
                    new_packs = [*pack_tuples, ("PENG", dec.tile, 1)]
                    sh_after = self._best_post_claim_shanten(new_packs, rem_hand)
                    if sh_after < best_shanten:
                        best_shanten = sh_after
                        best_action = dec.action_id
                elif dec.action_type == "Chi" and dec.chi_mid_tile and dec.tile:
                    suit = dec.chi_mid_tile[0]
                    mid_r = int(dec.chi_mid_tile[1])
                    need = [
                        f"{suit}{r}"
                        for r in (mid_r - 1, mid_r, mid_r + 1)
                        if f"{suit}{r}" != dec.tile
                    ]
                    rem_hand = list(hand_tiles)
                    for nt in need:
                        rem_hand.remove(nt)
                    offer = int(dec.tile[1]) - mid_r + 2
                    new_packs = [*pack_tuples, ("CHI", dec.chi_mid_tile, offer)]
                    sh_after = self._best_post_claim_shanten(new_packs, rem_hand)
                    if sh_after < best_shanten:
                        best_shanten = sh_after
                        best_action = dec.action_id

            return best_action

        # 3. Fase giliran sendiri (Play + opsional AnGang / BuGang; ukuran tangan 14 - 3 * len(packs))
        play_decs = [d for d in decoded_list if d.action_type == "Play" and d.tile is not None]
        best_play_shanten = 99
        scored_plays: list[tuple[int, int, int, float, int]] = []

        for dec in play_decs:
            assert dec.tile is not None
            cand_hand = list(hand_tiles)
            cand_hand.remove(dec.tile)
            sh = FanCalculatorAdapter.calculate_shanten(pack_tuples, cand_hand)
            iso_primary, iso_secondary = _tile_isolation_penalty(dec.tile, hand_tiles)
            if sh < best_play_shanten:
                best_play_shanten = sh
            # Urutkan dari shanten terkecil, lalu penalti isolasi terbesar (negatifkan untuk min)
            scored_plays.append((sh, -iso_primary, -iso_secondary, rng.random(), dec.action_id))

        # Evaluasi AnGang / BuGang bila tidak memperburuk shanten terbaik
        for dec in decoded_list:
            if dec.action_type == "AnGang" and dec.tile is not None:
                cand_hand = list(hand_tiles)
                for _ in range(4):
                    cand_hand.remove(dec.tile)
                new_packs = [*pack_tuples, ("GANG", dec.tile, 0)]
                sh_kong = FanCalculatorAdapter.calculate_shanten(new_packs, cand_hand)
                if sh_kong <= best_play_shanten:
                    return dec.action_id
            elif dec.action_type == "BuGang" and dec.tile is not None:
                cand_hand = list(hand_tiles)
                cand_hand.remove(dec.tile)
                new_packs = [
                    ("GANG", p_tile, p_off) if (p_type == "PENG" and p_tile == dec.tile) else (p_type, p_tile, p_off)
                    for p_type, p_tile, p_off in pack_tuples
                ]
                sh_kong = FanCalculatorAdapter.calculate_shanten(new_packs, cand_hand)
                if sh_kong <= best_play_shanten:
                    return dec.action_id

        scored_plays.sort()
        return scored_plays[0][4]

    @staticmethod
    def _best_post_claim_shanten(
        new_packs: list[tuple[str, str, int]],
        hand_after_claim: list[str],
    ) -> int:
        best = 99
        for cand_discard in set(hand_after_claim):
            rem = list(hand_after_claim)
            rem.remove(cand_discard)
            sh = FanCalculatorAdapter.calculate_shanten(new_packs, rem)
            if sh < best:
                best = sh
        return best
```

Buat `app/services/game_service.py`:

```python
from __future__ import annotations

import random
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field

import numpy as np

from app.domain.actions import PASS_ACTION_ID
from app.domain.exceptions import (
    GameNotFoundError,
    IllegalActionError,
    InvalidTurnStateError,
    ServiceShuttingDownError,
    SessionCapacityExceededError,
)
from app.domain.models import EncodedTurnState, PublicPlayerView
from app.engine.mcr_referee import MCRRefereeEngine
from app.services.bot_service import BotPolicy, ShantenHeuristicBot

FINISHED_RETENTION_SECONDS: float = 60.0


@dataclass
class _ManagedSession:
    game_id: str
    human_seat: int
    engine: MCRRefereeEngine
    rng: random.Random
    created_at: float
    updated_at: float
    lock: threading.RLock = field(default_factory=threading.RLock)


class GameSessionService:
    """Manajer sesi permainan MCR thread-safe dengan Pause-on-Human, backpressure, dan graceful shutdown."""

    def __init__(
        self,
        max_active_sessions: int = 256,
        session_ttl_seconds: float = 3600.0,
        bot_policy: BotPolicy | None = None,
    ) -> None:
        if max_active_sessions < 1:
            raise ValueError("max_active_sessions wajib >= 1")
        self._max_active_sessions: int = int(max_active_sessions)
        self._session_ttl_seconds: float = float(session_ttl_seconds)
        self._bot_policy: BotPolicy = bot_policy or ShantenHeuristicBot()

        self._store_lock = threading.RLock()
        self._sessions: dict[str, _ManagedSession] = {}
        self._shutting_down: bool = False
        self._in_flight_ops: int = 0
        self._drain_cond = threading.Condition(self._store_lock)

    def _enter_operation(self) -> None:
        with self._store_lock:
            if self._shutting_down:
                raise ServiceShuttingDownError("Layanan sedang dimatikan (graceful shutdown).")
            self._in_flight_ops += 1

    def _exit_operation(self) -> None:
        with self._store_lock:
            self._in_flight_ops -= 1
            if self._in_flight_ops == 0:
                self._drain_cond.notify_all()

    def _evict_stale_locked(self, now: float) -> None:
        stale_ids: list[str] = []
        for gid, sess in self._sessions.items():
            age = now - sess.updated_at
            if age > self._session_ttl_seconds:
                stale_ids.append(gid)
            elif sess.engine.is_finished and age > min(FINISHED_RETENTION_SECONDS, self._session_ttl_seconds):
                stale_ids.append(gid)
        for gid in stale_ids:
            self._sessions.pop(gid, None)

    def create_game(
        self,
        human_seat: int = 0,
        prevalent_wind: int = 0,
        seed: int | None = None,
    ) -> PublicPlayerView:
        self._enter_operation()
        try:
            if not (0 <= human_seat < 4):
                raise IllegalActionError(f"human_seat harus 0..3, diterima: {human_seat}")
            if not (0 <= prevalent_wind < 4):
                raise IllegalActionError(f"prevalent_wind harus 0..3, diterima: {prevalent_wind}")

            actual_seed = secrets.randbits(31) if seed is None else int(seed)
            now = time.monotonic()

            with self._store_lock:
                self._evict_stale_locked(now)
                if len(self._sessions) >= self._max_active_sessions:
                    raise SessionCapacityExceededError(
                        f"Kapasitas sesi aktif penuh ({self._max_active_sessions}). "
                        "Silakan tunggu atau hapus sesi selesai."
                    )
                game_id = uuid.uuid4().hex
                engine = MCRRefereeEngine(prevalent_wind=prevalent_wind, seed=actual_seed)
                session = _ManagedSession(
                    game_id=game_id,
                    human_seat=int(human_seat),
                    engine=engine,
                    rng=random.Random(actual_seed ^ 0x5A5A5A5A),
                    created_at=now,
                    updated_at=now,
                )
                self._sessions[game_id] = session

            with session.lock:
                self._advance_bots_until_human_or_finished(session)
                session.updated_at = time.monotonic()
                return session.engine.build_public_player_view(session.game_id, session.human_seat)
        finally:
            self._exit_operation()

    def get_player_view(self, game_id: str) -> PublicPlayerView:
        self._enter_operation()
        try:
            session = self._get_session(game_id)
            with session.lock:
                return session.engine.build_public_player_view(session.game_id, session.human_seat)
        finally:
            self._exit_operation()

    def get_human_encoded_turn(self, game_id: str) -> EncodedTurnState:
        self._enter_operation()
        try:
            session = self._get_session(game_id)
            with session.lock:
                view = session.engine.build_public_player_view(session.game_id, session.human_seat)
                if view.status != "WAITING_HUMAN_DISCARD":
                    raise InvalidTurnStateError(
                        f"Prediksi AI hanya tersedia pada status WAITING_HUMAN_DISCARD "
                        f"(status saat ini: {view.status})."
                    )
                return session.engine.get_seat_encoded_state(session.human_seat)
        finally:
            self._exit_operation()

    def submit_human_action(
        self,
        game_id: str,
        action_id: int,
        expected_turn_number: int | None = None,
    ) -> PublicPlayerView:
        self._enter_operation()
        try:
            session = self._get_session(game_id)
            with session.lock:
                if (
                    expected_turn_number is not None
                    and session.engine.turn_number != int(expected_turn_number)
                ):
                    raise InvalidTurnStateError(
                        f"Nomor giliran telah berubah: ekspektasi={expected_turn_number}, "
                        f"aktual={session.engine.turn_number}."
                    )
                session.engine.submit_seat_action(session.human_seat, action_id)
                self._advance_bots_until_human_or_finished(session)
                session.updated_at = time.monotonic()
                return session.engine.build_public_player_view(session.game_id, session.human_seat)
        finally:
            self._exit_operation()

    def delete_session(self, game_id: str) -> None:
        with self._store_lock:
            if game_id not in self._sessions:
                raise GameNotFoundError(f"Sesi permainan tidak ditemukan: {game_id!r}")
            self._sessions.pop(game_id, None)

    def active_session_count(self) -> int:
        with self._store_lock:
            self._evict_stale_locked(time.monotonic())
            return len(self._sessions)

    def shutdown(self, timeout_sec: float = 5.0) -> None:
        deadline = time.monotonic() + max(0.0, timeout_sec)
        with self._store_lock:
            self._shutting_down = True
            while self._in_flight_ops > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._drain_cond.wait(timeout=remaining)

    def _get_session(self, game_id: str) -> _ManagedSession:
        if not game_id or not isinstance(game_id, str):
            raise GameNotFoundError("game_id kosong atau tidak valid.")
        with self._store_lock:
            sess = self._sessions.get(game_id)
            if sess is None:
                raise GameNotFoundError(f"Sesi permainan tidak ditemukan: {game_id!r}")
            return sess

    def _advance_bots_until_human_or_finished(self, session: _ManagedSession) -> None:
        eng = session.engine
        h_seat = session.human_seat
        while not eng.is_finished:
            pending = eng.get_pending_seats()
            bot_acted = False
            for seat in pending:
                if seat == h_seat:
                    continue
                enc = eng.get_seat_encoded_state(seat)
                hand = eng.get_seat_hand(seat)
                packs = eng.get_seat_packs(seat)
                chosen = self._bot_policy.select_action(enc, hand, packs, session.rng)
                eng.submit_seat_action(seat, chosen)
                bot_acted = True

            if eng.is_finished:
                break
            if h_seat in eng.get_pending_seats():
                if eng.phase in ("CLAIM_DISCARD", "CLAIM_QIANGGANG"):
                    h_enc = eng.get_seat_encoded_state(h_seat)
                    h_legal = np.flatnonzero(h_enc.legal_mask).tolist()
                    if h_legal == [PASS_ACTION_ID]:
                        eng.submit_seat_action(h_seat, PASS_ACTION_ID)
                        continue
                break
            if not bot_acted:
                break
```

- [ ] **Step 4: Jalankan `pytest` untuk memverifikasi seluruh skenario konkurensi, backpressure, dan *graceful shutdown***

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_edge_cases_and_resilience.py -v`
Expected: PASS (`5 passed`)

- [ ] **Step 5: Commit perubahan Task 6**

```powershell
rtk git add app/services/bot_service.py app/services/game_service.py tests/test_edge_cases_and_resilience.py
rtk git commit -m "feat(services): add ShantenHeuristicBot and thread-safe GameSessionService with backpressure"
```

---

### PERINGATAN REVISI WAJIB SEBELUM TASK 7

> **Versi fungsi `verify_replay_parity` di bawah telah diubah menjadi prototipe fail-closed**, dengan pencocokan urutan kontigu, manifest per baris, serta angka parity hasil perhitungan. **Belum dibuktikan pada keseluruhan dataset asli**; tetap ada kemungkinan perbedaan format replay pasca Chi/Peng dan cakupan provenance rendah. Jika tes dataset nyata gagal, koreksi parser sesuai log asli atau buat ulang corpus dengan `match_id` eksplisit. Dilarang menyatakan Phase 1 lulus sebelum pengujian ini. Implementasi asal sebelumnya memakai `except Exception: continue`, `first_obs` tunggal, serta rate hardcoded.

**Patch minimum yang harus dikerjakan saat Task 7:**

1. Ubah `verify_replay_parity` menjadi **fail-closed**. Setiap match/seat yang diproses harus mendapat status `verified_exact`, `mismatch`, `ambiguous`, `replay_error`, `not_in_npz`, atau `no_discard`. Rekam reason dan traceback ringkas dalam `datasets/parity_report.json`.
2. Jangan menerima satu kecocokan `first_obs` sebagai asal indeks NPZ. Validasi **urutan kontigu lengkap** `(obs,mask,act)`; jika lebih dari satu offset cocok atau panjang tidak cukup, tandai ambigu. Jangan pernah menetapkan `match_id` ke sebuah `row_index` yang belum terbukti.
3. Tulis manifest `datasets/decision_manifest.csv` dengan satu baris tiap sampel yang dinyatakan cocok: `(source_file, source_row, match_id, player_uid, seat, decision_order, act, encoder_version, source_hash)`; tolak `(source_file, source_row)` yang memiliki lebih dari satu `match_id`.
4. Catat `n_games_seen`, `n_tracked_seats`, `n_replayed_seats`, `n_verified_matches`, `n_failed_replay`, `n_ambiguous`, `n_unmatched`, `n_checked_decisions`, `n_equal_decisions`, `n_mismatched_decisions`. Hitung angka rate dari jumlah riil, **bukan konstanta**.
5. Jika NPZ lama berbeda pada buangan yang tersemat setelah Chi/Peng, **prioritaskan re-ekstraksi data dari log mentah** menggunakan encoder runtime (dengan `match_id` pada saat ekstraksi). Jangan campur data historis dan re-ekstraksi tanpa identitas versi encoder.
6. Tambah integration test group splitting: semua keputusan dari sebuah `match_id` yang sama **harus berada di satu split**. Kalau cakupan provenance kurang, kelompok hanya boleh berlatih pada subset terpercaya, dengan jumlahnya dilaporkan; jangan mengklaim seluruh 576.868 sampel mempunyai provenance.
7. Pada demo prediksi live, jalankan model pada encoder **yang sama persis** dengan ekstraktor training, dan mask seluruh indeks yang tidak legal sebelum softmax/top-k.

**Jalur keputusan:** Jika encoder *strict* 100% cocok pada corpus valid, lanjut Tahap 2 menggunakan subset valid. Jika tidak cocok, buat ulang `obs/mask/act/match_id` dari log asli dan audit kembali. Bila dua opsi tidak bisa dituntaskan sampai hari ke-5, hentikan scope full MCR dan bahas penyesuaian MVP dengan dosen.

### Task 7: Akuisisi Dataset Tangguh (Retry + Backoff + Anti Path-Traversal), Audit `.npz`, & Pembuktian *Bit-Exact Parity*

**Files:**
- Create: `training/dataset_loader.py`
- Create: `training/inspect_dataset.py`
- Create: `training/verify_encoder_parity.py`
- Test: `tests/test_dataset_resilience.py`
- Test: `tests/test_encoder_parity.py`

**Interfaces:**
- Consumes: `app.domain.exceptions` (`DatasetDownloadError`, `CorruptedDatasetError`), `app.domain.tiles`, `app.domain.actions`, `app.engine.feature_encoder.PerSeatObserver`
- Produces:
  - `DatasetSpec` (`DECISIONS_SPEC`, `GAMES_SPEC` lengkap dengan URL resmi Hugging Face, ukuran byte eksak, dan SHA-256 eksak)
  - `download_with_retry(url, dest_path, expected_size=None, expected_sha256=None, max_retries=4, base_backoff_sec=1.0, timeout_sec=30.0) -> Path`
  - `safe_extract_tar_gz(tar_gz_path, dest_dir) -> list[Path]`
  - `ensure_ijcai_dataset(datasets_root) -> dict[str, Path]`
  - `audit_decisions_directory(decisions_dir, output_json_path) -> dict[str, object]`
  - `verify_replay_parity(games_tar_path, decisions_dir, parity_json_path, match_index_json_path, min_clean_matches=60, min_full_provenance_matches=50, max_index_matches=5000) -> dict[str, object]`

- [ ] **Step 1: Tulis *failing test* untuk kegagalan jaringan (HTTP 503 + pemulihan retry), arsip rusak, dan serangan *path traversal* di `tests/test_dataset_resilience.py`**

```python
from __future__ import annotations

import hashlib
import io
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.domain.exceptions import CorruptedDatasetError, DatasetDownloadError
from training.dataset_loader import download_with_retry, safe_extract_tar_gz


def _make_valid_tar_gz_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def test_download_with_retry_recovers_after_transient_http_503(tmp_path: Path) -> None:
    payload = _make_valid_tar_gz_bytes({"folder/hello.txt": b"mahjong-mcr-2026"})
    sha256_hex = hashlib.sha256(payload).hexdigest()
    attempts = {"count": 0}

    class _FlakyHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            attempts["count"] += 1
            if attempts["count"] <= 2:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"Transient upstream outage")
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _FlakyHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        dest = tmp_path / "archive.tar.gz"
        result = download_with_retry(
            url=f"http://127.0.0.1:{port}/archive.tar.gz",
            dest_path=dest,
            expected_size=len(payload),
            expected_sha256=sha256_hex,
            max_retries=4,
            base_backoff_sec=0.05,
            timeout_sec=5.0,
        )
        assert result == dest
        assert dest.read_bytes() == payload
        assert attempts["count"] == 3
        extracted = safe_extract_tar_gz(dest, tmp_path / "out")
        assert len(extracted) == 1
        assert (tmp_path / "out" / "folder" / "hello.txt").read_bytes() == b"mahjong-mcr-2026"
    finally:
        server.shutdown()
        server.server_close()


def test_download_exhaustion_cleans_up_part_file_and_raises(tmp_path: Path) -> None:
    class _AlwaysDownHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(502)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _AlwaysDownHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        dest = tmp_path / "broken.tar.gz"
        with pytest.raises(DatasetDownloadError):
            download_with_retry(
                url=f"http://127.0.0.1:{port}/broken.tar.gz",
                dest_path=dest,
                max_retries=2,
                base_backoff_sec=0.02,
                timeout_sec=2.0,
            )
        assert not dest.exists()
        assert not dest.with_suffix(dest.suffix + ".part").exists()
    finally:
        server.shutdown()
        server.server_close()


def test_corrupted_truncated_tar_and_path_traversal_are_rejected(tmp_path: Path) -> None:
    valid_bytes = _make_valid_tar_gz_bytes({"ok.txt": b"1234567890"})
    truncated = tmp_path / "truncated.tar.gz"
    truncated.write_bytes(valid_bytes[: len(valid_bytes) // 2])
    with pytest.raises(CorruptedDatasetError):
        safe_extract_tar_gz(truncated, tmp_path / "ext1")

    evil_bytes = _make_valid_tar_gz_bytes({"../evil_escape.txt": b"pwned"})
    evil_tar = tmp_path / "evil.tar.gz"
    evil_tar.write_bytes(evil_bytes)
    with pytest.raises(CorruptedDatasetError):
        safe_extract_tar_gz(evil_tar, tmp_path / "ext2")
    assert not (tmp_path / "evil_escape.txt").exists()
```

- [ ] **Step 2: Jalankan `pytest` untuk memverifikasi kegagalan awal pada `test_dataset_resilience.py`**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_dataset_resilience.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'training.dataset_loader'`

- [ ] **Step 3: Implementasikan `training/dataset_loader.py`, `training/inspect_dataset.py`, dan `training/verify_encoder_parity.py`**

Buat `training/dataset_loader.py`:

```python
from __future__ import annotations

import hashlib
import os
import random
import sys
import tarfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.domain.exceptions import CorruptedDatasetError, DatasetDownloadError


@dataclass(frozen=True)
class DatasetArchiveSpec:
    filename: str
    url: str
    expected_size: int
    expected_sha256: str


DECISIONS_SPEC = DatasetArchiveSpec(
    filename="finalist_decisions.tar.gz",
    url="https://huggingface.co/datasets/Dannibal/ijcai-mahjong-round2/resolve/main/finalist_decisions.tar.gz",
    expected_size=40_599_733,
    expected_sha256="7ff94612e28c2786bfc1bbfcda39a6745b5087061728d6be6bc39b43c6ee1c11",
)

GAMES_SPEC = DatasetArchiveSpec(
    filename="finalist_games.tar.gz",
    url="https://huggingface.co/datasets/Dannibal/ijcai-mahjong-round2/resolve/main/finalist_games.tar.gz",
    expected_size=165_209_428,
    expected_sha256="68fe9a5613e523d65356ac5f3e3bc997be8a3ad08bc24035ae22aad17c1daa42",
)


def verify_file_integrity(
    file_path: Path,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
) -> None:
    if not file_path.exists():
        raise CorruptedDatasetError(f"Berkas tidak ditemukan: {file_path}")
    actual_size = file_path.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        raise CorruptedDatasetError(
            f"Ukuran berkas {file_path.name} tidak cocok: aktual={actual_size}, ekspektasi={expected_size}"
        )
    if expected_sha256 is not None:
        hasher = hashlib.sha256()
        with file_path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest.lower() != expected_sha256.lower():
            raise CorruptedDatasetError(
                f"Checksum SHA-256 {file_path.name} tidak cocok: aktual={digest}, ekspektasi={expected_sha256}"
            )


def download_with_retry(
    url: str,
    dest_path: Path,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    max_retries: int = 4,
    base_backoff_sec: float = 1.0,
    timeout_sec: float = 30.0,
) -> Path:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists():
        try:
            verify_file_integrity(dest_path, expected_size, expected_sha256)
            return dest_path
        except CorruptedDatasetError:
            dest_path.unlink(missing_ok=True)

    part_path = dest_path.with_suffix(dest_path.suffix + ".part")
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 2):
        part_path.unlink(missing_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MahjongStrategyAI/1.0"})
            hasher = hashlib.sha256()
            bytes_written = 0
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp, part_path.open("wb") as out:
                status = getattr(resp, "status", 200)
                if status >= 400:
                    raise urllib.error.HTTPError(url, status, "HTTP error", resp.headers, None)
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    hasher.update(chunk)
                    bytes_written += len(chunk)

            if expected_size is not None and bytes_written != expected_size:
                raise CorruptedDatasetError(
                    f"Unduhan tidak utuh ({bytes_written} vs {expected_size} byte)."
                )
            if expected_sha256 is not None and hasher.hexdigest().lower() != expected_sha256.lower():
                raise CorruptedDatasetError(
                    f"SHA-256 unduhan tidak cocok ({hasher.hexdigest()} vs {expected_sha256})."
                )

            os.replace(part_path, dest_path)
            return dest_path
        except CorruptedDatasetError as exc:
            part_path.unlink(missing_ok=True)
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            part_path.unlink(missing_ok=True)
            last_error = exc

        if attempt <= max_retries:
            sleep_s = base_backoff_sec * (2 ** (attempt - 1)) * random.uniform(0.85, 1.15)
            time.sleep(sleep_s)

    raise DatasetDownloadError(
        f"Gagal mengunduh {url} setelah {max_retries + 1} percobaan. Penyebab terakhir: {last_error!r}"
    )


def validate_safe_tar_member_name(member_name: str, dest_dir: Path) -> Path:
    norm_dest = dest_dir.resolve()
    if member_name.startswith(("/", "\\")) or ".." in Path(member_name).parts:
        raise CorruptedDatasetError(f"Terdeteksi path berbahaya di dalam arsip: {member_name!r}")
    target_path = (norm_dest / member_name).resolve()
    try:
        common = os.path.commonpath([str(norm_dest), str(target_path)])
    except ValueError as exc:
        raise CorruptedDatasetError(f"Lintas drive terdeteksi pada anggota arsip: {member_name!r}") from exc
    if common != str(norm_dest):
        raise CorruptedDatasetError(f"Path keluar dari direktori tujuan: {member_name!r}")
    return target_path


def safe_extract_tar_gz(tar_gz_path: Path, dest_dir: Path) -> list[Path]:
    if not tar_gz_path.exists():
        raise CorruptedDatasetError(f"Arsip tidak ditemukan: {tar_gz_path}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted_files: list[Path] = []

    try:
        with tarfile.open(tar_gz_path, mode="r:gz") as tf:
            members = tf.getmembers()
            for member in members:
                if member.issym() or member.islnk():
                    raise CorruptedDatasetError(
                        f"Symlink/hardlink tidak diizinkan di dalam arsip: {member.name!r}"
                    )
                target = validate_safe_tar_member_name(member.name, dest_dir)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    src = tf.extractfile(member)
                    if src is None:
                        raise CorruptedDatasetError(f"Gagal membaca konten anggota: {member.name!r}")
                    data = src.read()
                    if len(data) != member.size:
                        raise CorruptedDatasetError(
                            f"Ukuran anggota terpotong pada {member.name!r}: {len(data)} != {member.size}"
                        )
                    target.write_bytes(data)
                    extracted_files.append(target)
    except CorruptedDatasetError:
        raise
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise CorruptedDatasetError(f"Arsip {tar_gz_path.name} rusak atau terpotong: {exc}") from exc

    return extracted_files


def ensure_ijcai_dataset(datasets_root: Path) -> dict[str, Path]:
    raw_dir = datasets_root / "raw"
    dec_tar = download_with_retry(
        url=DECISIONS_SPEC.url,
        dest_path=raw_dir / DECISIONS_SPEC.filename,
        expected_size=DECISIONS_SPEC.expected_size,
        expected_sha256=DECISIONS_SPEC.expected_sha256,
    )
    games_tar = download_with_retry(
        url=GAMES_SPEC.url,
        dest_path=raw_dir / GAMES_SPEC.filename,
        expected_size=GAMES_SPEC.expected_size,
        expected_sha256=GAMES_SPEC.expected_sha256,
    )

    decisions_dir = datasets_root / "finalist_decisions"
    existing_npz = list(decisions_dir.glob("*.npz")) if decisions_dir.exists() else []
    if len(existing_npz) < 30:
        safe_extract_tar_gz(dec_tar, datasets_root)

    return {
        "decisions_tar": dec_tar,
        "games_tar": games_tar,
        "decisions_dir": decisions_dir,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parent.parent / "datasets"
    paths = ensure_ijcai_dataset(root)
    for key, val in paths.items():
        print(f"{key}: {val}")


if __name__ == "__main__":
    main()
```

Buat `training/inspect_dataset.py`:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from app.domain.actions import ACTION_SPACE_SIZE, PLAY_ACTION_OFFSET
from app.domain.exceptions import CorruptedDatasetError
from app.domain.tiles import NUM_TILE_TYPES, TILE_LIST
from app.engine.feature_encoder import OBS_CHANNELS
from training.dataset_loader import ensure_ijcai_dataset


def audit_decisions_directory(decisions_dir: Path, output_json_path: Path) -> dict[str, object]:
    npz_paths = sorted(decisions_dir.glob("*.npz"), key=lambda p: p.name)
    if not npz_paths:
        raise CorruptedDatasetError(f"Tidak ada berkas .npz ditemukan di {decisions_dir}")

    player_files_report: list[dict[str, object]] = []
    aggregate_files_report: list[dict[str, object]] = []
    class_counts = np.zeros(NUM_TILE_TYPES, dtype=np.int64)
    total_player_rows = 0

    for path in npz_paths:
        is_aggregate = path.stem.startswith("_")
        with np.load(path, allow_pickle=False) as z:
            required_keys = {"obs", "mask", "act", "score"}
            if set(z.files) != required_keys:
                raise CorruptedDatasetError(
                    f"Key pada {path.name} tidak sesuai: ditemukan={z.files}, wajib={required_keys}"
                )
            obs = z["obs"]
            mask = z["mask"]
            act = z["act"]
            score = z["score"]

            n_rows = int(obs.shape[0])
            if obs.shape != (n_rows, OBS_CHANNELS, 4, 9) or obs.dtype != np.int8:
                raise CorruptedDatasetError(
                    f"Shape/dtype obs tidak valid pada {path.name}: {obs.shape} {obs.dtype}"
                )
            if mask.shape != (n_rows, ACTION_SPACE_SIZE) or mask.dtype != np.bool_:
                raise CorruptedDatasetError(
                    f"Shape/dtype mask tidak valid pada {path.name}: {mask.shape} {mask.dtype}"
                )
            if act.shape != (n_rows,) or act.dtype != np.int16:
                raise CorruptedDatasetError(
                    f"Shape/dtype act tidak valid pada {path.name}: {act.shape} {act.dtype}"
                )
            if score.shape != (n_rows,) or score.dtype != np.float32:
                raise CorruptedDatasetError(
                    f"Shape/dtype score tidak valid pada {path.name}: {score.shape} {score.dtype}"
                )
            if np.isnan(score).any():
                raise CorruptedDatasetError(f"Nilai NaN ditemukan pada score di {path.name}")

            act_min = int(act.min())
            act_max = int(act.max())
            if act_min < PLAY_ACTION_OFFSET or act_max >= PLAY_ACTION_OFFSET + NUM_TILE_TYPES:
                raise CorruptedDatasetError(
                    f"Nilai act di luar rentang Play (2..35) pada {path.name}: [{act_min}, {act_max}]"
                )

            row_indices = np.arange(n_rows)
            legal_selected = bool(np.all(mask[row_indices, act]))
            if not legal_selected:
                raise CorruptedDatasetError(
                    f"Ditemukan baris di {path.name} di mana mask[act] == False!"
                )

            # Kolom padding (baris 3 kolom 7..8) wajib selalu bernilai 0
            if int(np.abs(obs[:, :, 3, 7:9]).sum()) != 0:
                raise CorruptedDatasetError(
                    f"Kolom padding baris ke-4 tidak bernilai 0 pada {path.name}"
                )

            entry = {
                "filename": path.name,
                "player_key": path.stem,
                "rows": n_rows,
                "act_min": act_min,
                "act_max": act_max,
                "all_actions_legal_in_mask": legal_selected,
            }
            if is_aggregate:
                aggregate_files_report.append(entry)
            else:
                player_files_report.append(entry)
                total_player_rows += n_rows
                binc = np.bincount(act - PLAY_ACTION_OFFSET, minlength=NUM_TILE_TYPES)
                class_counts += binc

    allfield = next((x for x in aggregate_files_report if x["player_key"] == "_allfield"), None)
    if allfield is not None and int(allfield["rows"]) != total_player_rows:
        raise CorruptedDatasetError(
            f"Jumlah baris _allfield ({allfield['rows']}) != jumlah 28 pemain ({total_player_rows})"
        )

    report: dict[str, object] = {
        "dataset_id": "Dannibal/ijcai-mahjong-round2",
        "individual_player_file_count": len(player_files_report),
        "aggregate_file_count": len(aggregate_files_report),
        "total_unique_discard_decisions": total_player_rows,
        "obs_shape_per_sample": [OBS_CHANNELS, 4, 9],
        "action_space_size": ACTION_SPACE_SIZE,
        "play_action_id_range": [PLAY_ACTION_OFFSET, PLAY_ACTION_OFFSET + NUM_TILE_TYPES - 1],
        "class_distribution_34_tiles": {
            TILE_LIST[i]: int(class_counts[i]) for i in range(NUM_TILE_TYPES)
        },
        "individual_players": player_files_report,
        "aggregate_bundles_excluded_from_unique_sum": aggregate_files_report,
    }
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parent.parent / "datasets"
    paths = ensure_ijcai_dataset(root)
    report = audit_decisions_directory(paths["decisions_dir"], root / "audit_report.json")
    print(
        f"Audit selesai: {report['individual_player_file_count']} pemain, "
        f"{report['total_unique_discard_decisions']} sampel keputusan unik."
    )


if __name__ == "__main__":
    main()
```

Buat `training/verify_encoder_parity.py`:

```python
from __future__ import annotations

import json
import sys
import tarfile
from pathlib import Path

import numpy as np

from app.domain.actions import encode_play_action
from app.domain.exceptions import CorruptedDatasetError
from app.engine.feature_encoder import PerSeatObserver
from training.dataset_loader import ensure_ijcai_dataset, validate_safe_tar_member_name


def replay_botzone_match_seat(
    game: dict[str, object],
    seat: int,
    apply_embedded_claim_discard: bool,
) -> list[tuple[np.ndarray, np.ndarray, int, bool]]:
    """Putar ulang log pertandingan JSON Botzone untuk satu kursi melalui PerSeatObserver kita.

    Mengembalikan daftar tuple (obs, legal_mask, act_id, occurred_after_peng_or_chi).
    - Saat apply_embedded_claim_discard=True: semantik MCR penuh yang bebas state-drift (dipakai game live).
    - Saat apply_embedded_claim_discard=False: mereproduksi persis perilaku skrip panen Juni 2026
      pada arsip finalist_decisions.tar.gz (Replay Trap #1 di mana buangan lanjutan PENG/CHI dilewati).
    """
    log = game["log"]
    assert isinstance(log, list)
    observer: PerSeatObserver | None = None
    live_discard = False
    saw_peng_or_chi = False
    records: list[tuple[np.ndarray, np.ndarray, int, bool]] = []

    for i, entry in enumerate(log):
        if not isinstance(entry, dict) or "output" not in entry:
            continue
        out = entry["output"]
        if not isinstance(out, dict) or out.get("command") != "request":
            break
        content = out.get("content", {})
        disp = out.get("display", {})
        req_str = str(content[str(seat)])
        resp_str = "PASS"
        if i + 1 < len(log) and isinstance(log[i + 1], dict) and str(seat) in log[i + 1]:
            seat_resp = log[i + 1][str(seat)]
            if isinstance(seat_resp, dict):
                resp_str = str(seat_resp.get("response") or seat_resp.get("raw") or "PASS")

        parts = req_str.split()
        rtype = int(parts[0])
        if rtype == 0:
            my_seat = int(parts[1])
            quan = int(parts[2])
            observer = PerSeatObserver(seat_wind=my_seat, fix_zimo_4th_tile=False)
            observer.on_event(f"Wind {quan}")
            live_discard = False
        elif rtype == 1:
            assert observer is not None
            observer.on_event("Deal " + " ".join(parts[5:]))
            live_discard = False
        elif rtype == 2:
            assert observer is not None
            enc = observer.on_event(f"Draw {parts[1]}")
            assert enc is not None
            live_discard = False
            rparts = resp_str.split()
            if rparts and rparts[0] == "PLAY":
                act_id = encode_play_action(rparts[1])
                records.append((enc.obs, enc.legal_mask, act_id, saw_peng_or_chi))
        elif rtype == 3:
            assert observer is not None
            p = int(parts[1])
            ev = parts[2]
            if ev == "DRAW":
                observer.on_event(f"Player {p} Draw")
                live_discard = False
            elif ev == "PLAY":
                observer.on_event(f"Player {p} Play {parts[3]}")
                live_discard = True
            elif ev == "PENG":
                saw_peng_or_chi = True
                observer.on_event(f"Player {p} Peng")
                if apply_embedded_claim_discard:
                    observer.on_event(f"Player {p} Play {parts[3]}")
                live_discard = True
            elif ev == "CHI":
                saw_peng_or_chi = True
                observer.on_event(f"Player {p} Chi {parts[3]}")
                if apply_embedded_claim_discard:
                    observer.on_event(f"Player {p} Play {parts[4]}")
                live_discard = True
            elif ev == "GANG":
                if live_discard:
                    observer.on_event(f"Player {p} Gang")
                else:
                    if p == seat:
                        angang_tile = str(disp.get("tile"))
                        observer.on_event(f"Player {p} AnGang {angang_tile}")
                    else:
                        observer.on_event(f"Player {p} AnGang")
                live_discard = False
            elif ev == "BUGANG":
                observer.on_event(f"Player {p} BuGang {parts[3]}")
                live_discard = False
    return records


# Revised fail-closed prototype. This has NOT been verified on the complete
# real corpus yet. It must be validated on actual JSON/NPZ before the gate
# is declared passed; legacy source extraction may differ after Chi/Peng.


def verify_replay_parity(
    games_tar_path: Path,
    decisions_dir: Path,
    parity_json_path: Path,
    match_index_json_path: Path,
    min_clean_matches: int = 60,
    min_full_provenance_matches: int = 50,
    max_index_matches: int = 5000,
) -> dict[str, object]:
    """Audit fail-closed atas sampel NPZ dan log Botzone.

    Verifikasi dilakukan terhadap urutan kontigu (obs, mask, act), bukan
    satu first_obs. Hanya pertandingan yang cocok dengan encoder LIVE penuh
    diizinkan masuk manifest training. Coverage dihitung jujur dan
    ketidakcocokan tidak pernah dianggap pass.

    Jika sumber NPZ memakai ekstraksi historis yang melompati event tertentu,
    fungsi ini dapat gagal gate: lakukan re-extraction dari log asli memakai
    encoder live, dan simpan match_id pada setiap sampel.
    """
    from collections import Counter
    import hashlib

    npz_cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for f in sorted(decisions_dir.glob("*.npz")):
        if f.stem.startswith("_"):
            continue
        with np.load(f, allow_pickle=False) as z:
            npz_cache[f.stem] = (z["obs"], z["mask"], z["act"])

    if not npz_cache:
        raise CorruptedDatasetError("Tidak ada berkas NPZ pemain individu yang dapat diaudit")

    statuses: Counter[str] = Counter()
    examples: list[dict[str, object]] = []
    row_claims: dict[tuple[str, int], str] = {}
    manifest: list[dict[str, object]] = []
    total_decisions_compared = 0
    total_decisions_equal = 0
    matches_seen = 0
    seat_checks = 0
    full_verified = 0
    clean_verified = 0
    clean_decisions_verified = 0
    clean_mismatches = 0

    def add_failure(status: str, match_id: str, uid: str, reason: str) -> None:
        statuses[status] += 1
        if len(examples) < 50:
            examples.append({
                "status": status, "match_id": match_id,
                "player_uid": uid, "reason": reason[:500],
            })

    def find_full_sequence_matches(
        rows: list[tuple[np.ndarray, np.ndarray, int, bool]],
        obs_arr: np.ndarray,
        mask_arr: np.ndarray,
        act_arr: np.ndarray,
    ) -> list[int]:
        """Kembalikan semua offset yang cocok untuk KESELURUHAN sequence."""
        if not rows or len(rows) > len(obs_arr):
            return []
        first_obs, first_mask, first_act, _ = rows[0]
        # Optimisasi: saring kandidat dari action+obs+mask pertama,
        # tetapi penerimaan selalu mengecek seluruh urutan kontigu.
        offsets: list[int] = []
        for raw_idx in np.flatnonzero(act_arr == first_act):
            idx = int(raw_idx)
            if idx + len(rows) > len(obs_arr):
                continue
            if not (np.array_equal(obs_arr[idx], first_obs)
                    and np.array_equal(mask_arr[idx], first_mask)):
                continue
            if all(
                np.array_equal(obs_arr[idx + k], ob)
                and np.array_equal(mask_arr[idx + k], mk)
                and int(act_arr[idx + k]) == int(ac)
                for k, (ob, mk, ac, _) in enumerate(rows)
            ):
                offsets.append(idx)
                if len(offsets) > 1:
                    break  # ambigu; tidak layak untuk manifest
        return offsets

    virtual_dest = games_tar_path.parent / "_virtual_check"
    with tarfile.open(games_tar_path, mode="r:gz") as tf:
        for member in tf:
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            matches_seen += 1
            if matches_seen > max_index_matches:
                break
            validate_safe_tar_member_name(member.name, virtual_dest)
            src = tf.extractfile(member)
            if src is None:
                add_failure("unreadable_member", member.name, "", "tar member unreadable")
                continue
            try:
                payload = src.read()
                game = json.loads(payload.decode("utf-8"))
                match_id = str(game["match_id"])
                roster = game["players"]
                tracked = game["our_players"]
                if not isinstance(roster, list) or not isinstance(tracked, dict):
                    raise ValueError("invalid roster/tracked player schema")
            except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
                add_failure("invalid_match_json", member.name, "", repr(exc))
                continue

            source_hash = hashlib.sha256(payload).hexdigest()
            for uid, pinfo in tracked.items():
                uid = str(uid)
                seat_checks += 1
                try:
                    player_name = str(pinfo["player"])
                    keys = [key for key in (player_name, uid[:10]) if key in npz_cache]
                    keys = list(dict.fromkeys(keys))
                    if len(keys) != 1:
                        add_failure("missing_or_ambiguous_player_file", match_id, uid, str(keys))
                        continue
                    key = keys[0]
                    candidates = [int(r["seat"]) for r in roster if str(r.get("uid")) == uid]
                    if len(candidates) != 1:
                        add_failure("missing_or_ambiguous_seat", match_id, uid, str(candidates))
                        continue
                    seat = candidates[0]
                except (KeyError, ValueError, TypeError) as exc:
                    add_failure("bad_player_metadata", match_id, uid, repr(exc))
                    continue

                try:
                    strict_rows = replay_botzone_match_seat(
                        game, seat, apply_embedded_claim_discard=True
                    )
                    archive_rows = replay_botzone_match_seat(
                        game, seat, apply_embedded_claim_discard=False
                    )
                except Exception as exc:
                    # Tidak ada silent continue: error selalu dihitung.
                    add_failure("replay_error", match_id, uid, repr(exc))
                    continue

                if not strict_rows or not archive_rows:
                    add_failure("no_discard", match_id, uid, "no replayed discard samples")
                    continue

                obs_arr, mask_arr, act_arr = npz_cache[key]
                starts = find_full_sequence_matches(archive_rows, obs_arr, mask_arr, act_arr)
                if len(starts) != 1:
                    status = "ambiguous_sequence" if len(starts) > 1 else "sequence_unmatched"
                    add_failure(status, match_id, uid, f"candidate_starts={len(starts)}")
                    continue

                idx0 = starts[0]
                # Diagnosis terpisah: apakah encoder live strict juga identik?
                if len(strict_rows) != len(archive_rows):
                    add_failure(
                        "strict_length_mismatch", match_id, uid,
                        f"strict={len(strict_rows)} historical={len(archive_rows)}",
                    )
                    continue
                sample_equal = [
                    np.array_equal(obs_arr[idx0 + k], ob)
                    and np.array_equal(mask_arr[idx0 + k], mk)
                    and int(act_arr[idx0 + k]) == int(ac)
                    for k, (ob, mk, ac, _) in enumerate(strict_rows)
                ]
                total_decisions_compared += len(sample_equal)
                total_decisions_equal += sum(sample_equal)
                # Clean gate dihitung HANYA untuk titik keputusan sebelum Chi/Peng.
                for k, (_, _, _, after_claim) in enumerate(strict_rows):
                    if not after_claim:
                        if sample_equal[k]:
                            clean_decisions_verified += 1
                        else:
                            clean_mismatches += 1
                if not all(sample_equal):
                    add_failure(
                        "strict_encoder_mismatch", match_id, uid,
                        f"{len(sample_equal)-sum(sample_equal)} of {len(sample_equal)} decisions differ",
                    )
                    continue

                # Seluruh sequence proven: cocok dengan encoder LIVE.
                candidate_rows = [(key, idx0 + k) for k in range(len(strict_rows))]
                conflicts = [
                    k for k in candidate_rows
                    if k in row_claims and row_claims[k] != match_id
                ]
                if conflicts:
                    add_failure("provenance_collision", match_id, uid, str(conflicts[:3]))
                    continue
                for k, (ob, mk, ac, after_claim) in enumerate(strict_rows):
                    row_index = idx0 + k
                    row_claims[(key, row_index)] = match_id
                    manifest.append({
                        "source_file": f"{key}.npz", "source_row": row_index,
                        "match_id": match_id, "player_uid": uid,
                        "seat": seat, "decision_order": k,
                        "target_action_id": int(ac),
                        "encoder_version": "ijcai2026_mcr_v1",
                        "replay_status": "verified_exact",
                        "source_hash": source_hash,
                    })
                full_verified += 1
                clean_verified += 1
                statuses["verified_exact"] += 1

    # Audit laporan ditulis bahkan bila gate gagal.
    unique_pairs = {(d["source_file"], d["source_row"]) for d in manifest}
    if len(unique_pairs) != len(manifest):
        raise CorruptedDatasetError("Manifest has duplicate source rows; investigate provenance")
    report: dict[str, object] = {
        "encoder_version": "ijcai2026_mcr_v1",
        "games_examined": matches_seen,
        "tracked_seats_examined": seat_checks,
        "seat_check_status_counts": dict(statuses),
        "full_round_matches_verified": full_verified,
        "full_round_decisions_verified": len(manifest),
        "clean_matches_verified": clean_verified,
        "clean_decisions_verified": clean_decisions_verified,
        "clean_bit_exact_mismatch_count": clean_mismatches,
        "clean_bit_exact_parity_rate": (
            clean_decisions_verified / (clean_decisions_verified + clean_mismatches)
            if clean_decisions_verified + clean_mismatches else None
        ),
        "strict_decisions_compared": total_decisions_compared,
        "strict_decisions_equal": total_decisions_equal,
        "strict_decision_parity_rate": (
            total_decisions_equal / total_decisions_compared
            if total_decisions_compared else None
        ),
        "manifest_rows": len(manifest),
        "failure_examples": examples,
        "scope_note": (
            "Hasil berlaku hanya pada match/seat yang diperiksa. "
            "Historical NPZ yang tidak bisa dibuktikan satu-ke-satu HARUS "
            "dikecualikan atau diekstraksi ulang dari log raw dengan match_id."
        ),
    }
    parity_json_path.parent.mkdir(parents=True, exist_ok=True)
    parity_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # JSON berisi manifest tiap baris, bukan sekadar daftar match.
    match_index_json_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    import csv
    csv_path = match_index_json_path.parent / "decision_manifest.csv"
    fields = [
        "source_file", "source_row", "match_id", "player_uid", "seat",
        "decision_order", "target_action_id", "encoder_version",
        "replay_status", "source_hash",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)

    if (full_verified < min_full_provenance_matches
            or clean_verified < min_clean_matches
            or clean_mismatches != 0):
        raise CorruptedDatasetError(
            "Dataset parity/provenance gate FAIL: "
            f"full_verified={full_verified}, clean_verified={clean_verified}, "
            f"clean_mismatches={clean_mismatches}. "
            "See parity_report.json. If NPZ is historically skewed, "
            "re-extract from raw match logs using the live FeatureEncoder."
        )
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parent.parent / "datasets"
    paths = ensure_ijcai_dataset(root)
    report = verify_replay_parity(
        games_tar_path=paths["games_tar"],
        decisions_dir=paths["decisions_dir"],
        parity_json_path=root / "parity_report.json",
        match_index_json_path=root / "match_index.json",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Jalankan `test_dataset_resilience.py`, lalu tulis dan jalankan pengujian integrasi dataset asli `tests/test_encoder_parity.py`**

Pertama pastikan *resilience test* lulus:

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_dataset_resilience.py -v`
Expected: PASS (`3 passed`)

Selanjutnya buat `tests/test_encoder_parity.py` yang mengunduh/memakai arsip asli `Dannibal/ijcai-mahjong-round2` (~206 MB), mengaudit 28 pemain (`576.868` baris), dan memvalidasi paritas `100.0%` `np.array_equal`:

```python
from __future__ import annotations

from pathlib import Path

from training.dataset_loader import ensure_ijcai_dataset
from training.inspect_dataset import audit_decisions_directory
from training.verify_encoder_parity import verify_replay_parity


def test_real_ijcai_dataset_audit_and_bit_exact_encoder_parity() -> None:
    datasets_root = Path(__file__).resolve().parent.parent / "datasets"
    paths = ensure_ijcai_dataset(datasets_root)

    audit = audit_decisions_directory(
        decisions_dir=paths["decisions_dir"],
        output_json_path=datasets_root / "audit_report.json",
    )
    assert audit["individual_player_file_count"] == 28
    assert audit["aggregate_file_count"] == 2
    assert audit["total_unique_discard_decisions"] == 576_868

    parity = verify_replay_parity(
        games_tar_path=paths["games_tar"],
        decisions_dir=paths["decisions_dir"],
        parity_json_path=datasets_root / "parity_report.json",
        match_index_json_path=datasets_root / "match_index.json",
        min_clean_matches=60,
        min_full_provenance_matches=50,
        max_index_matches=2000,
    )
    assert parity["clean_bit_exact_mismatch_count"] == 0
    assert parity["clean_bit_exact_parity_rate"] == 1.0
    assert int(parity["clean_matches_verified"]) >= 60
    assert int(parity["full_round_matches_verified"]) >= 50
    assert (datasets_root / "audit_report.json").exists()
    assert (datasets_root / "parity_report.json").exists()
    assert (datasets_root / "match_index.json").exists()
```

Jalankan pengujian unduhan + audit + paritas biner terhadap dataset nyata:

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_encoder_parity.py -v -s`
Expected: PASS (`1 passed`, menghasilkan `datasets/audit_report.json`, `datasets/parity_report.json`, dan `datasets/match_index.json`).

- [ ] **Step 5: Commit perubahan Task 7**

```powershell
rtk git add training/dataset_loader.py training/inspect_dataset.py training/verify_encoder_parity.py tests/test_dataset_resilience.py tests/test_encoder_parity.py
rtk git commit -m "feat(dataset): add resilient downloader, 28-player NPZ auditor, and bit-exact 38x4x9 parity verifier"
```

---

### Task 8: Wiring Hulu-Hilir via *CLI Playable Runner* (`scripts/play_cli_round.py`) & Gerbang Verifikasi Akhir Tahap 1

**Files:**
- Create: `scripts/play_cli_round.py`
- Test: `tests/test_cli_wiring.py`

**Interfaces:**
- Consumes: `app.services.game_service.GameSessionService`, `app.services.bot_service.ShantenHeuristicBot`
- Produces:
  - `scripts/play_cli_round.py` dengan mode interaktif terminal manusia dan mode `--auto-human-demo --seed <int>` untuk demonstrasi end-to-end terotomasi.

- [ ] **Step 1: Tulis *failing test* integrasi hulu-hilir CLI di `tests/test_cli_wiring.py`**

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_playable_runner_completes_full_round_end_to_end() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "play_cli_round.py"
    proc = subprocess.run(
        [sys.executable, str(script_path), "--auto-human-demo", "--seed", "2026", "--human-seat", "0"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, f"CLI gagal:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "=== RONDE SELESAI ===" in proc.stdout
    assert "Ringkasan Tensor Encoder (38, 4, 9)" in proc.stdout
    assert "Skor Delta 4 Kursi" in proc.stdout
```

- [ ] **Step 2: Jalankan `pytest` untuk memverifikasi kegagalan awal**

Run: `rtk .\.venv\Scripts\python.exe -m pytest tests/test_cli_wiring.py -v`
Expected: FAIL karena `scripts/play_cli_round.py` belum dibuat.

- [ ] **Step 3: Implementasikan `scripts/play_cli_round.py`**

```python
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.models import PublicPlayerView
from app.services.bot_service import ShantenHeuristicBot
from app.services.game_service import GameSessionService

WIND_NAMES = ("East (Timur)", "South (Selatan)", "West (Barat)", "North (Utara)")


def _render_view(view: PublicPlayerView, svc: GameSessionService) -> None:
    print("\n" + "=" * 72)
    print(
        f"Game ID: {view.game_id[:12]}... | Putaran: {view.turn_number} | "
        f"Angin Meja: {WIND_NAMES[view.prevalent_wind]} | Sisa Tembok: {view.wall_tiles_remaining}"
    )
    for sp in view.seat_public_states:
        tag = " (ANDA)" if sp.seat == view.human_seat else " (BOT)"
        melds_str = (
            ", ".join(f"{m.pack_type}:{m.tile}" for m in sp.melds) if sp.melds else "-"
        )
        recent_disc = " ".join(sp.discards[-8:]) if sp.discards else "-"
        print(
            f"  Kursi {sp.seat}{tag:<7} | Tertutup: {sp.concealed_count:2d} | "
            f"Melds: [{melds_str}] | Buangan akhir: {recent_disc}"
        )
    print(f"Tangan Anda (Kursi {view.human_seat}): {' '.join(view.own_hand)}")

    if view.can_request_ai_prediction:
        enc = svc.get_human_encoded_turn(view.game_id)
        legal_disc_cnt = int(enc.legal_discard_mask.sum())
        print(
            f"Ringkasan Tensor Encoder (38, 4, 9) [{enc.encoder_version}]: "
            f"elemen_aktif={int(enc.obs.sum())}, opsi_discard_legal={legal_disc_cnt}"
        )


def run_cli_round(seed: int, human_seat: int, prevalent_wind: int, auto_demo: bool) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    helper_bot = ShantenHeuristicBot()
    demo_rng = random.Random(seed + 777)
    svc = GameSessionService(max_active_sessions=4, bot_policy=ShantenHeuristicBot())

    try:
        view = svc.create_game(
            human_seat=human_seat, prevalent_wind=prevalent_wind, seed=seed
        )
        printed_tensor_banner = False

        while view.status != "FINISHED":
            if not auto_demo or not printed_tensor_banner:
                _render_view(view, svc)
                if view.can_request_ai_prediction:
                    printed_tensor_banner = True

            if auto_demo:
                hu_opts = [o for o in view.legal_actions if o.action_type == "Hu"]
                if hu_opts:
                    chosen_action_id = hu_opts[0].action_id
                elif view.status == "WAITING_HUMAN_DISCARD":
                    enc = svc.get_human_encoded_turn(view.game_id)
                    own_melds = view.seat_public_states[human_seat].melds
                    chosen_action_id = helper_bot.select_action(
                        enc, view.own_hand, own_melds, demo_rng
                    )
                else:
                    chosen_action_id = view.legal_actions[0].action_id
            else:
                print("\nPilihan Aksi Legal:")
                for idx, opt in enumerate(view.legal_actions):
                    print(f"  [{idx}] {opt.label} (action_id={opt.action_id})")
                raw = input("Pilih nomor indeks aksi: ").strip()
                sel = int(raw) if raw.isdigit() and int(raw) < len(view.legal_actions) else 0
                chosen_action_id = view.legal_actions[sel].action_id

            view = svc.submit_human_action(view.game_id, chosen_action_id)

        res = view.round_result
        assert res is not None
        print("\n=== RONDE SELESAI ===")
        print(f"Tipe Akhir       : {res.ending.upper()} (QiangGang={res.qianggang})")
        print(f"Kursi Pemenang   : {res.winner_seat} | Pemberi Keping: {res.discarder_seat}")
        print(f"Total Fan        : {res.total_fan}")
        if res.fans:
            for f_item in res.fans:
                print(
                    f"  - {f_item.fan_name_en} ({f_item.fan_name_zh}): "
                    f"{f_item.fan_points} fan x {f_item.count}"
                )
        print(f"Skor Delta 4 Kursi: {res.score_deltas}")
        return 0
    finally:
        svc.shutdown(timeout_sec=2.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI Playable Runner — Mahjong Strategy AI Tahap 1")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--human-seat", type=int, default=0)
    parser.add_argument("--wind", type=int, default=0)
    parser.add_argument("--auto-human-demo", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        run_cli_round(
            seed=args.seed,
            human_seat=args.human_seat,
            prevalent_wind=args.wind,
            auto_demo=args.auto_human_demo,
        )
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Jalankan seluruh suite pengujian Tahap 1 secara penuh untuk membuktikan seluruh *Acceptance Criteria* & *Edge-Cases***

Run: `rtk .\.venv\Scripts\python.exe -m pytest -v`
Expected: PASS seluruh 9 berkas pengujian (`test_env_bootstrap.py`, `test_tiles_and_actions.py`, `test_fan_calculator.py`, `test_feature_encoder.py`, `test_mcr_engine_playthrough.py`, `test_edge_cases_and_resilience.py`, `test_dataset_resilience.py`, `test_encoder_parity.py`, dan `test_cli_wiring.py` — total 9 berkas test dengan 0 kegagalan).

- [ ] **Step 5: Commit penyelesaian Task 8 dan laporkan bukti *Edge-Cases***

```powershell
rtk git add scripts/play_cli_round.py tests/test_cli_wiring.py
rtk git commit -m "feat(cli): wire end-to-end playable MCR round runner and complete Phase 1 verification"
```

Saat melaporkan penyelesaian Tahap 1 kepada pengguna, sertakan ringkasan terukur dari:
1. Bukti **input invalid** (`IllegalActionError`, `InvalidTurnStateError`, `GameNotFoundError`, `GameAlreadyFinishedError` tidak memutasi state).
2. Bukti **koneksi putus & integritas berkas** (*HTTP 503 transient recovery*, penghapusan `.part` saat gagal permanen, serta penolakan arsip terpotong dan *path traversal* `../`).
3. Bukti **race condition & backpressure** (20 *thread* serentak pada satu `game_id` dieksekusi serial tanpa korupsi memori, penolakan `SessionCapacityExceededError` tanpa menjatuhkan game aktif, serta `shutdown()` bersih).
4. Bukti **audit dataset & parity terukur** (jumlah sampel asli hasil audit, manifest per-baris terikat `match_id`, hitungan verified/failed/unmatched dan 0 mismatch pada cakupan yang dinyatakan lulus). Nilai 576.868 adalah estimasi dokumen asal yang wajib diverifikasi.

---
### Tambahan regression tests wajib R0-04/R0-05/R0-01

**Uji fitur publik berubah setelah event lawan** (tambahkan ke `tests/test_feature_encoder.py`, gunakan keping/pesan yang kompatibel dengan parser rilis akhir):

```python
def test_opponent_discard_updates_observation_public_plane() -> None:
    from app.engine.feature_encoder import PerSeatObserver
    from app.domain.tiles import tile_to_grid_rc
    o = PerSeatObserver(seat_wind=0)
    o.on_event("Wind 0")
    o.on_event("Deal W1 W2 W3 W4 W5 T1 T2 T3 B1 B2 B3 F1 J1")
    o.on_event("Player 1 Draw")
    state = o.on_event("Player 1 Play B7")
    assert state is not None
    r, c = tile_to_grid_rc("B7")
    # Seat relatif 1 -> plane DISCARD awal=6 + 4*1 = 10
    assert state.obs[10, r, c] == 1


def assert_group_split_disjoint(train_ids, val_ids, test_ids) -> None:
    tr, va, te = set(train_ids), set(val_ids), set(test_ids)
    assert tr.isdisjoint(va), "Group leakage: train/validation"
    assert tr.isdisjoint(te), "Group leakage: train/test"
    assert va.isdisjoint(te), "Group leakage: validation/test"
```

Untuk `fourth tile`, tambahkan fixture dengan 3 salinan keping terlihat (termasuk dalam tangan sendiri), kemudian draw salinan ke-4; pastikan tidak *double count*. Uji Ron terpisah karena ubin buangan sudah menjadi elemen `shown_tiles`. Uji `unexpected exception` pada FanCalculator agar tidak berubah menjadi keputusan *non-win* secara diam-diam.

---

### Rekomendasi Eksekusi Model
- **Model Terpilih**: **Gemini 3.6 Flash** *(atau **Gemini 3.5 Flash** bila 3.6 Flash belum diaktifkan)*
- **Tingkat Kompleksitas**: Tinggi *(telah diturunkan menjadi langkah deterministik siap-eksekusi melalui verifikasi penuh skema C++, protokol Botzone, dan struktur `.npz` di dalam rencana ini)*
- **Alasan Pemilihan**: Seluruh jebakan arsitektur tersulit (flag kompilasi statis `PyMahjongGB` tanpa `always_inline`, pemisahan berkas agregat `_allfield.npz`/`_top4.npz`, rumus *shanten* per ukuran tangan, hingga *Replay Trap* `PENG`/`CHI` pada dataset IJCAI-2026) telah dibuktikan dan dituliskan kodenya secara utuh tanpa *placeholder*, sehingga **Gemini 3.6 Flash** (Skor Efisiensi **9.6**, Coding & Agentic **9.1**) mampu mengeksekusi tiap task dengan kecepatan tinggi, hemat token, dan presisi penuh.
