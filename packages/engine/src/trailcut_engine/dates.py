"""Calendar helpers for holding periods and Indian financial years.

Example:
    >>> add_months(date(2024, 1, 31), 1)
    datetime.date(2024, 2, 29)
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def add_months(d: date, months: int) -> date:
    """Same day ``months`` later, clamped to the month end (31 Jan + 1 → 29 Feb).

    Example:
        >>> add_months(date(2025, 3, 31), -1)
        datetime.date(2025, 2, 28)
    """
    index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(index, 12)
    last = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(d.day, last))


def add_years(d: date, years: int) -> date:
    """Same day ``years`` later; 29 Feb maps to 28 Feb in non-leap years.

    Example:
        >>> add_years(date(2024, 2, 29), 1)
        datetime.date(2025, 2, 28)
    """
    return add_months(d, 12 * years)


def held_more_than_months(bought: date, sold: date, months: int) -> bool:
    """True if a unit bought on ``bought`` and sold on ``sold`` was held MORE than ``months``.

    Bought 10 Jan 2025: sold 10 Jan 2026 is exactly 12 months (not more);
    sold 11 Jan 2026 is more than 12 months.

    Example:
        >>> held_more_than_months(date(2025, 1, 10), date(2026, 1, 11), 12)
        True
    """
    return sold > add_months(bought, months)


def first_day_more_than(bought: date, months: int) -> date:
    """The first sale date on which the holding exceeds ``months``.

    Example:
        >>> first_day_more_than(date(2025, 1, 10), 12)
        datetime.date(2026, 1, 11)
    """
    return add_months(bought, months) + timedelta(days=1)


def fy_start_year(d: date) -> int:
    """Calendar year in which the financial year containing ``d`` starts.

    Example:
        >>> fy_start_year(date(2027, 3, 31)), fy_start_year(date(2027, 4, 1))
        (2026, 2027)
    """
    return d.year if d.month >= 4 else d.year - 1


def fy_end(d: date) -> date:
    """31 March ending the financial year that contains ``d``."""
    return date(fy_start_year(d) + 1, 3, 31)


def next_fy_start(d: date) -> date:
    """1 April starting the financial year after the one containing ``d``."""
    return date(fy_start_year(d) + 1, 4, 1)
