"""Verify and load only the promoted runtime assets, never the training corpus."""
from dataclasses import dataclass
import json

import torch

from app.services.ai_prediction_service import AIDiscardPredictionService
from app.settings import Settings, V3_METADATA_SHA256, V3_SHA256
from training.dataset_loader import file_sha256


@dataclass(frozen=True)
class RuntimeModel:
    ai: AIDiscardPredictionService
    metadata: dict
    checkpoint_sha256: str


def load_runtime_model(settings: Settings) -> RuntimeModel:
    try:
        if file_sha256(settings.model_checkpoint_path) != V3_SHA256:
            raise ValueError('Wrong checkpoint')
        if file_sha256(settings.model_metadata_path) != V3_METADATA_SHA256:
            raise ValueError('Wrong metadata')
        contract = json.loads(settings.dataset_contract_path.read_text())
        metadata = json.loads(settings.model_metadata_path.read_text())
        torch.set_num_threads(1)
        ai = AIDiscardPredictionService(settings.model_checkpoint_path, settings.model_metadata_path, contract)
        return RuntimeModel(ai, metadata, V3_SHA256)
    except Exception:
        raise RuntimeError('Required MLP v3 runtime assets are missing, corrupt or incompatible') from None
