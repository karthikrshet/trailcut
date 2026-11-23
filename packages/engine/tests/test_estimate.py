from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from trailcut_engine.estimate import EstimateInput, estimate_commission
from trailcut_engine.projection import commission_leak

D = Decimal


def test_lump_sum_matches_the_annual_projection() -> None:
    """Monthly compounding at the equivalent rate equals annual compounding."""
    e = estimate_commission(
        EstimateInput(
            lump_sum=D(100000),
            years=10,
            ter_regular=D("0.02"),
            ter_direct=D("0.01"),
            expected_return=D("0.12"),
        )
    )
    annual = commission_leak(D(100000), D("0.02"), D("0.01"), D("0.12"), years=10)
    assert abs(e.regular_value - annual.regular_value) <= D("0.05")
    assert abs(e.direct_value - annual.direct_value) <= D("0.05")
    assert abs(e.leak - annual.leak) <= D("0.10")


def test_sip_only() -> None:
    e = estimate_commission(EstimateInput(monthly_sip=D(10000), years=10))
    assert e.invested == D(1200000)
    assert e.direct_value > e.regular_value > e.invested
    assert e.leak == e.direct_value - e.regular_value
    assert [p.year for p in e.series] == list(range(11))
    assert e.series[0].invested == 0
    assert e.series[-1].invested == D(1200000)


def test_lump_sum_plus_sip_series_is_monotonic() -> None:
    e = estimate_commission(EstimateInput(lump_sum=D(200000), monthly_sip=D(5000), years=20))
    regs = [p.regular for p in e.series]
    gaps = [p.direct - p.regular for p in e.series]
    assert regs == sorted(regs)
    assert gaps == sorted(gaps)
    assert e.series[0].regular == e.series[0].direct == D(200000)


def test_equal_expense_ratios_mean_no_leak() -> None:
    e = estimate_commission(
        EstimateInput(lump_sum=D(100000), ter_regular=D("0.01"), ter_direct=D("0.01"))
    )
    assert (e.leak, e.leak_share, e.first_year_fees_gap) == (D(0), D(0), D(0))


def test_first_year_fees_gap_for_a_lump_sum() -> None:
    e = estimate_commission(
        EstimateInput(
            lump_sum=D(100000), ter_regular=D("0.02"), ter_direct=D("0.01"), expected_return=D(0)
        )
    )
    # Value shrinks slightly each month at -2% a year, so the gap is just under 1,000.
    assert D(980) < e.first_year_fees_gap < D(1000)


def test_leak_share() -> None:
    e = estimate_commission(EstimateInput(lump_sum=D(100000), years=20))
    assert e.leak_share == (e.leak / e.direct_value).quantize(D("0.0001"))


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({}, "lump sum, a monthly SIP"),
        ({"lump_sum": D(1), "ter_direct": D("0.02"), "ter_regular": D("0.01")}, "can't be higher"),
        ({"lump_sum": D(-1)}, "lump_sum"),
        ({"lump_sum": D(1), "years": 0}, "years"),
        ({"lump_sum": D(1), "years": 41}, "years"),
        ({"lump_sum": D(1), "ter_regular": D("0.06")}, "ter_regular"),
        ({"lump_sum": 1000.5}, "floats"),
    ],
)
def test_invalid_input(fields: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        EstimateInput(**fields)  # type: ignore[arg-type]


@pytest.mark.property
@given(
    lump=st.integers(0, 10**7),
    sip=st.integers(0, 10**5),
    years=st.integers(1, 30),
    gap_bps=st.integers(0, 200),
)
def test_more_expensive_regular_never_beats_direct(
    lump: int, sip: int, years: int, gap_bps: int
) -> None:
    if lump == 0 and sip == 0:
        lump = 1000
    inp = EstimateInput(
        lump_sum=D(lump),
        monthly_sip=D(sip),
        years=years,
        ter_direct=D("0.005"),
        ter_regular=D("0.005") + D(gap_bps) / 10000,
    )
    e = estimate_commission(inp)
    assert e.leak >= 0
    assert e.direct_value >= e.regular_value
    assert e.invested == D(lump) + D(sip) * 12 * years
