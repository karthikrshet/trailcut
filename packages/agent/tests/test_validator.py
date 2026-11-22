from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trailcut_agent.validator import extract_claims, validate
from trailcut_engine.display import format_date, format_inr, format_percent

OUT = [
    {
        "totals": {
            "tax": "44494.85",
            "exit_load": "259.89",
            "net_benefit": "226588.80",
            "break_even_months": 42,
        },
        "as_of": "2026-11-20",
        "timeline": [{"on": "2026-12-16", "lots": 1, "value": "120262.66", "label": "Dec 2026"}],
        "xirr": "0.11710993",
        "ter_regular": "0.0165",
        "financial_year": "2026-27",
        "explanation": "Wait until 16 Dec 2026: the gain becomes long term and is taxed at a lower rate.",
    }
]


@pytest.mark.parametrize(
    "answer",
    [
        "Total tax is ₹44,495.",
        "Exit load is ₹260 and you net ₹2,26,589.",
        "You net ₹2.3L over your horizon.",
        "You net about ₹2.27 lakh.".replace("2.27", "2.3"),
        "Rs 44,495 in tax.",
        "INR 44,495 in tax.",
        "₹44,494.85 exactly.",
        "Break-even in 42 months.",
        "Your return is 11.71% a year.",
        "Your return is 11.7% a year.",
        "Your return is 12% a year.",
        "Regular expense ratio is 1.65%.",
        "Wait until 16 Dec 2026.",
        "Next step: Dec 2026.",
        "On 2026-12-16 the lot turns long term.",
        "This falls in FY 2026-27.",
        "Two funds, 3 steps, 1 lot.",
        "No figures here at all.",
        "Worth ₹1.2 lakh".replace("1.2", "1.2"),
    ],
)
def test_supported_figures_pass(answer: str) -> None:
    v = validate(answer, OUT)
    assert v.ok, v.invented


@pytest.mark.parametrize(
    ("answer", "bad"),
    [
        ("Total tax is ₹44,000.", "₹44,000"),
        ("You net ₹2.5L.", "₹2.5L"),
        ("Break-even in 40 months.", "40"),
        ("Your return is 15%.", "15%"),
        ("Wait until 17 Dec 2026.", "17 Dec 2026"),
        ("Next step: Jan 2027.", "Jan 2027"),
        ("This falls in FY 2027-28.", "FY 2027-28"),
        ("That is 1,234 rupees.", "1,234"),
        ("Worth ₹9.9 crore.", "₹9.9 crore"),
        ("₹15K saved.", "₹15K"),
    ],
)
def test_invented_figures_fail(answer: str, bad: str) -> None:
    v = validate(answer, OUT)
    assert not v.ok
    assert bad in v.invented


def test_numbers_from_the_users_question_are_allowed() -> None:
    assert validate("At 8% returns the plan changes.", OUT, "what if returns were 8%?").ok
    assert not validate("At 9% returns the plan changes.", OUT, "what if returns were 8%?").ok


def test_impossible_dates_are_rejected() -> None:
    assert not validate("On 31 Feb 2027.", OUT).ok


def test_counts_every_claim() -> None:
    assert validate("₹44,495 tax, 42 months, 16 Dec 2026.", OUT).checked == 3


def test_extract_claims_kinds() -> None:
    raws = [c.raw for c in extract_claims("₹3.8L by 14 Feb 2027 at 12.5% in FY 2026-27, 160 lots")]
    assert raws == ["₹3.8L", "12.5%", "14 Feb 2027", "FY 2026-27", "160"]


amounts = st.decimals(min_value=Decimal(1), max_value=Decimal(10**9), places=2)


@pytest.mark.property
@given(value=amounts)
def test_any_engine_formatted_amount_passes(value: Decimal) -> None:
    out = [{"x": str(value)}]
    assert validate(f"It is {format_inr(value)}.", out).ok


@pytest.mark.property
@given(value=amounts, delta=st.integers(min_value=2, max_value=10**6))
def test_shifted_amount_fails(value: Decimal, delta: int) -> None:
    out = [{"x": str(value)}]
    other = value + delta
    assert not validate(f"It is {format_inr(other)}.", out).ok


@pytest.mark.property
@given(fraction=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("0.9999"), places=4))
def test_engine_formatted_percent_passes(fraction: Decimal) -> None:
    assert validate(f"Rate {format_percent(fraction)}.", [{"r": str(fraction)}]).ok


@pytest.mark.property
@given(d=st.dates())
def test_engine_formatted_date_passes(d: object) -> None:
    from datetime import date  # noqa: PLC0415

    assert isinstance(d, date)
    assert validate(f"On {format_date(d)}.", [{"on": d.isoformat()}]).ok
