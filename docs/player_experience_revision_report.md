# Revisi website untuk pemain Mahjong — 11 November 2026

Status: **PASS untuk seluruh cakupan implementasi** pada branch
`codex/player-friendly-pages`, baseline HEAD
`a433f5dd3e765383f1f2d2dea9c658fcc9b909f5`. Checkout awal bersih. Tidak ditemukan
AGENTS.md pada repository/ancestor yang diperiksa. Instruksi pengguna yang
menyebut monorepo TypeScript tidak diterapkan sebagai stack: checkout aktual
adalah aplikasi Python/FastAPI Mahjong. Tidak ada install dependency, commit,
push, merge, reset, deployment, migrasi, provisioning, atau retraining.

## Kebutuhan → implementasi → file → bukti

| Kebutuhan | Implementasi / file utama | Bukti |
|---|---|---|
| Lima halaman | Home → Game → History → Contact Us → Model; `/model` baru; `pages.py`, `base.html`, `model.html` | Tes route/nav, browser 3 ukuran |
| Home umum | Hero/aset tile dipertahankan; pengenalan, tujuan, sejarah bersumber, CTA; `home.html` | Tes batas konten, screenshot |
| Model berurutan | Enam tahap: data, persiapan, representasi, model, latihan, evaluasi; `model.html` | Tes enam section dan metadata |
| Penamaan publik | Model AI; tanpa versi/hash/fold/seed/eksperimen/count; template dan view | Tes HTML/aria + browser |
| Evaluasi | Top-3 dari metadata; definisi F1 kelas utama tetap; `pages.py`, `model.html` | Metadata dan tes |
| Grafik | Tiga kelompok partisi dan 34 kelas/lima keluarga, persentase saja | Tes mapping/persentase/atribut, browser |
| Game sederhana | Panduan sebelum setup; tanpa seed/speed/dropdown aksi/debug; template, entry JS, view | RED/GREEN; renderer tanpa elemen lama |
| Semua aksi | Pilihan tile dan semua claim tetap berasal dari server dan dikonfirmasi | Unit tujuh jenis claim; dua round nyata; browser Chi |
| Animasi | Normal tetap, skip, cancellation, reduced motion tetap | Browser normal/skip; tes Node reduced motion |
| History sederhana | Hasil tersimpan, tanggal UTC, tile, skor, detail, hapus terkonfirmasi; tanpa JSON/ID publik | PG/API tests; browser save/detail/delete |
| Error History | Missing/invalid record memakai notice HTML, status404/422 tetap; API tetap JSON | Dua RED/GREEN cases, browser |
| Contact | Nama/NIM/email tetap; peran/scope dan notice karena peran disembunyikan | Tes roster/escaping/fallback; browser |
| Packaging | Model ditambahkan ke runtime allowlist; Docker `COPY app app` sudah mencakup template | ZIP ekstraksi/member hash/import |

## Angka dan definisi

Model internal tidak diganti. Arsitektur aktual 1368→256→128→34, ReLU, dropout 0.2,
AdamW, learning rate 0.001, batch 256, weight decay 0.001, masked cross-entropy;
best epoch 41 dari 49, batas 60, patience 8. Template memakai metadata aktif,
bukan hardcode angka evaluasi. Snapshot/identitas model tetap di API/database.

Top-3 = target pada data evaluasi berada dalam salah satu dari tiga saran model;
nilai metadata 0.8654546576949195 ditampilkan **86,55%**. Bukan akurasi rekomendasi
pertama atau peluang menang. Macro-F1=.6219443806911921, ditampilkan 0,622;
tetap dihitung dari prediksi kelas utama, bukan F1 Top-3. Evaluasi historis
retrospektif setelah pemilihan model; tidak diklaim sebagai blind test baru.
Bobot saran pada giliran permainan adalah preferensi di antara discard legal,
berbeda dari ketepatan agregat pada evaluasi.

Pembagian awal ditampilkan di antara tiga partisi utama saja, dinormalisasi
setelah mengecualikan holdout lama yang sangat kecil:79.935%/10.075%/9.990%,
total 100%, berlabel **sekitar 80/10/10**. Dataset asli tidak berubah. Pelatihan
akhir menyusun kembali train/validation menjadi sekitar 79.964%/20.036%, dijelaskan
sebagai **sekitar 80/20**, tanpa fold/seed/count pada halaman publik.

Distribusi 34 tile dan lima kelompok memakai support train aktual yang sama dari
ringkasan terverifikasi. Mapping/urutan0–33 tetap. Persentase memakai hitungan
internal dan largest-remainder rounding, sehingga total 100%; ukuran SVG mengikuti
proporsi asli. Tidak ada raw count pada bar, legend, pusat donut, caption, tooltip,
aria, atau data-count; tabel numerik lama dihapus. Summary 4595 byte dan generator
lama tetap identik; Model membaca cache kecil, tanpa membaca shard atau memuat
checkpoint tambahan per request. Home tidak membaca ringkasan penelitian.

## Sumber dan atribusi

- Sejarah: [UK Mahjong Association, What is Mahjong?](https://ukmahjong.co.uk/index.php/what-is-mahjong/),
  diperiksa 11 November 2026; mendukung asal Tiongkok pertengahan/akhir abad 19 dan
  popularitas di Barat pada 1920-an. Tautan sumber tampil di Home. Tidak ada klaim
  asal kuno atau pencipta tertentu. BritishMuseum/escholarship sempat dicari,
  tetapi akses dokumen dibatasi; tidak dijadikan sumber yang seolah dibaca penuh.
- Dataset: [Dannibal/ijcai-mahjong-round2](https://huggingface.co/datasets/Dannibal/ijcai-mahjong-round2),
  kartu sumber diperiksa, CC BY 4.0, rekaman Botzone. Proyek tidak mengklaim
  mengumpulkan sendiri seluruh data atau memakai jaringan pretrained dari sumber.
- Komponen: [PyMahjongGB](https://pypi.org/project/PyMahjongGB/1.4.0/), PyTorch,
  NumPy, FastAPI, Jinja2. Detail atribusi tetap di `THIRD_PARTY_NOTICES.md`,
  termasuk referensi FeatureAgent dan aturan MCR. Tidak mengklaim dibuat dari nol.
- Tile: spriteSVG lokal existing dipertahankan, sesuai laporan Phase4; tidak ada
  unduhan aset, font, CDN, atau library UI baru.
- Angka: metadata frozen promoted model, contract, summary publik yang checksum-nya
  diperiksa; histogram generator tetap berasal dari support training history.

## Pembagian tugas yang tidak lagi tampil di Contact

Kelima anggota resmi tetap sama dan memiliki scope bersama yang sudah ditetapkan:
analisis dataset; preprocessing/encoding; training/evaluasi AI; integrasi game,
web dan FastAPI; testing/debugging/dokumentasi/presentasi UAS. Data role tetap
utuh pada `config/contact_members.public.json`. Scope ini bukan klaim persentase
atau bukti sejarah kontribusi individu. Halaman Contact hanya menampilkan
nama/NIM/kontak; role kosong tidak membuat identitas dianggap belum lengkap.
Fallback roster missing/unverified dan escaping tetap diuji.

## Pengujian yang dijalankan

Evidence baru: `docs/evidence/player_experience_2026_11_11/`.

| Run | Hasil aktual |
|---|---|
| baseline.xml |543 passed,0 failure/error/skip;78.05 detik|
| node_baseline.txt |91 passed|
| red.xml / node_red.txt |11 Python gagal dan 3 Node gagal sebelum implementasi|
| green.xml / node_green.txt |11 Python dan 3 Node lulus|
| full_regression.xml |554 Python lulus sebelum refinement browser/review|
| browser_review_red.txt |3 gagal: definisi bobot dan dua error History|
| browser_review_green.xml |17 lulus|
| final_regression.xml |556 passed,0 failure/error/skip;79.61 detik|
| node_final_verified.txt |94 passed,0 failure/skip/cancelled|

Perintah Python: `.venv/bin/python -m pytest -q --junitxml=<evidence-baru>` dengan
`MAHJONG_TEST_DATABASE_URL` yang diverifikasi khusus `mahjong_phase3_test`,
socket project pada port 55437. Perintah Node:
`node --test tests/frontend/*.test.mjs`. Seluruh543 identitas Python baseline tetap
ada, ditambah13 kasus. Assertion UI lama diperbarui sesuai permintaan; pemeriksaan
API, legalitas, security, History, concurrency dan integrity tidak dihapus/dinonaktifkan.
Satu warning deprecation Starlette TestClient sudah ada pada baseline.

Tes unit/stub Node menguji semua jenis claim dan kondisi gagal/cancellation.
Bukti integrasi terpisah: `real_controller_acceptance.json`, diambil dari JUnit
live acceptance, memuat dua round nyata menggunakan controller ES module yang
dikirim, HTTP FastAPI, PostgreSQL asli dan checkpoint asli. Model weights tetap.
Ini tidak disamakan dengan fixture/stub.

Browser aktual di 1440/768/390 px memeriksa seluruh lima halaman, detail History,
dan notice error. Tidak ada page overflow atau warning/error console. Panduan
tersedia sebelum/saat bermain tanpa reset, round acak tanpa input seed berjalan,
keyboard memilih tile dan konfirmasi, claimChi berhasil, animasi normal dan skip
berfungsi. Prediksi checkpoint nyata F4/F1/B1 disimpan, dibuka dari History,
dihapus melalui konfirmasi hanya pada TEST, kemudian empty state dan notice
untuk tautan lama diperiksa. Raw identifiers tidak tampil pada teks publik.
Screenshot dan `browser_checks.json` mencatat pemeriksaan aktual.

## Preservasi, review dan batas verifikasi

Seluruh 98 recordDEV tetap identik (ID dan hash JSONcanonicalUTC) dalam pemeriksaan
READONLY sebelum/sesudah. Tidak ada migrasi/schema/provisioning, perubahan
checkpoint/metadata/contract/dataset/encoder/engine/referee/bot/security/API, atau
perubahan pada Windows provisioning/P43-IA01. Aset research dan roster tidak diubah.

Review independen read-only menemukan0 Critical/Important dan 1 Minor tentang tautan
penjelasan bobot; sudah diperbaiki. Reviewer menjalankan54 tesNode terarah dan
diffcheck, memeriksa definisi/statistik. Browser menemukan errorHistoryJSON yang
juga diperbaiki melaluiRED/GREEN. Tidak ada klaim re-approval independen sesudahnya.
Rincian ada di `independent_review.md`.

Batas nyata: Windows native, perangkat ponsel fisik, build/run imageDocker belum
diuji. Browser tidak menyediakan emulasi reduced-motion; preferensi browser saat
uji adalahfalse. Reduced-motiontrue/hidden/cancel diuji deterministik di Node,
bukan diklaim sebagai pengujian preferensi OS nyata. Semua server preview milik
task dihentikan. Tidak ada URL/deployment baru.

## Paket dan cara mencoba

Candidate final baru runtime-only:
`delivery/2026-11-11-player-experience-v2/mahjong-strategy-ai-lecturer-portable.zip`.
107 file runtime+manifest. Member, source, Model template dan asset frozen diperiksa
melalui ekstraksi. V1 adalah candidate sebelum pembaruan quickstart; V2 final,
tidak menimpa ZIP lama dan tidak rebuild audit besar. Lihat
`package_final_verification.json` untuk hash/ukuran final.

Setelah setup existing dan PostgreSQL berjalan, CMD dari root project:

```bat
.venv\Scripts\activate.bat
fastapi dev main.py
```

Buka `http://127.0.0.1:8000/`. Navigasi: Home → Game → History → Contact Us → Model.
Tidak perlu setup database atau model ulang. Hentikan dengan Ctrl+C.
Daftar file dan statusGit akhir ada di `final_verification.json`.
