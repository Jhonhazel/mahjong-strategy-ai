# Phase 4.1 — laporan implementasi dan verifikasi

Tanggal: 6 November 2026. Scope: melanjutkan working tree Phase 4, tanpa rebuild,
retraining, migrasi database, atau operasi Git yang mengubah state.

## 1. Final verdict

**GO WITH CAVEATS.** Tiga fitur selesai dan terverifikasi pada host yang tersedia:
entry dosen, presentasi perubahan publik, dan lima identitas Contact. Pengujian
akhir: **405 Python passed, 0 failed/error/skipped**, 65.67 detik; **91 Node
passed, 0 failed/cancelled/skipped**, 182.381542 ms. Ini bukan pernyataan bahwa
seluruh paket pengumpulan UAS telah selesai.

## 2. Exact files changed

Perubahan relatif terhadap preflight Phase 4.1, bukan seluruh diff Phase 4:

| Kelompok | File |
|---|---|
| Lecturer entry | `main.py` (baru), `requirements.txt`, `requirements-lock.txt` |
| Animasi | `app/static/phase4/playback.mjs` (baru), `app/static/phase4/controller.mjs`, `app/static/phase4/view.mjs`, `app/static/phase3.js`, `app/static/phase3.css`, `app/templates/game.html` |
| Contact | `config/contact_members.public.json` (baru), `app/settings.py`, `app/templates/contact.html`, `.env.example` (hanya template) |
| Tes | `tests/test_phase4_1.py`, `tests/frontend/playback.test.mjs` (keduanya baru), `tests/test_phase3_pages.py`, `tests/test_phase4_pages.py` |
| Dokumentasi | `README.md`, laporan ini, `docs/phase4_1_test_matrix.md`; append pada `docs/phase4_implementation_report.md` |
| Bukti | Semua file baru dalam `docs/evidence/phase4_1/` dan `artifacts/phase4_1/`; daftar tepat ada di `artifacts/phase4_1/file_inventory.json` |

File Phase 4 lain yang sudah dimodifikasi/untracked tetap dipertahankan. Factory,
API, engine, encoder, service prediksi, schema, dan script database tidak diedit.
Tidak menambahkan bootstrap helper karena helper persiapan eksplisit sudah ada.

## 3. Lecturer one-command proof

Perintah yang benar-benar dieksekusi dari root, sesudah aktivasi venv dan env
test disiapkan:

```sh
fastapi dev main.py
```

Python **3.12.10**, FastAPI **0.162.0**, FastAPI CLI **0.0.32**, WatchFiles
**1.3.0**. Import `main:app` berhasil; application startup complete pada
`127.0.0.1:8000`. GET `/health/ready`, `/`, `/game`, `/history`, `/contact`, dan
`/openapi.json` masing-masing **200**. Model dan database melaporkan ready.
Preview memakai database project **test**, secret acak hanya dalam env, tanpa
menulis `.env` atau data dev. CLI dan reloader milik task dihentikan dengan
shutdown normal setelah browser selesai. PID 2696 sudah tidak ada ketika
penghentian yang diizinkan pengguna dicoba; tidak ada proses asing dihentikan.

Runner lama `.venv/bin/python -m scripts.run_backend` juga benar-benar dijalankan
pada port 8875: readiness **200**, lalu subprocess milik task dihentikan.
Root entry memanggil factory yang sama. Import tidak membuka DB/memuat model;
resource tetap berada di lifespan, tidak ada schema bootstrap implisit.

Persiapan satu kali dijelaskan di README: CPython/venv, install lock, PostgreSQL
tools dan cluster project, schema initialization eksplisit, aset v3/metadata/
contract melalui checksum, serta DB URL dan signing secret privat yang stabil.
Aktifkan venv dan konfigurasi env atau `.env` privat sebelum menjalankan perintah.
FastAPI CLI memakai port defaultnya sendiri; `MAHJONG_PORT` berlaku pada runner
lama. Port 8000 harus tersedia. Dev reload menghapus game in-memory, bukan history.

12 dependency CLI ditambahkan dengan versi terpin; **0 versi dependency lama
berubah**. Clean install dan platform lain belum diuji. Bukti:
[CLI](../artifacts/phase4_1/cli_smoke.json),
[runner lama](../artifacts/phase4_1/legacy_runner_smoke.json),
[dependency delta](../artifacts/phase4_1/dependency_delta.json).

## 4. Gameplay UX

Server tetap menyelesaikan langkah/bot sinkron seperti sebelumnya. Browser
menerima final authoritative snapshot terlebih dahulu, lalu menyorot perbedaan
river, meld atau bunga per kursi. Tile baru memakai animasi opacity/translate;
perubahan wall/status/result tanpa perubahan kursi mendapat pesan umum. Pesan
eksplisit menjelaskan bahwa sorotan bukan urutan aksi asli. Tidak ada event
bot, tarikan tersembunyi, atau GameView antara yang direkayasa.

Normal **600 ms per grup**, Cepat **180 ms**, maksimal empat grup: batas tunggu
2.4 detik normal/720 ms cepat. Pergantian speed berlaku pada timer berikutnya.
Skip langsung membatalkan timer dan menyelesaikan tampilan. Reduced-motion dan
tab tersembunyi melewati playback; perubahan media, visibility/pagehide,
create/refresh, expiry, dan respons baru membatalkan presentasi lama.

Controller tetap mengunci aksi/prediksi/selection saat presentasi. Token operasi,
generation, dan identitas view menolak callback usang. New game/refresh dapat
membatalkan playback dengan aman. Guard P4-A01/P4-A02 tetap ada. Proyeksi existing
tetap menyembunyikan AnGang lawan. Tidak ada delay Python atau perubahan legal
actions, CSRF, cookie, model, transaction atau endpoint.

## 5. Group Contact

Default publik berisi tepat lima identitas yang disetujui pengguna:

| Nama | NIM | Email |
|---|---|---|
| Mishael Julindra Putra | 32240013 | s32240013@student.ubm.ac.id |
| Efraim Emanuelle Josrin | 32240015 | s32240015@student.ubm.ac.id |
| Jhonhazel Lionel Tjokahn | 32240016 | s32240016@student.ubm.ac.id |
| Roberto Ariyadhamma | 32240027 | s32240027@student.ubm.ac.id |
| Michael Kurniawan | 32240033 | s32240033@student.ubm.ac.id |

**Peran, kontribusi, dan pembagian tugas belum ditetapkan/dikonfirmasi**. Tidak
ada field role yang diisi atau ditampilkan. Missing/unverified roster tetap
menampilkan fallback incomplete. Escaping template dan tes keamanan lama utuh.

## 6. TDD evidence

Dengan `MAHJONG_TEST_DATABASE_URL` menunjuk project `_test` yang tersedia:

```sh
node --test tests/frontend/playback.test.mjs
.venv/bin/python -m pytest tests/test_phase4_1.py -q
node --test tests/frontend/playback.test.mjs tests/frontend/view.test.mjs
```

RED Node: **11 gagal**, fitur playback belum ada. RED Python: **3 gagal/3 lulus**
(entry hilang, roster default lama, wrapper playback belum lulus). GREEN fitur
Python: **6 lulus**, 1.41 detik. GREEN playback+view: **18 lulus**, 84.0405 ms.
Log RED asli tidak ditimpa: `playback_red.txt`, `features_red.txt`.

Selama pengembangan ada kesalahan fixture/import patch pada tes entry baru dan
asumsi route `.path` yang tidak sesuai `_IncludedRouter` FastAPI terpasang.
Tes dikoreksi agar patch tidak bocor dan menghitung router asli secara rekursif.
Run penuh pertama **404 lulus/1 gagal** karena asumsi tes route baru itu; bukan
kegagalan produksi. Bukti gagal dipertahankan; suite final berhasil setelah
perbaikan tes. Tidak mengganti dependency/backend untuk meloloskan tes.

## 7. Full Node and Python tests

| Run | Passed | Failed/error/skipped | Durasi |
|---|---:|---|---|
| Baseline Python segar | 399 | 0/0/0 | 64.28 s |
| Final Python | 405 | 0/0/0 | 65.67 s |
| Baseline Node | 80 | 0/0/0 | 108.268417 ms |
| Final Node | 91 | 0/0/0; cancelled 0 | 182.381542 ms |

Seluruh **399 identitas Python** dan **80 nama kasus Node** baseline ada pada
hasil final; tidak ada identitas Python duplikat. Tambahan **6 Python** (termasuk
satu wrapper 11 tes Node) dan **11 Node**. Jangan menjumlahkan wrapper Python
dengan Node sebagai tes independen tambahan. Satu warning deprecation Starlette/
httpx existing tetap ada. Node tidak diperlukan saat runtime web.

Dua assertion Contact lama dimigrasikan secara sengaja, nama tes tetap:
`test_foundation_pages_show_real_model_and_incomplete_contact` dan
`test_phase4_contact_keeps_unverified_group_explicit`. Default kini harus memuat
lima kartu resmi dan notice peran belum dikonfirmasi; dua kasus baru mempertahankan
fallback missing/unverified. Ini bukan klaim bahwa seluruh source tes lama identik.

Perintah akhir:

```sh
node --test tests/frontend/*.test.mjs
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase4_1/full_regression_final.xml
```

Suite benar-benar memakai PostgreSQL/v3; mencakup isolation, CSRF, race,
rollback, legal actions, schema drift, docs CSP, dan SQL export/restore ke DB
baru yang terisolasi. Tidak ada skip integrasi. Dua ronde TCP controller real
selesai: seed42 **23 aksi** (20 Play/3 Chi), seed43 **23 aksi** (21 Play/1 Chi/1
Peng), total enam prediksi tersimpan dan deletion terverifikasi; bobot model
in-memory sebelum/sesudah identik. Bukti diekstrak dari property JUnit final ke
[round_acceptance.json](../artifacts/phase4_1/round_acceptance.json).

JUnit final: [full_regression_final.xml](evidence/phase4_1/full_regression_final.xml).
Rekonsiliasi identitas dan hash: [integrity.json](../artifacts/phase4_1/integrity.json).
`pip check`, empat `node --check`, `py_compile`, dan `git diff --check` lulus.

## 8. Browser verification

Browser actual pada CLI port8000: keyboard tile/claim, real Play dan Chi,
Normal menampilkan satu seat highlight/tile arrival dengan aksi/prediksi disabled,
Skip berhasil, Cepat berhasil, prediksi v3 sebelum aksi dan POST_MELD_DISCARD,
History dua kartu dan detail bertabel, Home serta lima kartu Contact.
Satu ronde browser tambahan selesai setelah **23 aksi**, Bot Timur Zimo25fan,
delta `[99,-33,-33,-33]` dari engine.

Game/Contact diuji masing-masing pada **1440,1024,768,390,360 px**. Semua sepuluh
ukuran document width sama dengan viewport; hand mobile scroll lokal. Empat
screenshot disimpan, termasuk desktop dan mobile yang diperiksa visual:
[Game1440](evidence/phase4_1/game-1440.jpg),
[Game390](evidence/phase4_1/game-390.jpg),
[Contact1440](evidence/phase4_1/contact-1440.jpg),
[Contact390](evidence/phase4_1/contact-390.jpg).
Detail actual: [browser.json](../artifacts/phase4_1/browser.json).
Reduced-motion dibuktikan lewat predicate/scheduler tests dan CSS, bukan klaim
emulasi media browser. Actual200%zoom, physical mobile dan audit a11y menyeluruh
belum dilakukan.

## 9. Model, engine and database integrity

Checkpoint SHA-256:
`ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`.
Metadata SHA-256:
`84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e`.
Keduanya cocok frozen v3; tidak retrain atau force-add artifact.

Manifest Phase3 **1,868/1,868** dan Phase2.2 **1,624/1,624** tetap identik.
Preflight Phase4.1 membandingkan **2,130** file lama: hanya 14 perubahan yang
disengaja (termasuk append laporan Phase4); tidak ada perubahan tak diizinkan.
Engine/referee/encoder, API, schema source dan bukti Phase4 lama tetap identik,
selain append eksplisit laporan. Dataset/artifact besar tetap tidak diedit.

PostgreSQL **14.19** pada cluster project existing. Schema dev/test keduanya
lulus validator semantik existing (JSONB, constraints, ownership/privileges,
nullability, timestamp, uniqueness/indexes); tidak ada DDL baru dari fitur ini.
**23 record dev** saat preflight masih identik hash aggregate/per-ID setelah
seluruh tes/browser. SHA canonical:
`c09c76114272ca95985e1a7ba8dc83ee791a33456fc67f13f9934810cf58e46f`.
Angka11 pada laporan audit historis bukan baseline task ini; record tambahan
pengguna dipertahankan. Preview memakai test DB. Cluster existing tetap berjalan.
Bukti: `postgres_before.json`, `postgres_after.json`, `schema.json`.

Fresh independent review `/root/phase41_review`: **0 Critical/Important/Minor**;
read-only, reviewer menjalankan 11 tes playback dan memeriksa entry, lifecycle,
masking, escaping/roster serta hash source terkait. Reviewer tidak mengulang
Python/CLI/browser sendiri; hasil tersebut dijalankan implementer. Dokumentasi
akhir tidak termasuk scope review. Detail: [independent_review.md](evidence/phase4_1/independent_review.md).

## 10. Git state

Branch **main**, HEAD **263fd88c83df417de53051d6ab0127c9a544a8c4** tidak berubah.
Status akhir: **15 tracked modified, 168 untracked files, 0 staged** (termasuk
pekerjaan Phase4 sebelumnya). Scope task ini: **14 file existing diubah, 47 file
baru**, termasuk semua evidence. Daftar status tepat dicatat setelah semua
dokumen dibuat dalam `artifacts/phase4_1/git_final.json` serta
`docs/evidence/phase4_1/git_final.txt`.
Working tree sengaja berisi Phase4+4.1 yang belum di-commit; **0 staged**. Tidak
melakukan add, commit, push, reset, checkout, stash, clean, merge, rebase atau
deployment. Server preview milik task sudah dihentikan.

## 11. Remaining UAS work

Konfirmasi kontribusi/peran resmi, tulis PDF final berdasarkan bukti nyata,
rekam video, dan siapkan paket source/SQL dengan transfer model checksum serta
secret dikecualikan. Uji clean install/platform target, actual200%zoom, runtime
motion emulation dan physical devices/assistive technology masih diperlukan.
Tidak mengklaim kebenaran lintas platform atau seluruh submission selesai.

## 12. Final recommendation

Phase4+4.1 siap untuk verifikasi penerima secara independen dan review snapshot
milestone. Commit memerlukan otorisasi pengguna terpisah. Buka README untuk
persiapan; pada environment yang sudah siap jalankan `fastapi dev main.py`.
Tidak ada pekerjaan Phase5 atau publishing dilakukan.
