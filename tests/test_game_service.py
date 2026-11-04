from concurrent.futures import ThreadPoolExecutor
import random
import threading

import numpy as np
import pytest


def test_heuristic_prefers_hu_and_never_uses_illegal_actions():
    from app.engine.mcr_referee import MCRRefereeEngine
    from app.services.bot_service import ShantenHeuristicBot
    from tests.helpers import make_wall
    hand = "W1 W1 W1 W2 W3 W4 W5 W6 W7 W8 W9 W9 W9".split()
    engine = MCRRefereeEngine(wall=make_wall([hand, [], [], []], [["W5"], [], [], []]))
    bot = ShantenHeuristicBot()
    assert bot.select_action(engine.get_seat_encoded_state(0), engine.get_seat_hand(0), engine.get_seat_packs(0), random.Random(1)) == 1
    for seed in range(4):
        engine = MCRRefereeEngine(seed=seed)
        while not engine.is_finished:
            s = engine.get_pending_seats()[0]
            state = engine.get_seat_encoded_state(s)
            action = bot.select_action(state, engine.get_seat_hand(s), engine.get_seat_packs(s), random.Random(seed))
            assert state.legal_mask[action]
            engine.submit_seat_action(s, action)
        engine.assert_tile_conservation()


def test_heuristic_discards_isolated_honor_to_retain_tenpai():
    from app.engine.mcr_referee import MCRRefereeEngine
    from app.services.bot_service import ShantenHeuristicBot
    from app.domain.actions import encode_play_action
    from tests.helpers import make_wall
    hand = "W1 W2 W3 W4 W5 W6 T2 T3 T4 B6 B7 F1 F1".split()
    engine = MCRRefereeEngine(wall=make_wall([hand, [], [], []], [["J3"], [], [], []]))
    action = ShantenHeuristicBot().select_action(engine.get_seat_encoded_state(0), engine.get_seat_hand(0), (), random.Random(1))
    assert action == encode_play_action("J3")


def test_human_vs_three_bots_pause_and_complete_real_round():
    from app.services.game_service import GameSessionService
    from app.domain.exceptions import GameAlreadyFinishedError
    service = GameSessionService()
    view = service.create_game(human_seat=1, seed=42)
    steps = 0
    while view.status != "FINISHED":
        ids = [o.action_id for o in view.legal_actions]
        assert ids and ids != [0]
        if view.status == "WAITING_HUMAN_DISCARD":
            state = service.get_human_encoded_turn(view.game_id)
            assert state.legal_discard_mask.any()
        chosen = 1 if 1 in ids else ids[0]
        view = service.submit_human_action(view.game_id, chosen, view.turn_number)
        steps += 1
        assert steps < 300
    assert view.round_result and sum(view.round_result.score_deltas) == 0
    with pytest.raises(GameAlreadyFinishedError):
        service.submit_human_action(view.game_id, 0, view.turn_number)
    service.shutdown()


def test_invalid_stale_and_missing_turn_token_do_not_mutate():
    from app.services.game_service import GameSessionService
    from app.domain.exceptions import GameNotFoundError, IllegalActionError, InvalidTurnStateError
    service = GameSessionService()
    with pytest.raises(GameNotFoundError):
        service.get_player_view("unknown")
    view = service.create_game(seed=7)
    for aid, token, error in [(999, view.turn_number, IllegalActionError), (0, view.turn_number, IllegalActionError), (view.legal_actions[0].action_id, -1, InvalidTurnStateError), (view.legal_actions[0].action_id, None, InvalidTurnStateError)]:
        with pytest.raises(error):
            service.submit_human_action(view.game_id, aid, token)
        assert service.get_player_view(view.game_id) == view


def test_20_real_threads_accept_exactly_one_turn_token():
    from app.services.game_service import GameSessionService
    from app.domain.exceptions import InvalidTurnStateError
    service = GameSessionService()
    view = service.create_game(seed=101)
    barrier = threading.Barrier(20)
    def submit(_):
        barrier.wait(timeout=10)
        try:
            service.submit_human_action(view.game_id, view.legal_actions[0].action_id, view.turn_number)
            return "accepted"
        except InvalidTurnStateError:
            return "stale"
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(submit, range(20)))
    assert results.count("accepted") == 1 and results.count("stale") == 19
    assert service.get_player_view(view.game_id).turn_number > view.turn_number


def test_capacity_ttl_delete_and_shutdown():
    from app.services.game_service import GameSessionService
    from app.domain.exceptions import SessionCapacityExceededError, ServiceShuttingDownError
    service = GameSessionService(max_active_sessions=1)
    view = service.create_game(seed=1)
    with pytest.raises(SessionCapacityExceededError):
        service.create_game(seed=2)
    assert service.get_player_view(view.game_id) == view
    service.delete_session(view.game_id)
    assert service.active_session_count() == 0
    service.create_game(seed=2)
    service.shutdown()
    with pytest.raises(ServiceShuttingDownError):
        service.create_game(seed=3)
    expired = GameSessionService(max_active_sessions=1, session_ttl_seconds=0)
    expired.create_game(seed=1)
    expired.create_game(seed=2)
    assert expired.active_session_count() <= 1


def test_shutdown_waits_for_real_inflight_bot_step():
    from app.services.bot_service import RandomLegalBot
    from app.services.game_service import GameSessionService
    started, release = threading.Event(), threading.Event()
    class PausingBot(RandomLegalBot):
        def select_action(self, *args):
            started.set()
            assert release.wait(10)
            return super().select_action(*args)
    service = GameSessionService(bot_policy=PausingBot())
    view = service.create_game(seed=9)
    with ThreadPoolExecutor(max_workers=2) as pool:
        action = pool.submit(service.submit_human_action, view.game_id, view.legal_actions[0].action_id, view.turn_number)
        assert started.wait(5)
        draining = pool.submit(service.shutdown, 10)
        assert not draining.done()
        release.set()
        action.result(timeout=10)
        draining.result(timeout=10)
