# Independent Phase 4 code/security review

2026-11-06. One fresh-context reviewer, `/root/phase4_final_review`, model
gpt-6-astra/high. Read-only review of the uncommitted source against baseline
263 fd 88 c 83 df 417 de 53051 d 6 ab 0127 c 9 a 544 a 8 c 4, user brief, design, plan and ledger.
The reviewer ran 30 focused Node cases and additional read-only probes. No browser,
database access, file changes, Git mutation or delegated reviewer. This is the
reviewer's pre-fix assessment; it is not a post-fix approval.

## Assessment received

Changes requested;0 Critical, 4 Important, 2 Minor. Strengths: authoritative server
actions, exact duplicate-tile IDs, concealed opponent ANGANG, owned/CSRF-protected
deletion. Author independently checked findings against source and regressions.

| ID | Reviewer grade | Finding and verified effect |
|---|---|---|
| R 1 | Important | Manual refresh 503 leaves old advice; repeat prediction's delayed confirmation leaves a previously rendered recommendation visible. |
| R 2 | Important | Malformed prediction 200 `{}` can claim saved/link undefined; deletion 202 can be treated as completed although the API confirms with 204. |
| R 3 | Important | Null/expired view leaves finished result, game ID and public summary outside the hidden game section. |
| R 4 | Important | Unsafe centered overflow clips first tile before the scroll origin at 701–900 px with a full14-tile hand. |
| R 5 | Minor | Advisor lacks visible prediction/model identity; History listing lacks requested Top 3 summary. |
| R 6 | Minor | CHI `offer` is claimed tile position; accessible meld label incorrectly calls it a relative source seat. |

Declined to judge: actual 200% zoom, runtime reduced-motion behavior, platform
compatibility, final full-suite and preservation results. The author retains
the first three as explicit verification limitations; final suite/preservation
are verified separately. No claim of a second independent review is made.

## Author's one focused fix pass

- R 1: invalidate and emit advice at request start/failure; emit saved identity
  before awaiting confirmation. Preserve committed notice/history link.
- R 2: validate saved identity, context, actual legal server membership, Top 3,
  finite scores and provenance before success; DELETE requires actual 204.
- R 3: null-view transition hides/empties round result, seat/hand/claim/center DOM,
  game identity, public summary and selector.
- R 4: `safe center` preserves centering only when all tiles fit; overflow starts
  at its reachable origin. Browser705/768 tests use 14 real tiles, both edge tiles
  keyboard-selectable, no page overflow.
- R 5 regraded Important: explicit brief 11.3 and 20 require these fields. Added a
  compact provenance disclosure and server-owned Top 3 summary on History cards.
- R 6 regraded Important: wrong announced game information affects screen-reader
  users. Removed unsupported source interpretation; canonical meld type remains.

Evidence: `review_advice_protocol_red.txt`18 failed → corresponding GREEN38/38;
`review_view_red.txt`3 failed → `review_node_green.txt`66/66;
`review_presentation_red.txt`2 failed → `review_focused.xml`20/20 (2.67 s).
Final full-suite/browser/preservation results live in the final report and
verification_summary.json. No deferred Minor findings remain; regradings are
recorded as rulings in the execution ledger.
