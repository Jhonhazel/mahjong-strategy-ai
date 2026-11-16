# Minimum recommendation score implementation plan

Goal: one server policy minimum_score0.10 / maximum_suggestions3, preserving the
uncommitted player-friendly revision and all raw model/snapshot/API fields.
User's detailed specification authorizes inline implementation/routine choices;
no design approval/worktree/branch changes, commits, migration or training.

Design: pure shared policy projects the complete34 normalized scores and stored
legal-discard mask to recommendations{suggestions,minimum_score,maximum_suggestions,
status}. Exact >= comparison, stable descending score/class-index ordering, no
renormalization. Invalid distributions fail; no legal discard remains an invalid
prediction phase, distinct from a valid empty filtered result. Raw prediction and
output_snapshot stay exactly as before. Response projection happens on the saved
record for both new/reused predictions and History, so old records require no writes.

Page context publishes server policy for guide/copy and controller consistency.
Frontend validates complete raw/legal distribution plus filtered list/status/scores;
never supplies below-threshold cards or raw recommended_tile fallback. API clients
without page context still validate against response policy; browser pins to the
same server-rendered policy. No duplicate selection rule in templates or renderer.
0–3 cards/highlights, accessible empty success, analysis-saved wording. History
explains current-policy presentation, uses saved data, no reinference.
Model labels86.55% as original unfiltered retrospective evaluation and explains
this is an initial presentation policy, not a proven improvement/winning chance.

Checklist:
- [x] Read actual checkout/source/previous report; preserve initial hashes and DEV;
  fresh baseline Python/Node in new evidence namespace.
- [x] RED pure-policy boundaries/ties/legality/invalid input/no mutation; API/raw
  preservation/empty save+reuse/old History/failed commit; Node validation/render.
- [x] Implement shared policy + additive schemas/projection/context; integrate
  controller/view/templates without weakening legal-action/security checks.
- [x] GREEN focused; read-only validation-cohort policy analysis if local assets
  and established streaming evaluation are available; no test-set optimization.
- [x] Full regression, real PG/v3 and controlled-fixture browser0–3cards at desktop/
  phone; distinguish fixtures from actual checkpoint inference; review finaldiff.
- [x] Update API docs/report/allowlist; new versioned runtime-only package if built;
  final preserve hashes/DEV/previous unrelated changes, stop taskpreview; no Gitmutation.

Review focus: exact0.10 vs0.099999 before formatting; full-distribution denominator;
illegal/malformed responses must error rather than empty; zero visible candidates
must never fall back to raw recommendation in highlights or History; current-policy
projection of old snapshots must not mutate records or claim historical filtering.

Final ledger: preserved dirty branch/head; baseline556Python/94Node. Mainfeature
RED20Python+12Node failures; initialGREEN21Python/14Node. Final586Python/111Node
pass,0failure/error/skip; all556prior Python identities remain. Browser fixture0–3
and realcheckpoint cases distinguished, History identical projection, emptyrecord
keyboardcontinuation/reuse proven. Actual350917internalvalidation decisions:
coverage99.8968%, distribution362/135132/99617/115806, targetinclusion82.4446%all
or82.5297%covered. No optimization/blindtest claim. Independentread-only review
noCritical/Important. DEV98rows unchanged;50protectedsource/asset hashes unchanged;
newruntime-only108filepackageverified. No Gitmutation; taskpreviewstopped.
