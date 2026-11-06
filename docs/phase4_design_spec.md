# Phase 4 design specification

Date: 2026-11-06, Asia/Jakarta. Authority: the user's complete 2,029-line Phase 4
brief. Baseline main/263 fd 88 c 83 df 417 de 53051 d 6 ab 0127 c 9 a 544 a 8 c 4, initially clean.
No Git mutations or deployment. This specification records implementation choices
inside the supplied design direction; it does not replace the user's requirements.

## Intent and scope

Make Play, Predict & Learn a polished entertainment/academic Mahjong experience,
using the existing FastAPI/Jinja/vanilla JS/PostgreSQL/model contracts. Deliver
Home, playable four-seat Game with AI advisor, History, Detail and truthful
Contact. No additional engine, ML changes, schema/security rewrite, accounts,
leaderboards, betting, build framework, final PDF or video.

## Approach

Keep the existing entry points phase3.css/phase3.js and all routes/CSRF forms/
legal-action selector. Split growing JavaScript into small local ES modules.
A single monolithic callback file would make race testing and reusable tile
rendering harder; a framework/build pipeline adds no demonstrated requirement.
The builder's choice is modular vanilla JS with Node's built-in tests, not a
framework. No package installation is planned.

## Visual system

Ivory paper, deep jade navigation/table, forest-green controls, restrained antique
gold selection/advisor accents, slate text and coral errors. Use system sans for
controls/body and local system serif for editorial headings. Shared tokens define
spacing/radius/shadows/focus and responsive layouts. Buttons/tile selection remain
semantic and keyboard-operable. Selected and AI-recommended states have explicit
labels/badges, not color alone. Honor reduced motion.

Home: large editorial Play/Predict/Learn hero, original decorative tile composition,
three-step explanation and real metadata-driven model/dataset metrics. No fabricated
activity, wins or online counters. Game: table dominates desktop, advisor at right;
tablet stacks advisor, mobile uses compact four-seat layout with deliberate local
hand/river scrolling, no page overflow. Forms/start options collapse after create.
History uses readable cards with tile visuals, paging, provenance and two-step
deletion. Detail explains recommendations first and folds complete JSON snapshots
into technical details. Contact uses matching cards when verified; otherwise the
existing explicit incomplete notice, with no inferred identities.

## Verified display contracts

Canonical map from domain/tiles.py and the Phase 1 contract: W=Wan/characters,
T=Tiao/bamboo, B=Bing/circles, F 1..4=East/South/West/North,
J 1..3=red/green/white dragon, H 1..8=flowers. Do not invent flower/season names.
Original local SVG sprite: 34 normal +8 flower faces, concealed back and safe
unknown. Ivory faces, rank/code fallback, vectors for bamboo/circles, characters/
honors and numbered flowers. No external fonts/image CDN. One canonical server
catalog drives the generated sprite and JS catalog; Jinja and DOM renderers
only reference allowlisted symbols.

Relative seat=(absolute-human+4)%4: bottom/right/top/left for0/1/2/3. Always use
server seat IDs. Bot faces are never known: render only backs/counts and public
meld/discard/flower fields. Hidden ANGANG renders backs, even if an unexpected
input contains an identity. CHI display expansion follows MeldPack.tiles (middle
rank−1..+1); this is display projection, not legal-action calculation. No global
latest-discard chronology is inferred from per-seat rivers.

## Frontend behavior

One authoritative GameView snapshot plus UI selection/request/advisor state.
Tile selection finds a server Play option by its tile; repeated copies share
the same action ID while retaining their selected visual index. All eight action
types and distinct Chi options use exact server IDs. A fallback legal-action
selector remains accessible. No optimistic tile removal or automatic discard.
Validate seat/wind 0..3, boolean flowers, and seed 0..Number.MAX_SAFE_INTEGER;
empty seed=null. Keep the backend uint 64 contract unchanged.

Use cookie credentials same-origin, current CSRF meta/session token and JSON
headers. Fetch errors map to Indonesian messages. Mutations are exclusive;
guard duplicate clicks. Sequence GETs so an older response cannot replace a
newer view or an accepted action.409 refreshes and requires a fresh decision.
Uncertain action/network outcomes trigger one GET reconciliation, never mutation
retry.401/403 require session/token recovery without granting a new owner access
to old data;404 explains in-memory expiration/restart;503 never claims saved.

Prediction is explicit POST only. After committed prediction, verify current
state with GET before applying highlights. Bind prediction and selection to
game ID/turn. If the turn changed, show a saved-history notice/link without stale
recommendations; if confirmation fails, retain truthful saved identity but no
current advice. Scores/ranking come directly from the server and mean normalized
discard preference, never win probability. Clear selection/advice when context
changes. Render actual endings/fans/score deltas, with null-safe winner/discarder
and draw handling. Refresh/resume uses existing game_id URL and no storage of
secrets, ownership or state in localStorage.

## Integration and verification

Only existing files allowed to change: six templates, phase3.js/css, presentation
app/web/pages.py and README. Protect all other tracked files and the prior
integrity manifest (1,999 files total), including old tests/evidence, engine,
encoder, AI, database, security and weights. No old tests need weakening.
Development history is fingerprinted read-only; integration/browser work uses
the dedicated project test DB. The official two-page UAS PDF was rendered/read;
page 2 is blank. Keep coursework CRD/Home/Contact requirements and report genuine
roster/final-submission gaps.

TDD slices cover assets/catalog, board projection, actions/request controller,
AI/staleness, pages/history/security. Use Python/real PostgreSQL tests, Node
built-in unit tests and a live controller acceptance test, plus real browser
desktop/tablet/mobile/keyboard/two-tab checks and full rounds. Retain all 370
baseline identities. Save new Phase 4 JUnit/evidence only. Inspect actual visuals,
store screenshots when available, document measured bytes/timings, do one fresh
independent final review and fix verified findings with tests/full regression.
