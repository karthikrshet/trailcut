"""Quick commission estimate without a statement: lump sum plus monthly SIP.

Both plans hold the same portfolio; Regular compounds at return minus its expense
ratio, Direct at return minus the lower one. Contributions are made at the start
of each month and compound monthly at the equivalent monthly rate.

Example:
    >>> e = estimate_commission(EstimateInput(lump_sum=Decimal(500000), years=10))
    >>> e.leak > 0
    True
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trailcut_engine.types import DecimalField

PAISE = Decimal("0.01")
ZERO = Decimal(0)
MAX_YEARS = 40


def _paise(x: Decimal) -> Decimal:
    return x.quantize(PAISE, ROUND_HALF_UP)


class EstimateInput(BaseModel):
    """What someone can type without a statement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lump_sum: Annotated[DecimalField, Field(ge=0, le=Decimal(10**11))] = ZERO
    monthly_sip: Annotated[DecimalField, Field(ge=0, le=Decimal(10**9))] = ZERO
    years: Annotated[int, Field(ge=1, le=MAX_YEARS)] = 10
    ter_regular: Annotated[DecimalField, Field(ge=0, le=Decimal("0.05"))] = Decimal("0.0165")
    ter_direct: Annotated[DecimalField, Field(ge=0, le=Decimal("0.05"))] = Decimal("0.0070")
    expected_return: Annotated[DecimalField, Field(ge=Decimal("-0.2"), le=Decimal("0.3"))] = (
        Decimal("0.12")
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.lump_sum == 0 and self.monthly_sip == 0:
            msg = "enter a lump sum, a monthly SIP, or both"
            raise ValueError(msg)
        if self.ter_direct > self.ter_regular:
            msg = "the Direct plan's expense ratio can't be higher than the Regular plan's"
            raise ValueError(msg)
        return self


class EstimatePoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    year: int
    invested: DecimalField
    regular: DecimalField
    direct: DecimalField


class Estimate(BaseModel):
    """Projected values and the commission leak at the horizon."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    years: int
    invested: DecimalField
    regular_value: DecimalField
    direct_value: DecimalField
    leak: DecimalField
    """Direct minus Regular at the horizon: what commission costs."""
    leak_share: DecimalField
    """Leak as a fraction of the Direct value."""
    first_year_fees_gap: DecimalField
    """Extra fees in the first year (on money invested during year one)."""
    series: tuple[EstimatePoint, ...]


def _monthly_rate(annual: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 34
        return (1 + annual) ** (Decimal(1) / 12) - 1


def estimate_commission(inp: EstimateInput) -> Estimate:
    """Project a lump sum and monthly SIP in Regular vs Direct for ``inp.years``."""
    with localcontext() as ctx:
        ctx.prec = 34
        r_reg = _monthly_rate(inp.expected_return - inp.ter_regular)
        r_dir = _monthly_rate(inp.expected_return - inp.ter_direct)
        reg = dir_ = inp.lump_sum
        invested = inp.lump_sum
        series = [
            EstimatePoint(
                year=0, invested=_paise(invested), regular=_paise(reg), direct=_paise(dir_)
            )
        ]
        first_year_gap = ZERO
        for month in range(1, inp.years * 12 + 1):
            reg += inp.monthly_sip
            dir_ += inp.monthly_sip
            invested += inp.monthly_sip
            if month <= 12:
                first_year_gap += reg * (inp.ter_regular - inp.ter_direct) / 12
            reg *= 1 + r_reg
            dir_ *= 1 + r_dir
            if month % 12 == 0:
                series.append(
                    EstimatePoint(
                        year=month // 12,
                        invested=_paise(invested),
                        regular=_paise(reg),
                        direct=_paise(dir_),
                    )
                )
        leak = max(dir_ - reg, ZERO)
        return Estimate(
            years=inp.years,
            invested=_paise(invested),
            regular_value=_paise(reg),
            direct_value=_paise(dir_),
            leak=_paise(leak),
            leak_share=(leak / dir_).quantize(Decimal("0.0001")) if dir_ > 0 else ZERO,
            first_year_fees_gap=_paise(first_year_gap),
            series=tuple(series),
        )
