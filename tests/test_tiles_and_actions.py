from collections import Counter

import numpy as np
import pytest


def test_canonical_tiles_grid_and_wall_counts():
    from app.domain.tiles import TILE_LIST, FLOWER_TILES, tile_to_index, index_to_tile, tile_to_grid_rc, sort_hand_tiles, build_standard_136_wall, build_144_wall_with_flowers

    assert len(TILE_LIST) == 34
    assert [TILE_LIST[i] for i in [0, 8, 9, 17, 18, 26, 27, 30, 31, 33]] == ["W1", "W9", "T1", "T9", "B1", "B9", "F1", "F4", "J1", "J3"]
    for i, tile in enumerate(TILE_LIST):
        assert tile_to_index(tile) == i
        assert index_to_tile(i) == tile
        assert tile_to_grid_rc(tile) == divmod(i, 9)
    assert sort_hand_tiles(["J3", "W2", "B1", "T1", "W1", "F1"]) == ["W1", "W2", "T1", "B1", "F1", "J3"]
    assert build_standard_136_wall(42) == build_standard_136_wall(42)
    assert build_standard_136_wall(42) != build_standard_136_wall(43)
    assert Counter(build_standard_136_wall(42)) == Counter({t: 4 for t in TILE_LIST})
    assert Counter(build_144_wall_with_flowers(42)) == Counter({t: 4 for t in TILE_LIST} | {t: 1 for t in FLOWER_TILES})


@pytest.mark.parametrize("value", [-1, 34, True, 1.2, "1", None])
def test_invalid_tile_indices_fail_explicitly(value):
    from app.domain.tiles import index_to_tile
    from app.domain.exceptions import IllegalActionError
    with pytest.raises(IllegalActionError):
        index_to_tile(value)


@pytest.mark.parametrize("value", ["W0", "W10", "F5", "J4", "H1", "", None, []])
def test_invalid_normal_tiles_fail_explicitly(value):
    from app.domain.tiles import tile_to_index
    from app.domain.exceptions import IllegalActionError
    with pytest.raises(IllegalActionError):
        tile_to_index(value)


def test_all_235_actions_roundtrip_and_discard_contract():
    from app.domain import actions as a
    from app.domain.tiles import TILE_LIST

    encoders = {"Play": a.encode_play_action, "Peng": a.encode_peng_action, "Gang": a.encode_gang_action, "AnGang": a.encode_angang_action, "BuGang": a.encode_bugang_action}
    types = Counter()
    for aid in range(235):
        dec = a.decode_action(aid)
        types[dec.action_type] += 1
        assert dec.action_id == aid
        if dec.action_type == "Chi":
            assert a.encode_chi_action(dec.chi_mid_tile, dec.tile) == aid
        elif dec.action_type in encoders:
            assert encoders[dec.action_type](dec.tile) == aid
    assert types == {"Pass": 1, "Hu": 1, "Play": 34, "Chi": 63, "Peng": 34, "Gang": 34, "AnGang": 34, "BuGang": 34}
    assert a.encode_chi_action("W2", "W1") == 36
    assert a.encode_chi_action("W2", "W3") == 38
    assert a.encode_chi_action("B8", "B9") == 98
    for i, tile in enumerate(TILE_LIST):
        assert a.action_id_to_discard_class(a.encode_play_action(tile)) == i
        assert a.decode_discard_class_to_action_id(i) == i + 2
    mask = np.zeros(235, dtype=np.bool_)
    mask[[0, 2, 35, 234]] = True
    assert np.flatnonzero(a.extract_legal_discard_mask(mask)).tolist() == [0, 33]
    sliced = a.extract_legal_discard_mask(mask)
    sliced[:] = False
    assert mask[2]


@pytest.mark.parametrize("aid", [-1, 235, True, 1.5, "2", None])
def test_invalid_actions_fail_explicitly(aid):
    from app.domain.actions import decode_action
    from app.domain.exceptions import IllegalActionError
    with pytest.raises(IllegalActionError):
        decode_action(aid)


@pytest.mark.parametrize("mid,claimed", [("W1", "W2"), ("W8", "W6"), ("F2", "F1"), ("W2", "T1"), ("Wx", "W2")])
def test_invalid_chi_fails_explicitly(mid, claimed):
    from app.domain.actions import encode_chi_action
    from app.domain.exceptions import IllegalActionError
    with pytest.raises(IllegalActionError):
        encode_chi_action(mid, claimed)
