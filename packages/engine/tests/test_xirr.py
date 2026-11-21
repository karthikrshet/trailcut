from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trailcut_engine.xirr import XirrError, xirr

D = Decimal


def close(a: Decimal, b: Decimal, tol: str = "0.000001") -> bool:
    return abs(a - b) <= D(tol)


# ---------- golden cases ----------


def test_spreadsheet_reference_example() -> None:
    """The classic XIRR example from spreadsheet documentation: 37.336%."""
    flows = [
        (date(2008, 1, 1), D(-10000)),
        (date(2008, 3, 1), D(2750)),
        (date(2008, 10, 30), D(4250)),
        (date(2009, 2, 15), D(3250)),
        (date(2009, 4, 1), D(2750)),
    ]
    assert close(xirr(flows), D("0.373362535"))


@pytest.mark.parametrize(
    ("days", "end_value", "expected"),
    [
        (365, "1100", "0.10"),
        (730, "1210", "0.10"),
        (365, "1000", "0"),
        (365, "900", "-0.10"),
        (365, "2000", "1.00"),
        (365, "500", "-0.50"),
        (1095, "1331", "0.10"),
        (3650, "2593.7424601", "0.10"),
    ],
)
def test_single_investment(days: int, end_value: str, expected: str) -> None:
    start = date(2020, 1, 1)
    flows = [(start, D(-1000)), (start + timedelta(days=days), D(end_value))]
    assert close(xirr(flows), D(expected))


def test_half_year_compounds_annually() -> None:
    # 5% in 182.5 days is (1.05)^2 - 1 = 10.25% a year; use 365/2 via two flows.
    start = date(2021, 1, 1)
    flows = [(start, D(-1000)), (start + timedelta(days=73), D(1000) * D("1.10") ** (D(73) / 365))]
    assert close(xirr(flows), D("0.10"))


def test_monthly_sip_with_known_rate() -> None:
    rate = D("0.12")
    start = date(2020, 1, 1)
    flows = []
    value = D(0)
    end = date(2025, 1, 1)
    for m in range(60):
        d = date(2020 + m // 12, m % 12 + 1, 1)
        flows.append((d, D(-5000)))
        value += D(5000) * (1 + rate) ** (D((end - d).days) / 365)
    flows.append((end, value))
    assert close(xirr(flows), rate)
    assert start == flows[0][0]


def test_order_of_cashflows_does_not_matter() -> None:
    flows = [(date(2020, 1, 1), D(-1000)), (date(2021, 6, 1), D(300)), (date(2022, 1, 1), D(900))]
    assert xirr(flows) == xirr(list(reversed(flows)))


def test_zero_cashflows_are_ignored() -> None:
    flows = [(date(2020, 1, 1), D(-1000)), (date(2020, 6, 1), D(0)), (date(2021, 1, 1), D(1100))]
    assert close(xirr(flows), D("0.0997"), "0.001")


def test_result_has_eight_decimal_places() -> None:
    r = xirr([(date(2020, 1, 1), D(-1000)), (date(2021, 1, 1), D(1123))])
    assert r.as_tuple().exponent == -8


def test_total_loss_near_lower_bound() -> None:
    r = xirr([(date(2020, 1, 1), D(-1000)), (date(2021, 1, 1), D("0.001"))])
    assert r < D("-0.99")


def test_huge_gain() -> None:
    # 2021 is not a leap year, so this is exactly 365 days.
    assert close(xirr([(date(2021, 1, 1), D(-1)), (date(2022, 1, 1), D(50))]), D(49), "0.0001")


# ---------- no-solution cases ----------


@pytest.mark.parametrize(
    ("flows", "match"),
    [
        ([], "at least two"),
        ([(date(2020, 1, 1), D(-100))], "at least two"),
        ([(date(2020, 1, 1), D(-100)), (date(2021, 1, 1), D(0))], "at least two"),
        ([(date(2020, 1, 1), D(-100)), (date(2021, 1, 1), D(-50))], "both money in"),
        ([(date(2020, 1, 1), D(100)), (date(2021, 1, 1), D(50))], "both money in"),
        ([(date(2020, 1, 1), D(-100)), (date(2020, 1, 1), D(110))], "same date"),
        ([(date(2020, 1, 1), D(-1)), (date(2020, 1, 2), D(10**9))], "no rate"),
    ],
)
def test_no_solution(flows: list[tuple[date, Decimal]], match: str) -> None:
    with pytest.raises(XirrError, match=match):
        xirr(flows)


# ---------- properties ----------


@pytest.mark.property
@given(
    rate=st.decimals(min_value=D("-0.5"), max_value=D("1.5"), places=4),
    gaps=st.lists(st.integers(min_value=1, max_value=400), min_size=1, max_size=12),
    amounts=st.lists(st.integers(min_value=100, max_value=100000), min_size=12, max_size=12),
)
def test_recovers_the_rate_used_to_build_cashflows(
    rate: Decimal, gaps: list[int], amounts: list[int]
) -> None:
    start = date(2015, 1, 1)
    dates = [start]
    for g in gaps:
        dates.append(dates[-1] + timedelta(days=g))
    end = dates[-1] + timedelta(days=30)
    flows = []
    terminal = D(0)
    for d, a in zip(dates, amounts, strict=False):
        flows.append((d, D(-a)))
        terminal += D(a) * (1 + rate) ** (D((end - d).days) / 365)
    flows.append((end, terminal))
    assert close(xirr(flows), rate, "0.00001")


@pytest.mark.property
@given(scale=st.integers(min_value=1, max_value=10**6))
def test_scale_invariant(scale: int) -> None:
    base = [(date(2020, 1, 1), D(-1000)), (date(2020, 9, 1), D(-500)), (date(2022, 1, 1), D(1800))]
    scaled = [(d, a * scale) for d, a in base]
    assert close(xirr(base), xirr(scaled), "0.0000001")
