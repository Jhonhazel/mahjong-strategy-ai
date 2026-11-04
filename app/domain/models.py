from dataclasses import dataclass
from typing import Literal

import numpy as np

# Strict events are refreshed immediately; historical extraction is audited separately.
ENCODER_VERSION = "ijcai2026_mcr_v1_strict"
GameStatus = Literal["WAITING_HUMAN_DISCARD", "WAITING_HUMAN_CLAIM", "FINISHED"]
RoundEnding = Literal["zimo", "ron", "draw"]
PackType = Literal["CHI", "PENG", "GANG", "ANGANG"]
LibraryPack = tuple[str, str, int]


@dataclass(frozen=True)
class MeldPack:
    pack_type: PackType
    tile: str | None
    offer: int

    def as_library_pack(self) -> LibraryPack:
        if self.tile is None:
            raise ValueError("A hidden opponent meld cannot be used for scoring")
        return ("GANG" if self.pack_type == "ANGANG" else self.pack_type, self.tile, self.offer)

    def tiles(self) -> tuple[str, ...]:
        if self.tile is None:
            return ()
        if self.pack_type == "CHI":
            suit, rank = self.tile[0], int(self.tile[1])
            return tuple(f"{suit}{n}" for n in range(rank - 1, rank + 2))
        return (self.tile,) * (3 if self.pack_type == "PENG" else 4)


@dataclass(frozen=True)
class FanItem:
    fan_points: int
    count: int
    fan_name_zh: str
    fan_name_en: str


@dataclass(frozen=True)
class LegalActionOption:
    action_id: int
    action_type: str
    tile: str | None
    meld_tiles: tuple[str, ...] | None
    label: str


@dataclass(frozen=True)
class SeatPublicState:
    seat: int
    concealed_count: int
    melds: tuple[MeldPack, ...]
    flowers: tuple[str, ...]
    discards: tuple[str, ...]
    wall_remaining: int


@dataclass(frozen=True)
class RoundResult:
    ending: RoundEnding
    winner_seat: int | None
    discarder_seat: int | None
    qianggang: bool
    win_tile: str | None
    total_fan: int
    fans: tuple[FanItem, ...]
    score_deltas: tuple[int, int, int, int]
    revealed_hands: tuple[tuple[str, ...], ...]

    @property
    def outcome_type(self) -> Literal["HU", "HUANGZHUANG"]:
        return "HUANGZHUANG" if self.ending == "draw" else "HU"


@dataclass(frozen=True)
class PublicPlayerView:
    game_id: str
    status: GameStatus
    human_seat: int
    prevalent_wind: int
    active_seat: int
    turn_number: int
    wall_tiles_remaining: int
    own_hand: tuple[str, ...]
    own_flowers: tuple[str, ...]
    seat_public_states: tuple[SeatPublicState, ...]
    legal_actions: tuple[LegalActionOption, ...]
    can_request_ai_prediction: bool
    round_result: RoundResult | None = None


@dataclass(frozen=True)
class EncodedTurnState:
    obs: np.ndarray
    legal_mask: np.ndarray
    legal_discard_mask: np.ndarray
    seat: int
    turn_number: int
    encoder_version: str = ENCODER_VERSION
