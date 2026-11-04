import numpy as np
import pytest
import torch


def toy_split(name, n=12):
    """Isolated optimizer fixture, never used for reported model performance."""
    from training.phase2_dataset import PreparedSplit
    features = np.zeros((n, 1368), dtype=np.float32)
    targets = np.arange(n, dtype=np.int64) % 3
    features[np.arange(n), targets] = 1.
    masks = np.zeros((n, 34), dtype=bool)
    masks[:, :3] = True
    return PreparedSplit(name, features, targets, masks, np.array([name + "-fixture"] * n), np.arange(n))


def test_early_stopping_selects_minimum_validation_and_stops_after_patience():
    from training.train_mlp import EarlyStopping
    stop = EarlyStopping(patience=2)
    decisions = [stop.observe(i, value) for i, value in enumerate([1.2, 1., 1.1, 1.15], 1)]
    assert decisions == [True, True, False, False]
    assert stop.best_epoch == 2 and stop.best_loss == 1.
    assert stop.should_stop
    with pytest.raises(ValueError):
        stop.observe(5, float("nan"))


def test_real_training_updates_weights_and_restores_independent_best_state():
    from training.train_mlp import TrainConfig, train_model, predict_log_probabilities
    from training.metrics import classification_metrics
    train, validation = toy_split("train"), toy_split("validation")
    config = TrainConfig(max_epochs=4, patience=2, batch_size=4, device="cpu", seed=7)
    result = train_model(train, validation, config)
    assert 1 <= result.best_epoch <= result.epochs_executed <= 4
    assert result.initial_weights_sha256 != result.best_weights_sha256
    assert result.optimizer_steps > 0 and result.elapsed_seconds > 0
    assert all(np.isfinite(r["train_loss"]) and np.isfinite(r["validation_loss"]) for r in result.history)
    assert result.best_validation_metrics["nll"] == min(r["validation_loss"] for r in result.history)
    logs = predict_log_probabilities(result.model, validation, "cpu")
    actual = classification_metrics(logs, validation.targets, validation.legal_masks)
    assert actual["nll"] == pytest.approx(result.best_validation_metrics["nll"])
    assert result.model.training is False
    original = {k: v.clone() for k, v in result.best_state_dict.items()}
    with torch.no_grad():
        next(result.model.parameters()).add_(1.)
    assert all(torch.equal(original[k], v) for k, v in result.best_state_dict.items())


def test_cpu_training_is_repeatable_with_same_seed():
    from training.train_mlp import TrainConfig, train_model
    config = TrainConfig(max_epochs=2, batch_size=6, device="cpu", seed=18)
    first = train_model(toy_split("train"), toy_split("validation"), config)
    second = train_model(toy_split("train"), toy_split("validation"), config)
    assert first.best_weights_sha256 == second.best_weights_sha256
    assert first.history == second.history


def test_training_rejects_test_split_before_reading_its_labels():
    from training.train_mlp import TrainConfig, train_model
    class HeldOut:
        name = "test"
        @property
        def targets(self):
            raise AssertionError("Test labels must not be read for model selection")
    with pytest.raises(ValueError, match="train.*validation"):
        train_model(toy_split("train"), HeldOut(), TrainConfig(max_epochs=1, device="cpu"))


def test_training_rejects_overlapping_match_groups():
    from training.train_mlp import TrainConfig, train_model
    from training.phase2_dataset import PreparedSplit
    train = toy_split("train")
    bad_validation = PreparedSplit("validation", train.features, train.targets, train.legal_masks, train.match_ids, train.row_indices)
    with pytest.raises(ValueError, match="overlap"):
        train_model(train, bad_validation, TrainConfig(max_epochs=1, device="cpu"))
