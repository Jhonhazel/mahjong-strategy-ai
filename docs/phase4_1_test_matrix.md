# Phase 4.1 — test matrix

Semua hasil di bawah berasal dari run baru 6 November 2026. Log gagal tetap
tersimpan sebagai evidence pengembangan; gunakan `full_regression_final.xml`
untuk verdict akhir. Env integrasi: PostgreSQL project `_test`, real frozen v3,
Node24.4.1, Python3.12.10.

| Kriteria | Bukti | Hasil |
|---|---|---|
| Root entry/factory/no import DB/model; legacy runner config | `tests/test_phase4_1.py` | PASS |
| Exact CLI port8000 + readiness/pages/OpenAPI | `artifacts/phase4_1/cli_smoke.json` | Semua200 |
| Legacy runner actual port8875 | `artifacts/phase4_1/legacy_runner_smoke.json` | Ready200, stopped |
| Public deltas, prefix/claimed river, hidden AnGang | `tests/frontend/playback.test.mjs` | PASS |
| 600/180ms, skip, reduced motion/hidden, cancellation | File Node yang sama | PASS, fake scheduler |
| Busy authoritative view, no duplicates, create/refresh/expiry | File Node yang sama | PASS |
| Five exact identities/no roles; missing/unverified fallback | `tests/test_phase4_1.py` | PASS |
| Contact escaping/security | Original Phase3/4 tests | PASS, assertions keamanan tetap |
| P4-A01/A02 guards | Original controller Node regressions | PASS, semua80 kasus lama tetap |
| TDD RED | `features_red.txt`, `playback_red.txt` | Python3fail/3pass; Node11fail |
| TDD GREEN | `features_green.xml`, `playback_green.txt` | Python6pass; Node18pass incl view |
| Baseline segar | `baseline.xml`, `node_baseline.txt` | Python399pass; Node80pass |
| Final penuh | `full_regression_final.xml`, `node_full.txt` | Python405pass, Node91pass; 0fail/error/skip |
| All historical identities | `artifacts/phase4_1/integrity.json` | 399Python/80Node preserved |
| PG isolation/CSRF/race/rollback/docsCSP/schema/exportrestore | Existing Phase3/4 tests in final JUnit | PASS; no integration skips |
| Two real TCP rounds + v3 + PG | `artifacts/phase4_1/round_acceptance.json` | Seed42/43 selesai,6prediksi, weights equal |
| Browser real UI round/predictions/Normal/Cepat/Skip/history | `artifacts/phase4_1/browser.json` | 23aksi selesai; controls disabled saat playback |
| Game+Contact five widths | JSON browser +4JPG | 10/10 tanpa document overflow |
| Engine/datasets/frozen model preservation | `integrity.json` | 0unexpected changes |
| Dev record preservation/schema | `postgres_after.json`, `schema.json` | 23records identical; dev/test PASS |
| Dependencies/static syntax | `static_checks.json`, `dependency_delta.json` | PASS; 0existing version changes |
| Fresh independent source review | `independent_review.md` | 0Critical/Important/Minor; Node11pass |
| Git hygiene | `git_final.json`, `git_final.txt` | No mutation, staged0, dirty tree reported |

Evidence paths without prefixes in this table are under `docs/evidence/phase4_1/`.
Source changes to two original Contact assertions are requirement migrations;
their names remain intact. Extra Python wrapper invokes11Node cases, so405+91
is not a count of entirely independent checks.

Not run: clean install, Windows/Linux, actual200%zoom, runtime reduced-motion
emulation, physical mobile and complete assistive-technology audit. Group roles,
final PDF/video and final packaging remain submission work.
