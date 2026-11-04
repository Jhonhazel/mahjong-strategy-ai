from collections import Counter
import dataclasses
import random

import numpy as np
import pytest

from tests.helpers import make_wall, pass_claims, play_pass


def test_deal_draw_privacy_illegal_actions_and_determinism():
    from app.engine.mcr_referee import MCRRefereeEngine
    from app.domain.exceptions import IllegalActionError, InvalidTurnStateError
    engine = MCRRefereeEngine(seed=42)
    other = MCRRefereeEngine(seed=42)
    assert engine.get_pending_seats() == (0,)
    assert len(engine.get_seat_hand(0)) == 14
    assert [len(engine.get_seat_hand(s)) for s in [1, 2, 3]] == [13, 13, 13]
    assert engine.build_public_player_view("g", 0) == other.build_public_player_view("g", 0)
    before = engine.build_public_player_view("g", 0)
    for seat, aid, error in [(0, 999, IllegalActionError), (0, 0, IllegalActionError), (1, 2, InvalidTurnStateError)]:
        with pytest.raises(error):
            engine.submit_seat_action(seat, aid)
        assert engine.build_public_player_view("g", 0) == before
    data = dataclasses.asdict(before)
    assert data["round_result"] is None
    for public in data["seat_public_states"]:
        assert "hand" not in public and "concealed_tiles" not in public
        assert isinstance(public["concealed_count"], int)
    engine.assert_tile_conservation()


PRIORITY_HANDS = [
    "W5 T1 T2 T3 T4 T5 T6 B1 B2 B3 F1 F2 F3".split(),
    "W4 W6 T1 T2 T3 B4 B5 B6 B7 B8 F1 F2 J1".split(),
    "W5 W5 T7 T8 T9 B1 B2 B3 F2 F3 F4 J2 J3".split(),
    "W1 W1 W1 W2 W3 W4 W6 W7 W8 W9 W9 W9 W2".split(),
]


@pytest.mark.parametrize("hu", [True, False])
def test_hu_beats_peng_beats_chi_with_arbitrary_response_order(hu):
    from app.domain.actions import encode_play_action, encode_chi_action, encode_peng_action
    from app.engine.mcr_referee import MCRRefereeEngine
    engine = MCRRefereeEngine(wall=make_wall(PRIORITY_HANDS, [["J3"], [], [], []]))
    engine.submit_seat_action(0, encode_play_action("W5"))
    engine.submit_seat_action(3, 1 if hu else 0)
    engine.submit_seat_action(1, encode_chi_action("W5", "W5"))
    engine.submit_seat_action(2, encode_peng_action("W5"))
    if hu:
        assert engine.round_result.winner_seat == 3
        assert engine.round_result.discarder_seat == 0
        assert engine.round_result.total_fan >= 24
    else:
        assert engine.active_seat == 2 and engine.phase == "POST_MELD_DISCARD"
        assert np.flatnonzero(engine.get_seat_encoded_state(2).legal_mask).min() >= 2
        assert np.flatnonzero(engine.get_seat_encoded_state(2).legal_mask).max() < 36
    engine.assert_tile_conservation()


def test_angang_and_minggang_replacement_and_concealment():
    from app.domain.actions import encode_play_action, encode_angang_action, encode_gang_action
    from app.engine.mcr_referee import MCRRefereeEngine
    engine = MCRRefereeEngine(wall=make_wall([["W1"] * 3, [], [], []], [["W1", "J3"], [], [], []]))
    engine.submit_seat_action(0, encode_angang_action("W1"))
    assert engine.phase == "SELF_TURN" and engine.active_seat == 0
    assert engine.get_seat_hand(0).count("W1") == 0
    assert engine.get_seat_hand(0)[-1] == "J3"
    view = engine.build_public_player_view("g", 1)
    assert view.seat_public_states[0].melds[0].tile is None
    assert engine.get_seat_encoded_state(1).obs[34:38].sum() == 0
    engine.assert_tile_conservation()
    engine = MCRRefereeEngine(wall=make_wall([["B2"], ["B2"] * 3, [], []]))
    engine.submit_seat_action(0, encode_play_action("B2"))
    for s in engine.get_pending_seats():
        engine.submit_seat_action(s, encode_gang_action("B2") if s == 1 else 0)
    assert engine.active_seat == 1 and engine.phase == "SELF_TURN"
    assert engine.get_seat_packs(1)[0].pack_type == "GANG"
    engine.assert_tile_conservation()


def test_bugang_robbery_reverts_pung_and_awards_ron():
    from app.domain.actions import encode_play_action, encode_peng_action, encode_bugang_action
    from app.engine.mcr_referee import MCRRefereeEngine
    hands = [
        "B2 B2 T1 T2 T3 T4 T5 T6 W1 W2 W3 F1 F2".split(),
        "B1 B3 B4 B5 B6 B7 B7 B7 B8 B8 B8 B9 B9".split(),
        "B2 W4 W5 W6 T7 T8 T9 F1 F2 F3 F4 J1 J2".split(),
        "W7 W8 W9 T1 T2 T3 F1 F2 F3 F4 J1 J2 J3".split(),
    ]
    engine = MCRRefereeEngine(wall=make_wall(hands, [["F3", "B2"], ["J1", "J3"], ["J2", "J3"], ["F4"]]))
    play_pass(engine, 0, "F3")
    play_pass(engine, 1, "J1")
    engine.submit_seat_action(2, encode_play_action("B2"))
    for s in engine.get_pending_seats():
        engine.submit_seat_action(s, encode_peng_action("B2") if s == 0 else 0)
    play_pass(engine, 0, "F2")
    play_pass(engine, 1, "J3")
    play_pass(engine, 2, "J3")
    play_pass(engine, 3, "F4")
    engine.submit_seat_action(0, encode_bugang_action("B2"))
    assert engine.phase == "CLAIM_QIANGGANG"
    for s in engine.get_pending_seats():
        engine.submit_seat_action(s, 1 if s == 1 else 0)
    result = engine.round_result
    assert result.qianggang and result.ending == "ron"
    assert result.winner_seat == 1 and result.discarder_seat == 0
    assert engine.get_seat_packs(0)[0].pack_type == "PENG"
    assert sum(result.score_deltas) == 0
    engine.assert_tile_conservation()


def test_flower_after_kong_replacement_does_not_award_replacement_fan():
    from app.domain.actions import encode_angang_action
    from app.engine.mcr_referee import MCRRefereeEngine
    hand = "W1 W1 W1 W2 W3 W4 W5 W6 W7 W8 W9 F1 F1".split()
    engine = MCRRefereeEngine(wall=make_wall([hand, [], [], []], [["W1", "H1", "W7"], [], [], []], flowers=True))
    engine.submit_seat_action(0, encode_angang_action("W1"))
    assert engine.get_seat_encoded_state(0).legal_mask[1]
    engine.submit_seat_action(0, 1)
    assert "Out with Replacement Tile" not in {f.fan_name_en for f in engine.round_result.fans}
    assert "Self-Drawn" in {f.fan_name_en for f in engine.round_result.fans} or "Fully Concealed Hand" in {f.fan_name_en for f in engine.round_result.fans}
    engine.assert_tile_conservation()


def run_round(seed, flowers=False):
    from app.engine.mcr_referee import MCRRefereeEngine
    from app.domain.exceptions import GameAlreadyFinishedError
    engine = MCRRefereeEngine(seed=seed, include_flowers=flowers)
    rng = random.Random(seed)
    while not engine.is_finished:
        pending = engine.get_pending_seats()
        assert pending
        s = pending[0]
        st = engine.get_seat_encoded_state(s)
        actions = np.flatnonzero(st.legal_mask).tolist()
        assert actions
        aid = 1 if 1 in actions else rng.choice(actions)
        engine.submit_seat_action(s, aid)
        engine.assert_tile_conservation()
        assert engine.turn_number <= 600
    assert sum(engine.round_result.score_deltas) == 0
    if engine.round_result.ending != "draw":
        assert engine.round_result.total_fan >= 8
    assert engine.build_public_player_view("g", 0).round_result is not None
    with pytest.raises(GameAlreadyFinishedError):
        engine.submit_seat_action(0, 0)


@pytest.mark.parametrize("seed,flowers", [(0, False), (42, False), (7, True), (15, True)])
def test_full_round_conserves_tiles_and_finishes(seed, flowers):
    run_round(seed, flowers)


@pytest.mark.slow
def test_200_complete_seeded_rounds():
    for seed in range(200):
        run_round(seed, flowers=seed % 2 == 1)
