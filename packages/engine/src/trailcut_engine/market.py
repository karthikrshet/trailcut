"""Market inputs the engine needs per scheme: expense ratios, exit loads, FMV.

These are data, not tax rules. Every value carries its source and date so the
report can say "Data as of ...". Missing data is ``None`` and is flagged rather
than guessed.

Example:
    >>> rule = ExitLoadRule(tiers=(ExitLoadTier(within_days=365, rate=Decimal("0.01")),))
    >>> rule.rate_on(date(2025, 12, 15), date(2026, 12, 15))
    Decimal('0.01')
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trailcut_engine.types import DecimalField

ZERO = Decimal(0)
Fraction = Annotated[DecimalField, Field(ge=0, le=1)]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExitLoadTier(_Model):
    """``rate`` applies if units are redeemed within ``within_days`` of purchase.

    "Within 365 days" means 365 days or fewer since allotment.
    """

    within_days: Annotated[int, Field(ge=0, le=3650)]
    rate: Fraction


class ExitLoadRule(_Model):
    """An exit-load schedule. Tiers are checked from the shortest window up."""

    tiers: tuple[ExitLoadTier, ...] = ()
    source: str = "assumed"

    @model_validator(mode="after")
    def _sorted(self) -> Self:
        windows = [t.within_days for t in self.tiers]
        if windows != sorted(windows) or len(set(windows)) != len(windows):
            msg = "exit-load tiers must have unique, increasing windows"
            raise ValueError(msg)
        return self

    def rate_on(self, bought: date, sold: date) -> Decimal:
        """Exit-load rate for units bought on ``bought`` and redeemed on ``sold``."""
        held = (sold - bought).days
        for tier in self.tiers:
            if held <= tier.within_days:
                return tier.rate
        return ZERO

    def free_from(self, bought: date) -> date:
        """First redemption date with no exit load.

        Example:
            >>> one_year.free_from(date(2025, 12, 15))  # doctest: +SKIP
            datetime.date(2026, 12, 16)
        """
        charged = [t.within_days for t in self.tiers if t.rate > 0]
        if not charged:
            return bought
        return bought + timedelta(days=max(charged) + 1)


NO_EXIT_LOAD = ExitLoadRule(source="none")


class SchemeMarket(_Model):
    """Market data for one Regular scheme and its Direct counterpart."""

    ter_regular: Fraction | None = None
    """Total expense ratio of the scheme held (yearly, 0.0175 = 1.75%)."""
    ter_direct: Fraction | None = None
    """Expense ratio of the Direct plan of the same scheme."""
    direct_name: str | None = None
    exit_load: ExitLoadRule | None = None
    fmv_2018_per_unit: Annotated[DecimalField, Field(gt=0)] | None = None
    """NAV on 31 Jan 2018, for grandfathering pre-Feb-2018 equity units."""
    source: str = "unknown"
    as_of: date | None = None

    @property
    def ter_gap(self) -> Decimal | None:
        """Yearly cost of staying Regular, or ``None`` if either TER is unknown."""
        if self.ter_regular is None or self.ter_direct is None:
            return None
        return max(self.ter_regular - self.ter_direct, ZERO)


class MarketData(_Model):
    """Market inputs keyed by scheme id (``F1-S1``)."""

    schemes: dict[str, SchemeMarket] = Field(default_factory=dict)
    as_of: date | None = None
    source: str = "unknown"

    def for_scheme(self, scheme_id: str) -> SchemeMarket:
        """Data for a scheme, or an empty record (everything unknown)."""
        return self.schemes.get(scheme_id, SchemeMarket())
