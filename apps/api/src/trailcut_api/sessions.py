"""In-memory sessions with a TTL. Nothing is written to disk.

A session holds only the PII-free normalized portfolio, its market data and the
user's assumptions. Sessions expire after ``ttl`` seconds of inactivity and can be
deleted at any time ("Delete my data now").

Example:
    >>> store = SessionStore(ttl_seconds=1800)
    >>> sid = store.create(portfolio, market, assumptions)  # doctest: +SKIP
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from trailcut_engine.market import MarketData
from trailcut_engine.planner import Assumptions
from trailcut_engine.portfolio import Portfolio

Clock = Callable[[], float]


@dataclass(frozen=True)
class Session:
    session_id: str
    portfolio: Portfolio
    market: MarketData
    assumptions: Assumptions
    is_sample: bool
    created_at: float
    last_seen: float
    chat_turns: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


class SessionNotFoundError(KeyError):
    """Unknown, expired or deleted session."""


class SessionStore:
    """Thread-safe TTL store, oldest evicted first when full."""

    def __init__(
        self, *, ttl_seconds: int, max_sessions: int = 2000, clock: Clock = time.monotonic
    ) -> None:
        self.ttl = ttl_seconds
        self.max_sessions = max_sessions
        self._clock = clock
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            self._purge()
            return len(self._items)

    def _purge(self) -> None:
        now = self._clock()
        expired = [k for k, s in self._items.items() if now - s.last_seen > self.ttl]
        for k in expired:
            del self._items[k]

    def create(
        self,
        portfolio: Portfolio,
        market: MarketData,
        assumptions: Assumptions,
        *,
        is_sample: bool = False,
        notes: tuple[str, ...] = (),
    ) -> Session:
        now = self._clock()
        session = Session(
            session_id=secrets.token_urlsafe(24),
            portfolio=portfolio,
            market=market,
            assumptions=assumptions,
            is_sample=is_sample,
            created_at=now,
            last_seen=now,
            notes=notes,
        )
        with self._lock:
            self._purge()
            while len(self._items) >= self.max_sessions:
                self._items.popitem(last=False)
            self._items[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        """Fetch a live session and refresh its expiry."""
        with self._lock:
            self._purge()
            session = self._items.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            session = replace(session, last_seen=self._clock())
            self._items[session_id] = session
            self._items.move_to_end(session_id)
            return session

    def update(self, session: Session) -> Session:
        with self._lock:
            if session.session_id not in self._items:
                raise SessionNotFoundError(session.session_id)
            updated = replace(session, last_seen=self._clock())
            self._items[session.session_id] = updated
            return updated

    def delete(self, session_id: str) -> bool:
        """Remove a session. Returns False if it was already gone."""
        with self._lock:
            return self._items.pop(session_id, None) is not None
