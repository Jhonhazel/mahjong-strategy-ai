from datetime import datetime
from typing import Annotated, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid',hide_input_in_errors=True)


class GameCreate(StrictModel):
    human_seat: Annotated[StrictInt,Field(ge=0,le=3)] = 0
    prevalent_wind: Annotated[StrictInt,Field(ge=0,le=3)] = 0
    seed: Annotated[StrictInt,Field(ge=0,le=2**64-1)] | None = None
    include_flowers: StrictBool = False


class TurnRequest(StrictModel):
    expected_turn_number: Annotated[StrictInt,Field(ge=0,le=1000000)]


class ActionRequest(TurnRequest):
    action_id: Annotated[StrictInt,Field(ge=0,le=234)]


class MeldOut(StrictModel):
    pack_type: str
    tile: str | None
    offer: int


class SeatOut(StrictModel):
    seat: int
    concealed_count: int
    melds: list[MeldOut]
    flowers: list[str]
    discards: list[str]
    wall_remaining: int


class ActionOut(StrictModel):
    action_id: int
    action_type: str
    tile: str | None
    meld_tiles: list[str] | None
    label: str


class FanOut(StrictModel):
    fan_points: int
    count: int
    fan_name_zh: str
    fan_name_en: str


class RoundOut(StrictModel):
    ending: Literal['zimo','ron','draw']
    outcome_type: Literal['HU','HUANGZHUANG']
    winner_seat: int | None
    discarder_seat: int | None
    qianggang: bool
    win_tile: str | None
    total_fan: int
    fans: list[FanOut]
    score_deltas: list[int]


class GameViewOut(StrictModel):
    game_id: uuid.UUID
    status: Literal['WAITING_HUMAN_DISCARD','WAITING_HUMAN_CLAIM','FINISHED']
    human_seat: int
    prevalent_wind: int
    active_seat: int
    turn_number: int
    wall_tiles_remaining: int
    own_hand: list[str]
    own_flowers: list[str]
    seat_public_states: list[SeatOut]
    legal_actions: list[ActionOut]
    can_request_ai_prediction: bool
    round_result: RoundOut | None


class SuggestionOut(StrictModel):
    tile: str
    class_index: int
    action_id: int
    score: float


class PredictionData(StrictModel):
    recommended_tile: str
    recommended_class_index: int
    recommended_action_id: int
    top3: list[SuggestionOut]
    scores: Annotated[list[float],Field(min_length=34,max_length=34)]
    model_version: str
    encoder_version: str
    seat: int
    turn_number: int
    score_meaning: str


class SavedPredictionOut(PredictionData):
    prediction_id: uuid.UUID
    game_id: uuid.UUID
    turn_phase: Literal['SELF_TURN','POST_MELD_DISCARD']
    reused: bool


class HistorySummaryOut(StrictModel):
    prediction_id: uuid.UUID
    game_id: uuid.UUID
    turn_number: int
    turn_phase: str
    created_at: datetime
    model_version: str
    encoder_version: str
    recommended_tile: str
    top3: list[SuggestionOut]


class HistoryDetailOut(HistorySummaryOut):
    input_snapshot: dict
    output_snapshot: PredictionData
    checkpoint_sha256: str
    state_digest: str


class HistoryPageOut(StrictModel):
    items: list[HistorySummaryOut]
    total: int
    limit: int
    offset: int
