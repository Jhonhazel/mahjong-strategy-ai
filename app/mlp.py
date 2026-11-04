"""Shared observation conversion for training and advisory inference."""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

INPUT_SHAPE = (38, 4, 9)
INPUT_SIZE = 1368
NUM_CLASSES = 34
MLP_SPEC = {"name": "MahjongDiscardMLP", "architecture_version": "discard_mlp_v1", "input_dim": 1368, "hidden_dim": 64, "output_dim": 34, "activation": "ReLU", "dropout": 0.2}


def architecture_spec(hidden_dims=(64,),dropout=.2):
    widths=tuple(hidden_dims)
    if any(type(width)is not int for width in widths) or widths not in ((64,),(128,),(256,128),(512,256)):
        raise ValueError("Unsupported bounded MLP hidden dimensions")
    if type(dropout) not in (int,float) or not np.isfinite(dropout) or not 0<=dropout<=.5:
        raise ValueError("Dropout must be finite in [0,0.5]")
    if widths==(64,) and dropout==.2:return dict(MLP_SPEC)
    return {'name':'MahjongDiscardMLP','architecture_version':'discard_mlp_flexible_v1','input_dim':1368,'hidden_dims':list(widths),'output_dim':34,'activation':'ReLU','dropout':float(dropout)}


def validate_architecture(spec):
    if spec==MLP_SPEC:return dict(MLP_SPEC)
    try:
        normalized=architecture_spec(spec['hidden_dims'],spec['dropout'])
        if spec!=normalized:raise ValueError("Unknown architecture version/shape/activation")
        return normalized
    except (KeyError,TypeError) as exc:raise ValueError("Malformed MLP architecture") from exc


def parameter_count(spec):
    spec=validate_architecture(spec)
    widths=[1368]+([spec['hidden_dim']] if 'hidden_dim' in spec else spec['hidden_dims'])+[34]
    return sum((before+1)*after for before,after in zip(widths,widths[1:]))


class MahjongDiscardMLP(nn.Module):
    def __init__(self,spec=None):
        super().__init__()
        self.architecture=validate_architecture(MLP_SPEC if spec is None else spec)
        hidden=[self.architecture['hidden_dim']] if 'hidden_dim' in self.architecture else self.architecture['hidden_dims']
        layers=[];previous=INPUT_SIZE
        for width in hidden:
            layers.extend([nn.Linear(previous,width),nn.ReLU(),nn.Dropout(self.architecture['dropout'])]);previous=width
        layers.append(nn.Linear(previous,NUM_CLASSES))
        self.network = nn.Sequential(*layers)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        if features.ndim != 2 or features.shape[1] != INPUT_SIZE or features.dtype != torch.float32 or not len(features):
            raise ValueError("MLP input must be nonempty float32 (N,1368)")
        if not torch.isfinite(features).all():
            raise ValueError("MLP features must be finite")
        return self.network(features)


def masked_logits(logits: torch.Tensor, legal_masks: torch.Tensor) -> torch.Tensor:
    if logits.ndim != 2 or logits.shape[1] != NUM_CLASSES or logits.dtype != torch.float32 or not len(logits):
        raise ValueError("Logits must be nonempty float32 (N,34)")
    if legal_masks.shape != logits.shape or legal_masks.dtype != torch.bool or legal_masks.device != logits.device:
        raise ValueError("Masks must be bool (N,34) on the logits device")
    if not torch.isfinite(logits).all() or not legal_masks.any(dim=1).all():
        raise ValueError("Logits must be finite and every row needs a legal discard")
    return logits.masked_fill(~legal_masks, -torch.inf)


def masked_log_probabilities(logits: torch.Tensor, legal_masks: torch.Tensor) -> torch.Tensor:
    return F.log_softmax(masked_logits(logits, legal_masks), dim=1)


def masked_cross_entropy(logits: torch.Tensor, targets: torch.Tensor, legal_masks: torch.Tensor) -> torch.Tensor:
    masked = masked_logits(logits, legal_masks)
    if targets.shape != (len(logits),) or targets.dtype != torch.long or targets.device != logits.device:
        raise ValueError("Targets must be int64 (N,) on the logits device")
    if torch.any((targets < 0) | (targets >= NUM_CLASSES)) or not legal_masks.gather(1, targets[:, None]).all():
        raise ValueError("Every target must be a legal class 0..33")
    loss = F.cross_entropy(masked, targets)
    if not torch.isfinite(loss):
        raise ValueError("Masked cross entropy is not finite")
    return loss


def encode_observations(observations: np.ndarray) -> np.ndarray:
    if not isinstance(observations, np.ndarray) or observations.ndim != 4 or observations.shape[1:] != INPUT_SHAPE:
        raise ValueError("Observations must have shape (N,38,4,9)")
    if observations.dtype != np.int8 or not len(observations):
        raise ValueError("Observations must be a nonempty int8 batch")
    if np.any((observations != 0) & (observations != 1)) or observations[:, :, 3, 7:].any():
        raise ValueError("Observations must contain binary unary planes and zero honor padding")
    return np.ascontiguousarray(observations.reshape(len(observations), INPUT_SIZE, order="C"), dtype=np.float32)


def rank_legal_classes(scores: np.ndarray, legal_masks: np.ndarray) -> list[np.ndarray]:
    if not isinstance(scores, np.ndarray) or scores.ndim != 2 or scores.shape[1] != NUM_CLASSES or scores.dtype.kind != "f" or not len(scores):
        raise ValueError("Scores must be a nonempty floating (N,34) array")
    if not isinstance(legal_masks, np.ndarray) or legal_masks.shape != scores.shape or legal_masks.dtype != np.bool_:
        raise ValueError("Legal masks must be bool (N,34)")
    if not legal_masks.any(axis=1).all() or not np.isfinite(scores[legal_masks]).all():
        raise ValueError("Each row needs finite scores and at least one legal discard")
    rankings = []
    for row, mask in zip(scores, legal_masks):
        legal = np.flatnonzero(mask)
        rankings.append(legal[np.argsort(-row[legal], kind="stable")])
    return rankings
