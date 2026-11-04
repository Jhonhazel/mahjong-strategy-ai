import numpy as np
import pytest


def metric_fixture():
    # Four outcomes: true [0,0,1,2], predicted [0,1,1,1].
    probabilities = np.zeros((4, 34), dtype=np.float64)
    probabilities[:, :3] = [[.6, .3, .1], [.2, .7, .1], [.1, .8, .1], [.2, .6, .2]]
    logs = np.full((4, 34), -np.inf)
    logs[:, :3] = np.log(probabilities[:, :3])
    masks = probabilities > 0
    return logs, np.array([0, 0, 1, 2]), masks


def test_hand_calculated_metrics_and_zero_support_convention():
    from training.metrics import classification_metrics
    logs, targets, masks = metric_fixture()
    result = classification_metrics(logs, targets, masks)
    assert result["samples"] == 4
    assert result["top1"] == .5 and result["top3"] == 1.
    assert result["legal_rate"] == 1.
    assert result["nll"] == pytest.approx(-np.log([.6, .2, .8, .2]).mean())
    assert result["per_class"][0]["precision"] == 1.
    assert result["per_class"][0]["recall"] == .5
    assert result["per_class"][0]["f1"] == pytest.approx(2/3)
    assert result["per_class"][1]["f1"] == .5
    assert result["macro_f1_34"] == pytest.approx((2/3 + .5) / 34)
    assert result["macro_f1_supported"] == pytest.approx((2/3 + .5) / 3)
    assert result["confusion_matrix"][0][:3] == [1, 1, 0]
    assert result["confusion_matrix"][1][:3] == [0, 1, 0]
    assert result["confusion_matrix"][2][:3] == [0, 1, 0]
    assert result["per_class"][33]["support"] == 0 and result["per_class"][33]["f1"] == 0


def test_top3_uses_only_available_legal_classes_and_ties_are_stable():
    from training.metrics import classification_metrics, rank_legal_classes
    logs = np.full((2, 34), -np.inf)
    masks = np.zeros((2, 34), dtype=bool)
    masks[0, [4, 9]] = True
    masks[1, 33] = True
    logs[0, [4, 9]] = np.log(.5)
    logs[1, 33] = 0.
    rankings = rank_legal_classes(logs, masks)
    assert [r.tolist() for r in rankings] == [[4, 9], [33]]
    result = classification_metrics(logs, np.array([9, 33]), masks)
    assert result["top1"] == .5 and result["top3"] == 1.
    assert result["legal_rate"] == 1.


@pytest.mark.parametrize("tamper", ["empty", "illegal_target", "nan", "unnormalized"])
def test_invalid_metric_inputs_fail_explicitly(tamper):
    from training.metrics import classification_metrics
    logs, targets, masks = metric_fixture()
    if tamper == "empty": masks[0] = False
    elif tamper == "illegal_target": targets[0] = 33
    elif tamper == "nan": logs[0, 0] = np.nan
    else: logs[0, :3] += 1
    with pytest.raises(ValueError):
        classification_metrics(logs, targets, masks)


def test_baselines_fit_training_only_and_are_legal_and_reproducible():
    from training.baselines import class_prior_log_probabilities, random_legal_log_probabilities
    from training.metrics import rank_legal_classes
    masks = np.zeros((40, 34), dtype=bool)
    masks[:, [0, 1, 33]] = True
    train_labels = np.array([0, 0, 0, 1, 33], dtype=np.int64)
    log_prior = class_prior_log_probabilities(train_labels, masks)
    assert rank_legal_classes(log_prior, masks)[0].tolist() == [0, 1, 33]
    # Add-one training prior: counts [3,1,1] -> legal probabilities [4,2,2]/8.
    assert np.exp(log_prior[0, [0, 1, 33]]).tolist() == pytest.approx([.5, .25, .25])
    random_logs, first = random_legal_log_probabilities(masks, seed=2026)
    _, again = random_legal_log_probabilities(masks, seed=2026)
    _, different = random_legal_log_probabilities(masks, seed=2027)
    assert all(np.array_equal(a, b) for a, b in zip(first, again))
    assert any(not np.array_equal(a, b) for a, b in zip(first, different))
    assert all(set(r) == {0, 1, 33} for r in first)
    assert np.exp(random_logs[0, [0, 1, 33]]).tolist() == pytest.approx([1/3] * 3)
