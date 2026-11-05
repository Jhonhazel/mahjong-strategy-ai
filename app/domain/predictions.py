"""Immutable identity and detached JSON input/output for one prediction."""
from dataclasses import dataclass
import uuid


class PredictionInvariantError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionSnapshot:
    game_id: uuid.UUID
    turn_number: int
    turn_phase: str
    input_snapshot: dict
    output_snapshot: dict
    model_version: str
    encoder_version: str
    checkpoint_sha256: str
    state_digest: str
