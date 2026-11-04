import numpy as np
import pytest

HAND = "W2 W3 T5 T5 T5 B1 B2 B3 F1 F1 J2 J2 J3"


def observer(seat=1, hand=HAND):
    from app.engine.feature_encoder import PerSeatObserver
    obs = PerSeatObserver(seat)
    obs.on_event("Wind 0")
    obs.on_event("Deal " + hand)
    return obs


def test_exact_unary_channels_dtypes_padding_and_masks():
    obs = observer(2, "W1 W1 W2 W3 T5 T6 B7 B8 B9 F1 F2 J1 J1")
    obs.on_event("Wind 3")
    st = obs.on_event("Draw W4", turn_number=12)
    assert st.obs.shape == (38, 4, 9) and st.obs.dtype == np.int8
    assert st.legal_mask.shape == (235,) and st.legal_mask.dtype == np.bool_
    assert st.legal_discard_mask.shape == (34,) and st.legal_discard_mask.dtype == np.bool_
    assert st.obs[0, 3, 2] == 1 and st.obs[1, 3, 3] == 1
    assert st.obs[2:6].sum(axis=(1, 2)).tolist() == [12, 2, 0, 0]
    assert not st.obs[:, 3, 7:].any()
    assert st.legal_discard_mask.sum() == 12
    assert st.seat == 2 and st.turn_number == 12
    assert np.array_equal(st.legal_mask[2:36], st.legal_discard_mask)
    st.obs[:] = 0
    assert obs.get_encoded_state().obs[2].sum() == 12


def test_opponent_events_refresh_public_planes_immediately_without_hidden_tiles():
    from app.domain.actions import encode_chi_action, encode_peng_action, encode_gang_action
    obs = observer()
    obs.on_event("Player 0 Draw")
    claim = obs.on_event("Player 0 Play W1")
    assert claim.legal_mask[encode_chi_action("W2", "W1")]
    assert claim.obs[18, 0, 0] == 1  # previous seat's discard
    obs.on_event("Player 3 Draw")
    peng = obs.on_event("Player 3 Play T5")
    assert peng.legal_mask[encode_peng_action("T5")]
    assert peng.legal_mask[encode_gang_action("T5")]
    assert not peng.legal_mask[36:99].any()
    # Separate possible information state: no T5 in our hand when an opponent
    # exposes three/four of them. Chi is by the discarder’s next seat.
    public = observer(1, "W2 W3 T1 T2 T3 B1 B2 B3 F1 F1 J2 J2 J3")
    public.on_event("Player 3 Draw")
    public.on_event("Player 3 Play W1")
    public.on_event("Player 0 Chi W2")
    assert public.get_encoded_state().obs[34:38, 0, :3].sum() == 3
    public.on_event("Player 0 Play F2")
    public.on_event("Draw J3")
    public.on_event("Player 1 Play J3")
    public.on_event("Player 2 Draw")
    public.on_event("Player 2 Play T5")
    public.on_event("Player 3 Peng")
    assert public.get_encoded_state().obs[30:34, 1, 4].tolist() == [1, 1, 1, 0]
    public.on_event("Player 3 Play W5")
    public.on_event("Player 0 Draw")
    public.on_event("Player 0 Play F3")
    public.on_event("Draw J1")
    public.on_event("Player 1 Play J1")
    public.on_event("Player 2 Draw")
    public.on_event("Player 2 Play B9")
    public.on_event("Player 3 Draw")
    public.on_event("Player 3 BuGang T5")
    assert public.get_encoded_state().obs[30:34, 1, 4].tolist() == [1, 1, 1, 1]
    before = public.get_encoded_state().obs.copy()
    public.on_event("Player 0 AnGang")
    assert np.array_equal(before, public.get_encoded_state().obs)
    assert public.packs[3][-1][1] == "CONCEALED"


def test_own_chi_peng_kongs_hu_and_terminal_masks():
    from app.domain.actions import encode_play_action, encode_bugang_action, encode_angang_action
    obs = observer(0, "B2 B2 W1 W2 W3 T1 T2 T3 F1 F2 F3 J1 J2")
    obs.on_event("Player 1 Draw")
    obs.on_event("Player 1 Play B2")
    post = obs.on_event("Player 0 Peng")
    assert post.legal_mask[encode_play_action("J2")]
    assert not post.legal_mask[167:].any() and not post.legal_mask[1]
    obs.on_event("Player 0 Play J2")
    bg = obs.on_event("Draw B2")
    assert bg.legal_mask[encode_bugang_action("B2")]
    obs.on_event("Player 0 BuGang B2")
    assert obs.get_encoded_state().obs[22:26, 2, 1].tolist() == [1, 1, 1, 1]
    ang = observer(0, "W1 W1 W1 T1 T2 T3 B1 B2 B3 F1 F2 J1 J2")
    assert ang.on_event("Draw W1").legal_mask[encode_angang_action("W1")]
    ang.on_event("Player 0 AnGang W1")
    assert ang.hand.count("W1") == 0
    assert ang.get_encoded_state().obs[22:26, 0, 0].tolist() == [1, 1, 1, 1]
    nine = observer(0, "W1 W1 W1 W2 W3 W4 W5 W6 W7 W8 W9 W9 W9")
    assert nine.on_event("Draw W5").legal_mask[1]
    assert not nine.on_event("Player 0 Hu").legal_mask.any()
    assert not nine.on_event("Huang").legal_mask.any()


def test_wall_exhaustion_disables_claims_except_hu_and_pass():
    obs = observer()
    obs.tile_wall[0] = 0
    obs.on_event("Player 0 Draw")
    st = obs.on_event("Player 0 Play T5")
    assert np.flatnonzero(st.legal_mask).tolist() == [0]


def test_fourth_tile_counts_do_not_double_count_and_native_clears_concealed_copies():
    from app.engine.feature_encoder import is_fourth_tile
    assert is_fourth_tile("W9", ["W7", "W8"], {"W9": 3}, True)
    assert is_fourth_tile("W9", ["W7", "W8"], {"W9": 4}, False)
    assert not is_fourth_tile("W9", [], {"W9": 3}, False)
    # The library additionally clears Last Tile whenever win tile is already in concealed hand.
    assert is_fourth_tile("W9", ["W9"] * 3, {}, True)
    from tests.test_fan_calculator import evaluate, NINE
    ok, _, fans = evaluate(NINE, "W9", is_fourth_tile=True)
    assert ok and "Last Tile" not in {f.fan_name_en for f in fans}


@pytest.mark.parametrize("event", ["", "Unknown X", "Player 4 Draw", "Wind 4", "Draw ZZ"])
def test_invalid_events_fail_explicitly(event):
    from app.domain.exceptions import IllegalActionError
    with pytest.raises(IllegalActionError):
        observer().on_event(event)
