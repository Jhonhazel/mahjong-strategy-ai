"""Read-only local MLP suggestions; scores describe discard behavior, not wins."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from app.domain.exceptions import MahjongError
from app.domain.models import ENCODER_VERSION, EncodedTurnState
from app.domain.tiles import index_to_tile
from app.mlp import encode_observations, masked_log_probabilities, rank_legal_classes
from app.model_checkpoint import load_checkpoint


class InvalidPredictionStateError(MahjongError):
    pass


class PredictionUnavailableError(MahjongError):
    pass


@dataclass(frozen=True)
class DiscardSuggestion:
    tile: str
    class_index: int
    action_id: int
    score: float


@dataclass(frozen=True)
class DiscardPrediction:
    recommended_tile: str
    recommended_class_index: int
    recommended_action_id: int
    top3: tuple[DiscardSuggestion, ...]
    scores: tuple[float, ...]
    model_version: str
    encoder_version: str
    seat: int
    turn_number: int
    score_meaning: str = "Masked model scores for observed discard behavior; uncalibrated, not winning chances"


class AIDiscardPredictionService:
    def __init__(self, checkpoint_path: Path = Path("artifacts/models/mahjong_discard_mlp.pt"), metadata_path: Path | None = None, expected_contract: dict | None = None):
        self._model, metadata = load_checkpoint(checkpoint_path, metadata_path, expected_contract)
        self._model.requires_grad_(False)
        self.model_version = metadata["model_version"]
        self.encoder_version = metadata["encoder_version"]

    def predict(self, state: EncodedTurnState) -> DiscardPrediction:
        if not isinstance(state, EncodedTurnState):
            raise InvalidPredictionStateError("Expected a Phase 1 EncodedTurnState")
        if state.encoder_version != ENCODER_VERSION or state.encoder_version != self.encoder_version:
            raise InvalidPredictionStateError("Encoder version mismatch")
        if type(state.seat) is not int or not 0 <= state.seat < 4 or type(state.turn_number) is not int or state.turn_number < 0:
            raise InvalidPredictionStateError("Invalid seat/turn identity")
        if not isinstance(state.legal_mask, np.ndarray) or state.legal_mask.shape != (235,) or state.legal_mask.dtype != np.bool_:
            raise InvalidPredictionStateError("Expected bool legal_mask[235]")
        if not isinstance(state.legal_discard_mask, np.ndarray) or state.legal_discard_mask.shape != (34,) or state.legal_discard_mask.dtype != np.bool_:
            raise InvalidPredictionStateError("Expected bool legal_discard_mask[34]")
        if not np.array_equal(state.legal_discard_mask, state.legal_mask[2:36]):
            raise InvalidPredictionStateError("Discard mask disagrees with full action mask")
        if not state.legal_discard_mask.any():
            raise PredictionUnavailableError("Prediction is unavailable when no discard is legal")
        if not isinstance(state.obs, np.ndarray) or state.obs.shape != (38, 4, 9):
            raise InvalidPredictionStateError("Expected obs[38,4,9]")
        try:
            features = encode_observations(state.obs[None])
        except ValueError as exc:
            raise InvalidPredictionStateError(str(exc)) from exc
        masks = state.legal_discard_mask[None].copy()
        with torch.inference_mode():
            logits = self._model(torch.from_numpy(features))
            log_probabilities = masked_log_probabilities(logits, torch.from_numpy(masks))
            probabilities = log_probabilities.exp().numpy()[0]
        ranking = rank_legal_classes(log_probabilities.numpy(), masks)[0]
        suggestions = tuple(DiscardSuggestion(index_to_tile(int(i)), int(i), int(i) + 2, float(probabilities[i])) for i in ranking[:3])
        best = suggestions[0]
        return DiscardPrediction(best.tile, best.class_index, best.action_id, suggestions, tuple(float(p) for p in probabilities), self.model_version, self.encoder_version, state.seat, state.turn_number)
