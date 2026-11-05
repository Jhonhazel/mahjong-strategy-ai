# Inventaris Phase 3

Tanggal: 5 November 2026 (Asia/Jakarta). Seluruh perubahan tetap di working tree; tidak di-stage/commit.

Tracked modified: **4**. Untracked (Git, berkas individual): **114**. Scope Phase3: **117** berkas; source/config/test + empat perubahan tracked: **45**.

## Source, tests dan konfigurasi

| Status | Berkas | Fungsi |
|---|---|---|
| New | `.env.example` | Invalid placeholders and documented MAHJONG_* settings; no real secrets |
| Modified | `.gitignore` | Ignore cluster/SQL exports; allow only the example env file |
| Modified | `README.md` | Local setup, API/session usage, artifact policy, reproduction and handoff |
| New | `app/db.py` | SQLModel table, PostgreSQL engine, explicit schema bootstrap and semantic readiness |
| New | `app/domain/predictions.py` | Immutable observed prediction snapshot and invariant error |
| New | `app/main.py` | FastAPI factory/lifespan/resources/routes and sanitized errors |
| New | `app/services/prediction_history_service.py` | Owned JSONB CRD, immutable idempotent save, row lock and transactions |
| New | `app/services/web_prediction_service.py` | Real engine→v3→DB composition under a game lease with legality/state checks |
| New | `app/settings.py` | Typed PostgreSQL/secret/assets/limits/single-worker configuration |
| New | `app/static/phase3.css` | Basic responsive accessible page styling |
| New | `app/static/phase3.js` | Real JSON game controls, explicit human action and stale recommendation clearing |
| New | `app/templates/base.html` | Jinja base page/layout; escaped data and actual API/history controls |
| New | `app/templates/contact.html` | Jinja contact page/layout; escaped data and actual API/history controls |
| New | `app/templates/game.html` | Jinja game page/layout; escaped data and actual API/history controls |
| New | `app/templates/history.html` | Jinja history page/layout; escaped data and actual API/history controls |
| New | `app/templates/history_detail.html` | Jinja history_detail page/layout; escaped data and actual API/history controls |
| New | `app/templates/home.html` | Jinja home page/layout; escaped data and actual API/history controls |
| New | `app/web/__init__.py` | Web integration package boundary |
| New | `app/web/api.py` | Health/session/game/prediction/history JSON routes and documented cookie/CSRF dependencies |
| New | `app/web/contact.py` | Bounded configurable verified member roster; empty default |
| New | `app/web/documentation.py` | Generated Swagger/ReDoc with documentation-only CSP |
| New | `app/web/errors.py` | Safe HTTP boundary error representation |
| New | `app/web/games.py` | Bounded owner registry, leases/per-game locks/expiry and accepted-meld phase annotation |
| New | `app/web/pages.py` | Jinja page routes, owned history and CSRF form deletion |
| New | `app/web/runtime.py` | Exact promoted v3/metadata SHA verification and cached CPU initialization |
| New | `app/web/schemas.py` | Strict request and explicit public response DTOs |
| New | `app/web/security.py` | Signed visitor cookie, CSRF/origin validation and bounded-body/security headers |
| New | `app/web/views.py` | Public-state and owned-history allowlist serialization |
| New | `config/contact_members.example.json` | Unverified empty roster structure; no invented identities |
| Modified | `requirements-lock.txt` | Actual installed 41-package lock |
| Modified | `requirements.txt` | Direct web/database dependency pins; existing ML versions retained |
| New | `scripts/demo_backend.py` | Two-round actual engine/v3/PostgreSQL/HTTP acceptance and restart proof |
| New | `scripts/init_db.py` | Explicit non-destructive table initialization |
| New | `scripts/phase3_db.py` | Marker-protected socket-only cluster and bounded verified exclusive export/new-DB restore |
| New | `scripts/run_backend.py` | Supported single-worker Uvicorn runner |
| New | `tests/phase3_support.py` | Dedicated real PostgreSQL fixtures with namespace/marker guards |
| New | `tests/test_phase3_bootstrap.py` | Phase3 bootstrap regression cases (real boundaries where required) |
| New | `tests/test_phase3_concurrency.py` | Phase3 concurrency regression cases (real boundaries where required) |
| New | `tests/test_phase3_database_tools.py` | Phase3 database_tools regression cases (real boundaries where required) |
| New | `tests/test_phase3_documentation.py` | Phase3 documentation regression cases (real boundaries where required) |
| New | `tests/test_phase3_end_to_end.py` | Phase3 end_to_end regression cases (real boundaries where required) |
| New | `tests/test_phase3_history.py` | Phase3 history regression cases (real boundaries where required) |
| New | `tests/test_phase3_http.py` | Phase3 http regression cases (real boundaries where required) |
| New | `tests/test_phase3_pages.py` | Phase3 pages regression cases (real boundaries where required) |
| New | `tests/test_phase3_security.py` | Phase3 security regression cases (real boundaries where required) |

## Dokumentasi dan sumber persyaratan

`docs/phase3_implementation_report.md`: laporan20 bagian, API/schema, hasil nyata, UAS dan handoff.
`docs/phase3_execution_ledger.md`: keputusan, RED/GREEN, interruption/resume dan hasil final.
`docs/superpowers/{specs,plans}/2026-11-05-mahjong-phase3*.md`: desain/rencana yang dipertahankan.
`docs/reference/SOAL UAS PEMROGRAMAN WEB FRAMEWORK.pdf`: referensi resmi dari pengguna, dibaca saja.
`docs/evidence/phase3/code_review.md`: dua review independen dan closure executor.

## Seluruh berkas scope yang terlihat Git

Daftar ini mencakup source di atas, laporan, referensi, artefak kecil dan raw evidence. RED/failure historis tetap disimpan dengan nama/hasil aslinya.

- `.env.example`
- `.gitignore`
- `README.md`
- `app/db.py`
- `app/domain/predictions.py`
- `app/main.py`
- `app/services/prediction_history_service.py`
- `app/services/web_prediction_service.py`
- `app/settings.py`
- `app/static/phase3.css`
- `app/static/phase3.js`
- `app/templates/base.html`
- `app/templates/contact.html`
- `app/templates/game.html`
- `app/templates/history.html`
- `app/templates/history_detail.html`
- `app/templates/home.html`
- `app/web/__init__.py`
- `app/web/api.py`
- `app/web/contact.py`
- `app/web/documentation.py`
- `app/web/errors.py`
- `app/web/games.py`
- `app/web/pages.py`
- `app/web/runtime.py`
- `app/web/schemas.py`
- `app/web/security.py`
- `app/web/views.py`
- `artifacts/phase3/api_examples.json`
- `artifacts/phase3/backend_contract.json`
- `artifacts/phase3/database_verification.json`
- `artifacts/phase3/database_verification_complete.json`
- `artifacts/phase3/database_verification_final.json`
- `artifacts/phase3/end_to_end_complete.json`
- `artifacts/phase3/end_to_end_demo.json`
- `artifacts/phase3/end_to_end_final.json`
- `artifacts/phase3/environment_final.json`
- `artifacts/phase3/environment_recovery.json`
- `artifacts/phase3/final_checks.json`
- `artifacts/phase3/final_temporary_cleanup.json`
- `artifacts/phase3/final_test_scratch_recovery.json`
- `artifacts/phase3/git_verification.json`
- `artifacts/phase3/model_integration_verification.json`
- `artifacts/phase3/network_browser_verification.json`
- `artifacts/phase3/network_complete.json`
- `artifacts/phase3/preflight.json`
- `artifacts/phase3/preservation_manifest.json`
- `artifacts/phase3/preservation_verification.json`
- `artifacts/phase3/regression_case_reconciliation.json`
- `artifacts/phase3/runtime_asset_verification.json`
- `artifacts/phase3/session_isolation_verification.json`
- `artifacts/phase3/shutdown_verification.json`
- `artifacts/phase3/uas_reference_verification.json`
- `artifacts/phase3/verification_summary.json`
- `config/contact_members.example.json`
- `docs/evidence/phase3/baseline.txt`
- `docs/evidence/phase3/baseline.xml`
- `docs/evidence/phase3/baseline_recovered.txt`
- `docs/evidence/phase3/baseline_recovered.xml`
- `docs/evidence/phase3/bootstrap_green.txt`
- `docs/evidence/phase3/bootstrap_red.txt`
- `docs/evidence/phase3/code_review.md`
- `docs/evidence/phase3/concurrency_tests.txt`
- `docs/evidence/phase3/database_tools_green.txt`
- `docs/evidence/phase3/dependency_install.txt`
- `docs/evidence/phase3/dependency_resolution.txt`
- `docs/evidence/phase3/end_to_end_green.txt`
- `docs/evidence/phase3/end_to_end_red.txt`
- `docs/evidence/phase3/final_checks.txt`
- `docs/evidence/phase3/focused_complete.txt`
- `docs/evidence/phase3/focused_complete.xml`
- `docs/evidence/phase3/focused_final.txt`
- `docs/evidence/phase3/focused_final.xml`
- `docs/evidence/phase3/full_regression_complete.txt`
- `docs/evidence/phase3/full_regression_complete.xml`
- `docs/evidence/phase3/full_regression_final.txt`
- `docs/evidence/phase3/full_regression_final.xml`
- `docs/evidence/phase3/git_status_final.txt`
- `docs/evidence/phase3/history_green.txt`
- `docs/evidence/phase3/history_red.txt`
- `docs/evidence/phase3/http_green.txt`
- `docs/evidence/phase3/http_red.txt`
- `docs/evidence/phase3/pages_green.txt`
- `docs/evidence/phase3/pages_red.txt`
- `docs/evidence/phase3/phase_annotation_red.txt`
- `docs/evidence/phase3/postgres_start.txt`
- `docs/evidence/phase3/resumed_review_green.txt`
- `docs/evidence/phase3/resumed_review_green.xml`
- `docs/evidence/phase3/resumed_review_red.txt`
- `docs/evidence/phase3/review_fixes_green.txt`
- `docs/evidence/phase3/review_fixes_green.xml`
- `docs/evidence/phase3/review_fixes_red.txt`
- `docs/evidence/phase3/schema_type_red.txt`
- `docs/evidence/phase3/security_green.txt`
- `docs/evidence/phase3/security_red.txt`
- `docs/phase3_execution_ledger.md`
- `docs/phase3_file_inventory.md`
- `docs/phase3_implementation_report.md`
- `docs/reference/SOAL UAS PEMROGRAMAN WEB FRAMEWORK.pdf`
- `docs/superpowers/plans/2026-11-05-mahjong-phase3.md`
- `docs/superpowers/specs/2026-11-05-mahjong-phase3-design.md`
- `requirements-lock.txt`
- `requirements.txt`
- `scripts/demo_backend.py`
- `scripts/init_db.py`
- `scripts/phase3_db.py`
- `scripts/run_backend.py`
- `tests/phase3_support.py`
- `tests/test_phase3_bootstrap.py`
- `tests/test_phase3_concurrency.py`
- `tests/test_phase3_database_tools.py`
- `tests/test_phase3_documentation.py`
- `tests/test_phase3_end_to_end.py`
- `tests/test_phase3_history.py`
- `tests/test_phase3_http.py`
- `tests/test_phase3_pages.py`
- `tests/test_phase3_security.py`

## Artefak lokal penting yang tetap ignored

- `artifacts/models/mahjong_discard_mlp_v3.pt`: weights asli, SHA pinned; tidak di-force-add.
- `artifacts/transfer/mahjong_discard_mlp_v3_inference.tar.gz`: bundle transfer lama; prosedur checksum di docs/ml_artifact_transfer.md.
- `artifacts/phase3/prediction_history_complete.sql`: ekspor final88.936 byte,11 rows, restore identik; hash pada database_verification_complete.json.
- Ekspor Phase3 sebelumnya tetap ada dengan filename berbeda; bukan bukti final pengganti.
- `.local/phase3-postgres/`: cluster/socket/receipts dan dedicated dev/test/restore DBs; proses sudah dihentikan, data dipertahankan.
- `.venv/`, corpus/raw archives/shards, checkpoints/optimizer state dan temporary caches tetap di luar Git.

## Berkas tidak terkait

`docs/.DS_Store` adalah metadata Finder untracked, dibiarkan dan tidak dimasukkan scope implementasi. Tidak ada staging operation.

## Verifikasi inventaris

Status lengkap: docs/evidence/phase3/git_status_final.txt. Ringkasan: artifacts/phase3/git_verification.json.
Empat tracked modifications diperiksa secara eksplisit; seluruh1.868 prior protected files tetap identik. Source lama dan tests lama tidak diubah.


## Finalisasi P3-01 dan scope commit lokal yang diotorisasi

Inventaris117 berkas di atas adalah snapshot historis359 kasus. Permintaan baru
menambahkan24 berkas bukti finalisasi dan memperbaiki dua source/test yang sudah
ada; total calon scope commit **141 berkas**, termasuk45 berkas source/config/test
yang sudah diinventarisasi. Hanya app/web/security.py dan
tests/test_phase3_security.py berubah khusus untuk P3-01; empat dokumen memperoleh
append tanpa menimpa hasil lama. Full terbaru370/370; Phase3 focused91/91.

Bukti baru yang ditinjau:

- `artifacts/phase3/finalization_preflight.json`
- `artifacts/phase3/finalization_preservation_after.json`
- `artifacts/phase3/finalization_preservation_before.json`
- `artifacts/phase3/finalization_staging_review.json`
- `artifacts/phase3/security_fix_checks.json`
- `artifacts/phase3/security_fix_dev_history_before.json`
- `artifacts/phase3/security_fix_game_model_comparison.json`
- `artifacts/phase3/security_fix_model_preservation.json`
- `artifacts/phase3/security_fix_observed_after.json`
- `artifacts/phase3/security_fix_observed_before.json`
- `artifacts/phase3/security_fix_postgres_verification.json`
- `artifacts/phase3/security_fix_test_reconciliation.json`
- `artifacts/phase3/security_fix_verification.json`
- `docs/evidence/phase3/full_regression_security_fix.txt`
- `docs/evidence/phase3/full_regression_security_fix.xml`
- `docs/evidence/phase3/security_fix_affected.txt`
- `docs/evidence/phase3/security_fix_affected.xml`
- `docs/evidence/phase3/security_fix_checks.txt`
- `docs/evidence/phase3/security_fix_focused.txt`
- `docs/evidence/phase3/security_fix_focused.xml`
- `docs/evidence/phase3/security_fix_green.txt`
- `docs/evidence/phase3/security_fix_green.xml`
- `docs/evidence/phase3/security_fix_red.txt`
- `docs/evidence/phase3/security_fix_source.diff`

Pemeriksaan ukuran/content/secret/policy dan explicit allowlist dicatat pada
`artifacts/phase3/finalization_staging_review.json`. Tidak ada unrestricted git add.
Lima .DS_Store dan empat ZIP backup tetap untracked dan tidak disentuh. Model
weights, SQL exports, cluster/socket, environments/caches/corpus tetap ignored
dan tidak di-force-add. Actual staged names/content diperiksa ulang sebelum
commit; actual SHA dan status sesudah commit dibaca dari Git/final response.
