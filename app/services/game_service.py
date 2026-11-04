"""Bounded in-memory sessions; lock ordering is store → lease, then game lock."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import random
import secrets
import threading
import time
import uuid

from app.domain.actions import decode_action
from app.domain.exceptions import GameAlreadyFinishedError, GameNotFoundError, InvalidTurnStateError, ServiceShuttingDownError, SessionCapacityExceededError
from app.engine.mcr_referee import MCRRefereeEngine, validate_seat
from app.services.bot_service import BotPolicy, ShantenHeuristicBot


@dataclass
class _Session:
    engine: MCRRefereeEngine
    human_seat: int
    rng: random.Random
    lock: object = field(default_factory=threading.RLock)
    last_access: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    leases: int = 0
    deleted: bool = False


class GameSessionService:
    def __init__(self, max_active_sessions: int = 256, session_ttl_seconds: float = 3600.0, bot_policy: BotPolicy | None = None):
        if max_active_sessions < 1 or session_ttl_seconds < 0:
            raise ValueError("Session capacity must be positive and TTL nonnegative")
        self.max_active_sessions = max_active_sessions
        self.session_ttl_seconds = session_ttl_seconds
        self.bot_policy = bot_policy or ShantenHeuristicBot()
        self._sessions: dict[str, _Session] = {}
        self._store_lock = threading.RLock()
        self._condition = threading.Condition(self._store_lock)
        self._accepting = True
        self._creating = 0
        self._inflight = 0

    def _check_open(self):
        if not self._accepting:
            raise ServiceShuttingDownError("Service is shutting down")

    def _sweep(self):
        now = time.monotonic()
        for key, session in list(self._sessions.items()):
            expired = now - session.last_access >= self.session_ttl_seconds
            retained = session.finished_at is not None and now - session.finished_at >= 30.0
            if not session.leases and (expired or retained):
                session.deleted = True
                del self._sessions[key]

    @contextmanager
    def _lease(self, game_id):
        with self._condition:
            self._check_open()
            self._sweep()
            session = self._sessions.get(game_id)
            if session is None:
                raise GameNotFoundError("Unknown or expired game_id")
            session.leases += 1
            self._inflight += 1
        try:
            with session.lock:
                if session.deleted:
                    raise GameNotFoundError("Session has been deleted")
                session.last_access = time.monotonic()
                yield session
        finally:
            with self._condition:
                session.leases -= 1
                self._inflight -= 1
                self._condition.notify_all()

    def _advance(self, session):
        engine, human = session.engine, session.human_seat
        while not engine.is_finished:
            pending = engine.get_pending_seats()
            if human in pending:
                state = engine.get_seat_encoded_state(human)
                if engine.phase in ("SELF_TURN", "POST_MELD_DISCARD") or any(state.legal_mask[1:]):
                    return
                engine.submit_seat_action(human, 0)
                continue
            seat = pending[0]
            action = self.bot_policy.select_action(engine.get_seat_encoded_state(seat), engine.get_seat_hand(seat), engine.get_seat_packs(seat), session.rng)
            engine.submit_seat_action(seat, action)
        if session.finished_at is None:
            session.finished_at = time.monotonic()

    def create_game(self, human_seat=0, prevalent_wind=0, seed=None, include_flowers=False):
        validate_seat(human_seat)
        validate_seat(prevalent_wind)
        with self._condition:
            self._check_open()
            self._sweep()
            if len(self._sessions) + self._creating >= self.max_active_sessions:
                raise SessionCapacityExceededError("All session slots are occupied")
            self._creating += 1
            self._inflight += 1
        try:
            chosen_seed = secrets.randbits(64) if seed is None else seed
            session = _Session(MCRRefereeEngine(prevalent_wind, chosen_seed, include_flowers=include_flowers), human_seat, random.Random(chosen_seed))
            self._advance(session)
            game_id = str(uuid.uuid4())
            with self._condition:
                self._sessions[game_id] = session
            return session.engine.build_public_player_view(game_id, human_seat)
        finally:
            with self._condition:
                self._creating -= 1
                self._inflight -= 1
                self._condition.notify_all()

    def get_player_view(self, game_id):
        with self._lease(game_id) as session:
            return session.engine.build_public_player_view(game_id, session.human_seat)

    def get_human_encoded_turn(self, game_id):
        with self._lease(game_id) as session:
            engine = session.engine
            if engine.is_finished or session.human_seat not in engine.get_pending_seats() or engine.phase not in ("SELF_TURN", "POST_MELD_DISCARD"):
                raise InvalidTurnStateError("Human is not at a discard decision")
            return engine.get_seat_encoded_state(session.human_seat)

    def submit_human_action(self, game_id, action_id, expected_turn_number=None):
        with self._lease(game_id) as session:
            engine = session.engine
            if engine.is_finished:
                raise GameAlreadyFinishedError("Round has already finished")
            decode_action(action_id)
            # A mandatory token also protects repeated tiles / later identical masks.
            if type(expected_turn_number) is not int or expected_turn_number != engine.turn_number:
                raise InvalidTurnStateError("Missing or stale expected_turn_number")
            engine.submit_seat_action(session.human_seat, action_id)
            self._advance(session)
            return engine.build_public_player_view(game_id, session.human_seat)

    def delete_session(self, game_id):
        with self._lease(game_id) as session:
            with self._condition:
                session.deleted = True
                self._sessions.pop(game_id, None)

    def active_session_count(self):
        with self._condition:
            self._sweep()
            return len(self._sessions)

    def shutdown(self, timeout_sec=5.0):
        if timeout_sec < 0:
            raise ValueError("timeout_sec must be nonnegative")
        deadline = time.monotonic() + timeout_sec
        with self._condition:
            self._accepting = False
            while self._inflight:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Shutdown timed out while draining in-flight game operations")
                self._condition.wait(remaining)
