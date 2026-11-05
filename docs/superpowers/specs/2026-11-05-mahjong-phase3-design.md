# Phase 3 backend design

Authority: the user's Phase 3 master request, supplied 2026-11-05. Execute the
complete local vertical slice; no Git mutations, deployment, retraining, rule
changes or polished Phase 4 board. The supplied coursework requirements are the
working brief: the original PDF is outside this Mac repository. The user
confirmed that no group roster/roles are verified; Contact must remain explicitly
incomplete and configurable, including no inferred membership for a known name.

## Design decisions

- Add a FastAPI application factory/lifespan, synchronous HTTP handlers and
  short-lived SQLModel sessions. Existing game, observer, encoding, masking and
  prediction implementations remain byte-identical. Load the explicitly pinned
  v3 model once, on CPU, using its metadata and small contract. Startup fails
  closed for wrong/missing assets, unavailable PostgreSQL or incompatible schema.
- Use one SQLModel `prediction_results` table with UUID key, derived owner key,
  game/turn/phase, JSONB observed input and output, model/encoder/checkpoint
  identity, state digest and UTC creation time. Immutable state snapshots come
  solely from the server's `EncodedTurnState`. No referee/wall/private opponent
  state is serialized. PostgreSQL enforces unique owner/game/turn/model/digest;
  conflict handling returns the existing record. Owner + creation + ID supports
  deterministic bounded pagination. Each persistence operation commits or rolls
  back its own session; a failed save returns503 rather than a saved response.
- A small signed-cookie visitor context holds random identity/CSRF nonce only.
  Owner keys derive from the signing secret; stable secret and cookie preserve
  history ownership across application restarts. Expired/invalid cookies cannot
  mutate. Every mutation requires the CSRF token; cross-owner resources return
 404. HttpOnly/SameSite cookies, optional HTTPS Secure, trusted hosts, same-origin
  checks and a16 KiB body cap bound the web boundary. No CORS or account system.
- An ownership registry tracks bounded entries, leases, idle TTL and one lock per
  game. Predict/action share the lock through database commit. Global bookkeeping
  locks are released before model/database/game work. The registry handles idle
  expiration; legacy active idle expiry is disabled through its constructor
  parameter so another game's sweep cannot evict an in-flight prediction. The
  existing finished-game30s retention remains and is documented. No engine or
  scoring implementation is duplicated.
- Expose health live/ready; session/CSRF initialization; create/read/action/predict
  game endpoints; owner-filtered prediction list/detail/delete. Strict schemas
  reject client tensors and extra fields. Game responses explicitly map allowed
  `PublicPlayerView` fields and omit revealed opponent hands even in final results.
  Predictions never execute an action. Historical v3 scores are labelled as
  retrospective discard imitation, not win probability or new blind testing.
- Add basic Jinja2 Home/Contact/History/Game pages. JSON-backed game controls use
  legal action IDs and turn tokens; history deletion uses a protected POST form
  and redirect. Jinja escaping stays enabled; JS uses textContent for server data.
  Contact configuration initially contains no members and an incomplete notice.
- Initialize schema explicitly with create-if-missing only; never drop or migrate
  existing data automatically. Readiness checks actual PostgreSQL/schema, without
  reloading or rerunning the model. Single worker only; active games end on restart,
  while persistent history survives. Provide local run, schema, SQL dump and
  non-destructive restore-to-new-database commands.

## Environment and verification

Initial clean main/b9821fd.1,868 existing files protected by new Phase3 hashes.
Initial baseline failed due to the existing1 GiB disk reserve. Only inactive,
verified project pytest scratch101/102 was removed; no model/corpus/frozen evidence.
Unmodified baseline then passed279 tests in66.77s. Future test runs use disposable
temporary contexts. Existing PostgreSQL14.19 tools permit a fresh, project-owned,
Unix-socket-only cluster, separate demo/test/restore databases, private socket
permissions and no changes to existing PostgreSQL instances or credentials.

Use real PostgreSQL for database tests and a real v3/engine full-round HTTP proof.
Cover session forgery/expiry, CSRF, ownership, state allowlisting, body bounds,
capacity/expiry, duplicate actions, predict/action races, idempotency, rollback,
restart persistence and SQL export/restore. One fresh-context independent review
after implementation; reproduce/fix Important/Critical findings with TDD. Finish
with all old/new regressions, preservation hashes, OpenAPI examples,20-section
Indonesian report, inventory and a qualified Phase4 handoff.

API conventions follow [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[SQLModel session boundaries](https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/),
[PostgreSQL conflict handling](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert)
and [isolated initdb](https://www.postgresql.org/docs/14/app-initdb.html).

Completion note2026-11-05: the PDF availability statement above describes
preflight. The user subsequently supplied docs/reference/SOAL UAS PEMROGRAMAN
WEB FRAMEWORK.pdf; both pages were rendered/read. The report maps the actual
requirements; Contact remains unverified as explicitly requested.
