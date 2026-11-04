"""Deterministic four-seat Botzone MCR referee, isolated from session concerns."""
from collections import Counter
from collections.abc import Sequence
from numbers import Integral
from typing import Literal

import numpy as np

from app.domain.actions import decode_action
from app.domain.exceptions import EngineInvariantError, GameAlreadyFinishedError, IllegalActionError, InvalidTurnStateError
from app.domain.models import EncodedTurnState, LegalActionOption, MeldPack, PublicPlayerView, RoundResult, SeatPublicState
from app.domain.tiles import FLOWER_TILES, TILE_LIST, build_144_wall_with_flowers, build_standard_136_wall, is_flower_tile, sort_hand_tiles
from app.engine.fan_calculator import FanCalculatorAdapter, compute_mcr_score_deltas
from app.engine.feature_encoder import PerSeatObserver, is_fourth_tile

MAX_ROUND_STEPS = 600
EnginePhase = Literal["SELF_TURN", "POST_MELD_DISCARD", "CLAIM_DISCARD", "CLAIM_QIANGGANG", "FINISHED"]


def validate_seat(seat):
    if isinstance(seat, bool) or not isinstance(seat, Integral) or not 0 <= seat < 4:
        raise IllegalActionError(f"Seat must be 0..3: {seat!r}")


class MCRRefereeEngine:
    def __init__(self, prevalent_wind: int = 0, seed: int = 0, wall: Sequence[str] | None = None, include_flowers: bool = False):
        validate_seat(prevalent_wind)
        self.prevalent_wind = int(prevalent_wind)
        full_wall = list(wall) if wall is not None else (build_144_wall_with_flowers(seed) if include_flowers else build_standard_136_wall(seed))
        expected = Counter({t: 4 for t in TILE_LIST})
        if len(full_wall) == 144:
            expected.update(FLOWER_TILES)
        if len(full_wall) not in (136, 144) or Counter(full_wall) != expected:
            raise IllegalActionError("Wall must contain exactly four of each normal tile, optionally H1..H8")
        self._expected_tiles = expected
        segment = len(full_wall) // 4
        self._walls = [full_wall[s * segment:(s + 1) * segment] for s in range(4)]
        self._hands: list[list[str]] = [[] for _ in range(4)]
        self._melds: list[list[MeldPack]] = [[] for _ in range(4)]
        self._flowers: list[list[str]] = [[] for _ in range(4)]
        self._history: list[list[str]] = [[] for _ in range(4)]
        self._rivers: list[list[str]] = [[] for _ in range(4)]
        self._observers = [PerSeatObserver(s, initial_wall_per_seat=segment - 13) for s in range(4)]
        self.turn_number = 0
        self.active_seat = 0
        self.phase: EnginePhase = "SELF_TURN"
        self.round_result: RoundResult | None = None
        self._pending: list[int] = []
        self._responses = {}
        self._current_tile: str | None = None
        self._tile_from: int | None = None
        self._last_draw: str | None = None
        self._kong_replacement = False
        self._broadcast(f"Wind {prevalent_wind}")
        for seat in range(4):
            while len(self._hands[seat]) < 13:
                tile = self._walls[seat].pop()
                if is_flower_tile(tile):
                    self._flowers[seat].append(tile)
                    self._broadcast(f"Player {seat} BuHua {tile}")
                else:
                    self._hands[seat].append(tile)
            self._observers[seat].on_event("Deal " + " ".join(self._hands[seat]))
        self._draw(0)
        self.assert_tile_conservation()

    @property
    def is_finished(self) -> bool:
        return self.phase == "FINISHED"

    def _broadcast(self, event):
        for observer in self._observers:
            observer.on_event(event, self.turn_number)

    def get_pending_seats(self) -> tuple[int, ...]:
        return tuple(self._pending)

    def get_seat_encoded_state(self, seat: int) -> EncodedTurnState:
        validate_seat(seat)
        state = self._observers[seat].get_encoded_state(self.turn_number)
        if seat not in self._pending:
            state.legal_mask[:] = False
            state.legal_discard_mask[:] = False
        return state

    def get_seat_hand(self, seat: int) -> tuple[str, ...]:
        validate_seat(seat)
        return tuple(self._hands[seat])

    def get_seat_packs(self, seat: int) -> tuple[MeldPack, ...]:
        validate_seat(seat)
        return tuple(self._melds[seat])

    def _draw(self, seat, replacement=False):
        self.active_seat = seat
        self._responses = {}
        while self._walls[seat]:
            tile = self._walls[seat].pop()
            if is_flower_tile(tile):
                self._flowers[seat].append(tile)
                self._broadcast(f"Player {seat} BuHua {tile}")
                # A win after replacing a flower is not Out with Replacement
                # Tile, even if the flower itself was the Kong replacement.
                replacement = False
                continue
            self._hands[seat].append(tile)
            self._last_draw = tile
            self._kong_replacement = replacement
            for other, observer in enumerate(self._observers):
                observer.on_event(f"Draw {tile}" if other == seat else f"Player {seat} Draw", self.turn_number)
            self.phase = "SELF_TURN"
            self._pending = [seat]
            return
        self.phase = "FINISHED"
        self._pending = []
        self._broadcast("Huang")
        self.round_result = RoundResult("draw", None, None, False, None, 0, (), (0, 0, 0, 0), self._revealed_hands())

    def _open_claims(self, source, tile, qianggang=False):
        self._tile_from, self._current_tile = source, tile
        self.phase = "CLAIM_QIANGGANG" if qianggang else "CLAIM_DISCARD"
        self._pending = [(source + distance) % 4 for distance in (1, 2, 3)]
        self._responses = {}

    def submit_seat_action(self, seat: int, action_id: int) -> None:
        if self.is_finished:
            raise GameAlreadyFinishedError("Round has already finished")
        validate_seat(seat)
        action = decode_action(action_id)
        if seat not in self._pending:
            raise InvalidTurnStateError("Seat is not pending or already responded")
        if not self.get_seat_encoded_state(seat).legal_mask[action.action_id]:
            raise IllegalActionError(f"Illegal {action.action_type} for seat {seat} in {self.phase}")
        if self.turn_number >= MAX_ROUND_STEPS:
            raise EngineInvariantError("Round step ceiling exceeded")
        self.turn_number += 1
        if self.phase in ("CLAIM_DISCARD", "CLAIM_QIANGGANG"):
            self._responses[seat] = action
            self._pending.remove(seat)
            if not self._pending:
                self._resolve_claims()
        elif action.action_type == "Hu":
            self._finish_hu(seat, True)
        elif action.action_type == "Play":
            self._hands[seat].remove(action.tile)
            self._history[seat].append(action.tile)
            self._rivers[seat].append(action.tile)
            self._last_draw = None
            self._broadcast(f"Player {seat} Play {action.tile}")
            self._open_claims(seat, action.tile)
        elif action.action_type == "AnGang":
            for _ in range(4):
                self._hands[seat].remove(action.tile)
            self._melds[seat].append(MeldPack("ANGANG", action.tile, 0))
            for other, observer in enumerate(self._observers):
                observer.on_event(f"Player {seat} AnGang" + (f" {action.tile}" if other == seat else ""), self.turn_number)
            self._draw(seat, True)
        elif action.action_type == "BuGang":
            self._hands[seat].remove(action.tile)
            index = next(i for i, pack in enumerate(self._melds[seat]) if pack.pack_type == "PENG" and pack.tile == action.tile)
            pack = self._melds[seat][index]
            self._melds[seat][index] = MeldPack("GANG", pack.tile, pack.offer)
            self._broadcast(f"Player {seat} BuGang {action.tile}")
            self._open_claims(seat, action.tile, True)
        else:
            raise EngineInvariantError("Legal mask allowed an action outside the active phase")
        self.assert_tile_conservation()

    def _resolve_claims(self):
        source = self._tile_from
        order = [(source + distance) % 4 for distance in (1, 2, 3)]
        winners = [s for s in order if self._responses[s].action_type == "Hu"]
        if winners:
            self._finish_hu(winners[0], False)
            return
        if self.phase == "CLAIM_QIANGGANG":
            self._draw(source, True)
            return
        claimers = [s for s in order if self._responses[s].action_type in ("Peng", "Gang")]
        claimers += [s for s in order if self._responses[s].action_type == "Chi"]
        if not claimers:
            self._draw((source + 1) % 4)
            return
        seat = claimers[0]
        action = self._responses[seat]
        tile = action.chi_mid_tile if action.action_type == "Chi" else self._current_tile
        offer = int(self._current_tile[1]) - int(tile[1]) + 2 if action.action_type == "Chi" else (seat - source) % 4
        pack = MeldPack(action.action_type.upper(), tile, offer)
        consumed = list(pack.tiles())
        consumed.remove(self._current_tile)
        for t in consumed:
            self._hands[seat].remove(t)
        self._rivers[source].pop()
        self._melds[seat].append(pack)
        self.active_seat = seat
        self._broadcast(f"Player {seat} {action.action_type}" + (f" {tile}" if action.action_type == "Chi" else ""))
        if action.action_type == "Gang":
            self._draw(seat, True)
        else:
            self.phase = "POST_MELD_DISCARD"
            self._last_draw = None
            self._pending = [seat]

    def _finish_hu(self, winner, zimo):
        qianggang = self.phase == "CLAIM_QIANGGANG"
        tile = self._last_draw if zimo else self._current_tile
        observer = self._observers[winner]
        hand = list(self._hands[winner])
        if zimo:
            hand.remove(tile)
        ok, total, fans = FanCalculatorAdapter.try_evaluate_hu(
            self._melds[winner], hand, tile, zimo,
            is_fourth_tile(tile, hand, observer.shown_tiles, zimo),
            self._kong_replacement if zimo else qianggang,
            observer.wall_last, winner, self.prevalent_wind, len(self._flowers[winner]),
        )
        if not ok:
            raise EngineInvariantError("Hu in legal mask failed final independent scoring")
        source = None if zimo else self._tile_from
        if not zimo:
            if qianggang:
                index = next(i for i, m in enumerate(self._melds[source]) if m.pack_type == "GANG" and m.tile == tile)
                pack = self._melds[source][index]
                self._melds[source][index] = MeldPack("PENG", tile, pack.offer)
                for view in self._observers:
                    relative = (source - view.seat_wind) % 4
                    i = next(i for i, (kind, t, _) in enumerate(view.packs[relative]) if kind == "GANG" and t == tile)
                    view.packs[relative][i] = ("PENG", tile, pack.offer)
                    view.shown_tiles[tile] -= 1
            else:
                self._rivers[source].pop()
            self._hands[winner].append(tile)
        ending = "zimo" if zimo else "ron"
        self.round_result = RoundResult(ending, winner, source, qianggang, tile, total, fans, compute_mcr_score_deltas(ending, winner, source, total), self._revealed_hands())
        self.phase = "FINISHED"
        self._pending = []
        self._broadcast(f"Player {winner} Hu")

    def _revealed_hands(self):
        return tuple(tuple(sort_hand_tiles(hand)) for hand in self._hands)

    def assert_tile_conservation(self) -> None:
        actual = Counter()
        for group in (self._walls, self._hands, self._flowers, self._rivers):
            for tiles in group:
                actual.update(tiles)
        for packs in self._melds:
            for pack in packs:
                actual.update(pack.tiles())
        if actual != self._expected_tiles:
            raise EngineInvariantError(f"Tile conservation failed: missing={self._expected_tiles - actual}, extra={actual - self._expected_tiles}")
        if not self.is_finished:
            for seat, observer in enumerate(self._observers):
                if Counter(observer.hand) != Counter(self._hands[seat]):
                    raise EngineInvariantError("Observer hand differs from referee")
                remaining = [len(self._walls[(seat + relative) % 4]) for relative in range(4)]
                if observer.tile_wall != remaining:
                    raise EngineInvariantError("Observer wall counts differ from referee")

    def build_public_player_view(self, game_id: str, human_seat: int) -> PublicPlayerView:
        validate_seat(human_seat)
        status = "FINISHED" if self.is_finished else "WAITING_HUMAN_DISCARD" if human_seat in self._pending and self.phase in ("SELF_TURN", "POST_MELD_DISCARD") else "WAITING_HUMAN_CLAIM"
        public = []
        for seat in range(4):
            visible = tuple(MeldPack(m.pack_type, None, 0) if m.pack_type == "ANGANG" and seat != human_seat and not self.is_finished else m for m in self._melds[seat])
            public.append(SeatPublicState(seat, len(self._hands[seat]), visible, tuple(self._flowers[seat]), tuple(self._history[seat]), len(self._walls[seat])))
        options = []
        for aid in np.flatnonzero(self.get_seat_encoded_state(human_seat).legal_mask).tolist():
            action = decode_action(aid)
            meld = None
            if action.action_type in ("Chi", "Peng", "Gang", "AnGang", "BuGang"):
                meld = MeldPack("CHI" if action.action_type == "Chi" else "PENG" if action.action_type == "Peng" else "GANG", action.chi_mid_tile or action.tile, 1).tiles()
            label = action.action_type + (" " + "-".join(meld) if meld else " " + action.tile if action.tile else "")
            options.append(LegalActionOption(aid, action.action_type, action.tile, meld, label))
        return PublicPlayerView(game_id, status, human_seat, self.prevalent_wind, self.active_seat, self.turn_number, sum(map(len, self._walls)), tuple(sort_hand_tiles(self._hands[human_seat])), tuple(self._flowers[human_seat]), tuple(public), tuple(options), status == "WAITING_HUMAN_DISCARD", self.round_result)
