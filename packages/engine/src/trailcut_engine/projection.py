"""Regular vs Direct projections: the commission leak and the payoff of switching.

A Regular plan's expense ratio (TER) is higher than its Direct twin's by the
distributor's trail commission. Both plans hold the same portfolio, so with a
gross return ``g`` the Regular plan compounds at ``g - TER_regular`` and the
Direct plan at ``g - TER_direct``.

Projections ignore tax due when the money is finally withdrawn, on both paths,
so the cost of switching today is counted in full. That makes switching look
slightly worse than it is, never better.

Example:
    >>> leak = commission_leak(Decimal(100000), Decimal("0.02"), Decimal("0.01"),
    ...                        Decimal("0.12"), years=10)
    >>> leak.yearly_now
    Decimal('1000.00')
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext

from pydantic import BaseModel, ConfigDict

from trailcut_engine.types import DecimalField

ZERO = Decimal(0)
PAISE = Decimal("0.01")


def grow(value: Decimal, annual_rate: Decimal, years: Decimal | int) -> Decimal:
    """Compound ``value`` at ``annual_rate`` for ``years`` (fractional years allowed).

    Example:
        >>> grow(Decimal(1000), Decimal("0.10"), 2)
        Decimal('1210.00')
    """
    if value == 0:
        return ZERO
    with localcontext() as ctx:
        ctx.prec = 34
        factor = (1 + annual_rate) ** Decimal(years)
        return (value * factor).quantize(PAISE, ROUND_HALF_UP)


class LeakProjection(BaseModel):
    """What staying in Regular costs versus the same money in Direct."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    years: int
    yearly_now: DecimalField
    """This year's extra cost: value x TER gap."""
    regular_value: DecimalField
    direct_value: DecimalField
    leak: DecimalField
    """Direct value minus Regular value at the horizon."""


def commission_leak(
    value: Decimal,
    ter_regular: Decimal,
    ter_direct: Decimal,
    expected_return: Decimal,
    *,
    years: int,
) -> LeakProjection:
    """Project the cost of staying in Regular over ``years``."""
    gap = max(ter_regular - ter_direct, ZERO)
    regular = grow(value, expected_return - ter_regular, years)
    direct = grow(value, expected_return - ter_direct, years)
    return LeakProjection(
        years=years,
        yearly_now=(value * gap).quantize(PAISE, ROUND_HALF_UP),
        regular_value=regular,
        direct_value=direct,
        leak=max(direct - regular, ZERO),
    )


class GrowthPoint(BaseModel):
    """One year on the Regular-vs-Direct chart."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    year: int
    regular: DecimalField
    direct: DecimalField


def growth_series(
    value: Decimal,
    ter_regular: Decimal,
    ter_direct: Decimal,
    expected_return: Decimal,
    *,
    years: int,
) -> tuple[GrowthPoint, ...]:
    """Year-by-year values for the chart, year 0 to ``years`` inclusive."""
    return tuple(
        GrowthPoint(
            year=y,
            regular=grow(value, expected_return - ter_regular, y),
            direct=grow(value, expected_return - ter_direct, y),
        )
        for y in range(years + 1)
    )


def switch_net_benefit(
    value: Decimal,
    switch_cost: Decimal,
    ter_regular: Decimal,
    ter_direct: Decimal,
    expected_return: Decimal,
    *,
    years: int,
) -> Decimal:
    """Value at the horizon if switched today (after paying ``switch_cost``)
    minus value if left in Regular. Negative means switching doesn't pay.

    Example:
        >>> switch_net_benefit(Decimal(100000), Decimal(0), Decimal("0.02"),
        ...                    Decimal("0.01"), Decimal("0.12"), years=10) > 0
        True
    """
    switched = grow(value - switch_cost, expected_return - ter_direct, years)
    stayed = grow(value, expected_return - ter_regular, years)
    return switched - stayed


def break_even_months(
    value: Decimal,
    switch_cost: Decimal,
    ter_regular: Decimal,
    ter_direct: Decimal,
    expected_return: Decimal,
) -> int | None:
    """Months until switching has paid back its one-time cost.

    ``0`` if switching is free; ``None`` if it never pays back (no TER gap, or
    the cost is the whole value).

    Example:
        >>> break_even_months(Decimal(100000), Decimal(1000), Decimal("0.02"),
        ...                   Decimal("0.01"), Decimal("0.12"))
        14
    """
    if switch_cost <= 0:
        return 0
    if switch_cost >= value or ter_direct >= ter_regular:
        return None
    with localcontext() as ctx:
        ctx.prec = 34
        ratio_needed = (value / (value - switch_cost)).ln()
        ratio_per_year = (
            (1 + expected_return - ter_direct) / (1 + expected_return - ter_regular)
        ).ln()
        months = (12 * ratio_needed / ratio_per_year).to_integral_value(ROUND_CEILING)
    return int(months)
