from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from trailcut_engine.lots import Lot, LotBook, build_lots
from trailcut_engine.portfolio import TxnKind
from trailcut_engine.testing import buy, make_scheme, sell, tx

D = Decimal
J1, F1, M1, A1 = date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1), date(2024, 4, 1)


def test_purchases_become_lots_in_order() -> None:
    book = build_lots(make_scheme([buy(J1, "10"), buy(F1, "5", "110")]))
    assert [lot.lot_id for lot in book.open_lots] == ["F1-S1-L001", "F1-S1-L002"]
    assert [lot.buy_date for lot in book.open_lots] == [J1, F1]
    assert [lot.units for lot in book.open_lots] == [D(10), D(5)]
    assert [lot.cost for lot in book.open_lots] == [D(1000), D(550)]
    assert book.units == D(15)
    assert book.cost == D(1550)
    assert book.disposals == ()
    assert book.warnings == ()


def test_redemption_consumes_oldest_lot_first() -> None:
    book = build_lots(make_scheme([buy(J1, "10"), buy(F1, "10", "120"), sell(M1, "4", "130")]))
    first, second = book.open_lots
    assert (first.lot_id, first.units, first.cost) == ("F1-S1-L001", D(6), D(600))
    assert (second.lot_id, second.units) == ("F1-S1-L002", D(10))
    (d,) = book.disposals
    assert (d.lot_id, d.units, d.cost, d.proceeds, d.sell_date) == (
        "F1-S1-L001",
        D(4),
        D(400),
        D(520),
        M1,
    )


def test_redemption_spanning_several_lots() -> None:
    rows = [buy(J1, "10"), buy(F1, "10", "120"), buy(M1, "10", "130"), sell(A1, "25", "140")]
    book = build_lots(make_scheme(rows))
    (remaining,) = book.open_lots
    assert (remaining.lot_id, remaining.units, remaining.cost) == ("F1-S1-L003", D(5), D(650))
    assert [(d.lot_id, d.units) for d in book.disposals] == [
        ("F1-S1-L001", D(10)),
        ("F1-S1-L002", D(10)),
        ("F1-S1-L003", D(5)),
    ]
    assert sum((d.cost for d in book.disposals), D(0)) == D(1000 + 1200 + 650)


def test_full_redemption_leaves_no_lots() -> None:
    book = build_lots(make_scheme([buy(J1, "10"), sell(F1, "10")]))
    assert book.open_lots == ()
    assert book.units == 0


@pytest.mark.parametrize(
    "kind", [TxnKind.SWITCH_OUT, TxnKind.MERGER_OUT, TxnKind.GIFT_OUT, TxnKind.REDEMPTION]
)
def test_every_outflow_kind_is_fifo(kind: TxnKind) -> None:
    book = build_lots(make_scheme([buy(J1, "10"), buy(F1, "10"), tx(M1, kind, "-3")]))
    assert book.open_lots[0].units == D(7)
    assert book.disposals[0].kind is kind


@pytest.mark.parametrize(
    "kind",
    [
        TxnKind.SIP,
        TxnKind.SWITCH_IN,
        TxnKind.DIVIDEND_REINVEST,
        TxnKind.GIFT_IN,
        TxnKind.SEGREGATION,
    ],
)
def test_every_inflow_kind_creates_a_lot(kind: TxnKind) -> None:
    (lot,) = build_lots(make_scheme([tx(J1, kind, "5")])).open_lots
    assert lot.source is kind
    assert lot.units == D(5)


def test_reversal_undoes_the_newest_lot() -> None:
    rows = [buy(J1, "10"), buy(F1, "8"), tx(F1, TxnKind.REVERSAL, "-8")]
    book = build_lots(make_scheme(rows))
    assert [lot.lot_id for lot in book.open_lots] == ["F1-S1-L001"]
    assert book.disposals == ()


def test_stamp_duty_is_added_to_that_days_lot() -> None:
    rows = [buy(J1, "10"), tx(J1, TxnKind.TAX, None, None, "0.05"), buy(F1, "10")]
    book = build_lots(make_scheme(rows))
    assert book.open_lots[0].cost == D("1000.05")
    assert book.open_lots[1].cost == D(1000)


def test_stamp_duty_on_a_day_without_purchase_is_ignored() -> None:
    rows = [buy(J1, "10"), tx(F1, TxnKind.TAX, None, None, "0.05")]
    assert build_lots(make_scheme(rows)).open_lots[0].cost == D(1000)


def test_rows_without_units_are_skipped() -> None:
    rows = [buy(J1, "10"), tx(F1, TxnKind.DIVIDEND_PAYOUT, None, None, "50")]
    book = build_lots(make_scheme(rows))
    assert book.units == D(10)


def test_cost_falls_back_to_units_times_nav() -> None:
    (lot,) = build_lots(make_scheme([tx(J1, TxnKind.PURCHASE, "10", "50", None)])).open_lots
    assert lot.cost == D(500)
    assert lot.cost_known


def test_cost_unknown_without_amount_or_nav() -> None:
    row = tx(J1, TxnKind.SEGREGATION, "10", None, None)
    (lot,) = build_lots(make_scheme([row])).open_lots
    assert lot.cost == 0
    assert not lot.cost_known


def test_opening_balance_becomes_unknown_cost_lot() -> None:
    book = build_lots(make_scheme([buy(F1, "5")], open_units="20"))
    first = book.open_lots[0]
    assert (first.units, first.cost, first.cost_known, first.buy_date) == (D(20), D(0), False, F1)
    assert "before the statement period" in book.warnings[0]


def test_opening_balance_without_transactions_uses_valuation_date() -> None:
    book = build_lots(make_scheme([], open_units="20"))
    assert book.open_lots[0].buy_date == date(2026, 11, 20)


def test_over_redemption_warns_and_does_not_crash() -> None:
    book = build_lots(make_scheme([buy(J1, "5"), sell(F1, "8")], close_units=D(0)))
    assert book.open_lots == ()
    assert "removes 3 more units" in book.warnings[0]


def test_merger_in_warns_about_dates() -> None:
    book = build_lots(make_scheme([tx(J1, TxnKind.MERGER_IN, "10")]))
    assert "merger" in book.warnings[0]


def test_disposal_without_nav_has_no_proceeds() -> None:
    rows = [buy(J1, "10"), tx(F1, TxnKind.GIFT_OUT, "-4", None, None)]
    assert build_lots(make_scheme(rows)).disposals[0].proceeds is None


def test_lot_take_splits_cost_pro_rata() -> None:
    lot = Lot(
        lot_id="F1-S1-L001",
        scheme_id="F1-S1",
        buy_date=J1,
        units=D(3),
        cost=D(100),
        source=TxnKind.PURCHASE,
    )
    taken, rest = lot.take(D(1))
    assert rest is not None
    assert taken.cost + rest.cost == D(100)
    assert (taken.units, rest.units) == (D(1), D(2))
    whole, none = lot.take(D(3))
    assert whole is lot
    assert none is None


@pytest.mark.parametrize("units", ["0", "-1", "3.0001"])
def test_lot_take_rejects_bad_amounts(units: str) -> None:
    lot = Lot(
        lot_id="F1-S1-L001",
        scheme_id="F1-S1",
        buy_date=J1,
        units=D(3),
        cost=D(1),
        source=TxnKind.PURCHASE,
    )
    with pytest.raises(ValueError, match="cannot take"):
        lot.take(D(units))


@pytest.mark.parametrize("lot_id", ["L1", "F1-S1-L1", "F1-S1-X001"])
def test_lot_id_format(lot_id: str) -> None:
    with pytest.raises(ValidationError):
        Lot(
            lot_id=lot_id,
            scheme_id="F1-S1",
            buy_date=J1,
            units=D(1),
            cost=D(1),
            source=TxnKind.PURCHASE,
        )


def test_cost_per_unit() -> None:
    (lot,) = build_lots(make_scheme([buy(J1, "4", "25")])).open_lots
    assert lot.cost_per_unit == D(25)


# ---------- properties ----------

units_st = st.decimals(min_value=D("0.001"), max_value=D("5000"), places=3)


@st.composite
def histories(draw: st.DrawFn) -> list[tuple[str, Decimal]]:
    events: list[tuple[str, Decimal]] = []
    held = D(0)
    for _ in range(draw(st.integers(1, 40))):
        if held > 0 and draw(st.booleans()):
            fraction = draw(st.integers(1, 100))
            units = (held * fraction / 100).quantize(D("0.001"))
            if units > 0:
                events.append(("sell", units))
                held -= units
                continue
        u = draw(units_st)
        events.append(("buy", u))
        held += u
    return events


def replay(events: list[tuple[str, Decimal]]) -> tuple[list[tuple[date, Decimal]], LotBook]:
    rows = []
    buys = []
    d = date(2015, 1, 1)
    for kind, units in events:
        d += timedelta(days=7)
        if kind == "buy":
            rows.append(buy(d, str(units)))
            buys.append((d, units))
        else:
            rows.append(sell(d, str(units)))
    return buys, build_lots(make_scheme(rows))


@pytest.mark.property
@given(events=histories())
def test_units_and_cost_are_conserved(events: list[tuple[str, Decimal]]) -> None:
    buys, book = replay(events)
    bought = sum((u for _, u in buys), D(0))
    sold = sum((u for k, u in events if k == "sell"), D(0))
    assert book.units == bought - sold
    total_cost = book.cost + sum((d.cost for d in book.disposals), D(0))
    assert abs(total_cost - bought * 100) < D("0.0000001")
    assert book.warnings == ()


@pytest.mark.property
@given(events=histories())
def test_remaining_lots_are_the_newest_purchases(events: list[tuple[str, Decimal]]) -> None:
    buys, book = replay(events)
    lots = book.open_lots
    dates = [lot.buy_date for lot in lots]
    assert dates == sorted(dates)
    buy_dates = [d for d, _ in buys]
    # FIFO: what is left is a suffix of the purchase sequence (first may be partial).
    assert dates == buy_dates[len(buy_dates) - len(dates) :]
    for lot in lots[1:]:
        assert lot.units == dict(buys)[lot.buy_date]


@pytest.mark.property
@given(events=histories())
def test_lot_book_is_deterministic(events: list[tuple[str, Decimal]]) -> None:
    _, a = replay(events)
    _, b = replay(events)
    assert a == b
