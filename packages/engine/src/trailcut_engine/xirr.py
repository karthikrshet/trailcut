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
MAX_ITERATIONS = 300

Cashflow = tuple[date, Decimal]


class XirrError(ValueError):
    """Raised when XIRR has no solution for the given cashflows."""


def _npv(rate: Decimal, flows: Sequence[tuple[Decimal, Decimal]]) -> Decimal:
    base = 1 + rate
    return sum((amount / base**years for years, amount in flows), Decimal(0))


def xirr(cashflows: Sequence[Cashflow]) -> Decimal:
    """Annualised return as a fraction (0.12 = 12% a year), to 8 decimal places.

    Uses bisection on [-99.9999%, 10,000%], which always converges when a sign
    change exists, so there is no dependence on a starting guess.

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
        f_lo, f_hi = _npv(lo, timed), _npv(hi, timed)
        if f_lo == 0:
            return lo.quantize(RESULT_PLACES)
        if (f_lo > 0) == (f_hi > 0):
            msg = "no rate between -99.9999% and 10,000% sets NPV to zero"
            raise XirrError(msg)
        for _ in range(MAX_ITERATIONS):
            mid = (lo + hi) / 2
            f_mid = _npv(mid, timed)
            if f_mid == 0 or (hi - lo) / 2 < TOLERANCE:
                break
            if (f_mid > 0) == (f_lo > 0):
                lo, f_lo = mid, f_mid
            else:
                hi = mid
        return ((lo + hi) / 2).quantize(RESULT_PLACES)
