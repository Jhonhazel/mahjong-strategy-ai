# Mahjong Strategy AI — Phases 1–4.3

Phase4.3 menambahkan handoff deploymentHTTPS dengan proxytrust eksplisit dan
workflow buildWindows offline. **Belum ada URL publik atau executableWindows
terverifikasi.** Lihat [status jalur pengguna](README_START_HERE.md),
[deployment](deploy/README.md), dan [buildWindows](windows/README_BUILD.md).
Paket/arsip Phase4.2 tetap utuh; metode macOS/Docker di bawah tetap tersedia.

## Dosen / anggota kelompok: mulai dari paket bersih

Gunakan [README_START_HERE.md](README_START_HERE.md): prasyarat Docker Desktop,
setup sekali (`setup-windows.cmd` / `./setup-macos.sh`), startup berikutnya
(`run-windows.cmd` / `./run-macos.sh`), lalu buka http://127.0.0.1:8000/.
Node bukan prasyarat website. Alternatif native CPython3.12 juga dijelaskan;
prepared environment tetap dapat memakai `fastapi dev main.py`.

Pemilik membuat ZIP runtime dan audit terpisah dengan
`.venv/bin/python -m scripts.build_lecturer_release --output delivery/new-release`.
ZIP runtime menyertakan aset v3 checksum-verified; clone GitHub biasa tetap tidak
menyertakan checkpoint yang di-ignore. Tidak ada Release/upload otomatis.
Checkout engineering ini sengaja tetap lengkap. Panduan audit:
[README_AUDIT.md](README_AUDIT.md). Hasil platform aktual dan batas verifikasi
dicatat di [laporan Phase4.2](docs/phase4_2_implementation_report.md).

Bagian historis/pengembangan di bawah tetap tersedia untuk reproduksi.

Playable Botzone Chinese Standard Mahjong (MCR), one human and three local shanten bots. Phase 1 includes the referee, scoring, private-seat encoder and CLI. Phases 2–2.2 add the verified Behavior Cloning models. Phase 3 connects the unchanged engine and promoted v3 model to FastAPI and PostgreSQL. Phase 4 adds the responsive Play, Predict & Learn interface: original local tile art, a four-seat board, exact legal-action controls, an explicit AI advisor and visual prediction history.

## Lecturer startup — Phase 4.1

After the one-time preparation below, activate `.venv`, enter this repository,
and run exactly:

```sh
fastapi dev main.py
```

The root entry reuses the existing application factory. Database/model loading
occurs in the application lifespan; import does not create or migrate tables.
The existing `.venv/bin/python -m scripts.run_backend` entry remains supported.
The FastAPI CLI defaults to localhost port 8000; `MAHJONG_PORT` configures the
legacy runner, not this CLI command. Ensure port 8000 is available.

One-time preparation: install CPython 3.12 and PostgreSQL tools, create the venv
(`python3.12 -m venv .venv` if absent), install the lock below, restore the frozen
v3 inference assets using the checksum procedure, start the project database,
and explicitly initialize its schema. Configure `MAHJONG_DATABASE_URL` and a
strong private `MAHJONG_SESSION_SECRET` in your environment or ignored local
`.env` (restrict its permissions to the owner). Preserve that secret across
restarts. Never commit it or use the invalid example placeholders. Activate
the environment with `source .venv/bin/activate` before the lecturer command.
No automatic bootstrap, model download or training is performed.

This exact command was verified on the prepared macOS host with Python 3.12.10,
FastAPI 0.162.0 and FastAPI CLI 0.0.32. It is a development reloader: source
changes/restarts clear in-memory games; persistent history remains in PostgreSQL.
Clean-machine setup, Windows/Linux and production operation were not verified.

## Prepare and run the web app locally

Use CPython 3.12 and PostgreSQL 14 tools (`initdb`, `pg_ctl`, `pg_dump`, `psql`) on the tested macOS host. Installation in the existing environment used the previous lock as a constraint; a clean installation and Windows/Linux operation have not been repeated. Restore inference assets separately using [the checksum-verified procedure](docs/ml_artifact_transfer.md). The runtime needs only the v3 checkpoint, metadata and small expanded data contract; it does not read training shards or raw archives.

From the repository root:

```sh
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m scripts.phase3_db start
export MAHJONG_DATABASE_URL="$(.venv/bin/python -m scripts.phase3_db url --database dev)"
export MAHJONG_SESSION_SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(40))')"
export MAHJONG_ENVIRONMENT=local
export MAHJONG_WORKERS=1
.venv/bin/python -m scripts.init_db
.venv/bin/python -m scripts.run_backend
```

Open [Home](http://127.0.0.1:8000/), [Game](http://127.0.0.1:8000/game), [History](http://127.0.0.1:8000/history), [Contact](http://127.0.0.1:8000/contact), [Swagger](http://127.0.0.1:8000/docs) or [ReDoc](http://127.0.0.1:8000/redoc). Documentation UI assets use jsDelivr; the game, pages and JSON API use local assets. The database runs on its private Unix socket in `.local/phase3-postgres`; the helper does not modify global PostgreSQL services. Explicit schema initialization creates the missing table and validates it; startup never migrates or drops existing data.

Keep the same signing secret privately across restarts to retain access with the same signed cookie. Environment variables override a local ignored `.env`; `.env.example` lists names with invalid placeholders. Generate your own secret. Production mode requires HTTPS Secure cookies. Active games are in memory and disappear on restart; PostgreSQL history persists. Run **one worker**. Active games expire after one hour idle by default; finished games retain the existing 30-second cleanup policy.

Contact defaults to the five approved identities in `config/contact_members.public.json`.
Their task roles and contributions remain unconfirmed and are explicitly labeled
as such. To override the roster, set `MAHJONG_CONTACT_MEMBERS_PATH` to an approved
file following `config/contact_members.example.json`; missing/unverified data
still shows the incomplete-content fallback. The final UAS PDF, video, verified
group roles and submission packaging remain final-submission work.

## Phase 4 interface and verification

At `/game`, choose seat, round wind, an optional integer seed (0–9007199254740991), and flowers. The human stays at the bottom. Select a legal tile or claim and confirm with **Jalankan pilihan**; the advisor never executes a move. **Minta prediksi & simpan** saves the actual v3 result, verifies the current turn, and displays the server's Top 3. Scores describe discard preference, not winning probability. Open **Identitas prediksi** for its actual saved ID/model/encoder. History supports paging, Top 3 summaries, a semantic result table, complete folded JSON and explicit delete confirmation.

The browser uses local SVG, CSS and ES modules with no build step, external font, UI dependency or browser model download. The existing `phase3.js`/`phase3.css` filenames remain compatibility entry points. Use keyboard Tab/Enter/Space; the mobile hand scrolls within its own region. Unknown/expired games and uncertain requests require a fresh server view; actions are never retried automatically. Keep the same private signing secret across normal app restarts to retain history access.

Phase 4.1 highlights factual public snapshot changes after a successful action:
600 ms per seat group in Normal, 180 ms in Cepat, at most four groups (2.4 s).
Skip ends presentation immediately. Reduced motion and a hidden page bypass it;
new game, refresh, expiry and page lifecycle changes cancel stale playback.
These highlights do not reconstruct the bots' original action order. The final
server state is already authoritative while actions/predictions are locked.
See the [Phase 4.1 report](docs/phase4_1_implementation_report.md) and
[test matrix](docs/phase4_1_test_matrix.md) for current evidence (405 Python,
91 Node cases), Contact assertion migrations and remaining limitations.

Node v24.4.1 was used for the built-in frontend tests; Node is a **test** prerequisite, not a web-app runtime dependency. From this repository in the existing Python environment:

```sh
export MAHJONG_TEST_DATABASE_URL="$(.venv/bin/python -m scripts.phase3_db url --database test)"
node --test tests/frontend/*.test.mjs
.venv/bin/python -m pytest tests/test_phase4_*.py -q --junitxml=docs/evidence/phase4/local_focused.xml
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase4/local_reproduction.xml
```

Choose new evidence filenames to retain previous runs. Real PostgreSQL/localhost access and the frozen inference assets are required. Missing Node fails explicitly; missing PostgreSQL configuration produces explicit integration skips and cannot establish PASS. The original 370 regression identities remain intact. Regenerate the original tile sprite/catalog only when intentionally editing the art: `.venv/bin/python -m scripts.build_tile_assets` (determinism is tested).

See the [Phase 4 report](docs/phase4_implementation_report.md), [design](docs/phase4_design_spec.md), [test matrix](docs/phase4_test_matrix.md), [inventory](docs/phase4_file_inventory.md), [ledger](docs/phase4_execution_ledger.md), and [verification summary](artifacts/phase4/verification_summary.json). Browser evidence includes real desktop/mobile rounds and all five pages at six widths. Actual 200% zoom, runtime reduced-motion emulation, a clean installation and other platforms remain unverified. No Phase 4 Git commit or deployment is part of this implementation.

## Phase 3 API and verification

Initialize with `GET /api/session`, retaining the HttpOnly `mahjong_visitor` cookie and returned `csrf_token`. Send `X-CSRF-Token` on every JSON mutation and use the same origin. Swagger exposes both inputs: initialize the session, then copy its token into the mutation header field. Create a game with `{"human_seat":1,"seed":42}`. Read its current legal actions and turn from `GET /api/games/{game_id}`. Submit `{"action_id":33,"expected_turn_number":4}` to its `/actions` path only if those values match that game.

`POST /api/games/{game_id}/predict` accepts only `{"expected_turn_number":4}` and saves the server's observed input plus actual v3 output. It never executes an action. New committed records return 201; the same snapshot returns 200 with the same ID and `reused: true`. List owned history at `GET /api/predictions?limit=20&offset=0`, read `GET /api/predictions/{prediction_id}`, and delete on the detail path with `DELETE` (204, then 404). HTML history uses a CSRF-protected delete form.

Missing identity is 401, CSRF 403, unknown/cross-owner/expired resources 404, stale turns or unavailable discard decisions 409, illegal actions 400, invalid input 422, oversized bodies 413, capacity 429, and required DB/inference failures 503. Scores imitate observed discard behavior; they are not winning probabilities.

```sh
export MAHJONG_TEST_DATABASE_URL="$(.venv/bin/python -m scripts.phase3_db url --database test)"
.venv/bin/python -m pytest tests/test_phase3_*.py -q
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase3/local_reproduction.xml
.venv/bin/python -m scripts.demo_backend --output artifacts/phase3/my_round_demo.json
.venv/bin/python -m scripts.phase3_db export --database dev --output artifacts/phase3/my_history_export.sql
shasum -a 256 artifacts/phase3/my_history_export.sql
.venv/bin/python -m scripts.phase3_db restore --input artifacts/phase3/my_history_export.sql
```

Choose new evidence/export filenames. Database tests require the dedicated `_test` database; admin drift/export tests additionally require the marker-protected cluster. Missing configuration causes explicit skips, not integration PASS. Full historical regressions also require the original corpus/artifacts and temporary space above the existing 1 GiB reserve.

Restore accepts a nonempty export up to 64 MiB whose exact SHA-256 was registered by this cluster's export helper. Export is captured privately and published exclusively. Restore rejects unsafe psql/database commands and executes verified bytes transactionally into a **new** `mahjong_phase3_restore_*` database. It never selects an existing destination. Arbitrary or changed SQL is rejected. Preserve the SQL with a separately trusted checksum for transfer; cross-machine DB administration remains unverified. Dumps, cluster data, secrets and model weights remain Git-ignored. Stop only the private cluster with `.venv/bin/python -m scripts.phase3_db stop`.

See [Phase 3 report](docs/phase3_implementation_report.md), [file inventory](docs/phase3_file_inventory.md), and [ledger](docs/phase3_execution_ledger.md) for exact results, review fixes, UAS mapping and Phase 4 handoff. Earlier sections below retain their historical scope.

## Setup

Verified host: macOS arm64, CPython 3.12.10, PyMahjongGB 1.4.0 built unmodified with the local compiler. CPython 3.11/3.12 is required; Python 3.13 is not the tested target.

macOS (install a supported Python and Xcode Command Line Tools if unavailable):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.check_env
```

Windows x64 (**NOT RUN on this host**; install supported CPython and Visual Studio C++ Build Tools if needed):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.check_env
```

`requirements-lock.txt` records the actual verified environment. No custom source patch, global package installation, Docker, or `rtk` command is needed. If native compilation fails on another OS, diagnose it there; do not assume this host's result proves that build works.

## Play

```sh
.venv/bin/python -m scripts.play_cli_round --seed 42 --human-seat 0
.venv/bin/python scripts/play_cli_round.py --seed 42 --flowers
.venv/bin/python -m scripts.play_cli_round --auto-human-demo --seed 42 --human-seat 1 --output datasets/cli_round_42.json
```

Choose an action ID from the displayed legal actions. Opponent concealed tiles, AnGang identities and unused wall contents stay private until the round ends. Automated mode runs the same referee/session/bots and writes the real result; it is not an AI prediction.

## Acquire and audit data

```sh
.venv/bin/python -m training.dataset_loader
.venv/bin/python -m training.inspect_dataset
.venv/bin/python -m training.verify_encoder_parity --max-games 100 --min-matches 50
```

The downloader retrieves ~206 MB from a pinned Hugging Face revision, checks trusted SHA-256/size metadata, safely extracts decisions and reads games directly from the archive. It also pins the small public feature reference used by conformance tests. All data stay in ignored `datasets/`.

**The historical audit command currently exits nonzero intentionally**: the original 576,868 rows contain 13 illegal `mask[act]` labels. `datasets/audit_report.json` retains the complete inventory and errors. `_allfield.npz` (576,868 rows) and `_top4.npz` (48,476 rows) are verified aggregate copies, excluded from the individual total. Do not train from the original NPZ.

The selected training contract is **strict re-extraction**, not historical full parity. The first 100 archive entries yield 84 legal complete matches and 16 RE/WA terminal exclusions. Independent protocol replay and actual referee replay compare 4,482 decisions with zero observation/mask/action differences. The accepted tracked-seat subset contains 1,879 samples with full source hashes and match identity. See `datasets/data_contract.json`, `parity_report.json`, and `decision_manifest.csv` for exact scope, exclusions, source versions, counts and group evidence. This is a limited verified subset, not a claim about every game in the archive. Increase `--max-games` to build a larger verified corpus, inspecting all new failures before use.

## Tests

```sh
.venv/bin/python -m pytest -m 'not slow and not integration' -q
.venv/bin/python -m pytest tests/test_mcr_engine_playthrough.py -q
.venv/bin/python -m pytest tests/test_encoder_parity.py -q
.venv/bin/python -m pytest -q
```

The complete suite includes a real localhost HTTP server, 20 concurrent threads, native scoring, 200 seeded rounds, CLI subprocesses and real corpus checks. Localhost bind permission is required for the HTTP tests. Missing downloaded corpus/reference files cause explicit dataset test skips, so inspect the skip count. The 50-match artifact check requires running the parity command first; it does not fabricate a report when absent.

## Shared engine and model contracts

- `EncodedTurnState`: `obs int8[38,4,9]` (flattened 1,368 inputs), `legal_mask bool[235]`, `legal_discard_mask bool[34]`, seat, turn, version `ijcai2026_mcr_v1_strict`.
- Channel 0/1 = seat/prevalent wind; 2–5 = own hand unary counts; 6–21 = historical discards by relative seat; 22–37 = known meld tiles by relative seat. Honor-row columns 7/8 are padding. Relative seats are self/next/opposite/previous. Claimed tiles remain in discard history; physical conservation uses a separate river.
- Botzone action IDs: Pass 0, Hu 1, Play 2–35, Chi 36–98, Peng 99–132, MingGang 133–166, AnGang 167–200, BuGang 201–234. Phase 2 discard classes are `action_id - 2`, 0–33. Always apply the legal mask.
- `GameSessionService`: create/get/view/submit/delete/shutdown. A human submission **must include `expected_turn_number`** from the returned view. Stale or missing tokens are rejected. New sessions are bounded; in-flight sessions are never expired or evicted. Per-game locks serialize operations; shutdown drains accepted work.
- Wall scheduling follows the actual Botzone variant: each seat draws its own segment backwards, and a round ends when the required drawer's segment is empty. This can leave tiles in other segments. It is not a physical continuous wall simulator.
- Only manifest rows from `strict_decisions/accepted.npz` are approved for future training. Arrays include real source `score`, `match_id`, and `seat`. Keep every `match_id` in exactly one train/validation/test group. `partition_for_match` defines reproducible 80/10/10 buckets; group evidence is checked now, not a model training pipeline.

See [implementation report](docs/phase1_implementation_report.md), [execution ledger](docs/execution_ledger.md), and [third-party attribution](THIRD_PARTY_NOTICES.md). Historical approved plans under `docs/superpowers/` are unchanged. No Git repository existed at preflight; no Git publishing operations were performed.

## Phase 2: verified MLP training and inference

Phase 2 reads the approved Phase 1 snapshot without regenerating it. The source hash gate pins run `84c2606383794fa8bc072d5edac7b252`, 1,879 decisions / 84 matches, encoder `ijcai2026_mcr_v1_strict`. Train/validation/test stay at 1,564/213/102 decisions and 72/7/5 distinct matches. Four known player identities occur in the corpus; this evaluates held-out matches, not unseen-player generalization.

Use the existing `.venv`; install the pinned new PyTorch dependency:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m training.phase2_dataset
.venv/bin/python -m training.baselines
.venv/bin/python -m training.train_mlp --device auto --seed 2026 --max-epochs 80 --patience 10
.venv/bin/python -m training.evaluate_mlp
.venv/bin/python -m scripts.demo_ai_prediction --smoke --seed 42 --human-seat 1 --output artifacts/phase2/live_demo.json
.venv/bin/python -m pytest tests/test_phase2_*.py -q
.venv/bin/python -m pytest -q
```

The first baseline command evaluates validation only. The evaluator freezes the selected checkpoint before reading test tensors; a subsequent evaluation must use `--verify-existing` to recalculate the same frozen model, rather than overwrite the held-out record. Reproducing training into new artifact paths avoids replacing an already evaluated model:

```sh
.venv/bin/python -m training.train_mlp --device cpu --checkpoint artifacts/models/reproduction.pt --report-dir artifacts/phase2/reproduction
.venv/bin/python -m training.evaluate_mlp --checkpoint artifacts/models/reproduction.pt --report-dir artifacts/phase2/reproduction
```

If artifact publication fails, the evaluator records FAIL and supports `--resume` only for the same frozen checkpoint/configuration/data. Reverification requires the original freeze record, saved predictions, checksums, and consistent final checkpoint metadata; it rejects missing or altered evidence.

The model is 1368 → 64 → 34, ReLU and dropout 0.2 (89,826 parameters), initialized randomly. Training uses masked cross-entropy and AdamW, direct float32 conversion of the existing C-order observation, no extra features or normalization. Validation loss selects the checkpoint. MPS is used only after actual forward/backward checks; saved weights are CPU-compatible and inference runs on CPU. MPS reproducibility is best effort; cross-device bit equality is not claimed.

Artifacts:

- `artifacts/models/mahjong_discard_mlp.pt` — local trained state_dict, ignored by Git.
- `artifacts/models/mahjong_discard_mlp.metadata.json` — architecture, mappings, dataset/encoder identity, training provenance and checksums.
- `artifacts/phase2/` — data validation, baseline metrics, training history, freeze record, final evaluation, per-class/confusion CSVs and real-game demo evidence.

The test set has only **102 decisions from five matches**, with no T3 target examples. Macro F1 is reported across all 34 classes with zero-denominator F1=0, and separately across supported classes. Top-3 uses up to three legal choices. Random baseline rankings are seeded legal permutations; their NLL is the uniform legal-policy likelihood. Class prior uses only training counts with add-one smoothing. These are behavior predictions, not calibrated chances of winning.

Minimal future application integration:

```python
from pathlib import Path
from app.services.ai_prediction_service import AIDiscardPredictionService

ai = AIDiscardPredictionService(Path("artifacts/models/mahjong_discard_mlp.pt"))
state = game_service.get_human_encoded_turn(game_id)
prediction = ai.predict(state)
# User chooses a legal action separately, carrying state.turn_number.
```

Pass the current data contract through `expected_contract=` when strict dataset-identity binding is required. The service loads once, validates metadata/hash/mapping before `weights_only=True` CPU loading, and never advances the game. `PredictionUnavailableError` signals no legal discard; `InvalidPredictionStateError` signals an incompatible state; `CheckpointValidationError` signals an invalid local model artifact. Claim-only or finished turns cannot request a discard prediction through the game service.

See [Phase 2 implementation report](docs/phase2_implementation_report.md) and [Phase 2 execution ledger](docs/phase2_execution_ledger.md). Windows commands use `.\\.venv\\Scripts\\python.exe`; Windows training/inference remain **NOT RUN** on this host. Phase 2 does not replace opponent bots, expose private hands, or implement Phase 3/4 web/database features.

## Phase 2.1: full-corpus strict expansion

The separate `datasets/expanded_strict_v2/` pipeline preserves all original Phase 1/2 artifacts. The pinned archive contains **44,420 JSON games** plus `_sid.txt` metadata (the historical44,421 count included that file). Full processing accepted **1,946,122 decisions from 38,250 matches**, covering 581 public player UIDs. All four roster seats are independently replayed; every attempted/excluded game has an audit record. Repeated states from distinct source decisions are retained and counted.

Run one extractor per output directory. The default has no game limit; `--max-games` is an operational checkpoint. Committed compressed shards survive interruption and are not replayed on resume. READY is published only after full manifest/shard/source validation. Do not use the earlier Phase 1 parity command to overwrite the original snapshot for expansion.

```sh
.venv/bin/python -m training.expanded_dataset --max-games 600 --workers 2
.venv/bin/python -m training.expanded_dataset --audit-partial
.venv/bin/python -m training.expanded_dataset --max-games 5000 --workers 2
.venv/bin/python -m training.expanded_dataset --max-games 15000 --workers 2
.venv/bin/python -m training.expanded_dataset --workers 2
.venv/bin/python -m training.expanded_dataset --validate
.venv/bin/python -m training.expanded_training --device cpu
# Resume interrupted experiments with their original frozen protocol:
.venv/bin/python -m training.expanded_training --device cpu --resume
.venv/bin/python -m training.expanded_evaluation
.venv/bin/python -m training.expanded_evaluation --verify-existing
.venv/bin/python -m scripts.demo_ai_prediction --checkpoint artifacts/models/mahjong_discard_mlp_v2.pt --contract datasets/expanded_strict_v2/data_contract.json --smoke --seed 42 --human-seat 1 --output artifacts/phase2_1/live_demo.json
.venv/bin/python -m pytest tests/test_phase2_1_*.py -q
.venv/bin/python -m pytest -q
```

The original 84 match roles stay fixed; the original five test matches are reserved as `historical_test` (all their seats excluded from training and fresh test). New matches use SHA-256 `phase2.1-match-split-v1:` with 80/10/10 buckets. The fresh test has 194,388 decisions /3,816 matches. Experiment APIs expose train/validation only. Nested match-complete learning curves and minimum validation NLL select the new checkpoint before any fresh test comparison. The evaluator compares old/new models and train-only prior/random baselines on that same fresh cohort, saves streaming predictions, recalculates metrics independently, and bootstraps complete matches.

The original 1368→64→34 MLP/encoder remain compatible with `AIDiscardPredictionService`; pass the new small contract via `expected_contract=`. The service needs only checkpoint, metadata and optional contract, never raw archives or training shards. New metadata preserves parent Phase 1 identity and explicitly identifies expanded run, shard/manifest inventory digests, split roles and trained subset. CPU was selected after real masked optimizer benchmarks (batch 32: about 107k samples/s CPU vs 10.7k MPS); MPS was available and passed. No additional dependency was installed for Phase 2.1. Windows expansion/training is NOT RUN; resource instrumentation currently targets the verified Unix host.

Primary outputs are under `artifacts/phase2_1/` and `artifacts/models/mahjong_discard_mlp_v2.pt`. Training uses one shard on CPU, batch float32 conversion, deterministic shard/row ordering, early stopping and completed-epoch resume. Resume generations commit with one atomic pointer; power-loss/concurrent-writer guarantees are outside this local workflow. Once `selection_freeze.json` exists, training refuses further selection in that directory. Evaluation failures support `--resume` only with the same frozen model/config/data. Use new dataset/model/report paths for a new independent experiment protocol.

See [Phase 2.1 report](docs/phase2_1_implementation_report.md), [ledger](docs/phase2_1_execution_ledger.md) and [file inventory](docs/phase2_1_file_inventory.md) for measured results and limitations. Model scores describe recorded discard behavior; they do not establish winning strength or unseen-player generalization. The 80–85% target refers to Top-1 and is a stretch goal.

## Phase 2.2: controlled MLP optimization

Phase 2.2 reuses the verified Phase 2.1 shards without extraction or filtering. Every historical test match stays excluded from fitting and selection. The permitted development pool combines the earlier train and validation roles. Identical input-only whole trajectories share a group; two deterministic development folds and two model seeds provide three paired comparisons. This is internal development evaluation. No new blind external cohort is available.

The bounded matrix retrains the original 1368→64→34 architecture as E0, then tests 128 and 256→128 hidden layers and one evidence-driven regularization change. All eight runs use the same frozen training budget. Minimum development NLL selects the primary candidate; paired classification, player, latency, game-safety and regression checks determine promotion. The model and decision freeze precede retrospective evaluation on the already-known Phase 2.1 test cohort. Saved v2 is excluded from fair development comparisons because its prior training overlaps these new folds.

The separate candidate uses `artifacts/models/mahjong_discard_mlp_v3.pt` and its metadata. Both older checkpoints and the service's default model path are preserved. The flexible MLP loader retains the original default architecture and validates explicit architecture, parameter count, development lineage and weight checksums before returning a model.

```sh
# Continue an interrupted, already initialized matrix under its frozen protocol:
.venv/bin/python -m training.optimization_runner --resume
# After all eight runs and a green full-suite XML:
.venv/bin/python -m pytest -q --junitxml=docs/evidence/phase2_2/full_suite.xml
.venv/bin/python -m training.optimization_finalize
# Recheck frozen evidence and repeat actual inference without further tuning:
.venv/bin/python -m training.optimization_finalize --verify-existing
.venv/bin/python -m pytest tests/test_phase2_2_*.py -q
```

Use the [Phase 2.2 report](docs/phase2_2_implementation_report.md) for the promotion decision, actual metrics and complete fresh-output initialization/reproduction commands. See also the [execution ledger](docs/phase2_2_execution_ledger.md) and [file inventory](docs/phase2_2_file_inventory.md). Completed matrices refuse further tuning in the same directory. Historical test results remain retrospective; accuracy measures imitation of recorded discards, and CPU/macOS is the tested deployment environment.

Weights, raw data, optimizer caches and bulky diagnostic dumps stay outside Git. See [artifact transfer and restore](docs/ml_artifact_transfer.md) for the checksum-verified v3 inference bundle and the additional local files required for full audit/retraining. A Git checkout alone does not contain the trained weights or corpus.
