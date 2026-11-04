import pytest

NINE = ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W9", "W9")
LOW_PACKS = (("CHI", "W2", 1), ("CHI", "T6", 2), ("PENG", "B9", 3))
LOW_HAND = ("W7", "W8", "F2", "F2")


def evaluate(hand=NINE, win="W5", packs=(), **flags):
    from app.engine.fan_calculator import FanCalculatorAdapter
    options = dict(is_zimo=False, is_fourth_tile=False, is_about_kong=False, is_wall_last=False, seat_wind=0, prevalent_wind=0, flower_count=0)
    options.update(flags)
    return FanCalculatorAdapter.try_evaluate_hu(packs, hand, win, **options)


def test_nine_gates_and_real_non_winning_hand():
    ok, total, fans = evaluate(is_zimo=True)
    assert ok and total == 92
    assert sum(f.fan_points * f.count for f in fans) == total
    hand = ("W1", "W3", "W5", "T1", "T3", "T5", "B1", "B3", "B5", "F1", "F2", "F3", "J1")
    assert evaluate(hand, "J2") == (False, 0, ())


def test_flowers_cannot_qualify_low_fan_hand():
    assert evaluate(LOW_HAND, "W9", LOW_PACKS)[:2] == (False, 2)
    assert evaluate(LOW_HAND, "W9", LOW_PACKS, flower_count=8)[:2] == (False, 10)
    ok, total, _ = evaluate(is_zimo=True, flower_count=2)
    assert ok and total == 94


def test_exact_eight_fan_chicken_hand_is_accepted():
    packs = (("CHI", "W2", 1), ("CHI", "W6", 2), ("CHI", "T4", 3))
    ok, total, fans = evaluate(("B6", "B7", "F2", "F2"), "B8", packs)
    assert ok and total == 8
    assert [f.fan_name_en for f in fans] == ["Chicken Hand"]


@pytest.mark.parametrize("flags,fan_name", [({"is_zimo": True, "is_about_kong": True}, "Out with Replacement Tile"), ({"is_about_kong": True}, "Robbing The Kong"), ({"is_zimo": True, "is_wall_last": True}, "Last Tile Draw"), ({"is_wall_last": True}, "Last Tile Claim"), ({"is_fourth_tile": True}, "Last Tile")])
def test_context_fans_are_scored_by_real_library(flags, fan_name):
    # Native calculator correctly clears replacement fan if there is no actual Kong.
    packs = LOW_PACKS[:2] + (("GANG", "B9", 3),) if flags.get("is_zimo") and flags.get("is_about_kong") else LOW_PACKS
    ok, total, fans = evaluate(LOW_HAND, "W9", packs, **flags)
    assert fan_name in {f.fan_name_en for f in fans}
    if fan_name == "Last Tile":
        assert not ok and total == 6
    else:
        assert ok and total >= 8


def test_invalid_counts_tiles_and_unexpected_native_errors_are_visible(monkeypatch):
    from app.domain.exceptions import EngineInvariantError
    from app.engine import fan_calculator as module
    for hand in [("W1",), NINE[:-1] + ("ZZ",), ("W1",) * 13]:
        with pytest.raises(EngineInvariantError):
            evaluate(hand)
    def broken(*args, **kwargs):
        raise RuntimeError("native calculation failure")
    monkeypatch.setattr(module, "MahjongFanCalculator", broken)
    with pytest.raises(RuntimeError, match="native calculation failure"):
        evaluate()


def test_special_hand_shanten_and_scores():
    from app.engine.fan_calculator import FanCalculatorAdapter, compute_mcr_score_deltas
    from app.domain.exceptions import IllegalActionError
    seven = ("W1", "W1", "W4", "W4", "T2", "T2", "T8", "T8", "B3", "B3", "F1", "F1", "J1")
    orphans = ("W1", "W9", "T1", "T9", "B1", "B9", "F1", "F2", "F3", "F4", "J1", "J2", "J3")
    assert FanCalculatorAdapter.calculate_shanten((), seven) == 0
    assert FanCalculatorAdapter.calculate_shanten((), orphans) == 0
    assert evaluate(orphans, "J3")[0]
    assert compute_mcr_score_deltas("zimo", 1, None, 20) == (-28, 84, -28, -28)
    assert compute_mcr_score_deltas("ron", 2, 3, 20) == (-8, -8, 44, -28)
    assert compute_mcr_score_deltas("draw", None, None, 0) == (0, 0, 0, 0)
    for ending, winner, discarder, fan in [("ron", 1, 1, 8), ("zimo", 4, None, 8), ("zimo", 0, None, 7), ("other", 0, 1, 8)]:
        with pytest.raises(IllegalActionError):
            compute_mcr_score_deltas(ending, winner, discarder, fan)
