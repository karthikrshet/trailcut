"""Display formatting shared by the engine's plain-language reasons and the agent.

Matches the web app's ``formatINR`` / ``formatDate`` so a number in a sentence is
byte-for-byte the number in the table.

Example:
    >>> format_inr(Decimal("125000"))
    '₹1,25,000'
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _group_indian(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    pairs: list[str] = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join([*pairs, tail])


def format_inr(amount: Decimal, *, paise: bool = False) -> str:
    """Indian rupee format: ``₹1,25,000`` (or ``₹1,250.50`` with ``paise=True``).

    Example:
        >>> format_inr(Decimal("-1234567.5"))
        '-₹12,34,568'
    """
    places = Decimal("0.01") if paise else Decimal(1)
    rounded = amount.quantize(places, ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    whole, _, frac = f"{abs(rounded):f}".partition(".")
    body = _group_indian(whole)
    return f"{sign}₹{body}.{frac}" if paise else f"{sign}₹{body}"


def format_percent(fraction: Decimal, places: int = 2) -> str:
    """``0.1171`` → ``11.71%``.

    Example:
        >>> format_percent(Decimal("0.0175"))
        '1.75%'
    """
    q = Decimal(1).scaleb(-places)
    return f"{(fraction * 100).quantize(q, ROUND_HALF_UP)}%"


def format_date(d: date) -> str:
    """``14 Feb 2027``.

    Example:
        >>> format_date(date(2027, 2, 14))
        '14 Feb 2027'
    """
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
