"""Runtime settings from environment variables (no secrets in the repo).

| Variable | Default | Meaning |
| --- | --- | --- |
| ``TRAILCUT_ALLOWED_ORIGINS`` | ``http://localhost:5173`` | Comma-separated CORS origins |
| ``TRAILCUT_SESSION_TTL`` | ``1800`` | Seconds a session lives |
| ``TRAILCUT_MAX_SESSIONS`` | ``2000`` | In-memory session cap |
| ``TRAILCUT_RATE_LIMIT`` | ``30`` | Uploads/chat requests per client per minute |
| ``TRAILCUT_DATA_DIR`` | repo ``data/`` | Tax rules, exit-load defaults, market data |
| ``TRAILCUT_CACHE_DIR`` | ``.cache/market`` | Cached public market files (never user data) |
| ``TRAILCUT_ONLINE`` | ``0`` | ``1`` to refresh AMFI NAV data from the internet |
| ``ANTHROPIC_API_KEY`` | unset | Enables the chat agents |
| ``TRAILCUT_MODEL`` | ``claude-sonnet-5-5`` | Model for explanations |
| ``TRAILCUT_ROUTER_MODEL`` | ``claude-haiku-5-5`` | Model for routing and the guard |
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr

REPO_ROOT = Path(__file__).resolve().parents[4]


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    allowed_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    session_ttl_seconds: int = 1800
    max_sessions: int = 2000
    rate_limit_per_minute: int = 30
    data_dir: Path = REPO_ROOT / "data"
    cache_dir: Path = REPO_ROOT / ".cache" / "market"
    online: bool = False
    anthropic_api_key: SecretStr | None = None
    model: str = "claude-sonnet-5-5"
    router_model: str = "claude-haiku-5-5"
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``env`` (defaults to ``os.environ``)."""
        e = os.environ if env is None else env
        origins = tuple(
            o.strip() for o in e.get("TRAILCUT_ALLOWED_ORIGINS", "").split(",") if o.strip()
        )
        key = e.get("ANTHROPIC_API_KEY")
        base = cls()
        return cls(
            allowed_origins=origins or base.allowed_origins,
            session_ttl_seconds=int(e.get("TRAILCUT_SESSION_TTL", base.session_ttl_seconds)),
            max_sessions=int(e.get("TRAILCUT_MAX_SESSIONS", base.max_sessions)),
            rate_limit_per_minute=int(e.get("TRAILCUT_RATE_LIMIT", base.rate_limit_per_minute)),
            data_dir=Path(e.get("TRAILCUT_DATA_DIR", str(base.data_dir))),
            cache_dir=Path(e.get("TRAILCUT_CACHE_DIR", str(base.cache_dir))),
            online=_flag(e.get("TRAILCUT_ONLINE")),
            anthropic_api_key=SecretStr(key) if key else None,
            model=e.get("TRAILCUT_MODEL", base.model),
            router_model=e.get("TRAILCUT_ROUTER_MODEL", base.router_model),
        )
