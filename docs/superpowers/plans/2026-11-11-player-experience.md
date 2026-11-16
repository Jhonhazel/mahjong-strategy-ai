# Player-focused website revision implementation plan

Goal: Home / Game / History / Contact Us / Model, with player-friendly copy and
no public developer identifiers. Existing FastAPI/Jinja/SVG/ES modules retained.
Spec: user's detailed 11 November 2026 request. Execute routine choices inline;
no further design approval/worktree/commit ceremony, as explicitly requested.
Work in the authorized development branch codex/player-friendly-pages. No commits.

Design: split Home's existing academic section into a dedicated Model template,
rewrite explanations in six connected stages, keep verified metadata and summary
internally. Top3 is the only accuracy headline; MacroF1 retains its original
class-prediction definition. Initial partition chart uses the three ordinary
corpus partitions, renormalized after excluding the legacy holdout, and labels
approximately80/10/10; final train/validation approximately80/20 described separately.
All tile charts use actual train supports converted to percentages. No public counts,
fold/experiment/seed/version/hash/JSON. Source artifact remains unchanged.

Game: guide before setup, available throughout round; keep seat/wind/flowers,
remove seed/speed/action dropdown and debug panels. Tile and claim selection still
use server-supplied actions and confirmation. Remove stale DOM handlers/rendering;
normal playback and skip/reduced-motion/cancel remain. Preserve API/controller
idempotency/legality/concurrency. Hide metadata from advice and History HTML only;
JSON API, snapshots, old model_version and data remain unchanged. Contact preserves
configured official identities, hides roles and role-driven incomplete notice.

Checklist:
- [x] Inspect and snapshot clean checkout, protected assets and DEV; fresh baseline.
- [x] RED Python and Node tests for new routes, navigation, public content boundaries,
  percent-only charts, absent controls/handlers, all claims, saved History and roles.
- [x] Implement templates/pages and minimal JS/model/view/playback copy changes.
  Update old UI expectations without removing security/data assertions.
- [x] GREEN focused tests; full Python/Node; actual PostgreSQL/v3/live-controller
  smoke; browser1440/768/390, keyboard/claim/delete/normal/reduced motion/error.
- [x] Packaging inclusion; verify sources/history/hashes; final diff review.
- [x] One concise revision report with sources, definitions, commands, evidence,
  actual remaining limits; no commit/push/deployment.

Review focus: removal of action dropdown must not remove any claim or duplicate
selection; stale predictions must not reappear; saved records rendered without
reinference; raw counts/IDs cannot leak through aria/title/legend; incomplete
member identities must retain fallback while hidden roles never cause one.

Final ledger: baseline543Python/91Node; RED11Python+3Node; first integrated
554Python/94Node. ReviewMinor and observed HistoryJSON error fixed via3additional
RED assertions, final556Python/94Node, zero failures/errors/skips. All543baseline
Python identities preserved. Actual browser all five pages plus detail/error at
1440/768/390; randomround, keyboard, Chi, normal/skip, realinfer/save/detail/delete
onTEST verified. Native reduced-motion preference not emulated; Node covers it.
98DEV records unchanged; protectedassets/engine/schema/API/security/roster unchanged.
Modeltemplate included in new runtime-onlycandidateV2, no historicalZIPoverwrite
or auditrebuild. Taskpreview stopped; independentreview0Critical/Important,1Minor
resolved. No commit/push/deployment.
