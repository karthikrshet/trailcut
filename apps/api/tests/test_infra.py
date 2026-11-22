"""Sessions, rate limiting and settings."""

from datetime import date
from pathlib import Path

import pytest

from trailcut_api.ratelimit import RateLimiter
from trailcut_api.sessions import SessionNotFoundError, SessionStore
from trailcut_api.settings import Settings
from trailcut_engine.market import MarketData
from trailcut_engine.planner import Assumptions
from trailcut_ingest.sample import load_sample_portfolio


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def new(store: SessionStore) -> str:
    p = load_sample_portfolio()
    return store.create(p, MarketData(), Assumptions(as_of=date(2026, 11, 20))).session_id


# ---------- sessions ----------


def test_session_round_trip(clock: FakeClock) -> None:
    store = SessionStore(ttl_seconds=60, clock=clock)
    sid = new(store)
    assert store.get(sid).session_id == sid
    assert len(store) == 1


def test_session_ids_are_unguessable(clock: FakeClock) -> None:
    store = SessionStore(ttl_seconds=60, clock=clock)
    ids = {new(store) for _ in range(50)}
    assert len(ids) == 50
    assert all(len(i) >= 32 for i in ids)


@pytest.mark.parametrize(
    ("elapsed", "alive"), [(59, True), (60, True), (61, False), (10_000, False)]
)
def test_session_expires_after_ttl(clock: FakeClock, elapsed: int, alive: bool) -> None:
    store = SessionStore(ttl_seconds=60, clock=clock)
    sid = new(store)
    clock.now += elapsed
    if alive:
        assert store.get(sid).session_id == sid
    else:
        with pytest.raises(SessionNotFoundError):
            store.get(sid)


def test_access_refreshes_expiry(clock: FakeClock) -> None:
    store = SessionStore(ttl_seconds=60, clock=clock)
    sid = new(store)
    for _ in range(5):
        clock.now += 50
        store.get(sid)
    assert store.get(sid).session_id == sid


def test_delete(clock: FakeClock) -> None:
    store = SessionStore(ttl_seconds=60, clock=clock)
    sid = new(store)
    assert store.delete(sid) is True
    assert store.delete(sid) is False
    with pytest.raises(SessionNotFoundError):
        store.get(sid)


def test_oldest_session_is_evicted_when_full(clock: FakeClock) -> None:
    store = SessionStore(ttl_seconds=60, max_sessions=2, clock=clock)
    first, second, third = new(store), new(store), new(store)
    with pytest.raises(SessionNotFoundError):
        store.get(first)
    assert {store.get(second).session_id, store.get(third).session_id} == {second, third}


def test_update_unknown_session_fails(clock: FakeClock) -> None:
    store = SessionStore(ttl_seconds=60, clock=clock)
    sid = new(store)
    session = store.get(sid)
    store.delete(sid)
    with pytest.raises(SessionNotFoundError):
        store.update(session)


# ---------- rate limiter ----------


def test_allows_burst_then_blocks(clock: FakeClock) -> None:
    limiter = RateLimiter(per_minute=3, clock=clock)
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]
    assert limiter.retry_after("a") >= 1


def test_refills_over_time(clock: FakeClock) -> None:
    limiter = RateLimiter(per_minute=60, clock=clock)
    for _ in range(60):
        assert limiter.allow("a")
    assert not limiter.allow("a")
    clock.now += 1
    assert limiter.allow("a")


def test_clients_are_independent(clock: FakeClock) -> None:
    limiter = RateLimiter(per_minute=1, clock=clock)
    assert limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("a")


@pytest.mark.parametrize("per_minute", [0, -1])
def test_rate_must_be_positive(per_minute: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        RateLimiter(per_minute=per_minute)


# ---------- settings ----------


def test_settings_defaults() -> None:
    s = Settings.from_env({})
    assert s.session_ttl_seconds == 1800
    assert s.anthropic_api_key is None
    assert not s.online
    assert (s.data_dir / "tax_rules").is_dir()


def test_settings_from_env() -> None:
    s = Settings.from_env(
        {
            "TRAILCUT_ALLOWED_ORIGINS": "https://trailcut.app, https://www.trailcut.app",
            "TRAILCUT_SESSION_TTL": "60",
            "TRAILCUT_RATE_LIMIT": "5",
            "TRAILCUT_ONLINE": "yes",
            "TRAILCUT_DATA_DIR": "/tmp/data",
            "ANTHROPIC_API_KEY": "sk-test-not-real",
        }
    )
    assert s.allowed_origins == ("https://trailcut.app", "https://www.trailcut.app")
    assert (s.session_ttl_seconds, s.rate_limit_per_minute, s.online) == (60, 5, True)
    assert s.data_dir == Path("/tmp/data")
    assert s.anthropic_api_key is not None
    assert "sk-test" not in repr(s)
