# Batas bobot saran AI 10% — 11 November 2026

**PASS.** Implementasi dilanjutkan pada `codex/player-friendly-pages`, HEAD tetap
`a433f5dd3e765383f1f2d2dea9c658fcc9b909f5`. Revisi halaman sebelumnya yang belum
commit dipertahankan. Tidak ada commit, push, merge, deployment, migrasi, perubahan
checkpoint/encoder/dataset, atau retraining.

## Kebijakan dan kontrak API

Sumber konfigurasi tunggal: `app/services/recommendation_policy.py`, immutable
`RECOMMENDATION_POLICY`: **minimum_score=0.10, maximum_suggestions=3**.
Filter memakai seluruh 34 skor yang sudah dinormalisasi terhadap discard legal:
perbandingan asli `>=0.10`, urutan skor menurun, tie mengikuti indeks kelas lebih
kecil, maksimal tiga. Tidak ada padding, epsilon cutoff, perbandingan string,
normalisasi ulang, atau mutasi input. Toleransi jumlah hanya memeriksa validitas
distribusi, bukan menentukan kelulusan cutoff. Distribusi rusak atau tanpa discard
legal adalah error; distribusi legal tanpa kandidat lolos adalah hasil sukses.

| Distribusi valid | Saran tampil |
|---|---|
|60%, 25%, 15%|3|
|62%, 25%, 8%, 5%|2: tetap 62% dan 25%|
|96%, 3%, 1%|1|
|12 aksi legal merata sekitar 8,33%|0|
|Tepat 10% / sedikit di bawah 10%|Lolos / tidak lolos sebelum pembulatan|

Respons prediksi dan History menambahkan `recommendations` dengan fields
`suggestions` (0–3), `minimum_score`, `maximum_suggestions`, serta `status`
(`available` atau `no_suggestions`). Field lama `top3`, `recommended_tile`,
`scores`, identitas model, dan output_snapshot tetap mentah untuk audit dan
kompatibilitas. Kandidat tampilan terpisah dari hasil model mentah.

Hasil diperiksa sebelum penyimpanan. Proyeksi respons dibuat dari record yang
benar-benar tersimpan, untuk 201 baru maupun 200 reuse. Snapshot tidak menyimpan
field baru; schema dan idempotency key tidak berubah. Hasil kosong tetap disimpan.

History memakai policy yang sama terhadap skor/mask tersimpan, tanpa inference
ulang atau penulisan ulang record lama. Notice menjelaskan bahwa **batas saat ini**
dipakai juga untuk catatan lama. OpenAPI dan bagian API README diperbarui.

## Tampilan dan semantik

- Game menampilkan 0–3 kartu/highlight dari kandidat server saja. Tidak ada fallback
  ke raw recommended_tile/Top-3. Controller memverifikasi skor asli, legalitas,
  distribusi, urutan/status dan kebijakan halaman; tidak mengisi atau memperbaiki
  daftar. Konstanta cutoff tidak diduplikasi pada JavaScript atau template.
- Panduan dan pesan memakai kebijakan server. Hasil kosong berbunyi persis sesuai
  permintaan, menyatakan pemain tetap dapat memilih tile. Live region polite
  dipertahankan tanpa memindahkan fokus. Pesan sukses: “Hasil analisis disimpan.”
- History menghitung hasil analisis, bukan mengklaim setiap record berisi saran.
  List/detail memakai kandidat yang sama, tetap dapat dipaginasi/dihapus dengan
  konfirmasi dan CSRF. Sesi, ownership, legal actions dan rollback dipertahankan.
- Model menyebut 10% sebagai kebijakan awal preferensi, bukan peluang menang atau
  hasil optimasi. Angka 86,55% tetap evaluasi retrospektif lama tanpa filtering,
  dengan label “Hasil evaluasi model sebelum penerapan batas minimal saran.”

## Evaluasi validasi aktual

Evaluator offline bounded memakai checkpoint lokal dan membership validasi yang
sama dengan metadata promoted model melalui loader existing. Tidak melakukan
training, kalibrasi, download atau pencarian threshold. Tidak menjalankan inference
pada test/historical_test. Cohort: **350.917 keputusan / 6.914 match**, 9,52 detik,
CPU satu thread, batch 512.

| Ukuran | Pembilang / penyebut | Persentase |
|---|---:|---:|
|Ada setidaknya satu saran|350.555 / 350.917 keputusan|99,8968%|
|0 saran|362 / 350.917|0,1032%|
|1 saran|135.132 / 350.917|38,5083%|
|2 saran|99.617 / 350.917|28,3876%|
|3 saran|115.806 / 350.917|33,0010%|
|Target tercakup, seluruh keputusan|289.312 / 350.917|82,4446%|
|Target tercakup, hanya keputusan bersaran|289.312 / 350.555|82,5297%|

Ini **validasi internal retrospektif yang sudah dipakai memilih model**, bukan
blind test baru. Target adalah discard yang tercatat, bukan bukti langkah optimal
atau kemenangan. Tidak dibandingkan langsung dengan 86,55% dari cohort test berbeda.
Semua 349 NPZ dan 363 input terikat hash tetap identik setelah evaluasi. Rincian,
command reproduksi, denominator dan provenance tersedia di
`docs/evidence/recommendation_threshold_2026_11_11/validation_policy_summary.md`.

## TDD, regresi dan browser

Semua evidence baru berada di `docs/evidence/recommendation_threshold_2026_11_11/`.

| Run | Hasil aktual |
|---|---|
|Baseline baru|556 Python, 94 Node lulus|
|RED awal|20 Python gagal/1 lulus; 12 Node gagal/2 lulus|
|GREEN awal|21 Python dan 14 Node lulus|
|Label count History|1 gagal → 7 lulus|
|Regresi final|**586 Python, 111 Node lulus;0 failure/error/skip**|

Perintah Python: `.venv/bin/python -m pytest -q --junitxml=<evidence-baru>` dengan
`MAHJONG_TEST_DATABASE_URL` khusus TEST yang sudah diverifikasi. Node:
`node --test tests/frontend/*.test.mjs`. Seluruh 556 identitas Python baseline tetap
ada, ditambah 30 kasus. Fixture tie lama diperbaiki agar distribusi penuh berjumlah 1;
validasi tidak dilemahkan. Satu warning deprecation TestClient sudah ada di baseline.

Tes mencakup batas/ties/ilegal/no mutation/no rescaling, raw snapshot lama,
empty save/reuse, failed commit, schema/panduan, malformed frontend response dan
agregasi evaluasi. Integrasi memakai PostgreSQL, engine dan checkpoint asli,
termasuk dua round live-controller existing.

Browser 1440/768/390 px memeriksa 0–3 kartu/highlight, pesan kosong, keyboard dan
kelanjutan game setelah hasil kosong, reuse, serta History list/detail.
Kasus 0–3 dipaksa memakai **fixture skor legal** pada harness TEST disposable;
tidak diklaim sebagai output model asli. Tahap terpisah memakai checkpoint asli
tanpa penggantian skor: 60,96% /16,10% /12,67%. Kasus dua kandidat tetap 62% /25%.
Tidak ada overflow atau error console. Screenshot dan `browser_checks.json`
menyimpan bukti. Harness tidak menambahkan flag/route fixture produksi dan dihentikan.

Fresh independent read-only review tidak menemukan Critical/Important; reviewer
menjalankan 19 tes policy, 3 agregasi dan 17 Node serta memeriksa provenance evaluator.
Reviewer tidak mengklaim rerun database, browser, broad suite atau cohort penuh.

## Preservasi, file, paket dan batas verifikasi

Ke-98 record DEV tetap identik; seluruh snapshot lama juga berhasil diproyeksikan
tanpa inference atau penulisan. Pembandingan memakai ID/hash JSON canonical UTC dalam transaksi
read-only. Checkpoint, metadata, contract, encoder, engine, security, API routes,
native setup, Contact, navigasi, serta desain sebelumnya tetap terjaga.
Rincian hash dan delta awal tugas ada di `source_and_test_integrity.json` dan
`final_verification.json`. Tidak ada record History lama yang ditulis ulang.

File utama: policy service baru, schemas/views/pages, web prediction service,
controller/view/entry JS, template Game/History/Model/Home, runtime allowlist,
evaluator offline, tes dan dokumentasi. API mentah dan schema DB tetap.

Candidate runtime-only baru di
`delivery/2026-11-11-recommendation-threshold-v1/`: 108 file runtime+manifest,
1.943.192 byte. Policy service ikut paket; evaluator, fixture dan dataset latihan
tidak ikut. Seluruh member hash cocok; ekstraksi policy/template dan asset frozen
berhasil diverifikasi. ZIP lama tidak ditimpa; audit besar tidak direbuild.

Windows native, perangkat ponsel fisik dan build/run image Docker belum diuji.
Evaluasi bukan blind test baru. Tidak ada commit/push/deployment; hasil berada
pada working tree branch pengembangan. Laporan menyimpan sumber teknis lengkap;
website mempertahankan penjelasan sederhana untuk pemain.
