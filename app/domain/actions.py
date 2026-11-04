"""235-action contract verified against Dannibal's published FeatureAgent."""
from dataclasses import dataclass
from numbers import Integral
from typing import Literal

import numpy as np

from app.domain.exceptions import IllegalActionError
from app.domain.tiles import NUMBERED_SUITS, index_to_tile, tile_to_index

ActionType = Literal["Pass", "Hu", "Play", "Chi", "Peng", "Gang", "AnGang", "BuGang"]
ACTION_SPACE_SIZE = 235
PASS_ACTION_ID, HU_ACTION_ID, PLAY_ACTION_OFFSET = 0, 1, 2
CHI_ACTION_OFFSET, PENG_ACTION_OFFSET, GANG_ACTION_OFFSET = 36, 99, 133
ANGANG_ACTION_OFFSET, BUGANG_ACTION_OFFSET = 167, 201


@dataclass(frozen=True)
class DecodedAction:
    action_id: int
    action_type: ActionType
    tile: str | None = None
    chi_mid_tile: str | None = None
    chi_claimed_pos: int | None = None


def encode_play_action(tile: str) -> int:
    return PLAY_ACTION_OFFSET + tile_to_index(tile)


def decode_discard_class_to_action_id(class_idx: int) -> int:
    return encode_play_action(index_to_tile(class_idx))


def action_id_to_discard_class(action_id: int) -> int:
    action = decode_action(action_id)
    if action.action_type != "Play":
        raise IllegalActionError(f"Not a discard action: {action_id!r}")
    return action.action_id - PLAY_ACTION_OFFSET


def encode_chi_action(mid_tile: str, claimed_tile: str) -> int:
    tile_to_index(mid_tile)
    tile_to_index(claimed_tile)
    if mid_tile[0] not in NUMBERED_SUITS or mid_tile[0] != claimed_tile[0]:
        raise IllegalActionError("Chi needs tiles of the same numbered suit")
    mid, rank = int(mid_tile[1]), int(claimed_tile[1])
    if not 2 <= mid <= 8 or abs(rank - mid) > 1:
        raise IllegalActionError("Invalid Chi middle/claimed tile")
    return CHI_ACTION_OFFSET + NUMBERED_SUITS.index(mid_tile[0]) * 21 + (mid - 2) * 3 + rank - mid + 1


def encode_peng_action(tile: str) -> int:
    return PENG_ACTION_OFFSET + tile_to_index(tile)


def encode_gang_action(tile: str) -> int:
    return GANG_ACTION_OFFSET + tile_to_index(tile)


def encode_angang_action(tile: str) -> int:
    return ANGANG_ACTION_OFFSET + tile_to_index(tile)


def encode_bugang_action(tile: str) -> int:
    return BUGANG_ACTION_OFFSET + tile_to_index(tile)


def decode_action(action_id: int) -> DecodedAction:
    if isinstance(action_id, bool) or not isinstance(action_id, Integral) or not 0 <= action_id < ACTION_SPACE_SIZE:
        raise IllegalActionError(f"Action ID must be an integer 0..234: {action_id!r}")
    aid = int(action_id)
    if aid < 2:
        return DecodedAction(aid, "Pass" if aid == 0 else "Hu")
    if CHI_ACTION_OFFSET <= aid < PENG_ACTION_OFFSET:
        combo, pos = divmod(aid - CHI_ACTION_OFFSET, 3)
        suit, mid = NUMBERED_SUITS[combo // 7], combo % 7 + 2
        return DecodedAction(aid, "Chi", f"{suit}{mid + pos - 1}", f"{suit}{mid}", pos)
    for offset, kind in [(BUGANG_ACTION_OFFSET, "BuGang"), (ANGANG_ACTION_OFFSET, "AnGang"), (GANG_ACTION_OFFSET, "Gang"), (PENG_ACTION_OFFSET, "Peng"), (PLAY_ACTION_OFFSET, "Play")]:
        if aid >= offset:
            return DecodedAction(aid, kind, index_to_tile(aid - offset))
    raise IllegalActionError(f"Unreachable action ID: {aid}")


def extract_legal_discard_mask(legal_mask: np.ndarray) -> np.ndarray:
    if not isinstance(legal_mask, np.ndarray) or legal_mask.shape != (ACTION_SPACE_SIZE,):
        raise IllegalActionError("legal_mask must have shape (235,)")
    return legal_mask[PLAY_ACTION_OFFSET:CHI_ACTION_OFFSET].astype(np.bool_, copy=True)
