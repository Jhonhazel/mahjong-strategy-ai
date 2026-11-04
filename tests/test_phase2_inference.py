from dataclasses import replace
from pathlib import Path
import random

import numpy as np
import pytest
import torch

from tests.test_phase2_checkpoint import checkpoint_fixture


@pytest.fixture
def prediction_service(tmp_path, checkpoint_fixture):
    from app.model_checkpoint import save_checkpoint
    from app.services.ai_prediction_service import AIDiscardPredictionService
    model, metadata, contract = checkpoint_fixture
    checkpoint = tmp_path / "model.pt"
    save_checkpoint(model, checkpoint, metadata)
    return AIDiscardPredictionService(checkpoint, expected_contract=contract), checkpoint


def test_predictions_are_legal_normalized_readonly_and_model_is_cached(prediction_service):
    from app.services.game_service import GameSessionService
    service, checkpoint = prediction_service
    games = GameSessionService()
    view = games.create_game(seed=42)
    state = games.get_human_encoded_turn(view.game_id)
    before_obs, before_mask = state.obs.copy(), state.legal_mask.copy()
    weights = {k: v.clone() for k, v in service._model.state_dict().items()}
    prediction = service.predict(state)
    assert prediction.recommended_action_id == prediction.recommended_class_index + 2
    assert state.legal_mask[prediction.recommended_action_id]
    assert 1 <= len(prediction.top3) <= 3
    assert all(state.legal_mask[s.action_id] and s.action_id == s.class_index + 2 for s in prediction.top3)
    assert sum(prediction.scores) == pytest.approx(1., abs=1e-6)
    assert all(score == 0. for score, legal in zip(prediction.scores, state.legal_discard_mask) if not legal)
    assert games.get_player_view(view.game_id) == view
    assert np.array_equal(state.obs, before_obs) and np.array_equal(state.legal_mask, before_mask)
    assert all(torch.equal(weights[k], v) for k, v in service._model.state_dict().items())
    assert service._model.training is False and all(p.grad is None for p in service._model.parameters())
    checkpoint.unlink()  # Own temporary unit artifact; repeated inference must reuse loaded model.
    assert service.predict(state) == prediction
    games.shutdown()


@pytest.mark.parametrize("tamper", ["obs_shape", "obs_dtype", "mask_shape", "mask_dtype", "mask_disagreement", "encoder", "seat", "turn", "obs_values"])
def test_service_rejects_incompatible_encoded_state(prediction_service, tamper):
    from app.services.ai_prediction_service import InvalidPredictionStateError
    from app.services.game_service import GameSessionService
    service, _ = prediction_service
    games = GameSessionService()
    view = games.create_game(seed=1)
    state = games.get_human_encoded_turn(view.game_id)
    if tamper == "obs_shape": bad = replace(state, obs=np.zeros((38, 4, 8), dtype=np.int8))
    elif tamper == "obs_dtype": bad = replace(state, obs=state.obs.astype(np.float32))
    elif tamper == "mask_shape": bad = replace(state, legal_mask=np.ones(34, dtype=bool))
    elif tamper == "mask_dtype": bad = replace(state, legal_mask=state.legal_mask.astype(np.int8))
    elif tamper == "mask_disagreement": bad = replace(state, legal_discard_mask=~state.legal_discard_mask)
    elif tamper == "encoder": bad = replace(state, encoder_version="wrong")
    elif tamper == "seat": bad = replace(state, seat=4)
    elif tamper == "turn": bad = replace(state, turn_number=-1)
    else:
        state.obs[2, 0, 0] = 2
        bad = state
    with pytest.raises(InvalidPredictionStateError):
        service.predict(bad)
    games.shutdown()


def test_service_handles_no_legal_discard_explicitly(prediction_service):
    from app.services.ai_prediction_service import PredictionUnavailableError
    from app.services.game_service import GameSessionService
    service, _ = prediction_service
    games = GameSessionService()
    view = games.create_game(seed=1)
    state = games.get_human_encoded_turn(view.game_id)
    unavailable = replace(state, legal_mask=np.zeros(235, dtype=bool), legal_discard_mask=np.zeros(34, dtype=bool))
    with pytest.raises(PredictionUnavailableError): service.predict(unavailable)
    one_mask = np.zeros(235, dtype=bool)
    action = int(np.flatnonzero(state.legal_discard_mask)[0]) + 2
    one_mask[action] = True
    single = replace(state, legal_mask=one_mask, legal_discard_mask=one_mask[2:36].copy())
    result = service.predict(single)
    assert len(result.top3) == 1 and result.top3[0].score == 1.
    games.shutdown()


@pytest.mark.integration
def test_inference_and_normal_gameplay_complete_round_with_post_meld_turns(prediction_service):
    from app.services.game_service import GameSessionService
    service, _ = prediction_service
    encountered = set()
    for seed in range(4):
        games = GameSessionService()
        view = games.create_game(seed=seed, human_seat=0)
        previous_action = None
        while view.status != "FINISHED":
            if view.status == "WAITING_HUMAN_DISCARD":
                state = games.get_human_encoded_turn(view.game_id)
                result = service.predict(state)
                assert state.legal_mask[result.recommended_action_id]
                assert games.get_player_view(view.game_id) == view
                if previous_action in ("Chi", "Peng"):
                    encountered.add(previous_action)
            choices = [o for o in view.legal_actions if o.action_type == "Hu"] or [o for o in view.legal_actions if o.action_type in ("Chi", "Peng")] or list(view.legal_actions)
            chosen = choices[0]
            previous_action = chosen.action_type
            view = games.submit_human_action(view.game_id, chosen.action_id, view.turn_number)
        assert view.round_result and sum(view.round_result.score_deltas) == 0
        games.shutdown()
    assert encountered == {"Chi", "Peng"}
