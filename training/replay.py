"""Two independent translations of real Botzone logs to the live encoder.

Observer replay consumes each seat's private protocol only. Referee replay
reconstructs the consumed wall prefix from displays, then executes real legal
actions. Unconsumed wall suffixes are deterministic fillers, never training data.
"""
from collections import Counter
from dataclasses import dataclass

from app.domain.actions import encode_angang_action, encode_bugang_action, encode_chi_action, encode_gang_action, encode_peng_action, encode_play_action
from app.domain.exceptions import CorruptedDatasetError
from app.domain.models import EncodedTurnState
from app.domain.tiles import TILE_LIST
from app.engine.feature_encoder import PerSeatObserver
from app.engine.mcr_referee import MCRRefereeEngine


@dataclass(frozen=True)
class Decision:
    seat: int
    log_index: int
    action_id: int
    kind: str
    state: EncodedTurnState
    after_claim: bool = False


def _require(condition, message):
    if not condition:
        raise CorruptedDatasetError(message)


def _outputs(game):
    log = game["log"]
    _require(isinstance(log, list), "log must be an array")
    for index, entry in enumerate(log):
        if "output" in entry:
            yield index, entry["output"]


def _response(game, index, seat):
    log = game["log"]
    _require(index + 1 < len(log), f"Missing response after log row {index}")
    row = log[index + 1].get(str(seat))
    _require(isinstance(row, dict), f"Missing seat {seat} response at log row {index + 1}")
    response = row.get("response") or row.get("raw")
    _require(isinstance(response, str) and bool(response.strip()), "Empty Botzone response")
    return response.strip()


def terminal_display(game):
    for _, output in reversed(list(_outputs(game))):
        if output.get("command") == "finish":
            display = dict(output["display"])
            if "score" not in display:
                content = output.get("content", {})
                _require(all(str(s) in content and type(content[str(s)]) in (int, float) for s in range(4)), "Terminal missing explicit source scores")
                display["score"] = [content[str(s)] for s in range(4)]
            return display
    raise CorruptedDatasetError("Incomplete match: no terminal output")


def replay_observers(game) -> dict[int, list[Decision]]:
    observers = {}
    decisions = {s: [] for s in range(4)}
    last_draw_response = {}
    live_discard, saw_claim, finished = False, False, False
    for index, output in _outputs(game):
        display = output.get("display", {})
        if output.get("command") == "finish":
            ending = display.get("action")
            _require(ending in ("HU", "HUANG"), f"Excluded abnormal terminal: {ending}")
            _require(len(observers) == 4, "Terminal without initialization")
            for observer in observers.values():
                observer.on_event(f"Player {display['player']} Hu" if ending == "HU" else "Huang", index)
            finished = True
            break
        _require(output.get("command") == "request", "Unknown output command")
        action = display.get("action")
        for seat in range(4):
            request = output["content"][str(seat)].split()
            rtype = request[0]
            if rtype == "0":
                _require(len(request) == 3 and int(request[1]) == seat, "Bad seat initialization")
                observer = PerSeatObserver(seat)
                observer.on_event(f"Wind {request[2]}", index)
                observers[seat] = observer
                continue
            observer = observers[seat]
            if rtype == "1":
                _require(request[1:5] == ["0"] * 4, "Raw corpus flower-deal format requires explicit support")
                observer.on_event("Deal " + " ".join(request[5:]), index)
            elif rtype == "2":
                _require(action == "DRAW" and display["player"] == seat, "Private draw/display mismatch")
                state = observer.on_event(f"Draw {request[1]}", index)
                response = _response(game, index, seat)
                last_draw_response[seat] = response
                parts = response.split()
                if parts[0] == "PLAY":
                    aid = encode_play_action(parts[1])
                    _require(state.legal_mask[aid], f"Illegal recorded discard at log row {index}")
                    decisions[seat].append(Decision(seat, index, aid, "draw", state, saw_claim))
            elif rtype == "3":
                actor, event = int(request[1]), request[2]
                if event == "DRAW":
                    observer.on_event(f"Player {actor} Draw", index)
                elif event == "PLAY":
                    observer.on_event(f"Player {actor} Play {request[3]}", index)
                elif event in ("PENG", "CHI"):
                    middle = f" {request[3]}" if event == "CHI" else ""
                    state = observer.on_event(f"Player {actor} {event.title()}{middle}", index)
                    tile = request[4] if event == "CHI" else request[3]
                    if actor == seat:
                        aid = encode_play_action(tile)
                        _require(state.legal_mask[aid], "Illegal embedded claim discard")
                        decisions[seat].append(Decision(seat, index, aid, "post_meld", state, True))
                    observer.on_event(f"Player {actor} Play {tile}", index)
                elif event == "GANG":
                    if live_discard:
                        observer.on_event(f"Player {actor} Gang", index)
                    elif actor == seat:
                        private = last_draw_response[seat].split()
                        _require(len(private) == 2 and private[0] == "GANG", "Missing private AnGang declaration")
                        observer.on_event(f"Player {actor} AnGang {private[1]}", index)
                    else:
                        observer.on_event(f"Player {actor} AnGang", index)
                elif event == "BUGANG":
                    observer.on_event(f"Player {actor} BuGang {request[3]}", index)
                elif event == "BUHUA":
                    observer.on_event(f"Player {actor} BuHua {request[3]}", index)
                else:
                    raise CorruptedDatasetError(f"Unknown public protocol event {event}")
            else:
                raise CorruptedDatasetError(f"Unknown request type {rtype}")
        live_discard = action in ("PLAY", "PENG", "CHI")
        saw_claim = saw_claim or action in ("PENG", "CHI")
    _require(finished, "Incomplete match: no verified terminal record")
    return decisions


def reconstruct_consumed_wall(game):
    outputs = [out["display"] for _, out in _outputs(game)]
    deal = next(d for d in outputs if d.get("action") == "DEAL")
    hands = deal["hand"]
    _require(len(hands) == 4 and all(len(h) == 13 for h in hands), "Bad initial hands")
    draws = [[d["tile"] for d in outputs if d.get("action") == "DRAW" and d["player"] == s] for s in range(4)]
    known = Counter(t for h in hands + draws for t in h)
    expected = Counter({t: 4 for t in TILE_LIST})
    _require(not known - expected and all(len(d) <= 21 for d in draws), "Invalid consumed wall prefix")
    pool = list((expected - known).elements())
    wall = []
    for seat in range(4):
        filler = [pool.pop() for _ in range(21 - len(draws[seat]))]
        wall.extend(filler + list(reversed(draws[seat])) + list(reversed(hands[seat])))
    _require(not pool, "Wall reconstruction left unassigned tiles")
    wind = next(d["quan"] for d in outputs if d.get("action") == "INIT")
    return wall, wind


def _response_action(engine, response):
    parts = response.split()
    kind = parts[0]
    if kind == "PASS":
        return 0
    if kind == "HU":
        return 1
    if kind == "PLAY" and len(parts) == 2:
        return encode_play_action(parts[1])
    if kind == "PENG" and len(parts) == 2:
        return encode_peng_action(engine._current_tile)
    if kind == "CHI" and len(parts) == 3:
        return encode_chi_action(parts[1], engine._current_tile)
    if kind == "GANG":
        return encode_gang_action(engine._current_tile) if len(parts) == 1 else encode_angang_action(parts[1])
    if kind == "BUGANG" and len(parts) == 2:
        return encode_bugang_action(parts[1])
    raise CorruptedDatasetError(f"Unsupported recorded action {response!r}")


def replay_referee(game) -> dict[int, list[Decision]]:
    wall, wind = reconstruct_consumed_wall(game)
    engine = MCRRefereeEngine(wall=wall, prevalent_wind=wind)
    decisions = {s: [] for s in range(4)}
    finished, saw_claim = False, False
    for index, output in _outputs(game):
        display = output["display"]
        event = display["action"]
        if output.get("command") == "finish":
            _require(event in ("HU", "HUANG") and engine.is_finished, "Referee/record terminal mismatch")
            result = engine.round_result
            scores = terminal_display(game)["score"]
            _require(list(result.score_deltas) == scores, f"Final score mismatch: {result.score_deltas} vs {scores}")
            if event == "HU":
                _require(result.winner_seat == display["player"] and result.total_fan == display["fanCnt"], "Final winner/fan mismatch")
            else:
                _require(result.ending == "draw", "Expected drawn round")
            engine.assert_tile_conservation()
            finished = True
            break
        if event in ("INIT", "DEAL"):
            continue
        actor = display["player"]
        if event == "DRAW":
            _require(engine.phase == "SELF_TURN" and engine.active_seat == actor and engine._last_draw == display["tile"], f"Draw order mismatch at row {index}")
            response = _response(game, index, actor)
            aid = _response_action(engine, response)
            if response.startswith("PLAY "):
                decisions[actor].append(Decision(actor, index, aid, "draw", engine.get_seat_encoded_state(actor), saw_claim))
            engine.submit_seat_action(actor, aid)
        elif event in ("PENG", "CHI"):
            _require(engine.phase == "POST_MELD_DISCARD" and engine.active_seat == actor, "Claim arbitration mismatch")
            saw_claim = True
            aid = encode_play_action(display["tile"])
            decisions[actor].append(Decision(actor, index, aid, "post_meld", engine.get_seat_encoded_state(actor), True))
            engine.submit_seat_action(actor, aid)
        elif event == "PLAY":
            _require(engine.phase == "CLAIM_DISCARD" and engine._current_tile == display["tile"] and engine._tile_from == actor, "Discard/display mismatch")
        elif event == "BUGANG":
            _require(engine.phase == "CLAIM_QIANGGANG" and engine._tile_from == actor and engine._current_tile == display["tile"], "BuGang/display mismatch")
        elif event == "GANG":
            _require(engine.phase == "SELF_TURN" and engine.active_seat == actor, "Kong replacement mismatch")
            continue  # Referee has already drawn the replacement; next source DRAW validates it.
        else:
            raise CorruptedDatasetError(f"Unsupported display event {event}")
        if event in ("PLAY", "PENG", "CHI", "BUGANG"):
            for seat in engine.get_pending_seats():
                engine.submit_seat_action(seat, _response_action(engine, _response(game, index, seat)))
    _require(finished, "Incomplete referee replay: no terminal record")
    return decisions
