"""Read-only, fixed-policy analysis of the frozen v3 internal validation cohort.

Run from the repository root with ``python -m scripts.evaluate_recommendation_policy
--output docs/evidence/recommendation_threshold_2026_11_11/validation_policy.json``.
This never trains, calibrates, selects thresholds, or evaluates test cohorts.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
import torch

from app.mlp import masked_log_probabilities
from app.model_checkpoint import load_checkpoint
from app.services.recommendation_policy import RECOMMENDATION_POLICY, filter_recommendations
from training.dataset_loader import file_sha256
from training.expanded_dataset import SPLITS, canonical_hash, split_for_match
from training.expanded_training import ShardCorpus
from training.optimization_data import development_splits


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIRECTORY = ROOT / 'docs/evidence/recommendation_threshold_2026_11_11'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'rate': numerator / denominator if denominator else None}


class PolicyMetrics:
    """Decision-weighted counters applying the actual server presentation policy."""

    def __init__(self):
        self.samples = 0
        self.distribution = Counter({str(n): 0 for n in range(4)})
        self.included = 0

    def update(self, scores, targets, masks):
        require(scores.ndim == 2 and scores.shape[1] == 34 and
                masks.shape == scores.shape and masks.dtype == np.bool_ and
                targets.shape == (len(scores),) and targets.dtype.kind in 'iu',
                'Invalid policy evaluation batch')
        require(np.all((targets >= 0) & (targets < 34)) and
                masks[np.arange(len(targets)), targets].all(), 'Illegal observed target')
        for probabilities, target, legal in zip(scores, targets, masks):
            suggestions = filter_recommendations(probabilities.tolist(), legal.tolist())['suggestions']
            self.distribution[str(len(suggestions))] += 1
            self.included += int(any(row['class_index'] == target for row in suggestions))
            self.samples += 1

    def finish(self):
        require(self.samples > 0, 'Empty validation cohort')
        covered = self.samples - self.distribution['0']
        return {
            'samples': self.samples,
            'coverage': fraction(covered, self.samples),
            'suggestion_count_distribution': {
                str(n): {'count': self.distribution[str(n)], 'denominator': self.samples,
                         'rate': self.distribution[str(n)] / self.samples}
                for n in range(4)
            },
            'target_inclusion_all_decisions': fraction(self.included, self.samples),
            'target_inclusion_covered_decisions': fraction(self.included, covered),
        }


def prepare_validation():
    dataset = ROOT / 'datasets/expanded_strict_v2'
    checkpoint = ROOT / 'artifacts/models/mahjong_discard_mlp_v3.pt'
    contract_path = dataset / 'data_contract.json'
    freeze_path = ROOT / 'artifacts/phase2_2/candidate_freeze.json'
    lineage_path = ROOT / 'artifacts/phase2_2/evaluation_lineage.json'
    protocol_path = ROOT / 'artifacts/phase2_2/protocol.json'
    files = [checkpoint, checkpoint.with_suffix('.metadata.json'), contract_path,
             freeze_path, lineage_path, protocol_path]
    before = {path: file_sha256(path) for path in files}
    contract = json.loads(contract_path.read_text())
    frozen = json.loads(freeze_path.read_text())
    model, metadata = load_checkpoint(checkpoint, expected_contract=contract)
    development = metadata['development']
    require(frozen['status'] == 'FROZEN' and
            frozen['checkpoint'] == str(checkpoint.relative_to(ROOT)) and
            frozen['checkpoint_sha256'] == before[checkpoint] and
            frozen['dataset_contract_sha256'] == before[contract_path] and
            frozen['metadata_content_sha256'] == canonical_hash({
                key: value for key, value in metadata.items() if key != 'test_evaluation'
            }), 'Frozen checkpoint, metadata, or dataset contract changed')
    require(development['fold_id'] == 0 and development['new_blind_test_available'] is False,
            'Expected frozen primary internal validation fold')
    require(canonical_hash(json.loads(lineage_path.read_text())) ==
            development['lineage_content_sha256'] and
            before[protocol_path] == development['protocol_sha256'],
            'Frozen development lineage or protocol changed')
    history = ROOT / development['history_reference']
    before[history] = file_sha256(history)
    require(before[history] == development['history_sha256'], 'Frozen training history changed')

    # The normal constructor reruns the complete dataset audit and may write on
    # failure. Here the frozen contract plus verified compressed-shard hashes
    # establish byte identity; scan only match/split arrays to reconstruct folds.
    corpus = ShardCorpus.__new__(ShardCorpus)
    corpus.root = dataset
    corpus.contract = contract
    corpus.contract_sha256 = before[contract_path]
    corpus.allow_test = False
    corpus.group_keys = development['trajectory_group_keys']
    counts = Counter()
    validation_ids = set(development['validation_match_ids'])
    relevant_shards = []
    shard_evidence = []
    for shard in contract['shards']:
        path = dataset / shard['path'] / 'samples.npz'
        require(path.resolve().is_relative_to(dataset.resolve()), 'Shard path leaves dataset')
        before[path] = file_sha256(path)
        require(before[path] == shard['sha256']['samples.npz'], 'Frozen NPZ shard changed')
        with np.load(path, allow_pickle=False) as storage:
            matches, roles = storage['match_id'], storage['split']
        require(matches.shape == roles.shape == (shard['samples'],), 'Shard membership shape differs')
        permitted = np.isin(roles, [SPLITS.index('train'), SPLITS.index('validation')])
        for match in np.unique(matches[permitted]):
            expected_role = split_for_match(str(match), contract['original_roles'])
            require(expected_role in ('train', 'validation') and
                    np.all(roles[matches == match] == SPLITS.index(expected_role)),
                    'Development match has inconsistent original split')
        counts.update(map(str, matches[permitted]))
        selected = np.fromiter((match in validation_ids for match in matches), bool, len(matches))
        require(not np.any(selected & ~permitted), 'Validation member found in excluded split')
        if selected.any():
            relevant_shards.append(shard)
            shard_evidence.append({'path': str(path.relative_to(ROOT)),
                                   'sha256': before[path], 'validation_samples': int(selected.sum())})
    corpus.quality = {'samples_per_match': dict(counts)}
    corpus.shards = contract['shards']
    training, validation = development_splits(corpus, development['fold_id'])
    require(training.match_ids == set(development['training_match_ids']) and
            validation.match_ids == validation_ids and
            training.samples == development['training_samples'] and
            validation.samples == development['validation_samples'],
            'Actual development cohort differs from frozen model metadata')
    require(not validation.match_ids.intersection(development['historical_test_match_ids']),
            'Historical test entered validation')
    corpus.shards = relevant_shards
    return model, metadata, validation, before, shard_evidence


def evaluate(batch_size=512, threads=1):
    require(type(batch_size) is int and 1 <= batch_size <= 4096, 'Batch size must be 1..4096')
    require(type(threads) is int and 1 <= threads <= 4, 'CPU threads must be 1..4')
    require(RECOMMENDATION_POLICY.minimum_score == .10 and
            RECOMMENDATION_POLICY.maximum_suggestions == 3, 'Expected fixed 10%, max-three policy')
    started = time.perf_counter()
    torch.set_num_threads(threads)
    model, metadata, validation, before, shards = prepare_validation()
    source_paths = [Path(__file__), ROOT / 'app/services/recommendation_policy.py',
                    ROOT / 'app/mlp.py', ROOT / 'app/model_checkpoint.py',
                    ROOT / 'training/expanded_training.py', ROOT / 'training/optimization_data.py',
                    ROOT / 'training/expanded_dataset.py']
    before.update({path: file_sha256(path) for path in source_paths})
    metrics = PolicyMetrics()
    observed_matches = Counter()
    batches = 0
    with torch.inference_mode():
        for features, targets, masks, identities in validation.batches(batch_size):
            scores = masked_log_probabilities(model(torch.from_numpy(features)),
                                              torch.from_numpy(masks)).exp().numpy()
            metrics.update(scores, targets, masks)
            observed_matches.update(map(str, identities['match_id']))
            batches += 1
    require(dict(observed_matches) == validation.match_counts, 'Inference cohort membership/count differs')
    require(all(file_sha256(path) == digest for path, digest in before.items()),
            'Read-only input integrity changed during evaluation')
    return {
        'status': 'PASS', 'evaluated_at_utc': datetime.now(timezone.utc).isoformat(),
        'evaluation_kind': 'retrospective_internal_validation',
        'new_independent_blind_test': False,
        'policy': {'minimum_score': .10, 'maximum_suggestions': 3,
                   'score_transform': 'none; original masked model probabilities',
                   'selection': 'fixed before evaluation; no threshold comparison or optimization'},
        'cohort': {'source': 'v3 metadata.development.validation_match_ids', 'fold_id': 0,
                   'matches': len(observed_matches), 'samples': validation.samples,
                   'match_ids_sha256': canonical_hash(sorted(observed_matches)),
                   'match_counts_sha256': canonical_hash(dict(observed_matches)),
                   'training_overlap_matches': 0, 'test_or_historical_test_rows_inferred': 0},
        'metrics': metrics.finish(),
        'execution': {'device': 'cpu', 'batch_size': batch_size, 'cpu_threads': threads,
                      'batches': batches, 'seconds': time.perf_counter() - started,
                      'torch_version': str(torch.__version__), 'numpy_version': str(np.__version__),
                      'maximum_shard_rows': max(shard['samples'] for shard in validation.corpus.shards)},
        'provenance': {'model_version': metadata['model_version'],
                       'inputs_unchanged_after_evaluation': True,
                       'input_sha256': {str(path.relative_to(ROOT)): digest for path, digest in before.items()
                                        if path.suffix != '.npz'},
                       'verified_npz_shards': len(validation.corpus.contract['shards']),
                       'relevant_shard_sha256': shards,
                       'verification': 'Frozen checkpoint/metadata/contract and all compressed NPZ hashes; '
                                       'exact actual train/validation memberships and per-match sample counts; '
                                       'existing development_splits and ShardSplit loader; no full replay audit'},
        'limitations': ['This validation fold was already used for checkpoint/model selection; '
                        'it is not a new independent blind test.',
                        'Target inclusion measures observed discard agreement, not optimal play or win probability.',
                        'Rates are weighted by decisions; known-player and repeated-state dependence remains.',
                        'Test and historical_test rows were excluded from inference; no training, calibration, '
                        'downloads, threshold search, or artifact/database writes were performed.'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--batch-size', type=int, default=512)
    parser.add_argument('--threads', type=int, default=1)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.parent == EVIDENCE_DIRECTORY.resolve() and
            output.name.startswith('validation_policy') and output.suffix == '.json',
            'Output must be a new validation_policy*.json in the designated evidence directory')
    require(not output.exists(), 'Output already exists; refusing to overwrite evidence')
    report = evaluate(args.batch_size, args.threads)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'cohort', 'metrics', 'execution')}, indent=2))


if __name__ == '__main__':
    main()
