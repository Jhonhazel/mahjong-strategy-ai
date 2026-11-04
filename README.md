# Mahjong Strategy AI — Phase 1

Playable Botzone Chinese Standard Mahjong (MCR), one human and three local shanten bots. Phase 1 includes the 136/144-tile referee, scoring, private-seat encoder, CLI, corpus audit and strict re-extraction. Training, web APIs, PostgreSQL and frontend are later phases.

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

## Interfaces for later phases

- `EncodedTurnState`: `obs int8[38,4,9]` (flattened 1,368 inputs), `legal_mask bool[235]`, `legal_discard_mask bool[34]`, seat, turn, version `ijcai2026_mcr_v1_strict`.
- Channel 0/1 = seat/prevalent wind; 2–5 = own hand unary counts; 6–21 = historical discards by relative seat; 22–37 = known meld tiles by relative seat. Honor-row columns 7/8 are padding. Relative seats are self/next/opposite/previous. Claimed tiles remain in discard history; physical conservation uses a separate river.
- Botzone action IDs: Pass 0, Hu 1, Play 2–35, Chi 36–98, Peng 99–132, MingGang 133–166, AnGang 167–200, BuGang 201–234. Phase 2 discard classes are `action_id - 2`, 0–33. Always apply the legal mask.
- `GameSessionService`: create/get/view/submit/delete/shutdown. A human submission **must include `expected_turn_number`** from the returned view. Stale or missing tokens are rejected. New sessions are bounded; in-flight sessions are never expired or evicted. Per-game locks serialize operations; shutdown drains accepted work.
- Wall scheduling follows the actual Botzone variant: each seat draws its own segment backwards, and a round ends when the required drawer's segment is empty. This can leave tiles in other segments. It is not a physical continuous wall simulator.
- Only manifest rows from `strict_decisions/accepted.npz` are approved for future training. Arrays include real source `score`, `match_id`, and `seat`. Keep every `match_id` in exactly one train/validation/test group. `partition_for_match` defines reproducible 80/10/10 buckets; group evidence is checked now, not a model training pipeline.

See [implementation report](docs/phase1_implementation_report.md), [execution ledger](docs/execution_ledger.md), and [third-party attribution](THIRD_PARTY_NOTICES.md). Historical approved plans under `docs/superpowers/` are unchanged. No Git repository existed at preflight; no Git publishing operations were performed.
