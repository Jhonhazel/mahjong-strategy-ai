# Phase 3 implementation plan

Approved scope: user's complete Phase3 request; design in the sibling specs file.
Execute inline, TDD, one final fresh reviewer. Do not pause for approval ceremonies
or Git/worktree steps: the user explicitly authorized end-to-end implementation
and prohibited Git mutations. Preserve older evidence/checkpoints/tests.

## Tasks and interfaces

1. **Preflight** (completed): clean main/b9821fd; hash prior assets; verify explicit
   v3 SHA/model contract; baseline279 passed66.77s after isolated scratch recovery.
2. **Local PostgreSQL tooling**: new `scripts/phase3_db.py`, project-owned marker,
   init/start/stop/url/export/restore operations; no drops, unknown directories or
   unrelated database targets. Test URL uses dedicated `_test` database. Verify
   real version/connectivity, later pg_dump plus restore into a fresh database.
3. **Settings/runtime RED→GREEN**: `app/settings.py`, `app/web/runtime.py`;
   `Settings` validates required secret, PostgreSQL URL, bounded limits, single
   worker and repository-relative assets. `load_runtime_model(settings)` returns
   the existing AI service and verified metadata. Tests prove missing/invalid
   settings and wrong/missing/corrupt v3/metadata/encoder fail; no dataset shards.
4. **Persistence RED→GREEN**: `app/db.py` defines `PredictionResult`, engine/schema
   functions. `app/services/prediction_history_service.py` exposes save/list/get/
   delete owned operations. Real PostgreSQL tests cover JSONB/UTC/schema/unique
   idempotency, pagination, owner isolation, failed commit rollback and restart.
5. **Web security/coordination RED→GREEN**: `app/web/security.py`, `games.py`,
   `schemas.py`, `views.py`; signed anonymous context + CSRF;16 KiB body middleware;
   `OwnedGames` bounded leases/per-game serialization/TTL; explicit safe view
   response. Tests reject missing/forged/expired identities, cross-owner IDs,
   invalid/oversized input and hidden fields; game capacity/idle expiry is bounded.
6. **Factory/routes RED→GREEN**: `app/main.py:create_app(settings=None)`,
   `app/web/api.py`, `app/services/web_prediction_service.py`. Lifespan checks
   schema/assets then publishes singleton services; sync routes call real legacy
   games and AI. Test complete create/read/action/predict/history flows, wrong
   turns and illegal actions, real input/output snapshot, read-only prediction,
   duplicate prediction/action, concurrent predict/action and cross-game progress.
7. **Pages RED→GREEN**: `app/web/pages.py`, `app/templates/*`, `app/static/*`,
   `config/contact_members.example.json`; functional Home/Contact/History/Game,
   safe rendering and protected deletion redirect. Game JS uses actual endpoints,
   legal options and expected turn tokens. No polished board/animations.
8. **CLI/evidence**: schema and single-worker run commands; real HTTP full round
   with SELF_TURN/POST_MELD when reachable, direct before/after arrays/view/weights,
   actual PostgreSQL rows/read/delete, history after restart; SQL export and
   restore to a separate new disposable database. Save only actual results.
9. **Independent review and final**: fresh reviewer, one Important/Critical fix
   pass RED→GREEN plus full suite. Check preservation, syntax, import/version,
   diff safety; OpenAPI/schema/example artifacts; Indonesian20-section report,
   file inventory, Phase4 contract, UAS matrix and explicit unresolved content.

## Review Focus

- Forged/expired/missing cookies and CSRF on JSON/forms must not create identity
  implicitly for mutation or reveal another owner's game/history.
- Long/failed DB operations and idle expiry during predict/action must preserve
  one consistent turn without blocking unrelated games or leaking registry locks.
- Duplicate persistence, failed commit and deletion races must not return a false
  saved result; JSONB/UTC/owner predicates and constraints must be verified in PG.
- Startup must reject wrong model/schema, close partial resources and never load
  per request; readiness must fail safely on DB loss without secrets or inference.
- Chunked oversized input, unsafe member text and full-round serialization must
  retain body bounds, escaping and strict public-state allowlists, including final
  result fields; SQL restore must never target an existing/unrelated database.

For every behavior task: add focused failing tests, observe the intended RED,
implement minimal GREEN, rerun focused tests. Final test collection is dynamic;
never edit older tests or their frozen JUnit files to make new counts pass.
