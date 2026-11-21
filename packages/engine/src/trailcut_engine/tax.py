"""Capital-gains classification and tax for mutual fund lots.

Every rate, threshold and date comes from a :class:`TaxRules` argument
(``data/tax_rules/*.yaml``). Nothing here hardcodes a tax figure.

Example:
    >>> regime_on(date(2025, 1, 10), date(2026, 1, 11), AssetClass.EQUITY, rules)
    <TaxRegime.EQUITY_LTCG: 'equity_ltcg'>
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from trailcut_engine.dates import add_years, first_day_more_than, held_more_than_months
from trailcut_engine.lots import Lot
from trailcut_engine.portfolio import AssetClass
from trailcut_engine.tax_rules import TaxRules
from trailcut_engine.types import DecimalField

ZERO = Decimal(0)


class TaxRegime(StrEnum):
    """How a gain is taxed."""

    EQUITY_STCG = "equity_stcg"
    """Equity held 12 months or less: flat STCG rate."""
    EQUITY_LTCG = "equity_ltcg"
    """Equity held more than 12 months: LTCG rate above the yearly exemption."""
    OTHER_LTCG = "other_ltcg"
    """Non-equity bought before the specified-fund cutoff, held long term."""
    SLAB = "slab"
    """Taxed at the investor's income-tax slab rate."""


def _equity_like(asset_class: AssetClass) -> bool:
    return asset_class is AssetClass.EQUITY


def regime_on(bought: date, sold: date, asset_class: AssetClass, rules: TaxRules) -> TaxRegime:
    """Tax regime for units bought on ``bought`` if sold on ``sold``.

    Hybrid and unknown funds are taxed like debt (the conservative choice, so a
    plan never understates tax); the UI flags them for the user to confirm.
    """
    if _equity_like(asset_class):
        months = rules.equity.long_term_after_months.value
        return (
            TaxRegime.EQUITY_LTCG
            if held_more_than_months(bought, sold, months)
            else TaxRegime.EQUITY_STCG
        )
    if bought >= rules.debt.specified_fund_cutoff_date.value:
        return TaxRegime.SLAB
    months = rules.debt.legacy_long_term_after_months.value
    return TaxRegime.OTHER_LTCG if held_more_than_months(bought, sold, months) else TaxRegime.SLAB


def long_term_from(bought: date, asset_class: AssetClass, rules: TaxRules) -> date | None:
    """First sale date taxed as long term, or ``None`` if it never will be.

    Example:
        >>> long_term_from(date(2025, 12, 15), AssetClass.EQUITY, rules)
        datetime.date(2026, 12, 16)
    """
    if _equity_like(asset_class):
        return first_day_more_than(bought, rules.equity.long_term_after_months.value)
    if bought >= rules.debt.specified_fund_cutoff_date.value:
        return None
    return first_day_more_than(bought, rules.debt.legacy_long_term_after_months.value)


def lock_in_until(bought: date, is_elss: bool, rules: TaxRules) -> date | None:
    """First date an ELSS lot may be redeemed (``None`` if not locked).

    Example:
        >>> lock_in_until(date(2023, 6, 10), True, rules)
        datetime.date(2026, 6, 10)
    """
    if not is_elss:
        return None
    return add_years(bought, rules.equity.elss_lock_in_years.value)


def is_grandfathered(bought: date, asset_class: AssetClass, rules: TaxRules) -> bool:
    """True for equity units bought on or before the 31 Jan 2018 FMV date."""
    return _equity_like(asset_class) and bought <= rules.equity.grandfathering_fmv_date.value


class LotGain(BaseModel):
    """The gain if (part of) a lot is sold for ``sale_value`` on ``sold``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lot_id: str
    regime: TaxRegime
    units: DecimalField
    sale_value: DecimalField
    cost_used: DecimalField
    gain: DecimalField
    grandfathered: bool
    """True if the 31 Jan 2018 FMV raised the cost used."""


def lot_gain(
    lot: Lot,
    sold: date,
    sale_value: Decimal,
    asset_class: AssetClass,
    rules: TaxRules,
    *,
    fmv_2018_per_unit: Decimal | None = None,
) -> LotGain:
    """Gain on selling the whole ``lot`` for ``sale_value`` (net of exit load).

    For equity bought on or before 31 Jan 2018 and sold long term, the cost is
    ``max(actual cost, min(FMV on 31 Jan 2018, sale value))`` (grandfathering).
    Without an FMV the actual cost is used, which can only overstate tax.
    """
    regime = regime_on(lot.buy_date, sold, asset_class, rules)
    cost = lot.cost
    grandfathered = False
    if (
        regime is TaxRegime.EQUITY_LTCG
        and fmv_2018_per_unit is not None
        and is_grandfathered(lot.buy_date, asset_class, rules)
    ):
        fmv_cost = min(fmv_2018_per_unit * lot.units, sale_value)
        if fmv_cost > cost:
            cost, grandfathered = fmv_cost, True
    return LotGain(
        lot_id=lot.lot_id,
        regime=regime,
        units=lot.units,
        sale_value=sale_value,
        cost_used=cost,
        gain=sale_value - cost,
        grandfathered=grandfathered,
    )


class GainBuckets(BaseModel):
    """Net gains (negative = loss) per regime within one financial year."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    equity_stcg: DecimalField = ZERO
    equity_ltcg: DecimalField = ZERO
    other_ltcg: DecimalField = ZERO
    slab: DecimalField = ZERO

    @classmethod
    def from_gains(cls, gains: list[LotGain] | tuple[LotGain, ...]) -> GainBuckets:
        """Sum lot gains into buckets."""
        totals = dict.fromkeys(TaxRegime, ZERO)
        for g in gains:
            totals[g.regime] += g.gain
        return cls(
            equity_stcg=totals[TaxRegime.EQUITY_STCG],
            equity_ltcg=totals[TaxRegime.EQUITY_LTCG],
            other_ltcg=totals[TaxRegime.OTHER_LTCG],
            slab=totals[TaxRegime.SLAB],
        )

    def __add__(self, other: GainBuckets) -> GainBuckets:
        return GainBuckets(
            equity_stcg=self.equity_stcg + other.equity_stcg,
            equity_ltcg=self.equity_ltcg + other.equity_ltcg,
            other_ltcg=self.other_ltcg + other.other_ltcg,
            slab=self.slab + other.slab,
        )


Fraction = Annotated[DecimalField, Field(ge=0, le=1)]


class TaxBreakdown(BaseModel):
    """Tax on one financial year's gains after set-off and the LTCG exemption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    taxable_equity_stcg: DecimalField
    taxable_equity_ltcg: DecimalField
    taxable_other_ltcg: DecimalField
    taxable_slab: DecimalField
    exemption_used: DecimalField
    tax_before_cess: DecimalField
    cess: DecimalField
    total: DecimalField
    unused_short_term_loss: DecimalField
    unused_long_term_loss: DecimalField


def _absorb(loss: Decimal, gain: Decimal) -> tuple[Decimal, Decimal]:
    used = min(loss, gain)
    return loss - used, gain - used


def tax_on_gains(
    buckets: GainBuckets,
    rules: TaxRules,
    *,
    slab_rate: Decimal,
    exemption_available: Decimal | None = None,
) -> TaxBreakdown:
    """Tax for one financial year's gains.

    Set-off follows the Income-tax Act: short-term losses can absorb any gain,
    long-term losses only long-term gains. Losses are applied to the highest-taxed
    gains first, and to exemption-eligible equity LTCG last, which minimises tax.
    Surcharge is not modelled (assumes total income under Rs 50 lakh).

    Example:
        >>> tax_on_gains(GainBuckets(equity_ltcg=Decimal(200000)), rules,
        ...              slab_rate=Decimal("0.3")).total
        Decimal('9750.00000')
    """
    stcg_rate = rules.equity.stcg_rate.value
    ltcg_rate = rules.equity.ltcg_rate.value
    other_rate = rules.debt.legacy_ltcg_rate.value
    if exemption_available is None:
        exemption_available = rules.equity.ltcg_exemption_per_fy.value

    es, sl, el, ol = (
        max(v, ZERO)
        for v in (buckets.equity_stcg, buckets.slab, buckets.equity_ltcg, buckets.other_ltcg)
    )
    st_loss = -min(buckets.equity_stcg, ZERO) - min(buckets.slab, ZERO)
    lt_loss = -min(buckets.equity_ltcg, ZERO) - min(buckets.other_ltcg, ZERO)

    # Long-term losses: other LTCG first (no exemption), then equity LTCG.
    lt_loss, ol = _absorb(lt_loss, ol)
    lt_loss, el = _absorb(lt_loss, el)
    # Short-term losses: highest-rate short-term gains first, then long-term.
    if slab_rate >= stcg_rate:
        st_loss, sl = _absorb(st_loss, sl)
        st_loss, es = _absorb(st_loss, es)
    else:
        st_loss, es = _absorb(st_loss, es)
        st_loss, sl = _absorb(st_loss, sl)
    st_loss, ol = _absorb(st_loss, ol)
    st_loss, el = _absorb(st_loss, el)

    exemption = min(el, max(exemption_available, ZERO))
    taxable_el = el - exemption
    tax = es * stcg_rate + sl * slab_rate + taxable_el * ltcg_rate + ol * other_rate
    cess = tax * rules.surcharge_and_cess.health_education_cess_rate.value
    return TaxBreakdown(
        taxable_equity_stcg=es,
        taxable_equity_ltcg=taxable_el,
        taxable_other_ltcg=ol,
        taxable_slab=sl,
        exemption_used=exemption,
        tax_before_cess=tax,
        cess=cess,
        total=tax + cess,
        unused_short_term_loss=st_loss,
        unused_long_term_loss=lt_loss,
    )
