"""The commission-leak report: what Regular plans cost this portfolio.

Example:
    >>> r = build_report(portfolio, market)  # doctest: +SKIP
    >>> r.leak_20y
    Decimal('380000.00')
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from trailcut_engine.market import MarketData
from trailcut_engine.portfolio import Plan, Portfolio
from trailcut_engine.projection import GrowthPoint, commission_leak, growth_series
from trailcut_engine.summary import PortfolioSummary, paise, summarize
from trailcut_engine.types import DecimalField

ZERO = Decimal(0)
DEFAULT_RETURN = Decimal("0.12")
CHART_YEARS = 20


class SchemeLeak(BaseModel):
    """One fund's commission leak. ``None`` fields mean the TER is unknown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scheme_id: str
    name: str
    plan: Plan
    value: DecimalField
    ter_regular: DecimalField | None
    ter_direct: DecimalField | None
    yearly_leak: DecimalField | None
    leak_10y: DecimalField | None
    leak_20y: DecimalField | None


class Report(BaseModel):
    """Portfolio summary plus the cost of staying in Regular plans."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: PortfolioSummary
    leaks: tuple[SchemeLeak, ...]
    yearly_leak: DecimalField
    leak_10y: DecimalField
    leak_20y: DecimalField
    growth: tuple[GrowthPoint, ...]
    """Regular-plan money: value if left in Regular vs moved to Direct, years 0-20."""
    regular_share: DecimalField
    """Share of portfolio value in Regular plans (0-1)."""
    missing_ter: tuple[str, ...]
    """Regular schemes with no expense-ratio data (excluded from the leak)."""
    expected_return: DecimalField


def build_report(
    portfolio: Portfolio,
    market: MarketData,
    *,
    expected_return: Decimal = DEFAULT_RETURN,
) -> Report:
    """Summarize the portfolio and project its commission leak at 10 and 20 years."""
    summary = summarize(portfolio)
    leaks: list[SchemeLeak] = []
    missing: list[str] = []
    totals = {"yearly": ZERO, "10": ZERO, "20": ZERO}
    chart: dict[int, list[Decimal]] = {y: [ZERO, ZERO] for y in range(CHART_YEARS + 1)}
    for s in portfolio.schemes:
        m = market.for_scheme(s.scheme_id)
        value = s.valuation.value
        known = m.ter_regular is not None and m.ter_direct is not None
        if s.plan is not Plan.DIRECT and not known and value > 0:
            missing.append(s.scheme_id)
        if s.plan is Plan.DIRECT or not known or m.ter_regular is None or m.ter_direct is None:
            leaks.append(
                SchemeLeak(
                    scheme_id=s.scheme_id,
                    name=s.name,
                    plan=s.plan,
                    value=value,
                    ter_regular=m.ter_regular,
                    ter_direct=m.ter_direct,
                    yearly_leak=ZERO if s.plan is Plan.DIRECT else None,
                    leak_10y=ZERO if s.plan is Plan.DIRECT else None,
                    leak_20y=ZERO if s.plan is Plan.DIRECT else None,
                )
            )
            continue
        ten = commission_leak(value, m.ter_regular, m.ter_direct, expected_return, years=10)
        twenty = commission_leak(value, m.ter_regular, m.ter_direct, expected_return, years=20)
        totals["yearly"] += ten.yearly_now
        totals["10"] += ten.leak
        totals["20"] += twenty.leak
        for p in growth_series(
            value, m.ter_regular, m.ter_direct, expected_return, years=CHART_YEARS
        ):
            chart[p.year][0] += p.regular
            chart[p.year][1] += p.direct
        leaks.append(
            SchemeLeak(
                scheme_id=s.scheme_id,
                name=s.name,
                plan=s.plan,
                value=value,
                ter_regular=m.ter_regular,
                ter_direct=m.ter_direct,
                yearly_leak=ten.yearly_now,
                leak_10y=ten.leak,
                leak_20y=twenty.leak,
            )
        )
    share = summary.regular_value / summary.value if summary.value > 0 else ZERO
    return Report(
        summary=summary,
        leaks=tuple(leaks),
        yearly_leak=paise(totals["yearly"]),
        leak_10y=paise(totals["10"]),
        leak_20y=paise(totals["20"]),
        growth=tuple(
            GrowthPoint(year=y, regular=paise(r), direct=paise(d))
            for y, (r, d) in sorted(chart.items())
        ),
        regular_share=share.quantize(Decimal("0.0001")),
        missing_ter=tuple(missing),
        expected_return=expected_return,
    )
