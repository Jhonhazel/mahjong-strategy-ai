# Revisi feedback dosen UAS — 10 November 2026

**PASS untuk revisi website PostgreSQL utama.** Branch `main`, HEAD tetap
`d0a0168f578b5c00e83f45013972f4088d94dedd`. Tidak ada staging, commit, deployment,
publikasi, pergantian branch, retraining, provisioning, atau perubahan SQLite.

## Konten akademik dan sumber

Hero, How It Works, CTA, desain dan JavaScript game dipertahankan. Home menjelaskan
supervised Behavior Cloning, informasi yang terlihat pemain, legal masking,
perbedaan 34 kelas discard dengan 235 aksi engine, serta Advisor MLP yang berbeda
dari tiga bot heuristik. Arsitektur v3 terverifikasi: 1368 → 256 → 128 → 34,
ReLU, dropout 0.2, 387,746 parameter. Prediksi tidak menjalankan aksi otomatis.

Metrik berasal dari `test_evaluation.metrics` pada metadata promoted v3:

| Metrik | Tampilan |
|---|---:|
| Top-1 accuracy |64.35%|
| Top-3 accuracy |86.55%|
| Macro-F1, 34 kelas |0.622|
| Masked NLL |1.086|
| Legal recommendation rate |100%|

Cohort evaluasi: **194,388 keputusan / 3,816 match**, historical retrospective,
setelah seleksi checkpoint dibekukan. Bukan seluruh corpus, blind test eksternal,
win probability, atau bukti bahwa langkah model selalu optimal.

Dataset publik `Dannibal/ijcai-mahjong-round2`, revision
`c8435106623c106b9e03b980691bea24ba4ac240`, versi `expanded_strict_v2`:
44,420 file JSON sumber; 38,250 match strict diterima; 1,946,122 keputusan;
581 UID pemain/bot. Satu sampel berisi state, mask, dan target discard. UID bukan
klaim jumlah manusia. Sebanyak 6,170 match dikecualikan: 6,084 terminal abnormal,
31 aksi rekaman tidak legal, dan 55 replay error. Sumber: contract,
`data_quality_report.json`, `expansion_report.json`, dan ledger Phase 2.1.

Preprocessing mengikuti kode aktual: rekonstruksi dari sudut pandang private seat,
validasi replay, `int8[38,4,9]`, C-order flatten/cast menjadi `float32[1368]`,
tanpa normalisasi. Target `class_id = action_id - 2`, mask discard `policy[2:36]`.
Shard NPZ terkompresi memiliki contract dan manifest checksum. Tidak ada perubahan
pipeline, data, engine, atau model.

## Distribusi dan provenance

| Partisi corpus Phase 2.1 | Keputusan | Persentase |
|---|---:|---:|
| Train |1,555,412|79.924%|
| Validation |196,054|10.074%|
| Test retrospektif |194,388|9.988%|
| Historical test lama |268|0.014%|
| Total |1,946,122|100.000%|

V3 memakai **fold 0 / E3_f0_s2026**: 1,400,549 train / 27,515 match dan
350,917 validation / 6,914 match, dari development pool 1,751,466 / 34,429 match.
AdamW: learning rate 0.001, weight decay 0.001, batch 256, seed 2026. Sebanyak
49 epoch dijalankan, best epoch 41, maksimum 60, patience 8; seleksi berdasarkan
validation masked NLL terendah. Eksperimen terbatas, bukan full 5-fold CV.
Grouping trajectory mengurangi overlap; tidak membuktikan bebas leakage absolut.

Bar 34 kelas memakai **ground-truth support** dari
`artifacts/phase2_2/training_history.json:selected_train_metrics.per_class`.
Support diperiksa terhadap row sum confusion matrix dan total 1,400,549.
SHA history:
`bacdb2dbc813c500d6bd36351652342a293966d4dc4a319837cc8bf7aaf9ea9d`.
Mapping mengikuti metadata dan tile catalog: W karakter, T bambu, B lingkaran,
F angin, J naga. Semua kelas memiliki sampel; F4 terbanyak 59,187 dan B6
terendah 30,374. Donut kelompok menjumlahkan angka bar yang sama:
Karakter 334,739; Bambu 338,918; Lingkaran 327,460; Angin 232,357; Naga 167,075.

Tiga grafik SVG lokal memiliki label, legend, dan tabel numerik; tabel 34 kelas
tersedia melalui details. Persentase memakai largest-remainder rounding tiga
desimal sehingga total 100%; ukuran grafik memakai proporsi hitungan asli.
Scroll horizontal mobile hanya terjadi di dalam panel chart/tabel.

Ringkasan `config/home_research.public.json`: 4,595 byte,
SHA `d84063a958f54f49548dd996955e69ebe8ce1b90585d96a0f3e0b4786d375a46`.
Dibuat offline dari empat sumber terikat hash, tanpa membaca shard atau training.
Verifikasi reproduksi:

```sh
.venv/bin/python -m scripts.build_home_research_summary --check
```

Output baru dapat dibuat dengan `--output /tmp/home_research.public.json`;
exclusive create menolak overwrite. Runtime membaca ringkasan bounded dan cached
sekali, memeriksa checksum serta mapping/cohort. Jika hilang/rusak, notice jujur
ditampilkan tanpa menghalangi Home atau Game. Tidak ada endpoint, dependency,
CDN, atau pemuatan checkpoint baru per request.

## Contact dan footer

Nama, NIM, email kelima anggota resmi tidak berubah. Semua mendapat role identik:
dataset; preprocessing/encoding; training/evaluasi AI; integrasi game/web/FastAPI;
testing/debugging/dokumentasi/presentasi UAS. Ini scope tugas yang ditetapkan
pemilik, bukan pengukuran persentase atau sejarah kontribusi individu.
Notice lama hilang hanya untuk roster verified dengan tepat lima role resmi.
Konfigurasi missing, unverified, partial, atau alternatif tetap memiliki fallback.

Footer bersama pada Home, Game, History, Contact, dan History Detail:
© 2026 Kelompok 1 · Mahjong Strategy AI — Play, Predict & Learn ·
Universitas Bunda Mulia. Footer mengikuti alur dokumen, body flex menempatkannya
di bawah halaman pendek; tidak menutupi kontrol game.

## Pengujian aktual dan review

Evidence baru: `docs/evidence/uas_feedback_2026_11_10/`.

| Bukti | Hasil |
|---|---|
| baseline.xml |521 passed; 74.46 detik|
| node_baseline.txt |91 passed|
| red.xml |20 failed, 17 passed sebelum implementasi|
| green_verified.xml |37 passed|
| full_regression.xml |539 passed sebelum review fixes|
| review_package_red / green.txt |1 failed → 1 passed|
| review_contact_red.txt |3 failed sebelum perbaikan guard|
| review_green.xml |41 passed|
| final_regression.xml |543 passed; 75.38 detik|
| node_final.txt |91 passed|
| test_identity_reconciliation.json |521 identitas lama + 22 baru; 91 Node tetap|

Suite final: **0 failure, 0 error, 0 skip**. Ada satu warning Starlette TestClient
deprecation yang juga ada pada baseline. Run development intermediate tetap
disimpan; hasil final tidak boleh disimpulkan dari nama file “green” saja.
Tiga assertion Contact lama diperbarui untuk perilaku role yang baru diotorisasi;
nama testcase dan pemeriksaan identitas, jumlah kartu, fallback dan keamanan tetap.

Python dijalankan dengan `.venv/bin/python -m pytest -q`, JUnit baru, dan
`MAHJONG_TEST_DATABASE_URL` khusus `mahjong_phase3_test` pada socket project,
port 55437. Node: `node --test tests/frontend/*.test.mjs`. Tidak ada tes menulis DEV.

Browser nyata memeriksa lima tipe halaman pada 1440/768/390 px. Tidak ada page
overflow; 34 bar dan tabel 34 baris tersedia, footer static, warning/error console
kosong. Panel chart mobile 308 px menggulir konten 760 px. Prediksi browser nyata
F2/B1/W2 tersimpan, detail dibuka, lalu kembali ke Home. Screenshot mendahului
refinement satu istilah rejection dan guard roster alternatif; output roster
resmi tetap sama setelah guard diperbaiki.

`http_smoke.json`: proses FastAPI nyata mencapai readiness, halaman 200,
v3 menghasilkan Top-3 legal tanpa mutasi game, reuse idempotent, foreign access
404, missing CSRF/wrong origin 403. Setelah proses benar-benar dihentikan dan
restart dengan konfigurasi TEST sama, History identik tetap terbuka; game dalam
memori kedaluwarsa sesuai desain. Semua proses preview milik task dihentikan.
10 request Home memerlukan sekitar 1.08–1.84 ms pada host ini; HTML 32,091 byte,
summary 4,595 byte. Ini observasi lokal, bukan benchmark deployment.

Fresh independent read-only review menemukan 2 Important dan 1 Minor:
Docker COPY belum menyertakan summary; alternate roster menerima klaim scope yang
keliru; istilah rejection kurang tepat. Semuanya diperbaiki secara terfokus,
dengan RED/GREEN tambahan dan full regression final. Lihat `independent_review.md`.
Tidak ada putaran review kedua atau klaim independent re-approval patch akhir.

## Preservasi dan paket

`source_integrity.json`: 883 file preflight diperiksa; 13 file existing berubah
sesuai scope, 870 identik, 0 hilang. Hero/How It Works/CTA identik byte. Engine,
referee, bot, encoder, schema, game JS, native Windows, P43-IA01, evidence historis,
dan ZIP lama tidak berubah. Tiga SHA frozen tetap:

- Checkpoint: `ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`
- Metadata: `84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e`
- Contract: `95f21b15be55dbbe4b9cf001edbc8b52462e4461b9bbaf39431a0a482e73adbc`

`database_integrity_utc.json`: **44/44 record DEV identik**, seluruh ID tetap ada,
dibandingkan melalui JSON canonical UTC dalam transaksi READ ONLY. Dua upaya awal
memakai representasi timestamp berbeda; file `database_integrity.json` dan
`database_integrity_verified.json` bukan bukti data berubah. Pembanding final
mengikuti timezone UTC aplikasi dan cocok persis dengan seluruh hash preflight.

Candidate runtime-only baru:
`delivery/2026-11-10-uas-feedback-v1/mahjong-strategy-ai-lecturer-portable.zip`.
106 file runtime + manifest; 1,941,024 byte;
SHA `801453e6c36b953f34616e2be9688d497bc2c30f0fe8987ab26a047beb708eac`.
Seluruh member cocok dengan manifest dan source; hasil ekstraksi berhasil memuat
konteks 34 kelas dan memverifikasi tiga asset frozen. Summary ikut allowlist dan
Docker COPY. Tidak ada `.env` aktual, secret, venv, raw data, shard, tes atau evidence
baru dalam runtime; example config existing mengikuti kebijakan paket lama.
Audit 781 MB tidak direbuild dan ZIP historis tidak ditimpa.

Batasan: image Docker tidak dibangun/dijalankan; Windows native belum diuji.
Tidak ada executable Windows atau deployment baru. Verifikasi dilakukan pada
macOS arm64 dengan PostgreSQL dan MLP v3 asli. SQLite tidak disentuh.

## Demo dosen

Setelah setup native existing selesai dan PostgreSQL berjalan, buka CMD di root:

```bat
.venv\Scripts\activate.bat
fastapi dev main.py
```

Buka `http://127.0.0.1:8000/`, lalu Home → Contact → Game → prediksi → History →
detail → Home. Gunakan Ctrl+C untuk berhenti; tidak perlu setup DB atau retraining.
Daftar lengkap file baru/berubah tersedia di `final_verification.json`.
