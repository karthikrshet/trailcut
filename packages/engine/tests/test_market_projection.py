from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from trailcut_engine.market import (
    NO_EXIT_LOAD,
    ExitLoadRule,
    ExitLoadTier,
    MarketData,
    SchemeMarket,
)
from trailcut_engine.projection import (
    break_even_months,
    commission_leak,
    grow,
    growth_series,
    switch_net_benefit,
)

D = Decimal
ONE_YEAR = ExitLoadRule(tiers=(ExitLoadTier(within_days=365, rate=D("0.01")),))
GRADED = ExitLoadRule(
    tiers=(
        ExitLoadTier(within_days=30, rate=D("0.02")),
        ExitLoadTier(within_days=180, rate=D("0.01")),
        ExitLoadTier(within_days=365, rate=D("0.005")),
    )
)
B = date(2025, 12, 15)

# ---------- exit loads ----------


@pytest.mark.parametrize(
    ("days", "rate"),
    [(0, "0.01"), (1, "0.01"), (364, "0.01"), (365, "0.01"), (366, "0"), (1000, "0")],
)
def test_one_year_exit_load_window(days: int, rate: str) -> None:
    assert ONE_YEAR.rate_on(B, B + timedelta(days=days)) == D(rate)


@pytest.mark.parametrize(
    ("days", "rate"),
    [
        (0, "0.02"),
        (30, "0.02"),
        (31, "0.01"),
        (180, "0.01"),
        (181, "0.005"),
        (365, "0.005"),
        (366, "0"),
    ],
)
def test_graded_exit_load(days: int, rate: str) -> None:
    assert GRADED.rate_on(B, B + timedelta(days=days)) == D(rate)


@pytest.mark.parametrize(
    ("rule", "expected"),
    [(ONE_YEAR, date(2026, 12, 16)), (GRADED, date(2026, 12, 16)), (NO_EXIT_LOAD, B)],
)
def test_free_from(rule: ExitLoadRule, expected: date) -> None:
    assert rule.free_from(B) == expected


def test_free_from_ignores_zero_rate_tiers() -> None:
    rule = ExitLoadRule(
        tiers=(
            ExitLoadTier(within_days=7, rate=D("0.001")),
            ExitLoadTier(within_days=365, rate=D(0)),
        )
    )
    assert rule.free_from(B) == B + timedelta(days=8)


def test_no_exit_load_is_zero() -> None:
    assert NO_EXIT_LOAD.rate_on(B, B) == 0


@pytest.mark.parametrize(
    "tiers",
    [
        (
            ExitLoadTier(within_days=365, rate=D("0.01")),
            ExitLoadTier(within_days=30, rate=D("0.02")),
        ),
        (
            ExitLoadTier(within_days=30, rate=D("0.01")),
            ExitLoadTier(within_days=30, rate=D("0.02")),
        ),
    ],
)
def test_tiers_must_increase(tiers: tuple[ExitLoadTier, ...]) -> None:
    with pytest.raises(ValidationError, match="increasing"):
        ExitLoadRule(tiers=tiers)


@pytest.mark.parametrize(
    ("rate", "days"), [("1.5", 30), ("-0.01", 30), ("0.01", -1), ("0.01", 4000)]
)
def test_tier_bounds(rate: str, days: int) -> None:
    with pytest.raises(ValidationError):
        ExitLoadTier(within_days=days, rate=D(rate))


@pytest.mark.property
@given(bought=st.dates(date(2015, 1, 1), date(2030, 1, 1)), extra=st.integers(0, 2000))
def test_free_from_is_load_free_and_day_before_is_not(bought: date, extra: int) -> None:
    free = ONE_YEAR.free_from(bought)
    assert ONE_YEAR.rate_on(bought, free + timedelta(days=extra)) == 0
    assert ONE_YEAR.rate_on(bought, free - timedelta(days=1)) > 0


# ---------- market data ----------


@pytest.mark.parametrize(
    ("regular", "direct", "gap"),
    [
        ("0.0175", "0.0075", "0.0100"),
        ("0.01", "0.01", "0"),
        ("0.005", "0.01", "0"),
        (None, "0.01", None),
        ("0.01", None, None),
    ],
)
def test_ter_gap(regular: str | None, direct: str | None, gap: str | None) -> None:
    m = SchemeMarket(
        ter_regular=None if regular is None else D(regular),
        ter_direct=None if direct is None else D(direct),
    )
    assert m.ter_gap == (None if gap is None else D(gap))


def test_market_lookup_defaults_to_unknown() -> None:
    md = MarketData(schemes={"F1-S1": SchemeMarket(ter_regular=D("0.02"))})
    assert md.for_scheme("F1-S1").ter_regular == D("0.02")
    assert md.for_scheme("F9-S9") == SchemeMarket()


@pytest.mark.parametrize("field", ["ter_regular", "ter_direct"])
def test_ter_rejects_float_and_out_of_range(field: str) -> None:
    with pytest.raises(ValidationError):
        SchemeMarket(**{field: 0.01})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        SchemeMarket(**{field: D("1.5")})  # type: ignore[arg-type]


def test_fmv_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SchemeMarket(fmv_2018_per_unit=D(0))


# ---------- projections ----------


@pytest.mark.parametrize(
    ("value", "rate", "years", "expected"),
    [
        ("1000", "0.10", 1, "1100.00"),
        ("1000", "0.10", 2, "1210.00"),
        ("1000", "0", 5, "1000.00"),
        ("0", "0.1", 3, "0"),
        ("1000", "-0.5", 1, "500.00"),
        ("1000", "0.10", 0, "1000.00"),
    ],
)
def test_grow(value: str, rate: str, years: int, expected: str) -> None:
    assert grow(D(value), D(rate), years) == D(expected)


def test_grow_fractional_years() -> None:
    assert grow(D(1000), D("0.21"), D("0.5")) == D("1100.00")


def test_commission_leak_golden() -> None:
    leak = commission_leak(D(100000), D("0.02"), D("0.01"), D("0.12"), years=10)
    assert leak.yearly_now == D("1000.00")
    assert leak.regular_value == grow(D(100000), D("0.10"), 10)
    assert leak.direct_value == grow(D(100000), D("0.11"), 10)
    assert leak.leak == leak.direct_value - leak.regular_value
    # 1.11^10 x 1L = 2,83,942.10 and 1.10^10 x 1L = 2,59,374.25.
    assert (leak.direct_value, leak.regular_value) == (D("283942.10"), D("259374.25"))
    assert leak.leak == D("24567.85")


def test_no_gap_means_no_leak() -> None:
    leak = commission_leak(D(100000), D("0.01"), D("0.01"), D("0.12"), years=20)
    assert (leak.yearly_now, leak.leak) == (D(0), D(0))


def test_growth_series_shape() -> None:
    series = growth_series(D(100000), D("0.02"), D("0.01"), D("0.12"), years=20)
    assert [p.year for p in series] == list(range(21))
    assert series[0].regular == series[0].direct == D("100000.00")
    assert all(p.direct >= p.regular for p in series)
    assert (
        series[-1].direct - series[-1].regular
        == commission_leak(D(100000), D("0.02"), D("0.01"), D("0.12"), years=20).leak
    )


def test_switch_net_benefit_free_switch_equals_leak() -> None:
    args = (D(100000), D(0), D("0.02"), D("0.01"), D("0.12"))
    assert (
        switch_net_benefit(*args, years=10)
        == commission_leak(D(100000), D("0.02"), D("0.01"), D("0.12"), years=10).leak
    )


def test_switch_net_benefit_negative_when_cost_too_high() -> None:
    assert switch_net_benefit(D(100000), D(20000), D("0.02"), D("0.01"), D("0.12"), years=5) < 0


@pytest.mark.parametrize(
    ("cost", "expected"),
    [("0", 0), ("-5", 0), ("1000", 14), ("100", 2), ("100000", None), ("200000", None)],
)
def test_break_even_months(cost: str, expected: int | None) -> None:
    assert break_even_months(D(100000), D(cost), D("0.02"), D("0.01"), D("0.12")) == expected


def test_break_even_none_without_gap() -> None:
    assert break_even_months(D(100000), D(100), D("0.01"), D("0.01"), D("0.12")) is None


@pytest.mark.property
@given(
    value=st.decimals(D(1000), D(10000000), places=2),
    cost_share=st.decimals(D("0.0001"), D("0.2"), places=4),
    gap=st.decimals(D("0.001"), D("0.02"), places=4),
)
def test_break_even_is_where_benefit_turns_positive(
    value: Decimal, cost_share: Decimal, gap: Decimal
) -> None:
    cost = (value * cost_share).quantize(D("0.01"))
    months = break_even_months(value, cost, D("0.01") + gap, D("0.01"), D("0.12"))
    assert months is not None
    assert months > 0

    def benefit(m: int) -> Decimal:
        y = D(m) / 12
        return grow(value - cost, D("0.11"), y) - grow(value, D("0.11") - gap, y)

    assert benefit(months) >= D("-0.02")  # paise rounding
    if months > 1:
        assert benefit(months - 1) <= D("0.02")


@pytest.mark.property
@given(
    value=st.decimals(D(1), D(10**8), places=2),
    gap=st.decimals(D(0), D("0.03"), places=4),
    years=st.integers(0, 30),
)
def test_leak_is_non_negative_and_grows_with_gap(value: Decimal, gap: Decimal, years: int) -> None:
    small = commission_leak(value, D("0.005") + gap, D("0.005"), D("0.12"), years=years)
    big = commission_leak(value, D("0.006") + gap, D("0.005"), D("0.12"), years=years)
    assert small.leak >= 0
    assert big.leak >= small.leak
