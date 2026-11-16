import numpy as np
import pytest


def test_policy_aggregation_reports_coverage_distribution_and_explicit_denominators():
    from scripts.evaluate_recommendation_policy import PolicyMetrics

    scores = np.zeros((5, 34), dtype=np.float64)
    scores[0, :11] = 1 / 11
    scores[1, :4] = [.85, .05, .05, .05]
    scores[2, :4] = [.55, .35, .05, .05]
    scores[3, :4] = [.4, .3, .2, .1]
    scores[4, :4] = [.7, .1, .1, .1]
    masks = scores > 0
    targets = np.array([0, 0, 2, 3, 2])
    metrics = PolicyMetrics()
    metrics.update(scores[:2], targets[:2], masks[:2])
    metrics.update(scores[2:], targets[2:], masks[2:])

    result = metrics.finish()
    assert result['samples'] == 5
    assert result['coverage'] == {'numerator': 4, 'denominator': 5, 'rate': .8}
    assert result['suggestion_count_distribution'] == {
        '0': {'count': 1, 'denominator': 5, 'rate': .2},
        '1': {'count': 1, 'denominator': 5, 'rate': .2},
        '2': {'count': 1, 'denominator': 5, 'rate': .2},
        '3': {'count': 2, 'denominator': 5, 'rate': .4},
    }
    assert result['target_inclusion_all_decisions'] == {
        'numerator': 2, 'denominator': 5, 'rate': .4,
    }
    assert result['target_inclusion_covered_decisions'] == {
        'numerator': 2, 'denominator': 4, 'rate': .5,
    }


def test_policy_aggregation_rejects_empty_cohort_and_illegal_targets():
    from scripts.evaluate_recommendation_policy import PolicyMetrics

    metrics = PolicyMetrics()
    with pytest.raises(ValueError, match='Empty'):
        metrics.finish()
    scores = np.zeros((1, 34)); scores[0, 0] = 1
    with pytest.raises(ValueError, match='target'):
        metrics.update(scores, np.array([1]), scores > 0)


def test_policy_aggregation_has_defined_conditional_rate_when_no_decision_is_covered():
    from scripts.evaluate_recommendation_policy import PolicyMetrics

    scores = np.zeros((1, 34)); scores[0, :11] = 1 / 11
    metrics = PolicyMetrics()
    metrics.update(scores, np.array([0]), scores > 0)
    assert metrics.finish()['target_inclusion_covered_decisions'] == {
        'numerator': 0, 'denominator': 0, 'rate': None,
    }


def test_existing_evidence_is_preserved_and_rejected_before_evaluation(tmp_path, monkeypatch):
    import scripts.evaluate_recommendation_policy as module

    output = tmp_path / 'validation_policy.json'
    output.write_text('existing evidence')
    monkeypatch.setattr(module, 'EVIDENCE_DIRECTORY', tmp_path)
    monkeypatch.setattr('sys.argv', ['evaluate', '--output', str(output)])
    monkeypatch.setattr(module, 'evaluate', lambda *args: pytest.fail('Evaluation must not run'))
    with pytest.raises(ValueError, match='already exists'):
        module.main()
    assert output.read_text() == 'existing evidence'
