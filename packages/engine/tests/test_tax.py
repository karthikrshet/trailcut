from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trailcut_engine.lots import Lot
from trailcut_engine.portfolio import AssetClass, TxnKind
from trailcut_engine.tax import (
    GainBuckets,
    TaxRegime,
    is_grandfathered,
    lock_in_until,
    long_term_from,
    lot_gain,
    regime_on,
    tax_on_gains,
)
from trailcut_engine.tax_rules import TaxRules, parse_tax_rules

D = Decimal
RULES: TaxRules = parse_tax_rules(
    (Path(__file__).resolve().parents[3] / "data" / "tax_rules" / "fy2026_27.yaml").read_text(
        encoding="utf-8"
    )
)
SLAB = D("0.30")
E, DEBT, HYB, UNK = AssetClass.EQUITY, AssetClass.DEBT, AssetClass.HYBRID, AssetClass.UNKNOWN


def lot(bought: date, units: str = "10", cost: str = "1000") -> Lot:
    return Lot(
        lot_id="F1-S1-L001",
        scheme_id="F1-S1",
        buy_date=bought,
        units=D(units),
        cost=D(cost),
        source=TxnKind.PURCHASE,
    )


# ---------- regime: equity 12-month boundary ----------


@pytest.mark.parametrize(
    ("bought", "sold", "expected"),
    [
        (date(2025, 1, 10), date(2025, 1, 10), TaxRegime.EQUITY_STCG),
        (date(2025, 1, 10), date(2025, 12, 31), TaxRegime.EQUITY_STCG),
        (date(2025, 1, 10), date(2026, 1, 9), TaxRegime.EQUITY_STCG),
        (date(2025, 1, 10), date(2026, 1, 10), TaxRegime.EQUITY_STCG),
        (date(2025, 1, 10), date(2026, 1, 11), TaxRegime.EQUITY_LTCG),
        (date(2024, 2, 29), date(2025, 2, 28), TaxRegime.EQUITY_STCG),
        (date(2024, 2, 29), date(2025, 3, 1), TaxRegime.EQUITY_LTCG),
        (date(2016, 1, 5), date(2026, 11, 20), TaxRegime.EQUITY_LTCG),
        (date(2025, 12, 15), date(2026, 12, 15), TaxRegime.EQUITY_STCG),
        (date(2025, 12, 15), date(2026, 12, 16), TaxRegime.EQUITY_LTCG),
    ],
)
def test_equity_regime(bought: date, sold: date, expected: TaxRegime) -> None:
    assert regime_on(bought, sold, E, RULES) is expected


# ---------- regime: debt / hybrid / unknown ----------


@pytest.mark.parametrize("asset", [DEBT, HYB, UNK])
@pytest.mark.parametrize(
    ("bought", "sold", "expected"),
    [
        # On/after 1 Apr 2023: always slab, however long held.
        (date(2023, 4, 1), date(2030, 1, 1), TaxRegime.SLAB),
        (date(2024, 2, 15), date(2026, 11, 20), TaxRegime.SLAB),
        # Before 1 Apr 2023: long term after 24 months.
        (date(2023, 3, 31), date(2025, 3, 31), TaxRegime.SLAB),
        (date(2023, 3, 31), date(2025, 4, 1), TaxRegime.OTHER_LTCG),
        (date(2021, 8, 10), date(2023, 8, 10), TaxRegime.SLAB),
        (date(2021, 8, 10), date(2023, 8, 11), TaxRegime.OTHER_LTCG),
        (date(2021, 8, 10), date(2026, 11, 20), TaxRegime.OTHER_LTCG),
        (date(2022, 12, 1), date(2023, 12, 1), TaxRegime.SLAB),
    ],
)
def test_non_equity_regime(
    asset: AssetClass, bought: date, sold: date, expected: TaxRegime
) -> None:
    assert regime_on(bought, sold, asset, RULES) is expected


@pytest.mark.parametrize(
    ("bought", "asset", "expected"),
    [
        (date(2025, 12, 15), E, date(2026, 12, 16)),
        (date(2025, 1, 31), E, date(2026, 2, 1)),
        (date(2024, 2, 29), E, date(2025, 3, 1)),
        (date(2021, 8, 10), DEBT, date(2023, 8, 11)),
        (date(2023, 3, 31), HYB, date(2025, 4, 1)),
        (date(2023, 4, 1), DEBT, None),
        (date(2024, 2, 15), UNK, None),
    ],
)
def test_long_term_from(bought: date, asset: AssetClass, expected: date | None) -> None:
    assert long_term_from(bought, asset, RULES) == expected


@pytest.mark.property
@given(
    bought=st.dates(date(2010, 1, 1), date(2030, 12, 31)), asset=st.sampled_from(list(AssetClass))
)
def test_long_term_from_is_the_regime_boundary(bought: date, asset: AssetClass) -> None:
    first = long_term_from(bought, asset, RULES)
    if first is None:
        assert regime_on(bought, bought + timedelta(days=10000), asset, RULES) is TaxRegime.SLAB
    else:
        assert regime_on(bought, first, asset, RULES) in {
            TaxRegime.EQUITY_LTCG,
            TaxRegime.OTHER_LTCG,
        }
        assert regime_on(bought, first - timedelta(days=1), asset, RULES) in {
            TaxRegime.EQUITY_STCG,
            TaxRegime.SLAB,
        }


# ---------- ELSS lock-in and grandfathering ----------


@pytest.mark.parametrize(
    ("bought", "elss", "expected"),
    [
        (date(2023, 6, 10), True, date(2026, 6, 10)),
        (date(2024, 2, 29), True, date(2027, 2, 28)),
        (date(2026, 11, 10), True, date(2029, 11, 10)),
        (date(2023, 6, 10), False, None),
    ],
)
def test_lock_in_until(bought: date, elss: bool, expected: date | None) -> None:
    assert lock_in_until(bought, elss, RULES) == expected


@pytest.mark.parametrize(
    ("bought", "asset", "expected"),
    [
        (date(2018, 1, 31), E, True),
        (date(2018, 2, 1), E, False),
        (date(2016, 1, 5), E, True),
        (date(2016, 1, 5), DEBT, False),
        (date(2016, 1, 5), HYB, False),
    ],
)
def test_is_grandfathered(bought: date, asset: AssetClass, expected: bool) -> None:
    assert is_grandfathered(bought, asset, RULES) is expected


# ---------- lot gains ----------


def test_plain_gain() -> None:
    g = lot_gain(lot(date(2024, 1, 1)), date(2026, 1, 1), D(1500), E, RULES)
    assert (g.regime, g.gain, g.cost_used, g.grandfathered) == (
        TaxRegime.EQUITY_LTCG,
        D(500),
        D(1000),
        False,
    )


def test_loss() -> None:
    g = lot_gain(lot(date(2026, 1, 1)), date(2026, 6, 1), D(800), E, RULES)
    assert (g.regime, g.gain) == (TaxRegime.EQUITY_STCG, D(-200))


@pytest.mark.parametrize(
    ("cost", "fmv", "sale", "cost_used", "grandfathered"),
    [
        # FMV between cost and sale: FMV becomes the cost.
        ("1000", "150", "2000", "1500", True),
        # FMV above sale value: capped at the sale value (no artificial loss).
        ("1000", "300", "2000", "2000", True),
        # FMV below actual cost: actual cost wins.
        ("1000", "50", "2000", "1000", False),
        # Sale below actual cost: loss on actual cost.
        ("1000", "150", "900", "1000", False),
    ],
)
def test_grandfathering(
    cost: str, fmv: str, sale: str, cost_used: str, grandfathered: bool
) -> None:
    g = lot_gain(
        lot(date(2017, 6, 1), cost=cost),
        date(2026, 11, 20),
        D(sale),
        E,
        RULES,
        fmv_2018_per_unit=D(fmv),
    )
    assert g.cost_used == D(cost_used)
    assert g.grandfathered is grandfathered
    assert g.gain == D(sale) - D(cost_used)


def test_grandfathering_needs_fmv() -> None:
    g = lot_gain(lot(date(2017, 6, 1)), date(2026, 11, 20), D(2000), E, RULES)
    assert g.cost_used == D(1000)
    assert not g.grandfathered


def test_grandfathering_not_for_units_after_cutoff() -> None:
    g = lot_gain(
        lot(date(2018, 2, 1)), date(2026, 11, 20), D(2000), E, RULES, fmv_2018_per_unit=D(150)
    )
    assert g.cost_used == D(1000)


def test_grandfathering_not_for_debt() -> None:
    g = lot_gain(
        lot(date(2017, 6, 1)), date(2026, 11, 20), D(2000), DEBT, RULES, fmv_2018_per_unit=D(150)
    )
    assert (g.regime, g.cost_used) == (TaxRegime.OTHER_LTCG, D(1000))


# ---------- buckets ----------


def test_buckets_from_gains_and_addition() -> None:
    gains = [
        lot_gain(lot(date(2024, 1, 1)), date(2026, 1, 1), D(1500), E, RULES),
        lot_gain(lot(date(2026, 1, 1)), date(2026, 6, 1), D(800), E, RULES),
        lot_gain(lot(date(2024, 1, 1)), date(2026, 1, 1), D(1100), DEBT, RULES),
    ]
    b = GainBuckets.from_gains(gains)
    assert (b.equity_ltcg, b.equity_stcg, b.slab, b.other_ltcg) == (D(500), D(-200), D(100), D(0))
    assert (b + b).equity_ltcg == D(1000)


# ---------- tax on gains: golden cases ----------


@pytest.mark.parametrize(
    ("buckets", "expected_total"),
    [
        (GainBuckets(), "0"),
        # LTCG under the exemption: no tax.
        (GainBuckets(equity_ltcg=D(125000)), "0"),
        (GainBuckets(equity_ltcg=D(100000)), "0"),
        # 2 lakh LTCG: 75,000 taxable at 12.5% = 9,375 + 4% cess = 9,750.
        (GainBuckets(equity_ltcg=D(200000)), "9750"),
        # STCG 1 lakh at 20% = 20,000 + cess = 20,800.
        (GainBuckets(equity_stcg=D(100000)), "20800"),
        # Slab 1 lakh at 30% = 30,000 + cess = 31,200.
        (GainBuckets(slab=D(100000)), "31200"),
        # Other LTCG 1 lakh at 12.5% (no exemption) = 12,500 + cess = 13,000.
        (GainBuckets(other_ltcg=D(100000)), "13000"),
    ],
)
def test_tax_golden(buckets: GainBuckets, expected_total: str) -> None:
    assert tax_on_gains(buckets, RULES, slab_rate=SLAB).total == D(expected_total)


def test_exemption_used_is_reported() -> None:
    t = tax_on_gains(GainBuckets(equity_ltcg=D(200000)), RULES, slab_rate=SLAB)
    assert t.exemption_used == D(125000)
    assert t.taxable_equity_ltcg == D(75000)
    assert t.cess == D("375.000")


@pytest.mark.parametrize(
    ("available", "taxable"), [("0", "200000"), ("25000", "175000"), ("-5", "200000")]
)
def test_partial_exemption(available: str, taxable: str) -> None:
    t = tax_on_gains(
        GainBuckets(equity_ltcg=D(200000)), RULES, slab_rate=SLAB, exemption_available=D(available)
    )
    assert t.taxable_equity_ltcg == D(taxable)


# ---------- set-off ----------


def test_short_term_loss_offsets_highest_rate_short_term_gain_first() -> None:
    t = tax_on_gains(
        GainBuckets(equity_stcg=D(-50000), slab=D(80000), equity_ltcg=D(0)), RULES, slab_rate=SLAB
    )
    assert t.taxable_slab == D(30000)
    t2 = tax_on_gains(GainBuckets(slab=D(-50000), equity_stcg=D(80000)), RULES, slab_rate=D("0.05"))
    assert t2.taxable_equity_stcg == D(30000)


def test_short_term_loss_spills_to_long_term_gains_non_exempt_first() -> None:
    t = tax_on_gains(
        GainBuckets(equity_stcg=D(-100000), other_ltcg=D(60000), equity_ltcg=D(200000)),
        RULES,
        slab_rate=SLAB,
    )
    assert t.taxable_other_ltcg == 0
    assert t.taxable_equity_ltcg == D(200000 - 40000 - 125000)


def test_long_term_loss_cannot_offset_short_term_gain() -> None:
    t = tax_on_gains(
        GainBuckets(equity_ltcg=D(-100000), equity_stcg=D(100000)), RULES, slab_rate=SLAB
    )
    assert t.taxable_equity_stcg == D(100000)
    assert t.unused_long_term_loss == D(100000)


def test_long_term_loss_offsets_other_ltcg_before_equity_ltcg() -> None:
    t = tax_on_gains(
        GainBuckets(other_ltcg=D(-30000), equity_ltcg=D(300000)), RULES, slab_rate=SLAB
    )
    # A long-term loss in one bucket offsets long-term gains in the other.
    assert t.taxable_equity_ltcg == D(300000 - 30000 - 125000)
    t2 = tax_on_gains(
        GainBuckets(equity_ltcg=D(-30000), other_ltcg=D(50000)), RULES, slab_rate=SLAB
    )
    assert t2.taxable_other_ltcg == D(20000)


def test_unused_losses_are_reported() -> None:
    t = tax_on_gains(GainBuckets(equity_stcg=D(-10000)), RULES, slab_rate=SLAB)
    assert t.total == 0
    assert t.unused_short_term_loss == D(10000)


@pytest.mark.parametrize("slab", ["0", "0.05", "0.20", "0.30"])
def test_zero_slab_rate_has_no_slab_tax(slab: str) -> None:
    t = tax_on_gains(GainBuckets(slab=D(100000)), RULES, slab_rate=D(slab))
    assert t.tax_before_cess == D(100000) * D(slab)


# ---------- properties ----------

amounts = st.decimals(min_value=D(-1000000), max_value=D(1000000), places=2)
slabs = st.sampled_from([D(0), D("0.05"), D("0.1"), D("0.2"), D("0.3")])


@pytest.mark.property
@given(es=amounts, el=amounts, ol=amounts, sl=amounts, slab=slabs)
def test_tax_is_never_negative_and_bounded(
    es: Decimal, el: Decimal, ol: Decimal, sl: Decimal, slab: Decimal
) -> None:
    b = GainBuckets(equity_stcg=es, equity_ltcg=el, other_ltcg=ol, slab=sl)
    t = tax_on_gains(b, RULES, slab_rate=slab)
    assert t.total >= 0
    positive = sum((max(v, D(0)) for v in (es, el, ol, sl)), D(0))
    assert t.total <= positive * max(slab, D("0.2")) * D("1.04") + D("0.01")


@pytest.mark.property
@given(es=amounts, el=amounts, ol=amounts, sl=amounts, extra=st.decimals(D(0), D(100000), places=2))
def test_more_gain_never_means_less_tax(
    es: Decimal, el: Decimal, ol: Decimal, sl: Decimal, extra: Decimal
) -> None:
    base = GainBuckets(equity_stcg=es, equity_ltcg=el, other_ltcg=ol, slab=sl)
    for field in ("equity_stcg", "equity_ltcg", "other_ltcg", "slab"):
        bigger = base.model_copy(update={field: getattr(base, field) + extra})
        assert (
            tax_on_gains(bigger, RULES, slab_rate=SLAB).total
            >= tax_on_gains(base, RULES, slab_rate=SLAB).total
        )


@pytest.mark.property
@given(el=st.decimals(D(0), D(2000000), places=2))
def test_exemption_never_exceeds_limit_or_gain(el: Decimal) -> None:
    t = tax_on_gains(GainBuckets(equity_ltcg=el), RULES, slab_rate=SLAB)
    assert t.exemption_used <= RULES.equity.ltcg_exemption_per_fy.value
    assert t.exemption_used <= el
