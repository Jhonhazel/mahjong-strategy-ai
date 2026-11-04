# Phase 1 file inventory

The workspace was initially empty. Paths below are newly created; no prior implementation was overwritten.

| Exact path | Purpose |
| --- | --- |
| `README.md` | Setup, play, data and verification commands |
| `.gitignore` | Exclude venv/generated corpus |
| `requirements.txt` | Supported dependencies |
| `requirements-lock.txt` | Actual verified versions |
| `pytest.ini` | Focused/integration/dataset/slow categories |
| `THIRD_PARTY_NOTICES.md` | Dataset/library/source attribution |
| `app/__init__.py` | Package marker |
| `app/domain/__init__.py` | Package marker |
| `app/domain/actions.py` | Domain tile/action/data contract |
| `app/domain/exceptions.py` | Domain tile/action/data contract |
| `app/domain/models.py` | Domain tile/action/data contract |
| `app/domain/tiles.py` | Domain tile/action/data contract |
| `app/engine/__init__.py` | Package marker |
| `app/engine/fan_calculator.py` | MCR rules, scoring or private observation |
| `app/engine/feature_encoder.py` | MCR rules, scoring or private observation |
| `app/engine/mcr_referee.py` | MCR rules, scoring or private observation |
| `app/services/__init__.py` | Package marker |
| `app/services/bot_service.py` | Bot policy or session lifecycle |
| `app/services/game_service.py` | Bot policy or session lifecycle |
| `training/__init__.py` | Package marker |
| `training/dataset_loader.py` | Corpus acquisition, audit, replay or report publication |
| `training/inspect_dataset.py` | Corpus acquisition, audit, replay or report publication |
| `training/replay.py` | Corpus acquisition, audit, replay or report publication |
| `training/reporting.py` | Corpus acquisition, audit, replay or report publication |
| `training/verify_encoder_parity.py` | Corpus acquisition, audit, replay or report publication |
| `scripts/__init__.py` | Package marker |
| `scripts/check_env.py` | Environment/bootstrap/CLI entry point |
| `scripts/install_pymahjonggb.py` | Environment/bootstrap/CLI entry point |
| `scripts/play_cli_round.py` | Environment/bootstrap/CLI entry point |
| `tests/__init__.py` | Package marker |
| `tests/helpers.py` | Valid deterministic rule fixtures |
| `tests/test_cli.py` | Executable regression or integration test |
| `tests/test_dataset_audit.py` | Executable regression or integration test |
| `tests/test_dataset_resilience.py` | Executable regression or integration test |
| `tests/test_encoder_parity.py` | Executable regression or integration test |
| `tests/test_env_bootstrap.py` | Executable regression or integration test |
| `tests/test_fan_calculator.py` | Executable regression or integration test |
| `tests/test_feature_encoder.py` | Executable regression or integration test |
| `tests/test_game_service.py` | Executable regression or integration test |
| `tests/test_mcr_engine_playthrough.py` | Executable regression or integration test |
| `tests/test_source_action_contract.py` | Executable regression or integration test |
| `tests/test_tiles_and_actions.py` | Executable regression or integration test |
| `docs/MAHJONG_PHASE1_RINGKASAN_REVISI_DAN_GATE.md` | Approved source document, copied unchanged |
| `docs/evidence/cli-round-42.txt` | Actual command/review evidence |
| `docs/evidence/code-review.md` | Actual command/review evidence |
| `docs/evidence/dataset-acquisition.txt` | Actual command/review evidence |
| `docs/evidence/dataset-audit.txt` | Actual command/review evidence |
| `docs/evidence/encoder-parity.txt` | Actual command/review evidence |
| `docs/evidence/engine-stress.txt` | Actual command/review evidence |
| `docs/evidence/fast-tests.txt` | Actual command/review evidence |
| `docs/evidence/final-publication-red.txt` | Actual command/review evidence |
| `docs/evidence/final-review-red.txt` | Actual command/review evidence |
| `docs/evidence/full-suite.txt` | Actual command/review evidence |
| `docs/evidence/git-diff-check.txt` | Actual command/review evidence |
| `docs/evidence/parity-attempt-60-after-roster-fix.json` | Actual command/review evidence |
| `docs/evidence/parity-attempt-60.json` | Actual command/review evidence |
| `docs/evidence/pytest-results.xml` | Actual command/review evidence |
| `docs/evidence/task2-red.txt` | Actual command/review evidence |
| `docs/evidence/task3-red.txt` | Actual command/review evidence |
| `docs/evidence/task4-red.txt` | Actual command/review evidence |
| `docs/evidence/task5-red.txt` | Actual command/review evidence |
| `docs/evidence/task6-8-red.txt` | Actual command/review evidence |
| `docs/evidence/task7-audit-red.txt` | Actual command/review evidence |
| `docs/evidence/task7-loader-red.txt` | Actual command/review evidence |
| `docs/evidence/task7-parity-red.txt` | Actual command/review evidence |
| `docs/evidence/verification_summary.json` | Actual command/review evidence |
| `docs/execution_ledger.md` | Implementation, decisions or file inventory documentation |
| `docs/file_inventory.md` | Implementation, decisions or file inventory documentation |
| `docs/phase1_implementation_report.md` | Implementation, decisions or file inventory documentation |
| `docs/superpowers/plans/2026-11-04-mahjong-strategy-ai-phase1_REVISI_AUDIT.md` | Approved source document, copied unchanged |
| `docs/superpowers/specs/2026-11-04-mahjong-strategy-ai-phase1-design_REVISI_AUDIT.md` | Approved source document, copied unchanged |

## Generated / ignored artifacts

- `datasets/.gitkeep` — executed report, corpus or provenance artifact.
- `datasets/environment_report.json` — executed report, corpus or provenance artifact.
- `datasets/acquisition_report.json` — executed report, corpus or provenance artifact.
- `datasets/audit_report.json` — executed report, corpus or provenance artifact.
- `datasets/strict_audit_report.json` — executed report, corpus or provenance artifact.
- `datasets/parity_report.json` — executed report, corpus or provenance artifact.
- `datasets/data_contract.json` — executed report, corpus or provenance artifact.
- `datasets/decision_manifest.csv` — executed report, corpus or provenance artifact.
- `datasets/strict_decisions/accepted.npz` — executed report, corpus or provenance artifact.
- `datasets/cli_round_42.json` — executed report, corpus or provenance artifact.
- `datasets/finalist_decisions.tar.gz` — executed report, corpus or provenance artifact.
- `datasets/finalist_games.tar.gz` — executed report, corpus or provenance artifact.

`datasets/finalist_decisions/*.npz` contains the 30 safely extracted original files; `datasets/references/` contains source/metadata references. `.venv/` contains installed dependencies. These generated contents remain outside future Git tracking under `.gitignore`.
