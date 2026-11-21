from datetime import date
from decimal import Decimal

import pytest

from trailcut_engine.portfolio import Folio, Plan, Portfolio, StatementSource, TxnKind
from trailcut_engine.summary import scheme_cashflows, summarize, summarize_scheme
from trailcut_engine.testing import buy, make_scheme, sell, tx

D = Decimal
J24, J25 = date(2024, 1, 1), date(2025, 1, 1)


def test_cashflows_signs_and_terminal_value() -> None:
    s = make_scheme([buy(J24, "10"), sell(date(2024, 6, 1), "2", "110")], nav="120", on=J25)
    assert scheme_cashflows(s) == [
        (J24, D(-1000)),
        (date(2024, 6, 1), D(220)),
        (J25, D(960)),
    ]


@pytest.mark.parametrize(
    ("kind", "units", "expected_sign"),
    [
        (TxnKind.SIP, "1", -1),
        (TxnKind.SWITCH_IN, "1", -1),
        (TxnKind.GIFT_IN, "1", -1),
        (TxnKind.SWITCH_OUT, "-1", 1),
        (TxnKind.GIFT_OUT, "-1", 1),
        (TxnKind.DIVIDEND_PAYOUT, None, 1),
        (TxnKind.TAX, None, -1),
    ],
)
def test_cashflow_direction_per_kind(kind: TxnKind, units: str | None, expected_sign: int) -> None:
    rows = [buy(J24, "10"), tx(date(2024, 3, 1), kind, units, "100", "50")]
    flows = scheme_cashflows(make_scheme(rows, nav="100", on=J25))
    amount = flows[1][1]
    assert (amount > 0) == (expected_sign > 0)


@pytest.mark.parametrize(
    "kind", [TxnKind.DIVIDEND_REINVEST, TxnKind.MERGER_IN, TxnKind.SEGREGATION]
)
def test_unit_only_events_are_not_cashflows(kind: TxnKind) -> None:
    rows = [buy(J24, "10"), tx(date(2024, 3, 1), kind, "1", "100", "100")]
    flows = scheme_cashflows(make_scheme(rows, on=J25))
    assert [d for d, _ in flows] == [J24, J25]


@pytest.mark.parametrize(("units", "sign"), [("-5", 1), ("5", -1)])
def test_reversal_cashflow_direction(units: str, sign: int) -> None:
    rows = [buy(J24, "10"), tx(date(2024, 3, 1), TxnKind.REVERSAL, units, "100", "500")]
    flows = scheme_cashflows(make_scheme(rows, on=J25))
    assert (flows[1][1] > 0) == (sign > 0)


def test_scheme_summary_numbers() -> None:
    # 10 units at 100 a year ago, now worth 110 each: 10% XIRR (2024 is a leap year: 366 days).
    s = summarize_scheme(make_scheme([buy(date(2024, 1, 2), "10")], nav="110", on=J25))
    assert (s.value, s.invested, s.gain) == (D(1100), D(1000), D(100))
    assert s.xirr is not None
    assert abs(s.xirr - D("0.10")) < D("0.0001")
    assert s.cost_complete


def test_scheme_without_history_has_no_xirr() -> None:
    s = summarize_scheme(make_scheme([], open_units="10"))
    assert s.xirr is None
    assert not s.cost_complete


def test_fully_redeemed_scheme() -> None:
    s = summarize_scheme(make_scheme([buy(J24, "10"), sell(date(2024, 7, 1), "10", "120")], on=J25))
    assert (s.value, s.invested) == (D(0), D(0))
    assert s.xirr is not None
    assert s.xirr > 0


def test_portfolio_summary_aggregates() -> None:
    reg = make_scheme([buy(date(2024, 1, 2), "10")], scheme_id="F1-S1", nav="110", on=J25)
    direct = make_scheme(
        [buy(date(2024, 1, 2), "5")], scheme_id="F2-S1", nav="120", on=J25, plan=Plan.DIRECT
    )
    p = Portfolio(
        source=StatementSource.SAMPLE,
        statement_from=J24,
        statement_to=J25,
        folios=(
            Folio(folio_id="F1", amc="A", schemes=(reg,)),
            Folio(folio_id="F2", amc="B", schemes=(direct,)),
        ),
    )
    s = summarize(p)
    assert (s.value, s.invested, s.gain) == (D(1700), D(1500), D(200))
    assert (s.regular_value, s.direct_value) == (D(1100), D(600))
    assert s.as_of == J25
    assert s.xirr is not None
    assert D("0.10") < s.xirr < D("0.20")
    assert [x.scheme_id for x in s.schemes] == ["F1-S1", "F2-S1"]


def test_portfolio_xirr_none_if_any_scheme_incomplete() -> None:
    ok = make_scheme([buy(J24, "10")], scheme_id="F1-S1", on=J25)
    bad = make_scheme([], scheme_id="F1-S2", open_units="3", on=J25)
    p = Portfolio(
        source=StatementSource.SAMPLE,
        statement_from=J24,
        statement_to=J25,
        folios=(Folio(folio_id="F1", amc="A", schemes=(ok, bad)),),
    )
    assert summarize(p).xirr is None


def test_empty_portfolio() -> None:
    p = Portfolio(source=StatementSource.SAMPLE, statement_from=J24, statement_to=J25, folios=())
    s = summarize(p)
    assert (s.value, s.invested, s.xirr, s.as_of) == (D(0), D(0), None, J25)


def test_money_is_rounded_to_paise() -> None:
    # 3 units for 100, then sell 1: remaining cost is 66.666... -> 66.67.
    rows = [buy(J24, "3", "33.3333333", "100"), sell(date(2024, 6, 1), "1", "40")]
    s = summarize_scheme(make_scheme(rows, nav="40", on=J25))
    assert s.invested == D("66.67")
    assert s.invested.as_tuple().exponent == -2
