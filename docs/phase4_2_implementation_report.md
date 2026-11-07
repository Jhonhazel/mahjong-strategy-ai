# Phase4.2 — Portable Lecturer Edition

6 November2026 (Asia/Jakarta). Implementasi dari HEAD
`28623736f6ce9d90eeb86dea98908b182631aad1`. Tidak ada file project lama dipindah
atau dihapus. Paket merupakan hasil ekspor lokal, bukan GitHub Release.

## 1. Executive verdict

**GO WITH CAVEATS.** Runtime mandiri dari ZIP diuji pada native macOS arm64 dan
Docker Desktop macOS dengan container Linux/aarch64. Windows native dan Docker
Desktop Windows **NOT YET VERIFIED**, begitu pula macOS Intel/Linuxamd64.
Engineering dan audit yang dipulihkan masing-masing lulus437Python/91Node.
Ini tidak menyelesaikan PDF/video/pembagian tugas/pengumpulan UAS.

## 2. What changed

Application source **tidak berubah**. Perubahan file lama hanya `README.md` dan
`.gitignore` (tambahan `/delivery/`). Source baru:

| Kelompok | Path |
|---|---|
| Builder | `scripts/build_lecturer_release.py`, `packaging/runtime_allowlist.json` |
| Aset/setup | `scripts/lecturer_assets.py`, `scripts/lecturer_setup.py`, `requirements-runtime.txt` |
| Launcher | `setup-windows.cmd`, `run-windows.cmd`, `setup-macos.sh`, `run-macos.sh` |
| Docker | `Dockerfile`, `compose.yaml`, `.dockerignore`, `packaging/Dockerfile.postgres`, `packaging/postgres_init.sh` |
| Tes | `tests/test_phase4_2.py` (32kasus baru) |
| Panduan | `README_START_HERE.md`, `README_AUDIT.md`, laporan ini, `docs/phase4_2_plan.md`, `docs/phase4_2_test_matrix.md` |
| Evidence | `docs/evidence/phase4_2/`, `artifacts/phase4_2/` |

Daftar tepat seluruh file: [file_inventory.json](../artifacts/phase4_2/file_inventory.json).
Tidak mengubah main/factory, engine/referee/bot/action/encoder, model/metadata,
schema/API/security/session/CSRF, UI, animasi atau Contact. P4-A01/A02 tetap identik.

## 3. Windows experience

Pemilik memberikan **ZIP lecturer lokal yang berisi model**, bukan mengasumsikan
clone GitHub memiliki weights. Prasyarat utama: Docker Desktop, Linux containers,
virtualization yang didukung, internet dan disk. Extract All ke folder lokal.
Di CMD:

```bat
setup-windows.cmd
run-windows.cmd
```

Setup membangun web+DB, membuat secret lokal sekali, menjalankan Compose dan
menunggu health. Website: http://127.0.0.1:8000/. Tidak perlu Python/Node/compiler
host pada jalur Docker. CMD quoting/errorlevel/flow direview independen; **tidak
ada eksekusi Windows**, sehingga dukungan belum tersertifikasi.

Alternatif `--native` memerlukan CPython3.12x64, compiler C++, PostgreSQL service
dan DB/role lokal yang diprovisikan eksplisit melalui pgAdmin. URL diminta hidden;
tidak memakai Unix socket Mac. Provisioning admin Windows tidak diotomatisasi.

## 4. macOS experience

```sh
./setup-macos.sh
./run-macos.sh
```

Ekstraktor yang kehilangan executable bit dapat memakai `sh setup-macos.sh` / run.
Actual acceptance menggunakan launcher dengan project/port khusus untuk isolasi:
`COMPOSE_PROJECT_NAME=mahjong_phase42_final MAHJONG_WEB_PORT=8880 sh setup-macos.sh`.
Prasyarat Docker Desktop saja pada jalur utama. Native:
`sh setup-macos.sh --native`, lalu `sh run-macos.sh --native`.
Prasyarat native: CPython3.12, Xcode C++ tools, PostgreSQL14 tools pada PATH.

Exact `fastapi dev main.py` juga benar-benar dijalankan dari ekstraksi baru dengan
venv sendiri, env sendiri, dan cluster sendiri; startup dan HTTP berhasil.
Setup ulang tidak memasang ulang dependency atau mengubah secret/history.
Launcher native mempertahankan runner factory existing. Dev reload tetap
menghilangkan active game in-memory, sedangkan history PostgreSQL bertahan.

## 5. Docker experience

Compose adalah jalur utama: menghindari native C++/Postgres provisioning pada
laptop dosen. Official Python3.12.10 slim dan PostgreSQL14.19 bookworm; torch
**2.15.0+cpu**, PyMahjongGB1.4.0 asli dikompilasi pada build stage. Compiler tidak
dibawa ke web runtime. Container web berjalan sebagai UID10001, satu worker.

Setelah setup secret pertama, `docker compose up --build` menjalankan web nyata
dan PostgreSQL nyata. DB tidak mempublikasikan port host; web hanya loopback.
Volume mempertahankan history; secret stabil melalui file Compose yang diberikan
hanya kepada service terkait. Role aplikasi `mahjong_app|f|f|f` (superuser/createDB/
createRole semuanyafalse); password admin terpisah tidak diberikan ke web.

Initial fresh Compose gagal karena host-bind init script dan `\getenv` yang tidak
tersedia pada psql14. RED disimpan. Fix hanya packaging: init script dibake pada
image PG dengan mode644 agar disource, memakai perintah `\set` kompatibel14.
GREEN menggunakan volume/project baru; tidak menghapus DB yang sudah ada.
Setup final, fullHTTP dan persistensi stop/start DB+web berhasil.

## 6. Lecturer package structure

```text
delivery/phase4_2/
  mahjong-strategy-ai-lecturer-portable.zip
    mahjong-strategy-ai/
      main.py
      app/                     # unchanged application, templates, local assets
      config/contact_members.public.json
      scripts/                 # only setup/assets/legacy DB + runner/init helpers
      training/__init__.py
      training/dataset_loader.py
      artifacts/models/        # one promoted v3 checkpoint + metadata
      datasets/expanded_strict_v2/data_contract.json
      docs/ml_artifact_bundle_manifest.json
      packaging/               # PG image/init only
      requirements-runtime.txt
      setup-*.{cmd,sh}, run-*.{cmd,sh}
      Dockerfile, compose.yaml, .dockerignore, .env.example
      README_START_HERE.md, THIRD_PARTY_NOTICES.md
      RELEASE_MANIFEST.json
  mahjong-strategy-ai-audit.zip
    mahjong-strategy-ai-audit/  # non-runtime research/dev/evidence, own manifest
  release_manifest.json
  release_verification.json   # post-build verification, generated separately
```

Runtime79payload files plus generated manifest; no symlink to original repo.
Small unchanged `training.dataset_loader` remains because runtime imports its
hash helper; no full training stack/corpus is copied merely for that import.

## 7. Audit separation

Audit ZIP preserves tests, training/replay/inspection source, original data/shards,
historical experiment candidates/results/provenance, JUnit/browser evidence and
internal plans. It complements runtime paths. No original checkout/history moved.
README_AUDIT explains assembly into a **new** workspace, manifest preservation,
test prerequisites and deterministic rebuild. Audit reconstruction was actually
executed, using a new local PostgreSQL cluster and restored application/data.

Full restored audit: **437passed**,0failed/error/skipped,73.61s. Node91passed.
Its test-tool interpreter uses the existing engineering venv; runtime imports
and data come from restored paths. This is distinct from the independent new
runtime venv/container checks. Final archive adds only later reports/evidence;
audited source/test/data hashes are checked against the tested snapshot.

Known audit roots/top-level sources are allowlisted. Private configs, credential
files/JSON values, backups including compressed SQL/dumps, cluster data, logs,
Git internals, venv/cache and generated ZIPs are excluded. Unknown root notes
are excluded. Original caches/archives/DB remain untouched. Trusted original
inference transfer bundle remains an audit restore-test input, not a second
runtime checkpoint. Hashes/copy correspondence are in each manifest/sidecar.

## 8. Model distribution

Owner-generated lecturer ZIP includes the three inference assets unchanged:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| v3checkpoint | 1553925 | `ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720` |
| metadata | 1514897 | `84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e` |
| contract | 188448 | `95f21b15be55dbbe4b9cf001edbc8b52462e4461b9bbaf39431a0a482e73adbc` |

Manifest authority unchanged; original bundle hash
`96ea17fab9e13ae7061230a892cc302dfa74a7e765740f363cd7a27fa96119b2`.
Restore verifies archive/member hashes and regular files before writing missing
paths, rejects symlinks/tampering and different existing artifacts, and retains
identical files. Tests performed genuine restore/repeat/tamper checks.
No retraining, invented URL, download, upload or public model publication.
Attribution retained; local owner permission does not create a blanket new
license or authorize an external release. GitHub clone alone still lacks weights.

## 9. PostgreSQL portability

Primary uses an isolated official PG image, own persistent volume, strong random
credentials and a dedicated non-admin app role. Explicit init creates missing
schema and validates existing semantics; no drop/migrate/reset behavior added.
Native Mac uses its package-owned helper/Unix socket, not the developer cluster;
legacy helper's admin role is retained/documented. Native Windows uses explicitly
provisioned local TCP. Effective query-host/service/hostaddr overrides are rejected,
including in existing config, before native schema initialization.

## 10. Clean-environment testing

| Environment | Actual result |
|---|---|
| Existing macOS arm64 engineering | Full437Python/91NodePASS |
| Fresh macOS arm64 ZIP/newvenv | Python3.12.10, runtime-only install/lifespan/CLI/HTTP/persistencePASS |
| Fresh Docker Desktop Mac/Linuxaarch64 | Python3.12.10, CPUtorch2.15.0+cpu, PG14.19, setup/health/fullHTTP/persistencePASS |
| Restored audit workspace macOSarm64 | Own PG cluster; restored437Python/91NodePASS |
| Windows11x64 native | NOT YET VERIFIED; static launcher review/wheel metadata only |
| Docker Desktop Windows/Linuxamd64 | NOT YET VERIFIED; CPUwheel availability is not execution proof |
| macOSIntel / other platforms | NOT RUN |

Native new venv has no pytest; app/helper imports and model paths resolve only
inside extraction. Docker has no original repo mount, baked `.env` or secret;
only contract exists in runtime dataset directory. Developer DB was not reused.
Fresh environments were on this existing host; pip/build caches were available.

## 11. Functional integration

Actual HTTP native and Compose: nine page/asset/docs paths200, readiness200,
new game, legal discard/Chi, real v3 Top3 and saved PG prediction, unchanged game
during prediction, idempotent reuse, History/detail table, delete204→404, missing
CSRF403, foreign game/prediction404. Each HTTP round:23actions,20Play/3Chi, real
Zimo25fan and deltas `[99,-33,-33,-33]`. Final payload repeated the Compose round.

Actual browser on extracted Compose: local sprite/board, pre/postmeld predictions,
Chi, Normal highlightedseat/tile while busy, Fast action, Skip click, History two
cards, detail table, five Contact members with unchanged unconfirmed-role notice.
Screenshot: [compose-game.png](evidence/phase4_2/compose-game.png).
Full rounds were HTTP acceptance, not claimed as complete browser rounds.
Public animation source unchanged; no new responsive/a11y certification claimed.

## 12. Full regression and TDD

Fresh baseline405Python/91Node,65.45sPython. Final engineering **437Python**,
69.91s; final Node**91**,121.295375ms. Restored audit **437Python**,73.61s;
Node91,163.848292ms. All0failed/error/skipped/cancelled; one existing Starlette/
httpx deprecation warning in Python. Original405 testcase identities and all91
Node cases preserved;32new Python regressions. No original tests changed.

Initial RED18failed→GREEN18passed. Further asset-map/copy-race/launcher-port
RED→GREEN. Independent review found3Important issues (backup/credential admission,
manifest collision, effective DBhost override). Synthetic RED10failed/21passed
plus reserved-manifest RED1failed; final focused GREEN32passed. Fixes verified by
full suite and final-package setup. No Critical findings; no unresolved Important
findings after fix pass. No independent re-review/Windows execution claimed.

Reviewer independently ran21focusedtests; Python full/CLI/Docker/browser were
implementer-run. [Review details](evidence/phase4_2/independent_review.md).
JUnit: [engineering](evidence/phase4_2/full_regression_final.xml),
[restored audit](evidence/phase4_2/restored_audit_full.xml).
Static: shellsyntax, pycompile, pipcheck, gitdiffcheckPASS.

## 13. File sizes and measured timings

Preflight full checkout allocated**3602644KiB** including venv/Git/localstate;
eligible inventory**918556528bytes /2177files**. Runtime payload**3591024bytes /
79files**, ZIP**1878971bytes**. Inference assets**3257270bytes**. Runtime ZIP SHA
`2d57ce03d6cc34d5c4103d3f75b95a8384f26e35aa96df25b43c3fa2d6da996b`.
Audit snapshot tested:2159files,915927524sourcebytes,781135114ZIPbytes. Final audit
adds reporting evidence; authoritative final counts/sizes/SHA are in
`delivery/phase4_2/release_manifest.json`, not a fabricated fixed estimate.

New native venv footprint**887584KiB**; Python/PyTorch dependencies remain large.
Final native setup**35.75s**, warm pip cache. Native launcher ready**2.72s**,
restart**1.70s**. Initial Docker build**102.99s**; final cached setup**12.58s**;
DB+web stop/start→healthy**8.30s**. Docker timings from log birth/last-write or
monotonic timing as recorded; host load/cache applies. Exact final image sizes
are recorded in verification JSON. No general speed/zero-prerequisite claim.

## 14. Security and secret handling

Native `.env` created exclusively with owner mode600 and preserved. Compose
secret parent0700; read-only files exposed only through granted secret mounts,
never image/build args/archive. Windows ACL behavior remains unverified. Partial
missing secret sets fail rather than rotate credentials for existing history.
No credential values emitted into reports/manifests. ZIP source paths, byte sizes,
SHA and opaque dev-record fingerprints are recorded; raw records are not exported.
Source mutation during copy aborts. Generated manifest collisions reject/preserve
explicitly. No SQL backup, globalservice shutdown, deletion, or external upload.

## 15. Remaining caveats

Windows execution/ACL/compiler compatibility and Linuxamd64/macOSIntel not tested.
Internet/Docker Desktop/disk remain prerequisites. Native Mac retains helperadmin
role. Full accessibility/physical devices/actual200%zoom not newly tested. UAS
roles/contributions, final PDF, video, and final source/SQL submission approval
remain outstanding. Task-owned test services stopped; volumes/temp evidence
retained, original developer cluster/unrelated services left running.

Primary sources for dependency investigation:
[PyPI1.4 release files](https://pypi.org/project/PyMahjongGB/1.4.0/#files),
[upstream C++ extension setup](https://github.com/ailab-pku/PyMahjongGB/blob/master/setup.py),
[official CPUwheel index](https://download.pytorch.org/whl/cpu/torch/),
[official PostgreSQL image](https://hub.docker.com/_/postgres),
[Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/).
Observed wheel metadata is retained separately; wheel availability is not an OS
runtime PASS. No unverified third-party native binary distributed.

## 16. Git state and preservation

Branchmain, HEAD28623736f6ce9d90eeb86dea98908b182631aad1 unchanged. Final **2tracked
modified,80untracked files,0staged**. Initial tree
was clean before task evidence was created. Final tracked/untracked/staged counts
and exact paths: [git_final.json](../artifacts/phase4_2/git_final.json).
Intentional dirty tree,0staged; no add/commit/push/reset/clean/stash/checkout/switch/
rebase/merge/deploy/release publication. Original2177files:2175byte-identical,
only README/.gitignore intentionally changed. Frozen model/metadata/contract and
engine/schema/security/UI source unchanged. **44original dev records** retain
aggregate/per-ID hashes; original cluster remains running. This task did not
assume the older Phase4.1 report's23records were current.

## 17. Final recommendation

Classmates/lecturer on the verified Mac/Docker environment can use the clean ZIP
and short setup/run instructions without the engineering corpus. Windows users
have reviewed entrypoints but must complete an actual Windows verification before
being promised support. Separate audit remains runnable and checksum-correlated.
The full engineering checkout is deliberately retained; GitHub clone is not
silently made lean. Public release/milestone commit requires separate permission.
