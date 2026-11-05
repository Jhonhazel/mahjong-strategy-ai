"""Compose existing engine/ML under one game lease through PostgreSQL commit."""
from dataclasses import asdict
import hashlib
import json
import math
import uuid

import numpy as np

from app.domain.exceptions import InvalidTurnStateError
from app.domain.predictions import PredictionSnapshot, PredictionInvariantError
from app.domain.tiles import index_to_tile
from app.services.ai_prediction_service import PredictionUnavailableError


class WebPredictionService:
    def __init__(self, games, runtime, history):
        self.games, self.runtime, self.history = games, runtime, history

    def predict(self, owner_key, game_id, expected_turn_number):
        game_id = str(game_id)
        with self.games.owned(owner_key,game_id) as entry:
            view = self.games.games.get_player_view(game_id)
            if view.turn_number!=expected_turn_number:
                raise InvalidTurnStateError('Missing or stale expected turn number')
            state = self.games.games.get_human_encoded_turn(game_id)
            if not state.legal_discard_mask.any():
                raise PredictionUnavailableError('There is no legal human discard decision')
            before = (state.obs.copy(),state.legal_mask.copy(),state.legal_discard_mask.copy())
            input_snapshot = {'obs':before[0].tolist(),'shape':[38,4,9],'dtype':'int8','feature_order':'C',
                              'legal_mask':before[1].tolist(),'legal_discard_mask':before[2].tolist(),
                              'seat':state.seat,'turn_number':state.turn_number,'encoder_version':state.encoder_version}
            digest = hashlib.sha256(json.dumps({'game_id':game_id,'turn_phase':entry.turn_phase,
                                                'input':input_snapshot},sort_keys=True,separators=(',',':')).encode()).hexdigest()
            prediction = self.runtime.ai.predict(state)
            if (self.games.games.get_player_view(game_id)!=view or
                    not all(np.array_equal(a,b) for a,b in zip(before,(state.obs,state.legal_mask,state.legal_discard_mask)))):
                raise PredictionInvariantError('The prediction state changed unexpectedly')
            self._verify(prediction,state,view)
            snapshot = PredictionSnapshot(uuid.UUID(game_id),state.turn_number,entry.turn_phase,input_snapshot,
                                          asdict(prediction),prediction.model_version,prediction.encoder_version,
                                          self.runtime.checkpoint_sha256,digest)
            # The per-game lease is still held: an action cannot race this commit.
            return self.history.save(owner_key,snapshot)

    def _verify(self, prediction, state, view):
        valid = (prediction.turn_number==state.turn_number==view.turn_number and prediction.seat==state.seat
                 and prediction.model_version==self.runtime.ai.model_version
                 and prediction.encoder_version==state.encoder_version
                 and len(prediction.scores)==34
                 and all(math.isfinite(p) and 0<=p<=1 for p in prediction.scores)
                 and math.isclose(sum(prediction.scores),1.,abs_tol=1e-5)
                 and len(prediction.top3)==min(3,int(state.legal_discard_mask.sum())))
        allowed = {option.action_id for option in view.legal_actions}
        seen = set()
        for item in prediction.top3:
            valid = valid and (0<=item.class_index<34 and item.action_id==item.class_index+2
                               and item.action_id in allowed and state.legal_mask[item.action_id]
                               and state.legal_discard_mask[item.class_index]
                               and item.tile==index_to_tile(item.class_index)
                               and math.isclose(item.score,prediction.scores[item.class_index],abs_tol=1e-7)
                               and item.class_index not in seen)
            seen.add(item.class_index)
        valid = valid and all(prediction.scores[i]==0. for i,legal in enumerate(state.legal_discard_mask) if not legal)
        if prediction.top3:
            best = prediction.top3[0]
            valid = valid and (best.tile==prediction.recommended_tile and best.action_id==prediction.recommended_action_id
                               and best.class_index==prediction.recommended_class_index
                               and all(a.score>=b.score for a,b in zip(prediction.top3,prediction.top3[1:])))
        if not valid:raise PredictionInvariantError('The model result failed state or legality checks')
