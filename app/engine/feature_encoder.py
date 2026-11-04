"""Private-seat Botzone event observer with the published 38-plane layout.

Compared with the historical FeatureAgent, refresh every public event and expose
native failures. The strict version is used by both gameplay and re-extraction.
"""
from collections import Counter, defaultdict
from numbers import Integral

import numpy as np

from app.domain.actions import (
    ACTION_SPACE_SIZE, ANGANG_ACTION_OFFSET, BUGANG_ACTION_OFFSET, HU_ACTION_ID,
    PASS_ACTION_ID, encode_chi_action, encode_gang_action, encode_peng_action,
    encode_play_action, extract_legal_discard_mask,
)
from app.domain.exceptions import EngineInvariantError, IllegalActionError
from app.domain.models import EncodedTurnState, MeldPack
from app.domain.tiles import is_flower_tile, tile_to_index
from app.engine.fan_calculator import FanCalculatorAdapter

OBS_CHANNELS = 38
OFFSET_OBS = {"SEAT_WIND": 0, "PREVALENT_WIND": 1, "HAND": 2, "DISCARD": 6, "HALF_FLUSH": 22}


def is_fourth_tile(tile: str, hand, shown, is_self_drawn: bool) -> bool:
    """hand excludes incoming tile; Ron's incoming tile is already public.

    PyMahjongGB further clears Last Tile if any matching concealed tile exists,
    and infers it for an own exposed pung (fan_calculator.cpp:2356–2363).
    """
    return hand.count(tile) + shown.get(tile, 0) + int(is_self_drawn) == 4


class PerSeatObserver:
    def __init__(self, seat_wind: int, fix_zimo_4th_tile: bool = True, initial_wall_per_seat: int = 21):
        if isinstance(seat_wind, bool) or not isinstance(seat_wind, Integral) or not 0 <= seat_wind < 4:
            raise IllegalActionError("seat_wind must be 0..3")
        if not fix_zimo_4th_tile:
            raise IllegalActionError("Historical scoring is not supported by the strict live encoder")
        self.seat_wind = int(seat_wind)
        self.prevalent_wind = 0
        self.hand: list[str] = []
        self.packs: list[list[tuple[str, str, int]]] = [[] for _ in range(4)]
        self.history: list[list[str]] = [[] for _ in range(4)]
        self.tile_wall = [initial_wall_per_seat] * 4
        self.shown_tiles = defaultdict(int)
        self.flower_count = 0
        self.wall_last = False
        self.is_about_kong = False
        self.draw_about_kong = False
        self.last_draw: str | None = None
        self.tile_from = 0
        self.cur_tile: str | None = None
        self.valid_actions: list[int] = []

    def _evaluate(self, tile: str, zimo=False, about_kong=False):
        return FanCalculatorAdapter.try_evaluate_hu(
            self.packs[0], self.hand, tile, zimo,
            is_fourth_tile(tile, self.hand, self.shown_tiles, zimo),
            about_kong, self.wall_last, self.seat_wind, self.prevalent_wind, self.flower_count,
        )

    def on_event(self, request: str, turn_number: int = 0) -> EncodedTurnState | None:
        tokens = request.split()
        if not tokens:
            raise IllegalActionError("Empty event")
        head = tokens[0]
        if head == "Wind" and len(tokens) == 2 and tokens[1] in ("0", "1", "2", "3"):
            self.prevalent_wind = int(tokens[1])
            return None
        if head == "Deal":
            for tile in tokens[1:]:
                tile_to_index(tile)
            if len(tokens) != 14 or max(Counter(tokens[1:]).values()) > 4:
                raise IllegalActionError("Deal must contain 13 normal tiles")
            self.hand = tokens[1:]
            self.valid_actions = []
            return None
        if head == "Huang" and len(tokens) == 1:
            self.valid_actions = []
            return self.get_encoded_state(turn_number)
        if head == "Draw" and len(tokens) == 2:
            tile = tokens[1]
            tile_to_index(tile)
            self.tile_wall[0] -= 1
            self.wall_last = self.tile_wall[1] == 0
            self.draw_about_kong = self.is_about_kong
            self.valid_actions = [HU_ACTION_ID] if self._evaluate(tile, True, self.draw_about_kong)[0] else []
            self.is_about_kong = False
            self.last_draw = tile
            self.hand.append(tile)
            self.valid_actions.extend(encode_play_action(t) for t in set(self.hand))
            if not self.wall_last and self.tile_wall[0] > 0:
                self.valid_actions.extend(ANGANG_ACTION_OFFSET + tile_to_index(t) for t, n in Counter(self.hand).items() if n == 4)
                self.valid_actions.extend(BUGANG_ACTION_OFFSET + tile_to_index(t) for kind, t, _ in self.packs[0] if kind == "PENG" and t in self.hand)
            return self.get_encoded_state(turn_number)
        if head != "Player" or len(tokens) < 3 or tokens[1] not in ("0", "1", "2", "3"):
            raise IllegalActionError(f"Unknown event: {request!r}")
        p = (int(tokens[1]) - self.seat_wind) % 4
        event = tokens[2]
        expected = {"Draw": 3, "Hu": 3, "Invalid": 3, "Peng": 3, "Gang": 3, "BuHua": 4, "Play": 4, "Chi": 4, "BuGang": 4, "AnGang": 4 if p == 0 else 3}
        if event not in expected or len(tokens) != expected[event]:
            raise IllegalActionError(f"Invalid Player event: {request!r}")
        if len(tokens) == 4 and event != "BuHua":
            tile_to_index(tokens[3])
        self.valid_actions = []
        if event == "Draw":
            if p == 0:
                raise IllegalActionError("Own draw must include the private tile")
            self.tile_wall[p] -= 1
            self.wall_last = self.tile_wall[(p + 1) % 4] == 0
        elif event == "BuHua":
            if not is_flower_tile(tokens[3]):
                raise IllegalActionError("BuHua needs a flower")
            self.tile_wall[p] -= 1
            self.flower_count += int(p == 0)
            if p == 0:
                self.is_about_kong = False
            self.wall_last = self.tile_wall[(p + 1) % 4] == 0
        elif event in ("Hu", "Invalid"):
            return self.get_encoded_state(turn_number)
        elif event == "Play":
            self.tile_from, self.cur_tile = p, tokens[3]
            self.shown_tiles[self.cur_tile] += 1
            self.history[p].append(self.cur_tile)
            if p == 0:
                self.hand.remove(self.cur_tile)
                self.last_draw = None
            else:
                if self._evaluate(self.cur_tile)[0]:
                    self.valid_actions.append(HU_ACTION_ID)
                if not self.wall_last:
                    count = self.hand.count(self.cur_tile)
                    if count >= 2:
                        self.valid_actions.append(encode_peng_action(self.cur_tile))
                    if count == 3 and self.tile_wall[0] > 0:
                        self.valid_actions.append(encode_gang_action(self.cur_tile))
                    if p == 3 and self.cur_tile[0] in "WTB":
                        suit, rank = self.cur_tile[0], int(self.cur_tile[1])
                        for mid in range(max(2, rank - 1), min(8, rank + 1) + 1):
                            others = [f"{suit}{n}" for n in range(mid - 1, mid + 2)]
                            others.remove(self.cur_tile)
                            if all(t in self.hand for t in others):
                                self.valid_actions.append(encode_chi_action(f"{suit}{mid}", self.cur_tile))
                self.valid_actions.append(PASS_ACTION_ID)
                return self.get_encoded_state(turn_number)
        elif event in ("Chi", "Peng", "Gang"):
            if self.cur_tile is None:
                raise EngineInvariantError("Claim without a previous discard")
            if event == "Chi":
                tile = tokens[3]
                encode_chi_action(tile, self.cur_tile)
                offer = int(self.cur_tile[1]) - int(tile[1]) + 2
            else:
                tile, offer = self.cur_tile, (p - self.tile_from) % 4
            pack = MeldPack(event.upper(), tile, offer)
            self.packs[p].append(pack.as_library_pack())
            consumed = list(pack.tiles())
            consumed.remove(self.cur_tile)
            for t in consumed:
                self.shown_tiles[t] += 1
            self.wall_last = self.tile_wall[(p + 1) % 4] == 0
            if p == 0:
                for t in consumed:
                    self.hand.remove(t)
                if event == "Gang":
                    self.is_about_kong = True
                else:
                    self.valid_actions = [encode_play_action(t) for t in set(self.hand)]
                    return self.get_encoded_state(turn_number)
        elif event == "AnGang":
            tile = tokens[3] if p == 0 else "CONCEALED"
            self.packs[p].append(("GANG", tile, 0))
            if p == 0:
                for _ in range(4):
                    self.hand.remove(tile)
                self.is_about_kong = True
        elif event == "BuGang":
            tile = tokens[3]
            match = next((i for i, (k, t, _) in enumerate(self.packs[p]) if k == "PENG" and t == tile), None)
            if match is None:
                raise EngineInvariantError("BuGang without a matching Peng")
            _, _, offer = self.packs[p][match]
            self.packs[p][match] = ("GANG", tile, offer)
            self.shown_tiles[tile] += 1
            self.cur_tile, self.tile_from = tile, p
            if p == 0:
                self.hand.remove(tile)
                self.is_about_kong = True
            else:
                if self._evaluate(tile, False, True)[0]:
                    self.valid_actions.append(HU_ACTION_ID)
                self.valid_actions.append(PASS_ACTION_ID)
                return self.get_encoded_state(turn_number)
        return None

    def get_encoded_state(self, turn_number: int = 0) -> EncodedTurnState:
        flat = np.zeros((OBS_CHANNELS, 36), dtype=np.int8)
        flat[0, tile_to_index(f"F{self.seat_wind + 1}")] = 1
        flat[1, tile_to_index(f"F{self.prevalent_wind + 1}")] = 1
        def unary(base, tiles):
            for tile, n in Counter(tiles).items():
                if not 0 <= n <= 4:
                    raise EngineInvariantError("Invalid unary tile count")
                flat[base:base + n, tile_to_index(tile)] = 1
        unary(2, self.hand)
        for relative in range(4):
            unary(6 + relative * 4, self.history[relative])
            meld_tiles = []
            for kind, tile, offer in self.packs[relative]:
                if tile != "CONCEALED":
                    meld_tiles.extend(MeldPack(kind, tile, offer).tiles())
            unary(22 + relative * 4, meld_tiles)
        mask = np.zeros(ACTION_SPACE_SIZE, dtype=np.bool_)
        mask[self.valid_actions] = True
        return EncodedTurnState(flat.reshape(38, 4, 9), mask, extract_legal_discard_mask(mask), self.seat_wind, turn_number)

    def has_non_pass_action(self) -> bool:
        return any(a != PASS_ACTION_ID for a in self.valid_actions)


FeatureEncoder = PerSeatObserver
