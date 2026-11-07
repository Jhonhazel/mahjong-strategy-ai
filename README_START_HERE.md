# Mahjong Strategy AI — Lecturer Edition

## Windows — Native Python, Without Docker

**WINDOWS NATIVE — IMPLEMENTED / NOT YET VERIFIED.** Pengujian Windows asli belum
dilakukan; tes PostgreSQL nyata pada Mac tidak menggantikan pengujian CMD/ACL Windows.

### First-Time Setup

Install Python **3.12 x64** (sertakan Python launcher `py`) dan PostgreSQL lokal.
Pastikan service PostgreSQL berjalan. Install Microsoft C++ Build Tools beserta
Windows SDK **jika PyMahjongGB perlu dikompilasi**. Internet diperlukan untuk
dependency pada setup pertama.

Extract All dari ZIP Lecturer lengkap, lalu buka **CMD** di folder hasil ekstraksi:

```bat
setup-windows-native.cmd
```

Setup membuat `.venv`, memasang dependency terpin, memverifikasi model asli, dan
membuat role, database serta tabel aplikasi dengan aman. Setup dapat meminta port,
username administrator PostgreSQL dan password tersembunyi satu kali. Default port
5432, administrator `postgres`. Tidak perlu SQL Shell, pgAdmin, Docker atau Node.

Setup hanya diperlukan sekali. Untuk membuka website, gunakan langkah harian
di bawah. Aktivasi harus dilakukan dalam CMD yang sama dengan perintah FastAPI;
aktivasi dari PowerShell/double-click tidak berlaku pada terminal lain.

### Every Time You Start the Website

Buka CMD dari direktori root project, lalu jalankan **Option A**:

```bat
.venv\Scripts\activate.bat
fastapi dev main.py
```

Buka **http://127.0.0.1:8000/game**. Tidak perlu setup, install dependency,
provisioning database, atau retraining ulang. Tidak perlu PATH/global FastAPI.

### Stop

Tekan **Ctrl+C** pada CMD yang menjalankan FastAPI.

### Restart Later

Buka CMD baru dari root project dan ulangi:

```bat
.venv\Scripts\activate.bat
fastapi dev main.py
```

### Troubleshooting

Jika `fastapi` tidak dikenali, pastikan `.venv` ada dan aktif pada CMD yang sama:

```bat
where python
where fastapi
python --version
```

Hasil pertama harus menunjuk `.venv\Scripts\python.exe` dan
`.venv\Scripts\fastapi.exe` milik project; Python harus 3.12 x64. Jika venv hilang/
tidak lengkap, periksa kegagalan first-time setup; jangan install FastAPI global.

Jika koneksi database gagal, periksa service PostgreSQL existing. Jangan hapus
`.env`/database atau membuat credentials baru. Jika port 8000 terpakai, aplikasi
lain atau instance FastAPI sebelumnya mungkin masih berjalan; hentikan hanya
instance milik Anda melalui terminalnya, jangan kill proses sembarang.

### Important notes

PostgreSQL harus tetap berjalan. Jangan bagikan `.env` atau folder `.local`, dan
jangan hapus file database/config untuk memperbaiki startup. Setup ulang menjaga
credentials, session secret dan History. Role/database asing atau state ambigu
ditolak; tidak ada reset otomatis. Active game hilang saat dev reload/restart,
sedangkan History mengikuti identitas browser dan secret yang sama.
Launcher existing `run-windows-native.cmd` tetap tersedia untuk kompatibilitas;
alur utama di atas adalah aktivasi standar Option A.

## Phase4.3 — pilih jalur yang benar-benar tersedia

**A. Open Online Website:** belum ada URL publik. Paket deployment sudah disiapkan
dan diuji pada stagingHTTPS lokal; publikasi/domain/biaya memerlukan izin terpisah.
Localhost bukan website online untuk dosen. Panduan operator: `deploy/README.md`.

**B. Play Offline on Windows:** workflow build/launcher ada di `windows/README_BUILD.md`,
tetapi belum ada executable Windows yang diuji pada hostWindows. Jangan menganggap
template StartMahjong atau launcherDocker sebagai paket offline siap pakai.
Setelah pemilik menyelesaikan build+acceptanceWindows, langkah dosen ditargetkan:
ExtractAll -> double-clickStartMahjong -> tunggu browserready -> StopMahjong.

**C. Developer / jalur yang sudah diverifikasi:** gunakan macOS/Docker di bawah,
atau prepared environment `fastapi dev main.py`. Semua metode Phase4.2 tetap ada.
Source, audit dan channelpublikasi tetap dipisahkan; tidak ada upload otomatis.

Website asli: main Mahjong, minta saran MLP v3, dan simpan hasil di PostgreSQL.
Tidak membutuhkan Node/npm/pnpm untuk menjalankan website.

Platform aktual: native macOS arm64 dan Docker Desktop macOS/Linux arm64 diuji.
**Windows native maupun Docker Desktop Windows NOT YET VERIFIED**; launcher
Windows disediakan dan direview, tetapi belum dijalankan pada host Windows.

## Mulai di Windows / Mac (jalur utama: Docker Desktop)

**Prasyarat satu kali:** Docker Desktop terpasang dan berjalan, memakai Linux
containers/virtualization yang didukung, internet dan ruang disk untuk dependency.
Pakai ZIP `mahjong-strategy-ai-lecturer-portable.zip` yang dibuat pemilik project,
lalu **Extract All** ke folder lokal yang dapat ditulis. Jangan jalankan dari ZIP.
Clone GitHub biasa tidak menyertakan checkpoint; ZIP ini menyertakannya.

**Windows x64 — CMD**, di folder hasil ekstraksi:

```bat
setup-windows.cmd
run-windows.cmd
```

**macOS — Terminal**, di folder hasil ekstraksi:

```sh
./setup-macos.sh
./run-macos.sh
```

Jika tool ekstraksi menghilangkan executable bit: `sh setup-macos.sh` dan
`sh run-macos.sh`. Setup pertama membangun image, membuat secret acak lokal,
menyiapkan PostgreSQL dan memeriksa health. Setup ulang mempertahankan secret
dan history. Startup berikutnya tidak meng-install dependency lagi.

Buka **http://127.0.0.1:8000/**. Setup sudah menjalankan server; run berikutnya
menampilkan log. Ctrl+C menghentikan layanan foreground. `docker compose stop`
menghentikan demo tanpa menghapus data. Jangan hapus volume atau secret folder
jika ingin mempertahankan akses history. Jangan jalankan `down -v` sebagai reset.

Sesudah persiapan secret oleh setup, perintah langsung yang setara:

```sh
docker compose up --build
```

PostgreSQL tidak membuka port host. Web hanya dipublikasikan pada loopback.
Secret Compose berada di `.local/compose-secrets/`, bukan di image atau ZIP;
volume PostgreSQL mempertahankan history. Active game tetap in-memory dan hilang
saat aplikasi restart. Satu worker, local demo saja.

## Alternatif native (pengguna berpengalaman)

Prasyarat: **64-bit CPython3.12**, compiler C++ (macOS Xcode Command Line Tools;
Windows Visual Studio Build Tools dengan C++/SDK), dan PostgreSQL14 tools/service.
PyMahjongGB1.4.0 tidak menyediakan wheel resmi CPython3.12 pada PyPI; source
aslinya dikompilasi, tidak diganti library lain. PyTorch diunduh saat setup dan
tetap dependency besar. Native Windows belum dianggap verified dari pengujian Mac.

Mac: `./setup-macos.sh --native`, lalu `./run-macos.sh --native`.
Helper membuat cluster **milik paket ini** di `.local/phase3-postgres` jika config
belum ada; memerlukan `initdb`, `pg_ctl`, `psql`, `pg_dump` pada PATH. Tidak memakai
cluster MacBook pengembang. Jika port/socket berbenturan, pakai Compose.
Native Mac mempertahankan role administrator helper legacy; Compose memakai
role aplikasi terpisah tanpa superuser/create-role/create-db.

Windows CMD:

```bat
.venv\Scripts\activate.bat
fastapi dev main.py
```

Provisioning Windows dilakukan oleh setup eksplisit: default role `mahjong_app`
tanpa superuser/create-role/create-db dan database `mahjong_phase3_dev` miliknya.
Password admin tidak disimpan. Config lokal valid yang sudah ada dipakai ulang
tanpa meminta admin. Jalur lama `setup-windows.cmd --native` tetap tersedia,
tetapi petunjuk utama Windows adalah First-Time Setup dan Option A di atas.

Native setup membuat venv, memasang runtime terpin, memverifikasi model, membuat
`.env` privat jika belum ada, menginisialisasi tabel yang hilang secara eksplisit,
memvalidasi schema, serta menguji lifespan DB/model asli. Config yang sudah ada
tidak ditimpa dan secret tidak dirotasi. Jika setup gagal, perbaiki prasyarat;
tidak ada database/model fallback. Tidak ada retraining atau corpus download.

Prepared native environment tetap mendukung perintah dosen:

```bat
rem Windows CMD
.venv\Scripts\activate.bat
fastapi dev main.py
```

```sh
# macOS Terminal
source .venv/bin/activate
fastapi dev main.py
```

Dev reload dapat menghilangkan active games. Launcher native Windows baru memakai
`fastapi dev main.py`; launcher legacy normal memakai factory existing tanpa
reloader. Simpan secret yang sama untuk akses History sesudah restart.

## Jika gagal

| Gejala | Tindakan |
|---|---|
| Docker tidak ditemukan/tidak dapat tersambung | Install/start Docker Desktop, pilih Linux containers; tunggu engine ready |
| Container unhealthy | `docker compose ps`; periksa log lokal `docker compose logs web db`, jangan bagikan secret/config |
| Port8000 terpakai | Hentikan demo sendiri; atau CMD `set MAHJONG_WEB_PORT=8001`, Mac `export MAHJONG_WEB_PORT=8001`, lalu Compose; buka port baru |
| Python tidak ditemukan/versi salah | Native: install CPython3.12 x64, launcher `py -3.12` (Windows) / `python3.12` (Mac) |
| C++ / PyMahjongGB gagal build | Install C++ tools/SDK; pakai Compose jika native toolchain belum kompatibel |
| PyTorch wheel tidak cocok | Pastikan CPython3.12 64-bit dan OS didukung; jangan mengganti versi/model sembarang |
| PostgreSQL/auth/URL gagal | Pastikan service/DB/owner lokal benar; password URL encoded; Compose tunggu db healthy |
| `.env` hilang/invalid | Ulang setup jika belum pernah dibuat; config existing salah harus diperbaiki privat, jangan ditempel ke chat/Git |
| Secret Compose hilang sebagian | Restore set asli dari backup privat; jangan generate password baru untuk volume lama |
| Checkpoint hilang/mismatch | Dapatkan ZIP pemilik yang benar; verifikasi manifest; jangan bypass hash |
| Windows antivirus/path error | Extract ke path lokal pendek, hindari OneDrive/restricted folders; periksa quarantine sesuai kebijakan perangkat |
| Startup tetap gagal | Periksa health/prasyarat dan status platform; tidak ada klaim zero-prerequisite atau fake fallback |

Jika menerima bundle inferensi terpisah dari pemilik, restore terverifikasi:
`python -m scripts.lecturer_assets --bundle PATH_TO_APPROVED_BUNDLE`.
Script menolak checksum salah dan artifact existing yang berbeda. Tidak ada URL
download model otomatis. ZIP lokal ini menyertakan tepat aset inferensi yang
diizinkan pemilik; atribusi corpus ada di `THIRD_PARTY_NOTICES.md`. Tidak ada
publikasi atau lisensi menyeluruh baru yang diberikan oleh packaging ini.

## Alur kode untuk dosen

```text
Browser (app/static, app/templates)
  -> FastAPI / Jinja2 (main.py -> app/main.py; app/web/api.py, pages.py)
     -> Game Session Service (app/services/game_service.py)
        -> Engine + bots (app/engine, app/services/bot_service.py)
        -> MLP v3 advisor (app/web/runtime.py, app/services/ai_prediction_service.py)
        -> PostgreSQL history (app/services/prediction_history_service.py, app/db.py)
```

`training/dataset_loader.py` dipertahankan hanya karena helper hash diimpor saat
runtime; tidak ada dataset latihan atau pipeline training yang ikut dijalankan.
Saran AI tidak memainkan aksi otomatis dan bobotnya bukan peluang menang.
Contact memiliki lima identitas resmi; pembagian tugas/kontribusi belum dikonfirmasi.

## Developer/audit (opsional, terpisah)

Tes membutuhkan environment pengembangan dan Node; materi itu ada pada ZIP audit
terpisah dan checkout engineering, bukan prasyarat website. Lihat `README_AUDIT.md`
di paket audit untuk restore, checksums, test commands dan bukti platform aktual.
Paket lokal ini belum merupakan GitHub Release dan tidak dipublikasikan otomatis.
