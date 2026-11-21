from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trailcut_engine.display import format_date, format_inr, format_percent

D = Decimal


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("0", "₹0"),
        ("1", "₹1"),
        ("999", "₹999"),
        ("1000", "₹1,000"),
        ("99999", "₹99,999"),
        ("125000", "₹1,25,000"),
        ("1234567", "₹12,34,567"),
        ("12345678", "₹1,23,45,678"),
        ("1000000000", "₹1,00,00,00,000"),
        ("-125000", "-₹1,25,000"),
        ("1250.49", "₹1,250"),
        ("1250.5", "₹1,251"),
        ("-0.4", "₹0"),
        ("2134154.79", "₹21,34,155"),
    ],
)
def test_format_inr(amount: str, expected: str) -> None:
    assert format_inr(D(amount)) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [("1250.5", "₹1,250.50"), ("0.005", "₹0.01"), ("125000", "₹1,25,000.00"), ("-0.10", "-₹0.10")],
)
def test_format_inr_paise(amount: str, expected: str) -> None:
    assert format_inr(D(amount), paise=True) == expected


@pytest.mark.parametrize(
    ("fraction", "places", "expected"),
    [
        ("0.1171", 2, "11.71%"),
        ("0.0175", 2, "1.75%"),
        ("0", 2, "0.00%"),
        ("-0.05", 1, "-5.0%"),
        ("0.123456", 3, "12.346%"),
    ],
)
def test_format_percent(fraction: str, places: int, expected: str) -> None:
    assert format_percent(D(fraction), places) == expected


@pytest.mark.parametrize(
    ("d", "expected"),
    [
        (date(2027, 2, 14), "14 Feb 2027"),
        (date(2026, 4, 1), "1 Apr 2026"),
        (date(2026, 12, 16), "16 Dec 2026"),
    ],
)
def test_format_date(d: date, expected: str) -> None:
    assert format_date(d) == expected


@pytest.mark.property
@given(n=st.integers(min_value=-(10**15), max_value=10**15))
def test_grouping_round_trips(n: int) -> None:
    text = format_inr(D(n))
    digits = text.replace("₹", "").replace(",", "")
    assert int(digits) == n
    body = text.lstrip("-₹")
    groups = body.split(",")
    assert len(groups[-1]) == 3 or len(groups) == 1
    assert all(len(g) == 2 for g in groups[1:-1])
