"""Bounded owner registry; per-game leases serialize web operations through save."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import threading
import time

from app.domain.exceptions import GameNotFoundError, ServiceShuttingDownError, SessionCapacityExceededError

FINISHED_RETENTION_SECONDS = 30.0  # Existing GameSessionService retention policy.


@dataclass
class OwnedGame:
    owner_key: str
    last_access: float
    lock: object = field(default_factory=threading.RLock)
    leases: int = 0
    finished_at: float | None = None
    turn_phase: str = 'SELF_TURN'


class OwnedGames:
    def __init__(self, games, max_active_games=128, ttl_seconds=3600, clock=time.monotonic):
        self.games, self.maximum, self.ttl, self.clock = games, max_active_games, ttl_seconds, clock
        self._entries = {}
        self._condition = threading.Condition(threading.RLock())
        self._creating = 0
        self._closing = False

    def _sweep(self):
        expired = []
        with self._condition:
            now = self.clock()
            for game_id,entry in list(self._entries.items()):
                idle = now-entry.last_access>=self.ttl
                finished = entry.finished_at is not None and now-entry.finished_at>=FINISHED_RETENTION_SECONDS
                if not entry.leases and (idle or finished):
                    expired.append(game_id)
                    del self._entries[game_id]
        for game_id in expired:
            try:self.games.delete_session(game_id)
            except GameNotFoundError:pass

    def _check_open(self):
        if self._closing:raise ServiceShuttingDownError('Game service is shutting down')

    def create(self, owner_key, **parameters):
        self._sweep()
        with self._condition:
            self._check_open()
            if len(self._entries)+self._creating>=self.maximum:
                raise SessionCapacityExceededError('All game slots are occupied')
            self._creating+=1
        try:
            view = self.games.create_game(**parameters)
            entry = OwnedGame(owner_key,self.clock())
            self.note_view(entry,view)
            with self._condition:self._entries[view.game_id]=entry
            return view
        finally:
            with self._condition:
                self._creating-=1
                self._condition.notify_all()

    @contextmanager
    def owned(self, owner_key, game_id):
        game_id = str(game_id)
        self._sweep()
        with self._condition:
            self._check_open()
            entry = self._entries.get(game_id)
            if entry is None or entry.owner_key!=owner_key:
                raise GameNotFoundError('Unknown or expired game')
            entry.leases+=1
        try:
            with entry.lock:yield entry
        finally:
            with self._condition:
                entry.leases-=1
                entry.last_access=self.clock()
                self._condition.notify_all()

    def note_view(self, entry, view):
        if view.status=='FINISHED' and entry.finished_at is None:entry.finished_at=self.clock()

    def view(self, owner_key, game_id):
        with self.owned(owner_key,game_id) as entry:
            view = self.games.get_player_view(str(game_id))
            self.note_view(entry,view)
            return view

    def action(self, owner_key, game_id, action_id, expected_turn_number):
        with self.owned(owner_key,game_id) as entry:
            before = self.games.get_player_view(str(game_id))
            accepted_type = next((option.action_type for option in before.legal_actions if option.action_id==action_id),None)
            view = self.games.submit_human_action(str(game_id),action_id,expected_turn_number)
            gained_meld=(len(view.seat_public_states[view.human_seat].melds)>
                         len(before.seat_public_states[before.human_seat].melds))
            entry.turn_phase = ('POST_MELD_DISCARD' if accepted_type in ('Chi','Peng') and gained_meld
                                and view.status=='WAITING_HUMAN_DISCARD' else 'SELF_TURN')
            self.note_view(entry,view)
            return view

    def shutdown(self, timeout=10):
        deadline = time.monotonic()+timeout
        with self._condition:
            self._closing=True
            while self._creating or any(entry.leases for entry in self._entries.values()):
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('Timed out draining web game operations')
                self._condition.wait(remaining)
        self.games.shutdown(timeout_sec=timeout)
