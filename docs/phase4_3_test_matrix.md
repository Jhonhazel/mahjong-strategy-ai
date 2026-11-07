# Phase4.3 test matrix — 6 November2026

| Gate | Actual result | Evidence |
|---|---|---|
| Fresh baseline |437Python passed,0failed/errors/skipped,65.87s;91Node passed | `docs/evidence/phase4_3/baseline.xml`, `node_baseline.txt` |
| Focused review GREEN |66 passed,0failed/skipped,1.68s (34new Phase4.3 +32 Phase4.2) | `review_focused_green.xml` |
| Full final Python |471 passed,0failed/errors/skipped,69.03s; one existing Starlette/httpx deprecation | `full_regression_review_final.xml`, matching.txt |
| Final Node |91 passed,0failed/cancelled/skipped,144.758125ms | `node_final.txt` |
| Historical case identity |All279 Phase2.2 and437 Phase4.2/fresh baseline cases present and passing | `artifacts/phase4_3/preservation_regression.json` |
| Real PostgreSQL integration |Actual isolated project testPG; history/ownership/transactions/concurrency/CSRF/schema and SQL dump/restore tests executed, no skips | finalJUnit; `tests/test_phase3*.py` |
| Two complete rounds |Existing real two-round v3/PG/restart test executed and passed; seeds42/43, SELF_TURN+POST_MELD_DISCARD, immutable weights, finished states | finalJUnit: `test_real_two_round_web_model_postgres_workflow_and_restart` |
| Exported container build |Fresh runtime-only ZIP extraction; actual web/PG/Caddy built/started, CPUv3 and private DB | staging build/bootstrap/up GREEN evidence |
| Verified local TLS |HTTPS hostname/chain validated using taskCA public cert only; nine page/asset/docs200 with CSP/nosniff; Secure/HttpOnly/Lax cookie | `https_acceptance.json`, `production_staging.json` |
| Online flow |23legal actions/20Play3Chi, zimo25fan,2real v3 predictions, read-only/reuse, history/table/delete204→404 | `production_staging.json` |
| Origin/host/proxy |Missing/wrong CSRF403; foreign game/prediction404; wrongHost400; spoofed forwarded values ignored; direct untrusted forwarded403 | `production_staging.json` |
| Restart |Same cookie retained PG history; active game404; readiness2.57213425s | `production_staging.json` |
| TTL |Temporary2s setting,200→404 after2.3s; shipped3600s default restored | `expiry_cleanup.json` |
| Browser |Actual in-app Chromium, localhostHTTP preview only; prediction before/afterChi, History detail table, refresh, Home and five Contact cards, Normal/Fast/Skip | `browser.json`, desktop/mobilePNG |
| Responsive |Measured viewport/document width1440/1440 and390/390 (no horizontal page overflow); screenshots visually inspected | browser evidence |
| Windows cross-platform units |19launcher/build/provenance/ZIP/ownership/cleanup cases executed on Mac, included in34new total | focused/finalJUnit |
| Actual Windows runtime |**NOT RUN**; VBox reports0registered/0runningVMs; no executable/package built | `windows_environment_probe.json`, `windows/README_BUILD.md` |
| Public external HTTPS/network |**NOT RUN / NOT AUTHORIZED**; no URL | deployment handoff |
| Preservation |2257 original eligible files:2252identical,5intended changes,0missing;44DEV rows per-ID hashes identical;4historic delivery files identical;3frozen assets exact | `preservation_regression.json` |
| Cleanup |Task Compose web/db/Caddy exited, volumes retained; temporaryHTTP preview removed; originals untouched | `expiry_cleanup.json` |
| Source ZIP verification |All members/manifest/hashes/source correspondence/assets/exclusions verified | `artifacts/phase4_3/release_verification.json` |

Paths for short evidence names are under `docs/evidence/phase4_3/` for text/XML/PNG
and `artifacts/phase4_3/` for JSON. Initial RED outputs are retained deliberately;
final PASS evidence is the review-final XML, not an earlier failing log.

## Reproduce final regression in the established local test environment

From the repository root, using the existing private cluster/venv (not a lecturer
machine), set the non-secret dedicated test URL and choose a NEW evidence filename:

```sh
MAHJONG_TEST_DATABASE_URL='postgresql+psycopg://mahjong_phase3@/mahjong_phase3_test?host=%2FUsers%2Fjhonhazel%2Fmahjong-strategy-ai%2F.local%2Fphase3-postgres%2Fsocket&port=55437' .venv/bin/python -m pytest -q --junitxml=docs/evidence/phase4_3/full_regression_next.xml
node --test tests/frontend/*.test.mjs
```

Production staging: follow `deploy/README.md`; native Windows future-gate commands
and25scenario acceptance checklist are in `windows/README_BUILD.md` and the supplied
requirements. Do not use test credentials/database configuration for publication.
