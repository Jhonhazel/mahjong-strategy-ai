# Fixed 10% recommendation policy: internal validation

The policy was evaluated once on the frozen v3 fold-0 validation cohort: **350,917 decisions across 6,914 matches**. This cohort was already used for checkpoint/model selection. These are retrospective internal validation results, **not a new independent blind test**.

The fixed policy retains original masked-model scores at or above 10%, returns at most three suggestions, and breaks ties by class index. No threshold search, training, calibration, downloads, or source/artifact/database writes were performed.

| Metric | Numerator / denominator | Rate |
| --- | ---: | ---: |
| Coverage: at least one suggestion | 350,555 / 350,917 decisions | 99.8968% |
| Zero suggestions | 362 / 350,917 decisions | 0.1032% |
| One suggestion | 135,132 / 350,917 decisions | 38.5083% |
| Two suggestions | 99,617 / 350,917 decisions | 28.3876% |
| Three suggestions | 115,806 / 350,917 decisions | 33.0010% |
| Observed target included, all decisions | 289,312 / 350,917 decisions | 82.4446% |
| Observed target included, covered decisions | 289,312 / 350,555 decisions | 82.5297% |

Target inclusion measures agreement with the observed recorded discard, not optimal play or winning probability. Rates are weighted by decisions; known-player and repeated-state dependence remains.

Command (run from the repository root):

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.evaluate_recommendation_policy --output docs/evidence/recommendation_threshold_2026_11_11/validation_policy.json
```

The run completed in 9.523 seconds on one CPU thread with batch size 512, 860 batches, and a maximum shard size of 7,657 rows. The evaluator uses the existing `development_splits` and `ShardSplit` loader, reconstructs exact metadata validation membership and per-match counts, and excludes test/historical-test rows from inference. It verifies frozen checkpoint/metadata/contract/history/protocol/lineage identities and all 349 compressed NPZ shard hashes. It does not rerun the full replay audit. All 363 recorded inputs remained unchanged in a separate post-run verification.

- Checkpoint SHA-256: `ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720`
- Validation match-set SHA-256: `66f908b742b8907e0e0486d57aae2de8a760509f1833449d5061e23da92d2797`
- Full report SHA-256: `30ba8f94d1e8289098c1c9dc8d6490ddb0d44b8cd69c083cc4415c4db95709f6`
- Full scores/provenance: `validation_policy.json`; run output: `validation_policy_run.txt`; post-run verification: `validation_policy_integrity.json`.
- Focused aggregation and policy checks: **23 passed** using `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_recommendation_evaluation.py tests/test_recommendation_policy.py -q -p no:cacheprovider`; captured in `validation_policy_verified_tests.txt`. Initial missing-evaluator red tests are recorded in `validation_policy_red.txt`.

The script refuses to overwrite an existing output and restricts new JSON evidence to this directory. The complete application suite is owned by the main implementation task and was not independently rerun for this analysis.
