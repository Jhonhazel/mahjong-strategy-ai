"""Local policies receive only their own hand/packs and seat-visible features."""
from collections.abc import Sequence
from functools import lru_cache
import random
from typing import Protocol

import numpy as np

from app.domain.actions import decode_action, encode_play_action
from app.domain.exceptions import InvalidTurnStateError
from app.domain.models import EncodedTurnState, MeldPack
from app.engine.fan_calculator import FanCalculatorAdapter


class BotPolicy(Protocol):
    def select_action(self, encoded_state: EncodedTurnState, hand_tiles: Sequence[str], packs: Sequence[MeldPack], rng: random.Random) -> int: ...


class RandomLegalBot:
    def select_action(self, encoded_state, hand_tiles, packs, rng):
        actions = np.flatnonzero(encoded_state.legal_mask).tolist()
        if not actions:
            raise InvalidTurnStateError("No legal action for bot")
        return 1 if 1 in actions else rng.choice(actions)


@lru_cache(maxsize=32768)
def _shanten(packs, hand):
    return FanCalculatorAdapter.calculate_shanten(packs, hand)


def _distance(packs, hand):
    return _shanten(tuple(packs), tuple(sorted(hand)))


def _best_discard_distance(packs, hand):
    scores = {}
    for tile in set(hand):
        remaining = list(hand)
        remaining.remove(tile)
        scores[tile] = _distance(packs, remaining)
    return scores


class ShantenHeuristicBot:
    def select_action(self, encoded_state, hand_tiles, packs, rng):
        actions = np.flatnonzero(encoded_state.legal_mask).tolist()
        if not actions:
            raise InvalidTurnStateError("No legal action for bot")
        if 1 in actions:
            return 1
        hand = list(hand_tiles)
        packs = tuple(packs)
        discards = [a for a in actions if 2 <= a < 36]
        discard_scores = _best_discard_distance(packs, hand) if discards else {}
        before = min(discard_scores.values()) if discards else _distance(packs, hand)
        claims = []
        for aid in actions:
            if aid < 36:
                continue
            action = decode_action(aid)
            remaining, new_packs = hand.copy(), list(packs)
            if action.action_type == "BuGang":
                remaining.remove(action.tile)
                i = next(i for i, m in enumerate(new_packs) if m.pack_type == "PENG" and m.tile == action.tile)
                new_packs[i] = MeldPack("GANG", action.tile, new_packs[i].offer)
            else:
                kind = "CHI" if action.action_type == "Chi" else "PENG" if action.action_type == "Peng" else "ANGANG" if action.action_type == "AnGang" else "GANG"
                pack = MeldPack(kind, action.chi_mid_tile or action.tile, 0 if kind == "ANGANG" else 1)
                consumed = list(pack.tiles())
                if kind != "ANGANG":
                    consumed.remove(action.tile)
                for tile in consumed:
                    remaining.remove(tile)
                new_packs.append(pack)
            after = min(_best_discard_distance(new_packs, remaining).values()) if action.action_type in ("Chi", "Peng") else _distance(new_packs, remaining)
            if after < before or (after == before and action.action_type in ("AnGang", "BuGang")):
                claims.append((after, aid))
        if claims:
            best = min(s for s, _ in claims)
            return rng.choice([a for s, a in claims if s == best])
        if not discards:
            return 0
        best = min(discard_scores[decode_action(a).tile] for a in discards)
        candidates = [a for a in discards if discard_scores[decode_action(a).tile] == best]
        # Visible unary planes only. Claimed discards remain historical, so cap
        # this availability heuristic; it is not a probability estimate.
        visible = encoded_state.obs[2:].reshape(36, 36).sum(axis=0)
        def priority(aid):
            tile = decode_action(aid).tile
            index = aid - 2
            return (max(0, 4 - int(visible[index])), 0 if tile[0] in "FJ" and hand.count(tile) == 1 else 1, 0 if tile[1] in "19" else 1)
        value = min(priority(a) for a in candidates)
        return rng.choice([a for a in candidates if priority(a) == value])
