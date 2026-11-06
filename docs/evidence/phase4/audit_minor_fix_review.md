# Audit remediation P4-A01 / P4-A02 — 6 November 2026

## 1. Final Verdict

**PASS — BOTH MINOR FINDINGS CLOSED.** Perubahan produksi hanya empat baris
validasi tambahan pada controller. Semua bukti di bawah berasal dari eksekusi
baru; laporan dan evidence Phase 4 sebelumnya tetap dipertahankan.

## 2. Findings Fixed

**P4-A01:** Sebelumnya `submit()` menerima GameView sukses tanpa memeriksa
identitas game atau kemunduran turn. Guard baru memeriksa objek, game ID asli,
integer turn, serta `updated.turn_number >= submitted.turn_number` sebelum
`setView()`. Respons salah menjadi `HttpError(0)`, lalu memakai rekonsiliasi GET
game asli; tidak ada POST ulang atau pesan sukses palsu. Generic `setView`,
create, counter request, busy guard dan transaksi backend tidak berubah.
Respons turn sama, turn maju, finished round dan transisi claim tetap diterima.

**P4-A02:** Sebelumnya validator tidak menolak urutan Top 3 terbalik atau mapping
class/action yang tidak konsisten jika field lain koheren. Dua predicate baru
memeriksa urutan skor nonincreasing (ties sah) dan `action_id === class_index + 2`,
bersama membership `legal_actions` yang sudah ada. Tidak melakukan sort,
mengubah skor, menghitung rekomendasi atau menjalankan discard. Respons malformed
tidak dipercaya untuk membuat saved notice; hasil save sebenarnya tetap belum
pasti, tidak dinyatakan pasti gagal dan tidak dihapus dari database.

Keduanya direproduksi dengan fixture mock yang sengaja malformed, bukan bukti
bahwa FastAPI atau inferensi v3 nyata menghasilkan respons salah tersebut.

## 3. TDD Evidence

Command RED dan GREEN:

```sh
node --test tests/frontend/controller.test.mjs
```

RED: 44 collected,39 passed,5 failed. Kegagalan tepat pada cross-game response,
regressed turn, jalur rekonsiliasi gagal sesudah foreign response, Top 3 ascending,
dan mapping class/action salah. Tidak ada kegagalan karena modul/DB hilang.
GREEN: 44 passed,0 failed/cancelled/skipped,112.903542 ms.

Bukti: `audit_minor_fix_red.txt`, `audit_minor_fix_green.txt`, serta diff tepat
`audit_minor_fix_production.diff`. Empat belas nama kasus baru dicantumkan pada
appendix di bawah dan `audit_minor_fix_node_summary.json`.

## 4. Node Tests

Node v24.4.1. Command: `node --test tests/frontend/*.test.mjs`.
Baseline 66 +14 baru = **80 passed**,0 failed,0 cancelled,0 skipped,
81.622709 ms. Seluruh 66 nama kasus lama dipertahankan dengan multiplicity yang
sama, tanpa duplicate. Evidence: `audit_minor_fix_node_full.txt` dan
`artifacts/phase4/audit_minor_fix_node_summary.json`.

## 5. Full Python Regression

CPython 3.12.10; virtualenv proyek. Command memakai database test terisolasi:

```sh
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase4/audit_minor_fix_regression.xml
```

**399 passed,0 failed,0 errors,0 skipped**,64.64 detik stdout/64.635 detik JUnit.
Semua 399 identitas `classname + name` dari `regression_final.xml` tetap ada;
0 kasus hilang,0 kasus baru pytest,0 duplicate. Termasuk370 identitas Phase1–3.
Enam wrapper pytest kini menjalankan80 kasus Node: jangan menambahkannya lagi
ke 399. Satu warning deprecation TestClient/Starlette yang sudah ada tetap
dilaporkan. Bukti rekonsiliasi: `audit_minor_fix_test_reconciliation.json`.

## 6. Real Integration

PostgreSQL 14.19 proyek yang sudah berjalan dipakai ulang; test schema PASS.
Kasus `test_phase4_real_controller_two_rounds_v3_postgres_tcp` lulus di run399
yang sama, bukan completion independen kedua: controller produksi → Uvicorn TCP
→ engine asli → v3 CPU → PostgreSQL. Seed42:23aksi,3Chi,Zimo25fan;
seed43 dengan bunga:23aksi,Chi/Peng,draw. Save/read/reuse/delete, fase post-meld,
turn/action IDs dan bobot runtime identik sebelum/sesudah terverifikasi.

Checkpoint SHA-256:
`ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`.
Metadata SHA-256:
`84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e`.
Model aktual `discard_mlp_flexible_v1:ad05a5b2ce37` berhasil dimuat sebelum tes.
Tidak ada retraining/fallback atau perubahan metrik retrospektif64.35%/86.55%.

CUA browser aktual: game seed42/seat1, predict/save Top3, discard W5 turn4→17,
highlight lama hilang, Chi T2/T3/T4 turn17→20, post-meld predict dan Detail
History dengan tabel/dua JSON tertutup berhasil. Browser smoke tidak diberi
payload malformed; pengujian defensive dilakukan hanya dalam Node fixture.
Screenshot/JSON baru memakai prefix `audit_minor_fix_browser`. Preview task
sudah dihentikan dan tab ditutup; cluster PostgreSQL awal tetap berjalan.

## 7. Source and Data Integrity

Produksi: hanya `app/static/phase4/controller.mjs` (+4 baris). Tes: hanya append
14kasus pada `tests/frontend/controller.test.mjs`. Tiga dokumen wajib dan
inventory mendapat append terpisah; tidak mengubah isi historisnya.
Manifest36file lama tetap historis: controller/test sengaja memiliki hash baru,
34 file lain identik. Semua 1.999 file protected, checkpoint/metadata, engine,
encoder, FastAPI, datasets dan evidence lama tetap identik. Semua 11 record dev
identik per-row dan agregat UTC; schema test tidak berubah.

Fingerprint dev:
`d153bfcc7c9e9695d9ce1c71f933aae7133ce6577cd315beaed5bfdfff5028b7`.
Lihat `audit_minor_fix_source_deltas.json`, `audit_minor_fix_postgres.json`, dan
`audit_minor_fix_verification.json` untuk checksum aktual/delta yang disengaja.
Syntax 9 file JavaScript dan compile 5 file Python lulus; pip check tidak menemukan
dependency rusak (hanya warning cache host). `git diff --check` lulus.

## 8. Git State

Branch `main`, HEAD `263fd88c83df417de53051d6ab0127c9a544a8c4`, tidak berubah.
Hitungan final/path tersimpan di `audit_minor_fix_verification.json` dan append
inventory. Working tree sengaja tidak bersih. Staged0; tidak ada add,commit,
push,reset,checkout,clean,stash,merge,rebase atau deployment.

## 9. Remaining Caveats

Tetap berlaku dari Phase4: roster Contact belum terverifikasi, PDF UAS/video
belum dibuat, clean install/platform/browser/perangkat mobile fisik belum
diuji ulang, zoom200% dan reduced-motion runtime belum terverifikasi, tidak ada
audit WCAG penuh. Identitas anonim, active game in-memory dan single worker
tetap merupakan arsitektur yang sama. Caveat ini bukan akibat A01/A02.

## 10. Final Recommendation and Independent Review

Kedua temuan siap ditutup dan dilanjutkan ke audit post-fix atau milestone
commit lokal setelah otorisasi Git terpisah. Paket akhir UAS belum lengkap.

Fresh second-context reviewer `/root/phase4_minor_audit_review`,astra/high,
read-only: **tidak ada Critical/Important/Minor findings**. Reviewer membaca diff
empat baris, controller,14kasus baru serta fixtures dan menjalankan ulang44tes
controller:44passed,0failed. Reviewer menyatakan kedua temuan siap ditutup
dalam scope sempit ini. Backend correctness, hasil full suite dan browser smoke
tidak direverifikasi independen oleh reviewer; bukti eksekusi author dipisahkan.
Tidak ada perubahan file atau delegasi reviewer tambahan.

### Appendix — nama seluruh regresi baru

- P4-A01 rejects cross-game action success and reconciles only the original game
- P4-A01 rejects regressed turn action success and reconciles only the original game
- P4-A01 rejects missing object action success and reconciles only the original game
- P4-A01 rejects noninteger turn action success and reconciles only the original game
- P4-A01 rejects invalid structure action success and reconciles only the original game
- P4-A01 failed reconciliation keeps the original action outcome uncertain and blocks another mutation
- P4-A01 accepts valid advancing response without action retry or reconciliation GET
- P4-A01 accepts valid same turn response without action retry or reconciliation GET
- P4-A01 accepts valid finished response without action retry or reconciliation GET
- P4-A01 accepts valid claim transition response without action retry or reconciliation GET
- P4-A02 rejects ascending Top3 without sorting, trusting a save, or playing
- P4-A02 rejects incorrect action/class mapping without sorting, trusting a save, or playing
- P4-A02 accepts valid descending Top3 unchanged
- P4-A02 accepts equal adjacent scores unchanged
