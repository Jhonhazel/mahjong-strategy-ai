# Phase 4 — Interactive Mahjong Web Interface

Tanggal pengerjaan: 6 November 2026, Asia/Jakarta. Repository:
`/Users/jhonhazel/mahjong-strategy-ai`. Bukti hanya berasal dari eksekusi lokal,
respons server, PostgreSQL, file, dan browser yang benar-benar diperiksa.

## 1. Executive summary

**PHASE 4 GO WITH CAVEATS — FUNCTIONAL BUT LIMITED.** Antarmuka sudah terhubung ke
engine, MLP v3, dan PostgreSQL asli. Regresi akhir: **399 passed, 0 failed, 0 error,
0 skipped**, 63,78 detik (durasi suite JUnit 63,770 detik). Seluruh 370 identitas tes
lama tetap ada, termasuk 279 kasus Phase 1–2.2. Enam wrapper pytest menjalankan
66 kasus Node; angka 66 tidak ditambahkan lagi ke 399.

Tiga round browser selesai, termasuk dua skenario penerimaan desktop/mobile
dan satu pengulangan setelah perbaikan review. Review independen menemukan
empat Important dan dua Minor; seluruh temuan ditangani dalam satu fix pass
dengan regresi RED→GREEN. Tidak ada klaim persetujuan reviewer kedua.

Caveat: roster Contact belum terverifikasi; PDF/video final UAS belum dibuat;
clean install/platform lain, zoom 200%, dan emulasi reduced motion runtime belum
terverifikasi. Ini bukan pernyataan bahwa seluruh paket UAS sudah siap diserahkan.

## 2. Scope

Home, Game with AI, History, Detail, Contact, renderer tile, pengaturan round,
aksi legal, AI advisor, responsivitas, aksesibilitas praktis, keamanan frontend,
pengujian, dan dokumentasi. Stack tetap FastAPI/Jinja/CSS/vanilla ES modules.
Tidak ada framework/dependensi baru, engine kedua, retraining, schema migration,
akun, leaderboard, taruhan, staging, commit, push, atau deployment.

## 3. Baseline and Git state

Baseline awal bersih: `main` pada
`263fd88c83df417de53051d6ab0127c9a544a8c4`. Baseline baru benar-benar dijalankan:
370 passed 59,98 detik. HEAD dan branch tetap sama. Perubahan disengaja berada di
working tree: 10 file tracked dimodifikasi, 103 file untracked, 0 file staged.
Hitungan/path final tersedia pada
[verification_summary.json](../artifacts/phase4/verification_summary.json) dan
[inventaris](phase4_file_inventory.md). Jangan menyebut working tree bersih.

## 4. UI/UX design

Deep jade `#102f2b`, forest `#175448`, felt `#216659`, ivory `#f7f3e8`, cream
`#e9e4d7`, gold `#c6a66b`, ink `#243b38`, serta coral/error yang terukur. Serif
sistem untuk judul editorial, sans sistem untuk kontrol. Tidak mengunduh font.
Home menggunakan komposisi tile yang secara eksplisit diberi label ilustrasi,
bukan state game. Game menempatkan meja sebagai elemen utama dan advisor di
samping desktop; pilihan dan saran memakai teks/badge selain warna.

## 5. Component architecture

Entry `phase3.js`/`phase3.css` dipertahankan. Modul lokal memisahkan katalog,
tile DOM, proyeksi publik, HTTP, coordinator state, renderer, dan delete guard.
`app/web/pages.py` hanya mendapat dua baris import/global presentasi. Tile macro
Jinja dan renderer DOM memakai katalog yang sama. Tidak ada perubahan API,
service, ownership, settings, database, engine, encoder atau ML.

## 6. Tile rendering

Sprite SVG asli lokal berukuran 42.208 byte: 34 tile normal, 8 bunga, back, dan
unknown (44 simbol). W=karakter/Wan; T=bambu/Tiao; B=lingkaran/Bing; F 1–4=Timur,
Selatan, Barat, Utara; J 1–3=Merah, Hijau, Putih; H 1–8=bunga bernomor. Tidak memberi
nama bunga/musim yang tidak tersedia dalam kontrak. Artwork tidak bergantung pada
gambar CDN. Semua 42 kode diuji, generator identik byte-per-byte, simbol memakai
allowlist, label aksesibel, dan fallback unknown aman.

## 7. Board mapping

Posisi relatif `(seat-human+4)%4`: 0 bawah, 1 kanan, 2 atas, 3 kiri. Keempat seat manusia
diuji. Bot hanya memperlihatkan backs/jumlah concealed serta meld, bunga,
buangan dan jumlah wall publik. ANGANG lawan selalu ditutup, sekalipun objek
input ekstra memuat identitas. Tidak menyimpulkan urutan buangan global.
CHI divisualkan menurut tile tengah publik; `offer` tidak dilabel sebagai asal
seat karena untuk CHI nilainya merupakan posisi tile yang diklaim.

## 8. Legal action integration

Play, Chi, Peng, Gang, AnGang, BuGang, Hu, Pass memakai `action_id` persis dari server.
Frontend tidak menghitung legalitas, fan, skor, atau ID aksi. Duplikat tile
menggunakan aksi Play yang sama tetapi mempertahankan indeks visual terpilih.
Klik tile/claim hanya memilih; tombol Jalankan mengonfirmasi. Selector
`legal-action` tetap tersedia dan berlabel eksplisit. Tidak ada pengurangan
tangan optimistis, submit ganda, mutation retry otomatis, atau auto-discard AI.
Seed kosong menjadi null; integer 0–9007199254740991 diterima, sisanya ditolak.

## 9. AI recommendation integration

Checkpoint: `artifacts/models/mahjong_discard_mlp_v3.pt`, SHA- 256
`ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`.
Metadata SHA- 256:
`84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e`.
Model version aktual `discard_mlp_flexible_v1:ad05a5b2ce37`; encoder
`ijcai2026_mcr_v1_strict`. Arsitektur 1368→256→128→34,387.746 parameter.

Predict hanya atas permintaan eksplisit. Respons save divalidasi untuk ID,
game/turn/seat, fase, provenance, skor finite, dan keanggotaan aksi server.
GET sesudah save memverifikasi konteks sebelum highlight. Request mulai/gagal
menghapus advice aktif; hasil tersimpan tetap memiliki ID/link saat verifikasi
terlambat/gagal atau giliran berubah. Top 3 berurutan sesuai server, bukan ranking
baru frontend. Reused mempertahankan ID. Skor adalah preferensi discard yang
dinormalisasi, **bukan probabilitas menang**. State dan bobot model tidak berubah
akibat prediksi, dibuktikan pada integration/acceptance yang dieksekusi.

## 10. Session and security

HttpOnly cookie, CSRF meta/header, same-origin credentials, CSP/security headers
dan owner isolation lama tetap utuh. Tidak menyimpan cookie/token/state/history
di localStorage atau sessionStorage. DOM memakai textContent/SVG allowlist;
Jinja escaping tetap aktif. Pesan error Indonesia tidak menyalin detail backend.
Sequence GET menolak respons usang dan completion lama tidak melepas busy guard
baru.400/409/hasil aksi belum pasti direkonsiliasi dengan GET, tanpa mengulang
POST.401/403 meminta pemulihan sesi;404 menghapus state/hasil/ID lama;503 tidak
mengklaim save berhasil. Delete baru sukses pada 204, bukan200/201/202.

## 11. History integration

List/paging/detail/delete tetap memakai record PostgreSQL milik browser.
Kartu memuat waktu UTC, game ID, turn/fase, saran utama, Top 3 dan akses provenance.
Detail menampilkan tabel AI semantik, model/encoder, checksum, dan kedua snapshot
JSON lengkap dalam details tertutup. Input merupakan encoding informasi pemain,
bukan tangan rahasia lawan. Delete adalah konfirmasi dua langkah dengan form
POST lama sebagai fallback; enhancement DELETE memakai CSRF dan menunggu 204.
Kegagalan tidak menghapus kartu secara optimistis atau menyatakan sukses.

## 12. Responsive design

30 pengukuran browser pada lima halaman ×1440/1280/1024/768/390/360 CSS px:
documentWidth=viewportWidth di semuanya. Advisor di samping desktop, turun pada
tablet/mobile. Tangan menggulir lokal; target tile interaktif minimal 44 px.
Uji tambahan 14 tile pada705/768 px membuktikan tile pertama dan terakhir dapat
dipilih dengan keyboard; `safe center` menghindari clipping sebelum scroll origin.
Data geometri aktual ada pada `browser*_verification.json`. Ini bukan pengujian
pada perangkat mobile fisik atau semua kombinasi browser.

## 13. Accessibility

Native button/select/details, nama tile, explicit label, skip link, fokus
terlihat, aria-pressed, live status, busy/disabled state, dan badge tekstual.
Claim Chi dan tile dimainkan melalui keyboard pada browser. Tujuh pasangan
warna teks memiliki rasio 5,354–10,776: 1. Media rule reduced motion mematikan
transition/animation; rule hadir di browser, preference host false. Tool tidak
menyediakan emulasi media, shortcut zoom tidak mengubah ukuran, sehingga
runtime reduced-motion dan zoom 200% **belum terverifikasi**. Tidak mengklaim
sertifikasi WCAG penuh.

## 14. Testing strategy

TDD per slice: aset/controller/HTTP/proyeksi/presentasi, lalu regresi review.
Node menggunakan fixture DOM kecil hanya untuk unit rendering; tidak disebut
browser nyata. Live driver memakai controller/HTTP produksi melalui Uvicorn TCP,
MLP v3 CPU dan PostgreSQL; pilihan test hanya memilih opsi server dengan
prioritas claim/Hu. Tidak menjadi engine/policy gameplay produk.

| Kelompok | Hasil akhir |
|---|---|
| Phase 1–2.2 asli |279 lulus |
| Phase 3 asli |91 lulus |
| Phase 4 pytest baru |29 lulus (23 kasus Python +6 wrapper Node) |
| Total pytest |399 lulus, 0 fail/error/skip;63,78 sstdout/63,770 sJUnit |
| Node standalone |66 lulus, 0 fail/skip;87,00025 msrun final fix |
| Focus setelah review |20 lulus, 2,67 s |

Satu warning TestClient/Starlette deprecation berasal dari dependency lama dan
tetap dilaporkan. Compile Python, delapan syntax checks JS, pip check, dan
`git diff --check` lulus; pip hanya memperingatkan cache host tidak writable.
Lihat [test matrix](phase4_test_matrix.md) untuk pemetaan dan bukti RED/GREEN.

## 15. Browser verification

IAB/CUA terhubung: interaksi UI/render aktual, bukan mockup. Skenario:

| Skenario | Hasil |
|---|---|
| Seed 42, seat 1, wind 2, tanpa bunga |23 aksi, 3 Chi;Zimo bot Timur, 25 fan, [99, -33, -33, -33] |
| Seed 43, seat 3, wind 1, bunga |26 aksi, 2 Peng+1 Chi;Zimo bot Timur, 11 fan, [57, -19, -19, -19] |
| Post-fix seed 42, seat 1, wind 0 |23 aksi;Zimo 25 fan;GET sesudah expiry mengosongkan hasil/ID/public/hand |
| Dua tab |Turn 4→17 di tab kedua; tab pertama 409 memuat state, 0 highlight lama, link save tetap |
| Reload |Turn 20 tetap;0 selection/advice usang |
| History |Paging 1→2, detail, JSONlengkap, tabelAI, konfirmasi lalu 3→2 record |
| Sesi |404 expired dan 401 signing-key test restart menonaktifkan kontrol |

Test restart hanya pada preview milik task dengan secret uji baru, tidak pada
layanan pengguna. Preview dihentikan, tab ditutup, viewport dikembalikan. Cluster
PostgreSQL yang sudah berjalan sebelum task tetap berjalan.

## 16. Screenshots or visual evidence

Semua gambar berikut merupakan screenshot halaman yang benar-benar dirender:

- [Home desktop](evidence/phase4/home-1440.jpg), [Home mobile](evidence/phase4/home-390.jpg).
- [Game mobile dengan bunga/AI](evidence/phase4/game-360.jpg), [tablet sesudah fix](evidence/phase4/game-tablet-768.jpg).
- [Hasil round desktop](evidence/phase4/round-result-1440.jpg), [hasil mobile](evidence/phase4/round-result-360.jpg).
- [History mobile final](evidence/phase4/history-360.jpg), [Detail 360](evidence/phase4/history-detail-360.jpg), [Contact 390](evidence/phase4/contact-390.jpg).

Screenshot berasal dari beberapa giliran/build selama verifikasi; konteks dan
regresi pascaperbaikan dicatat terpisah, tanpa mengubah gambar menjadi mockup.

## 17. Security review

Review independen aktual tersimpan pada
[independent_review.md](evidence/phase4/independent_review.md). Empat Important:
advice belum terverifikasi; respons mutation malformed; hasil round tertinggal;
hand overflow center. Semua direproduksi dan diperbaiki. Dua temuan awal Minor
(provenance/Top 3 dan label offer Chi) dinaikkan author karena persyaratan/efek
pada pengguna, lalu diperbaiki dengan regresi.66 Node dan 399 regresi akhir hijau.
Tidak ada Critical/Important yang masih terbuka menurut verifikasi author.
Reviewer tidak diminta melakukan review kedua; jangan menafsirkan hasil ini
sebagai post-fix independent approval. Batas browser/platform yang tidak dinilai
reviewer tetap tercatat eksplisit.

## 18. Performance observations

Resource statis final total 122.334 byte tanpa kompresi; sprite 42.208 byte. Delapan
file JS (entry+7 modul), satu CSS, satu sprite. Semua 12 GETlokal yang diukur
(termasuk 2 HTML) menghasilkan 200 dan MIME benar. Cache-control `no-store` lama
dipertahankan. Detail waktu aktual tiap resource ada di
[performance_final.json](../artifacts/phase4/performance_final.json). Tidak ada
browser model download, font/CDN gambar, build dependency atau polling game.
Tidak mengklaim Lighthouse, Core Web Vitals, latency produksi, FPS atau hasil
jaringan yang tidak diukur. Durasi acceptance lokal bukan ukuran win rate.

## 19. Source file inventory

10 file lama berubah: README, 2 entry aset, 6 template, dan pages.py. Source baru:
7 modul, sprite, macro, katalog Python, generator. Tes baru berada di
`tests/test_phase4_*.py`, support dan `tests/frontend/`. Daftar lengkap file
modified/untracked beserta kategori ada di [inventory](phase4_file_inventory.md).
Tidak menyertakan venv, secret, raw archive, expanded shards, cache atau checkpoint
ke staging; staging tidak digunakan sama sekali.

## 20. Preservation verification

1.999 file terlindungi dibandingkan SHA- 256, termasuk engine/encoder/sourceML,
checkpoint/metadata/kontrak/dataset, semua tes/evidence lama.0 mismatch.
SHAcheckpoint/metadata v3 sesuai section 9; bobot runtime sebelum/sesudah sama.
11 record dev identik per-row dan canonical aggregate:
`d153bfcc7c9e9695d9ce1c71f933aae7133ce6577cd315beaed5bfdfff5028b7`.
Normalisasi memakai transaction read-only, timezoneUTC dan serializer preflight
yang sama; perbedaan zona waktu default bukan perubahan record. Semua write
verifikasi memakai testDB atau DB restore test baru yang dibatasi helper.
23 kasus database tools, termasuk SQL dump/restore asli, serta penerimaan
restart ASGI dan TCP dijalankan lagi dalam regresi akhir. Tidak menyalin isi
backupSQL ke repository atau overwrite ekspor lama. Bukti final pada
`preservation_final.json`, `postgres_final.json`, dan
`postgres_integration_evidence.json`.

## 21. Known limitations

Identitas anonim; cookie/key/masa berlaku menentukan akses History. Secret baru
setelah restart dapat memutus akses identitas lama. Active game berada di memory,
single worker, TTL normal 3600 s dan cleanup round selesai 30 s tetap berlaku. Tidak
ada resume active game lintas restart. Group roster belum diverifikasi, meskipun
konfigurasi anggotanya tersedia. Tidak menguji clean install baru, OS/browser
lain, perangkat fisik, zoom 200%, emulasi motion runtime atau audit WCAG lengkap.
Swagger/ReDoc tetap memakai aset CDN sesuai kebijakan Phase 3, sedangkan UI game
dan halaman memakai aset lokal. PDF/video/pengemasan akhir UAS belum dikerjakan.

## 22. UAS compliance

PDFresmi `docs/reference/SOAL UAS PEMROGRAMAN WEB FRAMEWORK.pdf` dibaca dan
dirender dua halaman (halaman 2 kosong), checksum sesuai bukti Phase 3.

| Persyaratan resmi | Status/bukti |
|---|---|
| FastAPI, Jinja, CSS/JS +AI +PostgreSQL |Tersedia dan diuji nyata |
| Home menjelaskan kategori, dataset, metode/model |Metadata asli, angka retrospektif, jelas bukan win probability |
| Contact anggota/peran kelompok |Struktur configurable tersedia; **isi belum lengkap/terverifikasi** |
| Minimal satu tabel hasilAI |Tabel Top 3 di Detail dengan caption dan scoped headers |
| Create/Read/Delete lewat website |Predict+save, List/Detail, konfirmasi Delete diuji |
| Source dan SQL |Source tersedia, workflowSQL asli teruji; paket final belum dirakit |
| PDFakhir alasan/capture/kontribusi |Belum dibuat; capture asli tersedia |
| Videodemo dan pembagian tugas |Belum tersedia/diverifikasi |

## 23. Reproduction instructions

Host yang diuji: macOSarm 64, Python 3.12.10, Node 24.4.1, PostgreSQL 14.19; virtualenv
dan dependency lama tetap digunakan. Restore aset inferensi mengikuti
[prosedur checksum](ml_artifact_transfer.md), bukan retraining atau force-add.
Tidak melakukan clean install ulang pada task ini. Dari repository:

```sh
cd /Users/jhonhazel/mahjong-strategy-ai
.venv/bin/python -m scripts.phase3_db start
export MAHJONG_DATABASE_URL="$(.venv/bin/python -m scripts.phase3_db url --database dev)"
export MAHJONG_SESSION_SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(40))')"
export MAHJONG_ENVIRONMENT=local
export MAHJONG_WORKERS=1
.venv/bin/python -m scripts.init_db
.venv/bin/python -m scripts.run_backend
```

Simpan secret secara privat dan gunakan nilai yang sama untuk restart normal;
jangan mencetak atau memasukkannya ke Git. Buka `http://127.0.0.1:8000/game`.
Perintah start, init_db dan run_backend benar-benar diverifikasi di host ini;
preview/init task memakai database **test**, port 8874 untuk isolasi, bukan
menulis prediksi ke dev. Start helper idempotent tidak membangun ulang cluster.

Terminal lain untuk verifikasi (Node harus tersedia padaPATH):

```sh
export MAHJONG_TEST_DATABASE_URL="$(.venv/bin/python -m scripts.phase3_db url --database test)"
node --test tests/frontend/*.test.mjs
.venv/bin/python -m pytest tests/test_phase4_*.py -q --junitxml=docs/evidence/phase4/local_focused.xml
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase4/local_reproduction.xml
```

Gunakan filename evidence baru. Missing PostgreSQL config menghasilkan skip
eksplisit dan tidak cukup untuk PASS. Nodehilang menghasilkan kegagalan wrapper,
bukan klaim pengujian browser. Jangan menghentikan cluster pengguna secara
otomatis; hanya preview task yang telah dihentikan.

## 24. Phase 5 or final submission handoff

Sebelum penyerahan: verifikasi roster/NIM/peran resmi lalu isi config Contact;
uji instalasi/platform target dan zoom/motion/a11 y secara manual; susun PDFUAS
berdasarkan bukti nyata serta kontribusi yang disetujui; rekam demo dan buat
paket source+SQL melalui helper/checksum yang ada. Jangan memasukkan secret,
venv, data latihan besar atau model tanpa prosedur transfer. Review working
tree dan minta otorisasi terpisah jika nanti membutuhkan commit/deploy. Tidak
ada implementasi Phase 5 atau tindakan Git lanjutan dalam task ini.

## 25. Final verdict

**PHASE 4 GO WITH CAVEATS — FUNCTIONAL BUT LIMITED.** Scope implementasi selesai,
399/399 regresi serta 66 kasus Node lulus, 370 identitas asli utuh, realv3/PG/browser
terbukti, fix review terverifikasi. Roster, PDF/video/paket final dan batas
aksesibilitas/platform pada section21/24 tetap menjadi pekerjaan final UAS.
Working tree sengaja belum di-commit; tidak ada push atau deployment.


## Audit remediation P4-A01/P4-A02 — 6 November 2026

PASS — BOTH MINOR FINDINGS CLOSED. Hanya controller bertambah empat baris guard;
14 regresi baru ditambahkan tanpa mengganti tes lama. RED39/44 +5 kegagalan
yang tepat → GREEN44/44. Node80/80 (66 historis +14 baru); pytest399/399,
0 failed/error/skipped,64.64detik; semua399 identitas historis utuh. Dua round
TCP real-v3/PG dan browser smoke normal lulus. Fresh narrow reviewer:0 findings,
44 tes controller lulus; bukan audit independen ulang atas seluruh backend.

Semua1.999file protected,34/36 file source historis selain controller/test, model,
metadata, schema dan11record dev tetap identik. Dua hash source berubah secara
sengaja:controller dan tes. Empat dokumen hanya mendapat append. Tidak ada Git
mutation/deploy. Caveat UAS/platform/aksesibilitas sebelumnya tetap berlaku.
Laporan lengkap beserta14nama regresi: [audit_minor_fix_review.md](evidence/phase4/audit_minor_fix_review.md).
Bukti terbaru: [audit_minor_fix_verification.json](../artifacts/phase4/audit_minor_fix_verification.json).
Laporan399/66 dan manifest awal di atas merupakan catatan historis, tidak ditimpa.

## Phase 4.1 handoff — 6 November 2026

GO WITH CAVEATS. Thin root `main.py` menjalankan factory existing melalui exact
`fastapi dev main.py`; actual startup, readiness dan empat halaman200 pada port8000.
Runner lama juga ready200. Public-snapshot highlights600ms/180ms, Cepat/Skip,
motion/lifecycle cancellation ditambahkan tanpa event bot rekaan atau engine/API
changes. Contact default kini tepat lima identitas resmi; **peran/kontribusi masih
belum dikonfirmasi**. Dua assertion Contact lama dimigrasikan secara eksplisit.

Fresh baseline399Python/80Node; final405Python/91Node,0failed/error/skipped.
Semua identitas lama dipertahankan. Dua ronde TCP realv3/PG serta satu ronde
browser selesai. Fresh focused reviewer:0Critical/Important/Minor. Checkpoint,
engine dan dataset tidak berubah; **23 record dev pada preflight Phase4.1** tetap
identik. Angka11 pada audit historis di atas bukan baseline task baru ini.
Preview task dihentikan, cluster existing tetap berjalan. Tidak ada Git mutation
atau deployment. Caveat PDF/video/peran/platform/a11y/submission packaging tetap.

Detail: [laporan Phase4.1](phase4_1_implementation_report.md),
[test matrix](phase4_1_test_matrix.md),
[verification JSON](../artifacts/phase4_1/verification_summary.json).
