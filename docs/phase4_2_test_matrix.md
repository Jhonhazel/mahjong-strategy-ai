# Phase4.2 verification matrix

| Boundary | Actual evidence | Result |
|---|---|---|
| Original baseline | baseline.xml/node_baseline.txt |405Python/91NodePASS |
| Initial packaging/setup RED | red.txt |18failed (missing capabilities) |
| Core focused GREEN | green_initial.txt |18passed |
| Asset destination/copy race/launcher port | *_red.txt |Genuine reproductions, thenGREEN |
| Independent review fix RED | review_red.txt/review_manifest_red.txt |10+1failed |
| Final focused | review_green.xml |32passed |
| Engineering full | full_regression_final.xml |437passed0fail/error/skip,69.91s |
| Final frontend | node_final.txt |91passed0fail/cancel/skip,121.295375ms |
| Restored full audit | restored_audit_full.xml |437passed0fail/error/skip,73.61s |
| Restored frontend | restored_audit_node.txt |91passed,163.848292ms |
| Exact baseline identities | artifacts/phase4_2/integrity.json |405Python+91Node preserved |
| Runtime installation | native_install.txt/final_native_setup.txt |Newvenv, runtime pins, no pytest; actual ownPG/v3 |
| Exact CLI | actual fresh native `fastapi dev main.py` |Ready/pages/fullHTTPPASS; gracefully stopped |
| Final native launcher/setup repeat | final_native_persistence.json |Same secret/cookie/history survive restart |
| Docker first failure | compose_red.txt |Init bind execution and psql14 command incompatibility identified |
| Docker final setup | final_compose_setup.txt |Official images, ownPG volume, web/dbhealthy |
| Final package functional HTTP | final_compose_http.json |23-action round, claims/v3/history/detail/delete/CSRF/ownershipPASS |
| Compose persistence | compose_persistence.json |Same secret/cookie/history after DB+web stop/start |
| Browser on extracted Compose | browser.json +compose-game.png |Actual tiles, Chi, pre/postML, Normal/Fast/Skip, History/table/Contact |
| Container environment | container_environment.json |Linuxaarch64, torch2.15+cpu, UID10001, no pytest/bakedsecret |
| Model restore/tamper/existing-file | tests/test_phase4_2.py |Trusted bundle +3assetsPASS |
| Archives | delivery/phase4_2/release_verification.json |Member hashes/unique names/runtime independence/source correspondence |
| Original preservation | integrity.json |2175unchanged/2authorized,44dev records unchanged |
| Security review | independent_review.md |3Important reproduced and fixed; noCritical; no re-review claim |
| Cleanup | cleanup.json |Only task-owned services stopped; no volumes/data deleted |
| Windowsnative/WindowsDocker/macIntel/Linuxamd64 | No execution environment |NOT YET VERIFIED |

Log/XML paths are under docs/evidence/phase4_2 unless explicitly prefixed;
JSON runtime/evidence records are under artifacts/phase4_2. Full Python suites
include existing frontend wrappers, so Python+Node totals are not fully independent.
One existing Starlette/httpx deprecation warning remains. No old testcase source
was altered or skipped to obtain green. No production app source changed.
