"""XIRR (annualised internal rate of return for dated cashflows) in Decimal.

Sign convention: money you put in is negative, money you get back (including
today's value) is positive. Day count is actual/365, matching spreadsheet XIRR.

Example:
    >>> xirr([(date(2025, 1, 1), Decimal(-1000)), (date(2026, 1, 1), Decimal(1100))])
    Decimal('0.10000000')
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal, localcontext

DAYS_PER_YEAR = Decimal(365)
RESULT_PLACES = Decimal("0.00000001")
LOWER = Decimal("-0.999999")
UPPER = Decimal(100)
TOLERANCE = Decimal("1e-12")
MAX_ITERATIONS = 200
GUESS = Decimal("0.1")

Cashflow = tuple[date, Decimal]


class XirrError(ValueError):
    """Raised when XIRR has no solution for the given cashflows."""


def _npv_and_slope(
    rate: Decimal, flows: Sequence[tuple[Decimal, Decimal]]
) -> tuple[Decimal, Decimal]:
    """NPV at ``rate`` and its derivative d(NPV)/d(rate)."""
    base = 1 + rate
    log_base = base.ln()
    npv = Decimal(0)
    slope = Decimal(0)
    for years, amount in flows:
        discounted = amount / (years * log_base).exp()
        npv += discounted
        slope -= years * discounted / base
    return npv, slope


def xirr(cashflows: Sequence[Cashflow]) -> Decimal:
    """Annualised return as a fraction (0.12 = 12% a year), to 8 decimal places.

    Safeguarded Newton's method: Newton steps inside a bracket on
    [-99.9999%, 10,000%] that always contains the root, falling back to bisection
    whenever a step would leave it. Converges like Newton (a handful of
    iterations) with the guarantee of bisection, and needs no starting guess.

    Raises:
        XirrError: fewer than two cashflows, all on one date, or no sign change
            (all money in or all money out), or no root in range.
    """
    flows = [(d, a) for d, a in cashflows if a != 0]
    if len(flows) < 2:
        msg = "need at least two non-zero cashflows"
        raise XirrError(msg)
    if not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        msg = "cashflows need both money in (negative) and money out (positive)"
        raise XirrError(msg)
    start = min(d for d, _ in flows)
    if all(d == start for d, _ in flows):
        msg = "all cashflows are on the same date"
        raise XirrError(msg)

    with localcontext() as ctx:
        ctx.prec = 34
        timed = [(Decimal((d - start).days) / DAYS_PER_YEAR, a) for d, a in flows]
        lo, hi = LOWER, UPPER
        f_lo, _ = _npv_and_slope(lo, timed)
        f_hi, _ = _npv_and_slope(hi, timed)
        if f_lo == 0:
            return lo.quantize(RESULT_PLACES)
        if (f_lo > 0) == (f_hi > 0):
            msg = "no rate between -99.9999% and 10,000% sets NPV to zero"
            raise XirrError(msg)
        rate = GUESS if lo < GUESS < hi else (lo + hi) / 2
        for _ in range(MAX_ITERATIONS):
            f, slope = _npv_and_slope(rate, timed)
            if f == 0:
                return rate.quantize(RESULT_PLACES)
            # Shrink the bracket around the root.
            if (f > 0) == (f_lo > 0):
                lo, f_lo = rate, f
            else:
                hi = rate
            step = f / slope if slope != 0 else None
            candidate = rate - step if step is not None else None
            if candidate is None or not lo < candidate < hi:
                candidate = (lo + hi) / 2  # Newton would leave the bracket: bisect
            if abs(candidate - rate) < TOLERANCE or hi - lo < TOLERANCE:
                return candidate.quantize(RESULT_PLACES)
            rate = candidate
        return rate.quantize(RESULT_PLACES)
