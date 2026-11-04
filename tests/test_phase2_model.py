import math

import numpy as np
import pytest
import torch


def test_original_mlp_dimensions_parameters_and_real_optimizer_step():
    from app.mlp import MahjongDiscardMLP, masked_cross_entropy
    torch.manual_seed(7)
    model = MahjongDiscardMLP()
    assert sum(p.numel() for p in model.parameters()) == 89826
    features = torch.rand(4, 1368)
    logits = model(features)
    assert logits.shape == (4, 34) and logits.dtype == torch.float32
    masks = torch.zeros((4, 34), dtype=torch.bool)
    masks[:, :3] = True
    targets = torch.tensor([0, 1, 2, 0])
    before = {k: v.detach().clone() for k, v in model.state_dict().items()}
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
    optimizer.zero_grad(set_to_none=True)
    loss = masked_cross_entropy(logits, targets, masks)
    assert torch.isfinite(loss)
    loss.backward()
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.parameters())
    optimizer.step()
    assert any(not torch.equal(before[k], v) for k, v in model.state_dict().items())


def test_illegal_logits_do_not_compete_or_receive_gradients():
    from app.mlp import masked_cross_entropy, masked_log_probabilities
    logits = torch.zeros((2, 34), requires_grad=True)
    with torch.no_grad():
        logits[:, 5] = 1000.
    masks = torch.zeros((2, 34), dtype=torch.bool)
    masks[0, [0, 33]] = True
    masks[1, [2, 3]] = True
    before = logits.detach().clone()
    loss = masked_cross_entropy(logits, torch.tensor([0, 3]), masks)
    assert loss.item() == pytest.approx(math.log(2))
    loss.backward()
    assert torch.equal(logits.detach(), before)
    assert torch.equal(logits.grad[~masks], torch.zeros_like(logits.grad[~masks]))
    assert logits.grad[masks].abs().sum() > 0
    probabilities = masked_log_probabilities(logits, masks).exp()
    assert torch.equal(probabilities[~masks], torch.zeros_like(probabilities[~masks]))
    assert torch.allclose(probabilities.sum(dim=1), torch.ones(2))


@pytest.mark.parametrize("tamper", ["empty", "illegal_target", "float_mask", "nan", "bad_shape", "bad_target"])
def test_masked_loss_rejects_invalid_states(tamper):
    from app.mlp import masked_cross_entropy
    logits = torch.zeros((2, 34), requires_grad=True)
    masks = torch.zeros((2, 34), dtype=torch.bool)
    masks[:, :2] = True
    targets = torch.tensor([0, 1])
    if tamper == "empty": masks[0] = False
    elif tamper == "illegal_target": targets[0] = 33
    elif tamper == "float_mask": masks = masks.float()
    elif tamper == "nan":
        with torch.no_grad(): logits[0, 0] = torch.nan
    elif tamper == "bad_shape": logits = torch.zeros((2, 33))
    else: targets[0] = 34
    with pytest.raises(ValueError):
        masked_cross_entropy(logits, targets, masks)


def test_single_legal_class_has_finite_zero_loss():
    from app.mlp import masked_cross_entropy
    masks = torch.zeros((1, 34), dtype=torch.bool)
    masks[0, 33] = True
    assert masked_cross_entropy(torch.rand(1, 34), torch.tensor([33]), masks).item() == 0.
