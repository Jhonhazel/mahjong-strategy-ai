# Laporan Implementasi Phase 3 — Mahjong Strategy AI

Tanggal: 5 November 2026, Asia/Jakarta. Laporan engineering ini bukan PDF laporan
akhir UAS. Bukti final menggunakan berkas berakhiran `complete`; bukti percobaan
awal/RED tetap disimpan dengan hasil aslinya.

## 1. Final Verdict

**PHASE 3 PASS — READY FOR PHASE 4**, dengan keputusan handoff **GO WITH CAVEATS**.
Backend lokal, model v3, engine asli, PostgreSQL, halaman dasar dan CRD telah
terhubung dan diverifikasi nyata. Suite penuh: **359 passed, 0 failed, 0 errors,
0 skipped** dalam **73.88 detik**. Seluruh **279 kasus lama** tetap ada dan lulus;
terdapat **80 kasus baru**. Suite Phase 3 terpisah: **80 passed** dalam **9.34 detik**.

PASS ini berlaku untuk fondasi lokal satu worker. Roster Contact belum
terverifikasi, papan Mahjong yang dipoles termasuk Phase 4, sedangkan PDF/video
akhir dan pembagian tugas kelompok belum diselesaikan. Tidak ada klaim seluruh
pengumpulan UAS atau deployment produksi sudah selesai.

## 2. Repository and Environment

Repository: `/Users/jhonhazel/mahjong-strategy-ai`; branch `main`; HEAD tetap
`b9821fd53b1ef73e2df85de238e028c0244d511f`. Tidak ada AGENTS.md pada disk.
Instruksi generic Reallysick tidak mengubah proyek Python ini menjadi monorepo
TypeScript. Seluruh implementasi Phase 3 yang sudah ada dipertahankan saat resume.

Host yang diuji: macOS arm64, CPython 3.12.10, PostgreSQL 14.19 Homebrew.
Torch 2.15.0, NumPy 2.5.4, PyMahjongGB 1.4.0 tetap pada versi sebelumnya.
FastAPI 0.162.0, Starlette 1.10.0, SQLModel 0.0.48, SQLAlchemy 2.0.57,
psycopg 3.3.8, Uvicorn 0.54.0, Jinja2 3.1.6, Pydantic 2.14.2.
Lock mencatat 41 paket terpasang. `pip check` lulus.

Rincian aktual: [environment_final.json](../artifacts/phase3/environment_final.json).
Instalasi bersih, Windows/Linux dan produksi tidak diuji ulang. Cluster khusus
proyek memakai socket privat di `.local/phase3-postgres/socket`, port label55437,
`listen_addresses=''`, tanpa listener PostgreSQL TCP atau perubahan layanan global.

## 3. Phase 1–2.2 Preservation

Manifest sebelum implementasi melindungi **1.868 berkas**. Pemeriksaan final
menemukan **0 berubah dan 0 hilang**. Engine/referee, encoder, bot, AI service
lama, training pipeline, tests lama, corpus, checkpoint, metadata dan bukti
eksperimen tidak diubah. Tidak ada retraining checkpoint v3.
Mini-training sintetis dalam regresi lama hanya memakai fixture sementara.

Hanya empat berkas tracked yang sengaja berubah: `README.md`, `requirements.txt`,
`requirements-lock.txt` dan `.gitignore`. Source backend/tests baru ditambahkan
sebagai berkas untracked. Lihat [preservation_verification.json](../artifacts/phase3/preservation_verification.json)
dan [rekonsiliasi kasus](../artifacts/phase3/regression_case_reconciliation.json).
JUnit Phase 2.2 tidak ditimpa. Seluruh279 identitas dari XML resmi
`docs/evidence/phase2_2/full_suite.xml` juga direkonsiliasi langsung dan tetap lulus.

## 4. Implemented Backend Architecture

`app.main:create_app` menyediakan factory dan lifespan. Startup memvalidasi
PostgreSQL/skema, memuat model v3 sekali di CPU, lalu menyediakan singleton game,
history, predictor dan visitor context. Impor modul tidak memuat checkpoint.
Startup gagal tertutup jika aset atau database salah; resource parsial ditutup.
Shutdown menunggu operasi game yang diterima dan menutup engine database.

Router JSON memakai DTO ketat. `OwnedGames` membungkus `GameSessionService`
asli dengan ownership, lease, TTL dan lock per game. `WebPredictionService`
mengambil encoded turn dari service asli, menjalankan AI asli, memeriksa hasil,
lalu menyimpan snapshot dalam lease yang sama. `PredictionHistoryService`
memiliki transaksi pendek per operasi. Tidak ada state Mahjong kedua atau
implementasi scoring/rules baru. Jinja menggunakan router halaman dan aset lokal.

## 5. File Inventory

Inventaris lengkap per berkas dan fungsinya:
[phase3_file_inventory.md](phase3_file_inventory.md).
Snapshot akhir Git: **4 tracked modified**, **114 untracked**
(termasuk `docs/.DS_Store` yang tidak terkait dan tetap dibiarkan).
Jumlah berkas source/config/test/konfigurasi tracked terkait: **45**.
Tidak ada berkas yang di-stage.

Source baru meliputi factory/settings/database, domain snapshot, dua service,
router/security/runtime/DTO/view/contact/documentation, enam template, CSS/JS,
empat CLI dan sepuluh berkas test/support. Bukti SQL, cluster dan bobot tetap
mengikuti kebijakan ignored; tersedia lokal, bukan diam-diam ditambahkan ke Git.

## 6. API Specification

OpenAPI aktual: [backend_contract.json](../artifacts/phase3/backend_contract.json).
Contoh request/response nyata tanpa token/cookie:
[api_examples.json](../artifacts/phase3/api_examples.json).

| Method / path | Input dan output utama | Status normal | Session / CSRF |
|---|---|---|---|
| GET `/health/live` | `{"status":"alive"}` | 200 | Tidak |
| GET `/health/ready` | Model initialized + skema/akses DB nyata | 200 /503 | Tidak |
| GET `/api/session` | Cookie bertanda tangan + JSON `csrf_token, expires_in` | 200 | Bootstrap same-origin |
| POST `/api/games` | `human_seat, prevalent_wind, seed, include_flowers` → GameView | 201 | Cookie + header |
| GET `/api/games/{game_id}` | UUID → public GameView | 200 | Cookie pemilik |
| POST `/api/games/{game_id}/actions` | `action_id, expected_turn_number` → GameView baru | 200 | Cookie + header |
| POST `/api/games/{game_id}/predict` | `expected_turn_number` → saved prediction | 201 baru /200 reuse | Cookie + header |
| GET `/api/predictions` | `limit=20, offset=0` → `items,total,limit,offset` | 200 | Cookie pemilik |
| GET `/api/predictions/{prediction_id}` | Snapshot input/output dan provenance | 200 | Cookie pemilik |
| DELETE `/api/predictions/{prediction_id}` | Hapus record milik visitor | 204 | Cookie + header |
| GET `/`, `/contact`, `/game` | Halaman Home/Contact/Game | 200 | Inisialisasi visitor bila perlu |
| GET `/history`, `/history/{prediction_id}` | List/detail owned HTML | 200 | Visitor; detail asing404 |
| POST `/history/{prediction_id}/delete` | Form `csrf_token` | 303 ke /history | Cookie + form token |
| GET `/docs`, `/redoc`, `/openapi.json` | Dokumentasi/generated schema | 200 | Tidak |
| GET `/static/...` | CSS/JS lokal | 200 | Tidak |

Contoh create: `{"human_seat":1,"seed":42}`. Action:
`{"action_id":6,"expected_turn_number":4}`, hanya jika ID/turn itu masih legal
pada game bersangkutan. Predict: `{"expected_turn_number":4}`.
Seat/wind0–3, seed opsional unsigned64-bit, action0–234, turn0–1.000.000.
Boolean sebagai integer, extra fields, client tensors dan owner ID ditolak.
Pagination limit1–100, offset0–100.000; body maksimal16 KiB.

GameView memuat game/status/seat/wind/active seat/turn, hand sendiri, flowers,
public seats/melds/discards/counts, legal actions, prediction availability dan
hasil akhir yang diizinkan. Prediction memuat ID/game/phase/reused, rekomendasi,
Top-3,34 skor, seat/turn, model/encoder dan score meaning.

Error memakai `{"detail":{"code":"...","message":"..."}}`; validation menambah
`fields` berisi lokasi/jenis tanpa menggemakan input. Status:400 illegal action,
401 session,403 CSRF/origin,404 unknown/expired/cross-owner,409 stale/phase,
413 oversized,422 invalid DTO/UUID,429 capacity,503 dependency/invariant/save
failure. Unexpected error500 disanitasi. Operasi gagal tidak dibungkus HTTP200.

## 7. PostgreSQL Schema

Tabel nyata `prediction_results` memiliki 12 kolom:

| Kolom | PostgreSQL / aturan |
|---|---|
| id | UUID primary key; dibuat server aplikasi |
| owner_key | VARCHAR(64), NOT NULL; HMAC visitor, bukan input klien |
| game_id | UUID NOT NULL |
| turn_number | INTEGER NOT NULL, CHECK >=0 |
| turn_phase | VARCHAR(32), CHECK SELF_TURN /POST_MELD_DISCARD |
| input_snapshot / output_snapshot | JSONB NOT NULL |
| model_version / encoder_version | VARCHAR(128) /VARCHAR(64), NOT NULL |
| checkpoint_sha256 / state_digest | VARCHAR(64), NOT NULL, CHECK panjang64 |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now(); koneksi UTC |

UNIQUE `uq_prediction_snapshot(owner_key,game_id,turn_number,model_version,state_digest)`
bersifat immediate/nondeferrable. Index
`ix_prediction_owner_created(owner_key,created_at DESC,id DESC)` mendukung paging.
CHECK: `ck_prediction_turn`, `ck_prediction_phase`, `ck_prediction_digests`.
Readiness memeriksa exact columns/types/nullability, PK, JSONB, timezone, default
waktu sekarang, ekspresi CHECK, constraint tervalidasi, uniqueness/index valid,
privilege SELECT/INSERT/DELETE/UPDATE dan koneksi writable.

Inspeksi katalog aktual dan restore:
[database_verification_complete.json](../artifacts/phase3/database_verification_complete.json).
Ekspor nyata `artifacts/phase3/prediction_history_complete.sql`: **88.936 byte**,
SHA-256 `9bf2d934f373e983a7864821e8adb747f004e959478c607a3a3dc3e781505e3d`.
Restore ke `mahjong_phase3_restore_0ea11a56365f` menghasilkan **11/11 record identik**,
termasuk JSONB, timestamp dan identitas. Tidak ada database lama ditimpa/dihapus.

## 8. Prediction Create/Read/Delete

POST predict mengambil input yang terlihat oleh manusia dari server, menyimpan
input/output/model/checksum dalam transaksi, dan mengembalikan201 hanya setelah
commit. Unique identity dan INSERT ON CONFLICT DO NOTHING menjaga idempotensi.
Reuse membaca record dengan FOR UPDATE sampai commit dan mengembalikan output
asli tanpa menimpanya. DELETE bersamaan menunggu titik commit; penghapusan sesudah
commit tetap merupakan operasi sah berikutnya, bukan jaminan record abadi.

List/detail/delete selalu memakai predicate owner. Delete204 lalu read404,
repeat delete404. Penghapusan history tidak mengubah game atau model.
Kesalahan insert/commit di-rollback dan menghasilkan503; tidak ada false saved
response. Ini diuji pada PostgreSQL nyata, termasuk Event-barrier save/delete,
empat insert bersamaan dan rollback statement yang benar-benar gagal.
HTTP TCP final membuktikan201→200 reuse→200 read→204 delete→404 read dan
cross-owner game/history404: [network_complete.json](../artifacts/phase3/network_complete.json).

## 9. MLP v3 Integration

Checkpoint: `artifacts/models/mahjong_discard_mlp_v3.pt`.
SHA-256:
`ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`.
Metadata SHA:
`84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e`.
Encoder: `ijcai2026_mcr_v1_strict`. Model version aktual:
`discard_mlp_flexible_v1:ad05a5b2ce37`. Nama format flexible_v1 berasal dari
service lama; identitas checkpoint yang dimuat adalah v3 dengan hash di atas.

Arsitektur1368→256→128→34,387.746 parameter, CPU/eval, load sekali saat lifespan.
Input `int8[38,4,9]` di-flatten C-order menjadi1368; full mask235 dan discard
mask34 tetap identik dengan kontrak lama. Class0–33 dipetakan ke action class+2.
Top-3 hanya legal, tidak berulang, terurut; illegal scores0 dan skor ternormalisasi.
Checkpoint/metadata/contract salah atau hilang memblokir startup tanpa fallback.

Runtime hanya membutuhkan weights, metadata dan small contract. Uvicorn tetap
berhasil startup/create/predict ketika `np.load` dipaksa gagal, membuktikan tidak
bergantung pada shard training. Array/input hash, game view, turn dan hash bobot
diperiksa langsung sebelum/sesudah prediksi. Lihat
[model_integration_verification.json](../artifacts/phase3/model_integration_verification.json).
Metrik Home memakai evaluasi retrospektif yang dibekukan: Top-1 64.35%,
Top-3 86.55%, macro F1 sekitar0.621944; bukan blind test baru atau peluang menang.

## 10. Game Integration

Create menjalankan engine dan bot asli sampai keputusan manusia. GET hanya
membaca public view. Action harus ada pada legal_actions dan menyertakan turn
saat ini. Bot berjalan sinkron setelah create/action, tanpa perubahan rules.
Predict tidak membuang tile, memajukan turn atau menjalankan rekomendasi.

Ownership diperiksa sebelum service game diakses. Turn stale atau dua action
bersamaan tidak mengeksekusi aksi dua kali. Prediksi dibatasi SELF_TURN atau
POST_MELD_DISCARD ketika discard tersedia; claim-only menolak409.
Phase setelah Chi/Peng sekarang ditentukan juga oleh bertambahnya meld manusia:
pada seed44/seat1, Chi73 turn33 yang kalah prioritas berlanjut ke turn48
SELF_TURN, bukan post-meld palsu. Tidak ada pembacaan private engine pada jalur
produksi untuk menduplikasi state.

Hasil akhir berasal dari referee asli. HTTP hanya mengirim ending, winner/
discarder, win tile, fans dan score deltas; revealed opponent hands tetap
tidak diserialisasi.

## 11. Session and Security Controls

Cookie `mahjong_visitor` ditandatangani HMAC-SHA256, HttpOnly, SameSite=Lax,
Secure pada mode produksi; TTL default86.400 detik. Cookie berisi nonce acak,
bukan kredensial database. Ownership diturunkan server; cookie rusak/expired
tidak dapat mutasi. JSON mutation memerlukan header X-CSRF-Token; form delete
memerlukan token form; Origin yang ada harus sama. Token/cookie tidak disimpan
di bukti publik. Cookie/header juga dideklarasikan pada OpenAPI.

Default128 game aktif, idle TTL3600 detik, finished retention30 detik. Lease
melindungi operasi in-flight dari expiry sampai commit; lock per game menyatukan
action/predict. Lock registry tidak menahan pekerjaan model/DB sehingga game
lain tetap maju. Engine pool5+overflow5 dan timeout DB5 detik.

Allowlist response tidak mengekspos concealed opponent hand, hidden AnGang
identity, wall contents atau referee object. Input body termasuk chunked dibatasi.
Jinja autoescape aktif, JS memakai textContent, cache private no-store/nosniff.
CSP hanya memberi pengecualian CDN/hash bootstrap pada docs; game tetap self-only.
Bukti: [session_isolation_verification.json](../artifacts/phase3/session_isolation_verification.json).

## 12. Jinja2 Pages

Home menampilkan tujuan hiburan, dataset strict1.946.122 sampel, metode,
arsitektur/model dan metrik retrospektif aktual. Contact memakai struktur data
konfigurabel; tanpa roster terverifikasi halaman menyatakan kontennya belum
lengkap. Tidak ada nama/NIM/email/role anggota yang dikarang.

Game menyediakan start, pilihan legal action, expected turn, predict/save,
refresh, own hand/public state dan hasil round. History menggunakan PostgreSQL
nyata untuk list/detail serta form delete dengan redirect303. Navigasi dan
aset CSS/JS berfungsi. Browser nyata menguji create/predict/read/delete,
Swagger/ReDoc dan refresh lintas tab; rekomendasi turn4 dibersihkan ketika view
berubah ke turn17. Papan tile visual, animasi, polish responsif dan UX lanjut
menjadi Phase4; fondasi ini tidak disebut UI final.

## 13. End-to-End Demonstration

[end_to_end_complete.json](../artifacts/phase3/end_to_end_complete.json) berasal
dari HTTP ASGI nyata melalui FastAPI TestClient, engine/model asli dan PostgreSQL.
Tambahan [network_complete.json](../artifacts/phase3/network_complete.json)
menguji server Uvicorn melalui TCP dan browser.

| Seed / game ID | Prediksi yang diverifikasi | Aksi manusia / hasil |
|---|---|---|
| 42 / `d9882aa4-dd74-4b90-9a69-c9f952760e31` | turn4 SELF_TURN→J1; turn20 POST_MELD_DISCARD→T1 | 11; ron, winner2, discarder0,9 fan; delta[-17,-8,33,-8] |
| 43 / `e5351e0f-81b6-4bbe-a404-b6dc706dbd50` | turn4/20 SELF_TURN→F4; turn52 POST_MELD_DISCARD→F4 | 26; draw/HUANGZHUANG; delta[0,0,0,0] |

Top-3 turn4 seed42: J1≈0.820400, J2≈0.069208, T1≈0.027153. Rincian seluruh
Top-3, UUID record, timestamp UTC, input digest dan hasil final ada dalam JSON.
Alur create→predict/save→read→human actions→finish→delete benar-benar dijalankan.
Prediksi ulang menghasilkan ID sama; first record dihapus dan read404; record
lain tetap terbaca setelah app restart menggunakan cookie/secret yang sama.
Game lama setelah restart404 sesuai kebijakan in-memory.

Kebijakan aksi manusia pada helper bersifat deterministik dan independen dari
saran model; rekomendasi tidak auto-execute. Dua round bukan estimasi win rate.
Baris demo dimiliki identitas uji, bukan akun publik; secret/cookie uji tidak
dipublikasikan.

## 14. Automated Tests

| Pemeriksaan | Hasil yang diamati |
|---|---|
| Baseline awal sebelum implementasi | 1 failed,257 passed,21 errors; disk guard1 GiB |
| Baseline setelah pemulihan scratch sendiri | 279 passed66.77s |
| Review awal RED /GREEN | 15 failed+3 passed /25 passed3.91s |
| Review resume RED /GREEN | 10 failed+26 passed /36 passed4.00s |
| Full sebelum temuan review tambahan | 349 passed77.08s |
| **Final Phase3 focused** | **80 passed9.34s;0 failures/errors/skips** |
| **Final Phase1–3 full** | **359 passed73.88s;0 failures/errors/skips** |
| Rekonsiliasi baseline | 279/279 identitas kasus lama masih lulus |
| Compile/import, Node syntax, pip check, diff checks | Semua exit0 |

JUnit final: [full_regression_complete.xml](evidence/phase3/full_regression_complete.xml)
dan [focused_complete.xml](evidence/phase3/focused_complete.xml).
Log tersedia dengan nama sama berakhiran.txt. Cakupan baru mencakup bootstrap,
schema, CRD, concurrency, cookie/CSRF, halaman, docs, real v3 dan full rounds.
Seluruh integrasi menggunakan PostgreSQL14.19, tanpa substitusi SQLite.

Perintah yang dijalankan dari root:

```sh
MAHJONG_TEST_DATABASE_URL='postgresql+psycopg://mahjong_phase3@/mahjong_phase3_test?host=%2FUsers%2Fjhonhazel%2Fmahjong-strategy-ai%2F.local%2Fphase3-postgres%2Fsocket&port=55437' .venv/bin/python -m pytest tests/test_phase3_*.py -q --junitxml=docs/evidence/phase3/focused_complete.xml
MAHJONG_TEST_DATABASE_URL='postgresql+psycopg://mahjong_phase3@/mahjong_phase3_test?host=%2FUsers%2Fjhonhazel%2Fmahjong-strategy-ai%2F.local%2Fphase3-postgres%2Fsocket&port=55437' .venv/bin/python -m pytest -q --basetemp=/private/tmp/mahjong-phase3-complete.URNxjP/fixtures --junitxml=docs/evidence/phase3/full_regression_complete.xml
.venv/bin/python -m compileall -q app scripts
.venv/bin/python -m pip check
node --check app/static/phase3.js
git diff --check
```

Log stdout/stderr pytest dialihkan ke pasangan.txt. Untuk reproduksi pilih
filename baru, jangan menimpa bukti final. Satu Starlette TestClient/httpx
deprecation warning tetap dilaporkan, tidak disembunyikan. Linter/typechecker
Python tidak dikonfigurasi. OS lain, clean install, produksi dan multi-worker
belum diuji; ini bukan klaim portable deployment PASS.

## 15. Problems, Fixes, and Remaining Risks

Dua review independen fresh-context menghasilkan0 Critical. Empat temuan awal
dan tiga Important berikutnya diperbaiki; dua Minor (kontrak OpenAPI dan saran
usang) dinaikkan berdasarkan dampak pengguna dan ikut diselesaikan.
Detail temuan, reproduksi, test dan closure:
[code_review.md](evidence/phase3/code_review.md). Tidak ada klaim reviewer memberi
persetujuan post-fix yang tidak dilakukan; closure final didasarkan pada regresi
dan inspeksi executor. Tidak ada Critical/Important yang belum diselesaikan.

Perintah sebelum interruption tidak dijalankan karena auto-review tidak dapat
selesai akibat usage limit. Itu bukan pytest FAIL atau keputusan tindakan tidak
aman. RED aktual dijalankan setelah resume dan lognya dipisahkan.

Disk guard sempat gagal pada baseline. Hanya fixture pytest milik sesi ini yang
selesai/tidak aktif dibersihkan setelah pemeriksaan UID, lock, timestamp dan nama
fixture; tidak ada corpus/weights/bukti lama dihapus. Ekspor SQL dibatasi64 MiB
dan hanya receipt cluster yang dipercaya; arbitrari SQL/cross-machine restore
bukan fitur terbuka. Fixture DB/role pengujian tetap terisolasi pada cluster proyek.

Batasan tersisa: satu worker, active game hilang saat restart, history anonymous
bergantung pada cookie dan signing secret; cookie hilang/expired atau secret
dirotasi membuat history lama tidak dapat diakses visitor baru. Roster belum
terverifikasi, assets docs membutuhkan CDN, warning TestClient masih ada, serta
UI final/PDF/video/produksi berada di luar hasil ini.

## 16. Reproduction Guide

Gunakan environment yang sudah ada. Untuk instalasi pada host baru, baca bagian
Setup README dan restore [bundle v3 terverifikasi](ml_artifact_transfer.md);
`.venv/bin/python -m pip install -r requirements-lock.txt` memakai lock aktual.
Instalasi bersih belum diulang. Dari root repository:

```sh
.venv/bin/python -m scripts.phase3_db start
export MAHJONG_DATABASE_URL="$(.venv/bin/python -m scripts.phase3_db url --database dev)"
export MAHJONG_SESSION_SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(40))')"
export MAHJONG_ENVIRONMENT=local
export MAHJONG_WORKERS=1
.venv/bin/python -m scripts.init_db
.venv/bin/python -m scripts.run_backend
```

Buka `http://127.0.0.1:8000/game`. Pertahankan secret yang sama secara privat
untuk restart; jangan membuat secret baru bila ingin menjaga ownership history.
`.env.example` berisi placeholder, bukan konfigurasi siap pakai atau secret nyata.
Frontend memperoleh token lewat /api/session dan memakai credentials same-origin.

Pada shell dengan konfigurasi sama:

```sh
export MAHJONG_TEST_DATABASE_URL="$(.venv/bin/python -m scripts.phase3_db url --database test)"
.venv/bin/python -m pytest tests/test_phase3_*.py -q
.venv/bin/python -m scripts.demo_backend --output artifacts/phase3/reproduction_rounds.json
.venv/bin/python -m scripts.phase3_db export --database dev --output artifacts/phase3/reproduction_history.sql
shasum -a 256 artifacts/phase3/reproduction_history.sql
.venv/bin/python -m scripts.phase3_db restore --input artifacts/phase3/reproduction_history.sql
```

Gunakan output baru. Helper ekspor menangkap bytes secara privat lalu menulis
eksklusif, restore memeriksa checksum receipt, batas ukuran dan command, lalu
memakai database baru. Database asli tidak dipilih sebagai target. SQL final
tersedia lokal dan harus disertakan terpisah pada pengumpulan, karena di-ignore.
Stop server dengan Ctrl+C dan cluster sendiri dengan
`.venv/bin/python -m scripts.phase3_db stop`. Data cluster tetap tersimpan.
Server verifikasi sementara dihentikan setelah pekerjaan selesai; lihat bukti
shutdown dan verification_summary.

## 17. Git Safety

Branch/HEAD tetap seperti bagian2. **Tidak ada add/stage, commit, push, reset,
clean, stash, rebase, branch switch, merge atau deployment pada Phase3 ini.**
Index kosong; working tree sengaja belum bersih.
Status akhir **4 modified /114 untracked** dicatat pada
`artifacts/phase3/git_verification.json`. `docs/.DS_Store` tidak terkait dan tidak
disentuh. Checkpoint, SQL exports dan .local tetap ignored, tidak di-force-add.

## 18. UAS Compliance Matrix

PDF resmi kini tersedia di `docs/reference/SOAL UAS PEMROGRAMAN WEB FRAMEWORK.pdf`,
dibaca melalui render dua halaman (halaman kedua kosong). Hash/status pembacaan:
[uas_reference_verification.json](../artifacts/phase3/uas_reference_verification.json).
PDF dipakai sebagai persyaratan sumber, bukan sebagai izin operasi tambahan.

| Persyaratan / sumber | Status | Bukti / sisa |
|---|---|---|
| Satu proyek bidang hiburan terintegrasi (PDF) | COMPLETED | FastAPI↔engine↔v3↔PostgreSQL nyata |
| Preprocessing, train/test/evaluasi, simpan model (PDF) | COMPLETED | Phases1–2.2 dipertahankan; v3/hash/metrics dipakai aktual |
| FastAPI/Jinja2/CSS/JS + Home berisi tujuan/dataset/model (PDF) | COMPLETED | Home aktual, halaman dan browser tests |
| Contact berisi anggota/pembagian kelompok (PDF) | PARTIALLY COMPLETED | Struktur/halaman ada; roster/roles menunggu verifikasi |
| Minimal satu tabel PostgreSQL/MySQL untuk hasil AI (PDF) | COMPLETED | prediction_results JSONB nyata |
| Create menyimpan input dan hasil AI (PDF) | COMPLETED | Observed state game pengguna + output v3, transaksi HTTP/PG |
| Read hasil tersimpan (PDF) | COMPLETED | Owned list/paging/detail JSON dan HTML |
| Delete melalui website (PDF) | COMPLETED | CSRF form303 dan API204; read sesudahnya404 |
| File database.sql (PDF) | COMPLETED | Ekspor88.936 byte, restore11/11 identik; terpisah dari Git |
| Source proyek utuh untuk pengumpulan (PDF) | FINAL SUBMISSION | Source Phase1–3 tersedia; bundling pengumpulan belum dilakukan |
| PDF masalah/dataset/alasan algoritma/capture struktur+DB (PDF) | FINAL SUBMISSION | Laporan Markdown engineering tersedia; PDF akhir belum dibuat |
| Link video demonstrasi (PDF) | FINAL SUBMISSION | Video akhir belum dibuat |
| Pembagian tugas kelompok (PDF) | FINAL SUBMISSION | Roster/roles belum disahkan; tidak dikarang |
| Polished Mahjong board dan UX lanjut (roadmap pengguna) | PHASE 4 | Fondasi JSON/HTML sudah stabil |

## 19. Phase 4 Handoff

Frontend melanjutkan /game dan routes pada bagian6; model atau engine tidak
perlu diganti. Gunakan schema OpenAPI dan DTO `app/web/schemas.py`, beserta contoh
HTTP aktual. Bootstrap /api/session, simpan cookie browser secara otomatis,
ambil csrf_token dan kirim X-CSRF-Token pada mutasi. Jangan mengirim owner atau
tensor buatan klien. Form delete memakai token yang sama di hidden field.

Render legal_actions server (ID/type/tile/meld_tiles/label). Kirim expected turn
persis dari view terakhir. Action0 Pass,1 Hu,2–35 Play; representasi Chi/Peng/Gang
juga berasal dari server, jangan hitung rules di frontend. Discard class=action−2.
Game statuses: WAITING_HUMAN_DISCARD, WAITING_HUMAN_CLAIM, FINISHED.

Predict/save adalah satu operasi:201 baru,200 reuse; tampilkan saved ID, Top-3
legal, score meaning dan turn/phase. Jangan otomatis menjalankan rekomendasi.
Ganti/hapus display rekomendasi bila game/turn berubah. Pada409 fetch state baru;
404 berarti resource tidak tersedia;401/403 membutuhkan sesi/token valid;503
harus ditampilkan sebagai belum tersimpan dan boleh retry turn yang sama.

History list/detail/delete tetap terpisah dari umur game. Gunakan paging,
created_at UTC dan provenance model. Jangan expose opponent hand/AnGang tersembunyi/
wall contents atau mengandalkan data private dari engine. API result akhir tetap
allowlisted. Pertahankan satu worker dan secret stabil; redis/account/recovery/
multi-worker adalah desain terpisah, bukan kemampuan yang sudah dibuktikan.
Lengkapi roster hanya setelah approval data, lalu polish papan/aksesibilitas/
responsif dan siapkan artefak final UAS.

## 20. Final Phase 4 Readiness Decision

**GO WITH CAVEATS.** Fondasi siap untuk pengembangan Phase4:359 regresi lulus,
279 kasus lama tetap utuh,80 tes baru, real v3/HTTP/PG, dua round selesai, riwayat
setelah restart, SQL restore11/11 identik dan1.868 berkas lama tidak berubah.
Semua temuan code review ditutup dengan bukti terarah/full suite atau browser
RED→GREEN. Ringkasan mesin: [verification_summary.json](../artifacts/phase3/verification_summary.json).

Caveat adalah roster yang belum diverifikasi, anonymous session/single worker,
platform yang belum diuji, dan pekerjaan UI/submission yang memang tersisa.
Tidak ada klaim deployment produksi, final PDF/video, atau grup terverifikasi.


## Finalisasi P3-01 — 5 November 2026

Bagian1–20 di atas merekam milestone historis359 kasus sebelum P3-01. Hasil itu,
XML lama dan snapshot audit tidak ditimpa. Finalisasi ini mengizinkan tepat satu
commit lokal Phase3 pada main setelah seluruh gate verifikasi/staging terpenuhi;
larangan commit pada milestone sebelumnya tidak berlaku untuk permintaan baru ini.
SHA commit aktual dibaca dari Git dan dilaporkan setelah commit, bukan ditebak
atau dimasukkan ke sertifikat pre-commit yang akan menyebabkan referensi diri.

### Temuan dan perbaikan

P3-01 LOW/MINOR terkonfirmasi pada source saat ini: wrapper ASGI security headers
berada setelah early return. Respons400 invalid/negative Content-Length dan413
(declared/streamed) memakai send asli. Wrapper yang sama kini didefinisikan
setelah passthrough non-HTTP dan sebelum parsing, lalu dipakai pada seluruh jalur
HTTP tersebut. Hanya app/web/security.py berubah pada production; tidak ada
perubahan CSP policy, cookie/CSRF, database schema, gameplay, encoder atau ML.

| Jalur | Status tetap | Header sebelum | Header sesudah |
|---|---|---|---|
| Normal | 200 | no-store/nosniff/CSP | Sama, masing-masing sekali |
| Invalid/negative Content-Length | 400 | Ketiganya hilang | Ketiganya hadir, sekali |
| Declared oversized | 413 | Ketiganya hilang | Ketiganya hadir, sekali; Connection close tetap |
| Streamed oversized/underdeclared | 413 | Ketiganya hilang | Ketiganya hadir, sekali; berhenti membaca saat batas terlampaui |
| Swagger/ReDoc | 200 | CSP khusus | CSP khusus tetap, tidak diganti default |

Body/status/extra header, exact-size acceptance, disconnect dan callback non-HTTP
juga diuji. Tidak ada downstream execution untuk request yang ditolak.
Patch persis terhadap source preflight yang diverifikasi SHA tersedia pada
`docs/evidence/phase3/security_fix_source.diff`.

### TDD dan regresi baru

RED: `.venv/bin/python -m pytest tests/test_phase3_security.py -q -k p3_01` →
**5 failed,6 passed,10 deselected,0.33s**, tepat karena header hilang.
GREEN perintah sama dengan `--junitxml=docs/evidence/phase3/security_fix_green.xml`
→ **11 passed,10 deselected,0.19s**. Tidak ada error import/prasyarat pada RED.
Identitas baru yang benar-benar dikoleksi:

- `tests.test_phase3_security::test_p3_01_declared_oversize_has_security_headers_and_connection_close`
- `tests.test_phase3_security::test_p3_01_disconnect_does_not_execute_downstream_or_respond`
- `tests.test_phase3_security::test_p3_01_exact_body_limit_preserves_the_full_request`
- `tests.test_phase3_security::test_p3_01_invalid_content_length_has_security_headers_without_route[-1]`
- `tests.test_phase3_security::test_p3_01_invalid_content_length_has_security_headers_without_route[malformed]`
- `tests.test_phase3_security::test_p3_01_non_http_scope_keeps_original_callbacks`
- `tests.test_phase3_security::test_p3_01_normal_and_documentation_responses_preserve_body_and_csp[normal]`
- `tests.test_phase3_security::test_p3_01_normal_and_documentation_responses_preserve_body_and_csp[redoc]`
- `tests.test_phase3_security::test_p3_01_normal_and_documentation_responses_preserve_body_and_csp[swagger]`
- `tests.test_phase3_security::test_p3_01_streamed_oversize_has_security_headers_and_stops_reading[1]`
- `tests.test_phase3_security::test_p3_01_streamed_oversize_has_security_headers_and_stops_reading[None]`

Tes security/docs/HTTP: **33 passed2.46s**. Phase3 focused: **91 passed6.80s**.
Full Phase1–3: **370 passed64.30s,0 failed,0 errors,0 skipped**.
XML individual diperiksa untuk uniqueness dan membership: seluruh359 identitas
lama (279 Phase1–2.2 +80 Phase3) tetap ada/lulus, ditambah11 identitas P3-01.

Perintah full dengan konfigurasi test PostgreSQL yang sama seperti bagian14:
`.venv/bin/python -m pytest -q --basetemp=/private/tmp/mahjong-p3-security-final.uz72sb/fixtures --junitxml=docs/evidence/phase3/full_regression_security_fix.xml`.
Focused: `.venv/bin/python -m pytest tests/test_phase3_*.py -q --junitxml=docs/evidence/phase3/security_fix_focused.xml`.
Stdout/stderr disimpan pada pasangan.txt baru. Warning httpx TestClient yang sama
masih ditampilkan. Compile/import/pip check/Node syntax/diff checks lulus.

### Infrastruktur, preservasi dan kesiapan commit

PostgreSQL14.19 nyata menggunakan cluster/test DB khusus yang sudah ada. Seluruh
11 row development tetap identik menurut canonical JSON hash sebelum/sesudah.
Dua round baru dalam full suite tetap ron/draw,11/26 aksi; hasil, prediksi, input
hash dan bobot identik dengan baseline ketika UUID/timestamp uji dikecualikan.
Checkpoint v3 tetap
`ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`;
metadata/contract/runtime CPU cocok;1.868 aset lama tetap identik. Bundle transfer
lama masih checksum-valid. Tidak ada retraining atau dataset regeneration.

Ringkasan finalisasi: `artifacts/phase3/security_fix_verification.json`;
rekonsiliasi: `artifacts/phase3/security_fix_test_reconciliation.json`;
full JUnit: `docs/evidence/phase3/full_regression_security_fix.xml`.
Commit yang diotorisasi: `feat(web): complete Phase 3 Mahjong backend integration`,
parent yang diharapkan b9821fd53b1ef73e2df85de238e028c0244d511f, tanpa amend/push/
deployment. Seluruh source Phase3 yang sudah ada ikut milestone ini; perubahan
khusus P3-01 hanya satu file production, satu file test, empat append dokumentasi
dan bukti baru. ZIP backup, seluruh .DS_Store, secrets, cluster, SQL dan weights
ignored dikecualikan dari staging. Actual staged scope diperiksa sebelum commit.

Handoff tetap GO WITH CAVEATS: roster belum disahkan, game in-memory/satu worker,
clean install/platform lain/produksi belum diverifikasi. Board final dan PDF/video
UAS masih pekerjaan berikutnya. Top1 retrospektif64.35% bukan peluang menang.
Tidak ada klaim reviewer independen baru memberi reapproval atas patch ini.
