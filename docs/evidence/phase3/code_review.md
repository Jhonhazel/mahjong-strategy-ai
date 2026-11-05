# Independent Phase 3 reviews and executor closure

Two fresh-context, read-only reviews were performed by separate gpt-6-astra
reviewers. Neither changed source, Git, database records or schemas. Their
assessments required fixes; this file separates their findings from the
executor's verified resolutions. No third review or post-fix reviewer approval
is claimed.

## Initial independent review

No Critical findings. Four Important findings:

| ID | Finding | Resolution and observed evidence |
|---|---|---|
| A1 | Reused prediction could be deleted between SELECT and commit | SELECT FOR UPDATE held through commit; real PostgreSQL Event-barrier regression verifies DELETE waits |
| A2 | Arbitrary SQL could escape a fresh restore target | Nonempty 64 MiB cap before reading, bounded read, trusted export checksum receipt, UTF-8/command validation, immutable stdin, transactional restore into new namespace only |
| A3 | Global self-only CSP blocked Swagger/ReDoc | Documentation-only CDN policy and inline bootstrap hashes; general pages retain self-only CSP; both documentation interfaces rendered in the actual browser |
| A4 | Schema readiness trusted CHECK names and any timestamp default | Validate exact types/nullability, now default, CHECK expressions, immediate validated uniqueness and valid backing index |

Initial RED: 15 failed / 3 passed in 3.30s.
Focused GREEN: 25 passed in 3.91s.
See `review_fixes_red.txt` and `review_fixes_green.{txt,xml}`.

Declined to judge: polished UI, deployment, multiple workers, incomplete group
roster and documentation still being written. These are recorded scope/content
limitations, not silently discarded requirements.

## Fresh review requested by the continuation

No Critical findings. Three Important findings plus two originally graded Minor:

| ID | Finding | Executor resolution |
|---|---|---|
| B1 | Export destination could be substituted before checksum attestation; mid-line psql commands were accepted | Capture pg_dump in a project-private temporary directory, validate/hash those bytes, publish with exclusive `xb`, then register only the private-byte digest; reject mid-line backslashes outside COPY |
| B2 | Requested Chi could lose priority yet label the next draw POST_MELD_DISCARD | Require an actual increase in the human's public meld count plus a waiting-discard state; seed44/seat1/action73 regression reaches turn48 with SELF_TURN |
| B3 | Readiness accepted an extra required column, a SELECT-only role or read-only connection | Exact dedicated-table columns, current effective SELECT/INSERT/DELETE/UPDATE privileges, and transaction_read_only=off; isolated real PostgreSQL drift/role fixtures |
| B4 | OpenAPI omitted required cookie and CSRF inputs | Explicit Cookie/Header dependencies with optional parsing to retain server 401/403 behavior; schema and HTTP regressions |
| B5 | Cross-tab Refresh retained a previous turn's recommendation | Clear displayed prediction when game ID or turn changes; actual browser RED turn4→17 retained old suggestion, GREEN turn4→17 cleared it |

The executor promoted B4/B5 into the fix pass because unusable mutation controls
in Swagger and a recommendation attached to the wrong turn affect normal use.
No minor finding was deferred.

Resumed RED: 10 failed / 26 passed in 3.58s (no unsafe SQL executed).
Resumed GREEN: 36 passed in 4.00s.
Final focused suite: 80 passed, 0 failures/errors/skips in 9.34s.
Final complete suite: 359 passed, 0 failures/errors/skips in 73.88s.
Browser/HTTP evidence: `artifacts/phase3/network_complete.json`.
Final JUnit: `full_regression_complete.xml`.

Fresh reviewer declined to judge production/multiple workers, roster accuracy,
in-progress reports and changes after that inspection. Executor ruling: retain
those explicit limitations and close actual code findings with observed
regressions. The final readiness decision concerns local Phase 4 development.

The executor checked final ownership, turn/action legality, read-only prediction,
pinned checkpoint, rollback/locking, sanitization, and non-destructive SQL scope
against the passing full suite and actual demo evidence. No unresolved Critical
or Important finding remains in these two review inventories.


## P3-01 finalization supplied by the user's independent audit

LOW/MINOR: early400 invalid/negative Content-Length and413 declared/streamed
responses bypassed the existing protected send callback. Executor reproduced
5 real missing-header failures before changing production;6 controls passed.
Moved the same wrapper before early returns and used it on all applicable HTTP
paths. Default and explicit docs CSP, statuses/bodies/Connection close, limits,
non-HTTP/disconnect and downstream rejection behavior are preserved.
GREEN11 cases0.19s; affected33 cases2.46s; focused91 cases6.80s;
full370 cases64.30s,0 failure/error/skip. All359 historical identities remain.
See security_fix_red/green/source.diff, full_regression_security_fix XML/TXT,
and artifacts/phase3/security_fix_verification.json. One production file and
one test file changed specifically for P3-01. No unrelated review issue fixed.
This is executor verification of a user-supplied independent finding; no fresh
independent post-fix reapproval is claimed. Prior review outcomes above remain
historical records. Current user explicitly authorizes the local Phase3 commit.
