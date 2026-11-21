from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trailcut_engine.dates import (
    add_months,
    add_years,
    first_day_more_than,
    fy_end,
    fy_start_year,
    held_more_than_months,
    next_fy_start,
)

dates = st.dates(min_value=date(1990, 1, 1), max_value=date(2090, 12, 31))


@pytest.mark.parametrize(
    ("d", "months", "expected"),
    [
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2023, 1, 31), 1, date(2023, 2, 28)),
        (date(2024, 3, 31), 1, date(2024, 4, 30)),
        (date(2024, 12, 15), 1, date(2025, 1, 15)),
        (date(2024, 1, 15), 12, date(2025, 1, 15)),
        (date(2024, 1, 15), 24, date(2026, 1, 15)),
        (date(2024, 1, 15), 0, date(2024, 1, 15)),
        (date(2024, 3, 31), -1, date(2024, 2, 29)),
        (date(2024, 1, 15), -13, date(2022, 12, 15)),
        (date(2018, 1, 31), 36, date(2021, 1, 31)),
    ],
)
def test_add_months(d: date, months: int, expected: date) -> None:
    assert add_months(d, months) == expected


@pytest.mark.parametrize(
    ("d", "years", "expected"),
    [
        (date(2024, 2, 29), 1, date(2025, 2, 28)),
        (date(2024, 2, 29), 4, date(2028, 2, 29)),
        (date(2023, 6, 10), 3, date(2026, 6, 10)),
        (date(2023, 6, 10), -3, date(2020, 6, 10)),
    ],
)
def test_add_years(d: date, years: int, expected: date) -> None:
    assert add_years(d, years) == expected


# The 12-month boundary is the most tax-sensitive date in the product.
@pytest.mark.parametrize(
    ("bought", "sold", "months", "expected"),
    [
        (date(2025, 1, 10), date(2026, 1, 9), 12, False),
        (date(2025, 1, 10), date(2026, 1, 10), 12, False),
        (date(2025, 1, 10), date(2026, 1, 11), 12, True),
        (date(2024, 2, 29), date(2025, 2, 28), 12, False),
        (date(2024, 2, 29), date(2025, 3, 1), 12, True),
        (date(2024, 3, 31), date(2025, 3, 31), 12, False),
        (date(2024, 3, 31), date(2025, 4, 1), 12, True),
        (date(2023, 4, 1), date(2025, 4, 1), 24, False),
        (date(2023, 4, 1), date(2025, 4, 2), 24, True),
        (date(2025, 1, 10), date(2025, 1, 10), 12, False),
    ],
)
def test_held_more_than_months(bought: date, sold: date, months: int, expected: bool) -> None:
    assert held_more_than_months(bought, sold, months) is expected


@pytest.mark.parametrize(
    ("bought", "months", "expected"),
    [
        (date(2025, 1, 10), 12, date(2026, 1, 11)),
        (date(2024, 2, 29), 12, date(2025, 3, 1)),
        (date(2025, 12, 15), 12, date(2026, 12, 16)),
        (date(2021, 8, 10), 24, date(2023, 8, 11)),
    ],
)
def test_first_day_more_than(bought: date, months: int, expected: date) -> None:
    assert first_day_more_than(bought, months) == expected


@pytest.mark.parametrize(
    ("d", "start", "end", "nxt"),
    [
        (date(2026, 4, 1), 2026, date(2027, 3, 31), date(2027, 4, 1)),
        (date(2027, 3, 31), 2026, date(2027, 3, 31), date(2027, 4, 1)),
        (date(2026, 11, 21), 2026, date(2027, 3, 31), date(2027, 4, 1)),
        (date(2026, 3, 31), 2025, date(2026, 3, 31), date(2026, 4, 1)),
        (date(2027, 1, 1), 2026, date(2027, 3, 31), date(2027, 4, 1)),
    ],
)
def test_financial_year_helpers(d: date, start: int, end: date, nxt: date) -> None:
    assert fy_start_year(d) == start
    assert fy_end(d) == end
    assert next_fy_start(d) == nxt


@pytest.mark.property
@given(d=dates, months=st.integers(-240, 240))
def test_add_months_round_trips_except_month_end(d: date, months: int) -> None:
    there = add_months(d, months)
    assert (there.year * 12 + there.month) - (d.year * 12 + d.month) == months
    if d.day <= 28:
        assert add_months(there, -months) == d


@pytest.mark.property
@given(bought=dates, months=st.sampled_from([12, 24, 36]))
def test_first_day_more_than_is_the_exact_boundary(bought: date, months: int) -> None:
    first = first_day_more_than(bought, months)
    assert held_more_than_months(bought, first, months)
    assert not held_more_than_months(bought, first - timedelta(days=1), months)


@pytest.mark.property
@given(d=dates)
def test_fy_contains_its_date(d: date) -> None:
    start = date(fy_start_year(d), 4, 1)
    assert start <= d <= fy_end(d)
    assert next_fy_start(d) == fy_end(d) + timedelta(days=1)
