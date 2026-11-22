"""Assemble :class:`MarketData` for a portfolio from local and cached public data.

Sources, in order of trust:

1. ``data/samples/sample_market.json`` for the demo portfolio.
2. ``data/market/ter.csv`` for expense ratios (by ISIN), AMFI ``NAVAll.txt`` to find
   each Regular scheme's Direct twin.
3. ``data/exit_loads/defaults.yaml`` for exit loads (marked as assumptions).
4. User overrides stored in the session (expense ratios typed in the UI).

Nothing here touches user data on disk; the cache holds only public AMFI files.
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from trailcut_api.market.amfi import NavRecord, by_isin, pair_direct, parse_navall
from trailcut_engine.market import (
    ExitLoadRule,
    ExitLoadTier,
    MarketData,
    SchemeMarket,
    market_for_portfolio,
)
from trailcut_engine.portfolio import AssetClass, Portfolio, Scheme

NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
CACHE_MAX_AGE_SECONDS = 24 * 3600
HUNDRED = Decimal(100)

Fetcher = Callable[[str], str]


def _http_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "TrailCut/0.1 (+open source)"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed https URL
        body: bytes = response.read()
    return body.decode("utf-8", errors="replace")


def parse_ter_csv(text: str) -> dict[str, tuple[Decimal, date | None, str]]:
    """``isin -> (ter as fraction, as_of, source)``. Bad rows are skipped."""
    out: dict[str, tuple[Decimal, date | None, str]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        isin = (row.get("isin") or "").strip().upper()
        try:
            ter = Decimal((row.get("ter_percent") or "").strip()) / HUNDRED
        except InvalidOperation:
            continue
        if not isin or not Decimal(0) <= ter <= Decimal(1):
            continue
        try:
            as_of: date | None = date.fromisoformat((row.get("as_of") or "").strip())
        except ValueError:
            as_of = None
        out[isin] = (ter, as_of, (row.get("source") or "ter.csv").strip())
    return out


def parse_exit_load_defaults(text: str) -> dict[str, ExitLoadRule]:
    """Exit-load assumptions keyed by ``equity``/``elss``/``hybrid``/``debt``/``unknown``."""
    raw = yaml.safe_load(text) or {}
    return {
        key: ExitLoadRule(
            tiers=tuple(
                ExitLoadTier(within_days=int(t["within_days"]), rate=Decimal(str(t["rate"])))
                for t in (tiers or [])
            ),
            source="assumed default for this fund type",
        )
        for key, tiers in raw.items()
    }


def exit_load_key(scheme: Scheme) -> str:
    if scheme.is_elss:
        return "elss"
    return {
        AssetClass.EQUITY: "equity",
        AssetClass.HYBRID: "hybrid",
        AssetClass.DEBT: "debt",
    }.get(scheme.asset_class, "unknown")


class MarketService:
    def __init__(
        self,
        data_dir: Path,
        cache_dir: Path,
        *,
        online: bool = False,
        fetcher: Fetcher = _http_get,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.online = online
        self._fetch = fetcher
        self._clock = clock
        self._ter = parse_ter_csv(self._read(data_dir / "market" / "ter.csv"))
        self._exit_loads = parse_exit_load_defaults(
            self._read(data_dir / "exit_loads" / "defaults.yaml")
        )
        self._navall: list[NavRecord] | None = None

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    # ---------- sample ----------

    def sample_market(self, portfolio: Portfolio) -> MarketData:
        raw = json.loads(self._read(self.data_dir / "samples" / "sample_market.json") or "{}")
        entries = {k: SchemeMarket.model_validate(v) for k, v in raw.get("schemes", {}).items()}
        as_of = date.fromisoformat(raw["as_of"]) if raw.get("as_of") else None
        return market_for_portfolio(
            portfolio, entries, as_of=as_of, source=raw.get("source", "sample")
        )

    # ---------- real statements ----------

    def navall(self) -> list[NavRecord]:
        """AMFI NAV records from cache, refreshed daily when online."""
        if self._navall is not None:
            return self._navall
        path = self.cache_dir / "NAVAll.txt"
        fresh = path.exists() and self._clock() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS
        if self.online and not fresh:
            try:
                text = self._fetch(NAVALL_URL)
                if "Scheme Code" in text:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
            except OSError:
                pass  # stale cache (or none) is used; the report shows the data date
        self._navall = parse_navall(self._read(path))
        return self._navall

    def market_for(
        self,
        portfolio: Portfolio,
        overrides: Mapping[str, tuple[Decimal, Decimal]] | None = None,
    ) -> MarketData:
        """Market data for an uploaded portfolio. Unknowns stay ``None``."""
        records = self.navall()
        twins = pair_direct(records)
        index = by_isin(records)
        schemes: dict[str, SchemeMarket] = {}
        dates: list[date] = []
        for s in portfolio.schemes:
            ter_regular = ter_direct = None
            direct_name = None
            source = "unknown"
            if s.isin and s.isin in self._ter:
                ter_regular, as_of, source = self._ter[s.isin]
                if as_of:
                    dates.append(as_of)
            twin = twins.get(s.isin or "")
            if twin is not None:
                direct_name = twin.name
                for isin in twin.isins:
                    if isin in self._ter:
                        ter_direct = self._ter[isin][0]
                        break
            if s.isin and s.isin in index and index[s.isin].is_direct:
                direct_name = index[s.isin].name
            if overrides and s.scheme_id in overrides:
                ter_regular, ter_direct = overrides[s.scheme_id]
                source = "entered by you"
            schemes[s.scheme_id] = SchemeMarket(
                ter_regular=ter_regular,
                ter_direct=ter_direct,
                direct_name=direct_name,
                exit_load=self._exit_loads.get(exit_load_key(s)),
                source=source,
            )
        return MarketData(
            schemes=schemes, as_of=max(dates) if dates else None, source="AMFI + defaults"
        )

    def with_overrides(
        self, market: MarketData, overrides: Mapping[str, tuple[Decimal, Decimal]]
    ) -> MarketData:
        """Apply user-entered expense ratios to existing market data."""
        schemes = dict(market.schemes)
        for scheme_id, (regular, direct) in overrides.items():
            base = schemes.get(scheme_id, SchemeMarket())
            schemes[scheme_id] = base.model_copy(
                update={"ter_regular": regular, "ter_direct": direct, "source": "entered by you"}
            )
        return market.model_copy(update={"schemes": schemes})
