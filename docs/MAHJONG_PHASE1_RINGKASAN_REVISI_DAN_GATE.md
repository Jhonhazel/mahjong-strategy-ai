# Mahjong Strategy AI + Playable Game — Ringkasan Revisi Phase 1

**Tanggal audit:** 4 November 2026  
**Status:** Dokumen desain dan implementation plan sudah direvisi; **belum** ada klaim Phase 1 telah diimplementasikan/lulus.

## Artefak hasil revisi

1. `2026-11-04-mahjong-strategy-ai-phase1-design_REVISI_AUDIT.md` — kontrak desain revisi (R0–R4).
2. `2026-11-04-mahjong-strategy-ai-phase1_REVISI_AUDIT.md` — implementation plan revisi termasuk patch contoh kode dan prototipe fail-closed parity.

Gunakan dua file revisi di atas sebagai dasar coding; jangan menggunakan bagian yang bertentangan dalam dokumen lama sebagai sumber keputusan. Simpan file lama untuk histori perbandingan.

## Yang sudah diperbaiki pada DOKUMEN dan CONTOH KODE

- Menambahkan matriks koreksi R0–R4 lengkap dengan syarat bukti (`go/no-go gate`).
- Mengganti kontrak `match_index` level pertandingan menjadi manifest **per sampel** berisi `(source_file, source_row, match_id, player_uid, seat, decision_order, target_action_id, encoder_version, source_hash)`.
- Mengganti contoh `verify_replay_parity()` yang bisa melewati error dan mengklaim 100% hardcoded dengan prototipe **fail-closed**: seluruh replay error/mismatch/ambigu tercatat, pengenal awal diperiksa sebagai sekuens kontigu lengkap, parity rate dihitung dari perbandingan nyata, manifest ditulis per baris, dan gate gagal bila target bukti tidak tercapai.
- Menambahkan strategi *re-extraction* dari log JSON mentah bila dataset NPZ historis berbeda dari encoder game live; target training tidak boleh memiliki kebocoran `match_id` lintas train/val/test.
- Memperbarui `PerSeatObserver` pada contoh kode supaya event publik dari lawan (Play/Chi/Peng/Gang/AnGang/BuGang) memperbarui tensor `obs` sebelum dipakai lagi.
- Mengubah penghitungan `is_fourth` pada contoh kode agar salinan di tangan sendiri ikut diperhitungkan, dengan syarat uji ulang terhadap dokumentasi MCR dan encoding sumber.
- Membatasi exception dari `MahjongFanCalculator`: `TypeError('ERROR_NOT_WIN')` diperlakukan sebagai non-winning hand; error input/state lain menjadi kegagalan engine. Ini dicocokkan dengan binding C++ PyMahjongGB upstream.
- Memperkuat contoh unduhan package PyMahjongGB: pilih `sdist` secara eksplisit, periksa SHA-256 metadata PyPI, validasi isi tar sebelum ekstraksi dan cari `setup.py` tanpa asumsi kapitalisasi.
- Memperjelas bahwa `rtk` bukan program terminal standar; perintah Python dapat dijalankan langsung.
- Menyusun prioritas MVP 21 hari; tidak menjadikan hardening production-grade sebagai prasyarat demo paling awal.
- Menambahkan regression test contoh untuk perubahan fitur `obs` saat lawan membuang keping dan pengecekan `match_id` tidak overlap.

## Hasil QA lokal terhadap DOKUMEN

- Seluruh **25 blok kode Python** yang terdapat dalam implementation plan revisi **lolos pemeriksaan sintaks `compile()`**.
- Belum dilakukan `pytest` menyeluruh, install PyMahjongGB di Windows/macOS, unduh dataset lengkap, replay log asli, maupun training/inferensi model. Sintaks benar **tidak** membuktikan seluruh algoritma/game sudah benar.
- Prototipe `verify_replay_parity()` *masih perlu divalidasi terhadap file `.npz` dan `.json` sungguhan*; hasilnya bisa menemukan ketidakcocokan data asal. Jika gagal, jangan paksa menyatakan 100%—gunakan jalur re-ekstraksi dan ubah timeline/ruang lingkup dengan jujur.

## Gerbang implementasi yang harus dibuktikan kelompok

1. **Hari 1–3:** environment hidup + CLI game satu ronde sah.
2. **Hari 4–5:** audit dataset + encoder parity yang transparan atau alur re-ekstraksi dengan `match_id`.
3. **Hari 6–10:** train/val/test berbasis match, baseline, training MLP, checkpoint, prediksi input game.
4. **Hari 11–16:** FastAPI, Jinja2/JS game board, PostgreSQL CRD.
5. **Hari 17–21:** uji integrasi, laporan PDF, `.sql` database, video demonstrasi.

**Keputusan:** **GO untuk mulai coding Phase 1** berdasarkan dokumen revisi. **NO-GO untuk Phase 2** sampai evidence Phase 1 diuji pada kode sungguhan dan memenuhi kriteria acceptance.

## Referensi yang diverifikasi

- Dataset: https://huggingface.co/datasets/Dannibal/ijcai-mahjong-round2
- PyMahjongGB: https://pypi.org/project/PyMahjongGB/
- Source error handling: https://github.com/ailab-pku/PyMahjongGB/blob/master/MahjongGB/mahjong.cpp
- Laporan teknis Mahjong: https://github.com/SuuTTT/IJCAI-mahjong/blob/master/doc/TECHNICAL_REPORT_IJCAI2026_MCR.md
