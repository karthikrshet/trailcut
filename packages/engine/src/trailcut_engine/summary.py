"""Portfolio summary: value, money still invested, gain and XIRR per fund and overall.

Example:
    >>> s = summarize(portfolio)  # doctest: +SKIP
    >>> s.value, s.xirr
    (Decimal('2134154.79'), Decimal('0.1342...'))
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict

from trailcut_engine.lots import build_lots
from trailcut_engine.portfolio import AssetClass, Plan, Portfolio, Scheme, TxnKind
from trailcut_engine.types import DecimalField
from trailcut_engine.xirr import Cashflow, XirrError, xirr

ZERO = Decimal(0)
PAISE = Decimal("0.01")


def paise(amount: Decimal) -> Decimal:
    """Round a rupee amount to paise for output (half up).

    Example:
        >>> paise(Decimal("10.005"))
        Decimal('10.01')
    """
    return amount.quantize(PAISE, ROUND_HALF_UP)


_MONEY_IN = frozenset(
    {TxnKind.PURCHASE, TxnKind.SIP, TxnKind.SWITCH_IN, TxnKind.GIFT_IN, TxnKind.TAX}
)
_MONEY_OUT = frozenset(
    {TxnKind.REDEMPTION, TxnKind.SWITCH_OUT, TxnKind.DIVIDEND_PAYOUT, TxnKind.GIFT_OUT}
)


def scheme_cashflows(scheme: Scheme) -> list[Cashflow]:
    """Dated cashflows for XIRR: purchases negative, payouts positive, value today positive.

    Reinvested dividends, mergers and segregations move units without moving money,
    so they are not cashflows.
    """
    flows: list[Cashflow] = []
    for t in scheme.transactions:
        if t.amount is None or t.amount == 0:
            continue
        if t.kind in _MONEY_IN:
            flows.append((t.date, -abs(t.amount)))
        elif t.kind in _MONEY_OUT:
            flows.append((t.date, abs(t.amount)))
        elif t.kind is TxnKind.REVERSAL and t.units is not None:
            # A reversed purchase gives money back; a reversed redemption takes it.
            flows.append((t.date, abs(t.amount) if t.units < 0 else -abs(t.amount)))
    if scheme.valuation.value > 0:
        flows.append((scheme.valuation.date, scheme.valuation.value))
    return flows


def _safe_xirr(flows: Iterable[Cashflow]) -> Decimal | None:
    try:
        return xirr(list(flows))
    except XirrError:
        return None


class SchemeSummary(BaseModel):
    """One fund's headline numbers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scheme_id: str
    name: str
    plan: Plan
    asset_class: AssetClass
    is_elss: bool
    units: DecimalField
    nav: DecimalField
    nav_date: date
    value: DecimalField
    invested: DecimalField
    """Cost of the units still held (FIFO), including stamp duty."""
    gain: DecimalField
    xirr: DecimalField | None
    """Annualised return; ``None`` when history is incomplete."""
    cost_complete: bool
    """False if some units have unknown cost (held before the statement period)."""


class PortfolioSummary(BaseModel):
    """Whole-portfolio headline numbers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of: date
    value: DecimalField
    invested: DecimalField
    gain: DecimalField
    xirr: DecimalField | None
    regular_value: DecimalField
    direct_value: DecimalField
    schemes: tuple[SchemeSummary, ...]


def summarize_scheme(scheme: Scheme) -> SchemeSummary:
    """Headline numbers for one scheme."""
    book = build_lots(scheme)
    complete = all(lot.cost_known for lot in book.open_lots) and scheme.open_units == 0
    value = scheme.valuation.value
    return SchemeSummary(
        scheme_id=scheme.scheme_id,
        name=scheme.name,
        plan=scheme.plan,
        asset_class=scheme.asset_class,
        is_elss=scheme.is_elss,
        units=scheme.close_units,
        nav=scheme.valuation.nav,
        nav_date=scheme.valuation.date,
        value=paise(value),
        invested=paise(book.cost),
        gain=paise(value - book.cost),
        xirr=_safe_xirr(scheme_cashflows(scheme)) if complete else None,
        cost_complete=complete,
    )


def summarize(portfolio: Portfolio) -> PortfolioSummary:
    """Headline numbers for the whole portfolio."""
    schemes = tuple(summarize_scheme(s) for s in portfolio.schemes)
    all_complete = all(s.cost_complete for s in schemes)
    flows: list[Cashflow] = []
    for s in portfolio.schemes:
        flows.extend(scheme_cashflows(s))
    value = sum((s.value for s in schemes), ZERO)
    invested = sum((s.invested for s in schemes), ZERO)
    as_of = max((s.nav_date for s in schemes), default=portfolio.statement_to)
    return PortfolioSummary(
        as_of=as_of,
        value=paise(value),
        invested=paise(invested),
        gain=paise(value - invested),
        xirr=_safe_xirr(flows) if all_complete else None,
        regular_value=sum((s.value for s in schemes if s.plan is Plan.REGULAR), ZERO),
        direct_value=sum((s.value for s in schemes if s.plan is Plan.DIRECT), ZERO),
        schemes=schemes,
    )
