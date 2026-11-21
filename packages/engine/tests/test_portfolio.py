from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from trailcut_engine.portfolio import (
    UNIT_INFLOWS,
    UNIT_OUTFLOWS,
    AssetClass,
    Folio,
    Plan,
    Portfolio,
    Scheme,
    SchemeOption,
    StatementSource,
    Transaction,
    TxnKind,
    Valuation,
)

D = Decimal


def txn(
    kind: TxnKind = TxnKind.SIP, units: str | None = "10.000", on: date | None = None
) -> Transaction:
    return Transaction(
        date=on or date(2024, 1, 10),
        kind=kind,
        amount=D("1000"),
        units=None if units is None else D(units),
        nav=D("100"),
    )


def scheme(scheme_id: str = "F1-S1", **overrides: Any) -> Scheme:
    fields: dict[str, Any] = {
        "scheme_id": scheme_id,
        "name": "Sample Flexi Cap Fund - Regular Plan - Growth",
        "amc": "Sample Mutual Fund",
        "isin": "INF000S01011",
        "amfi_code": "100001",
        "plan": Plan.REGULAR,
        "option": SchemeOption.GROWTH,
        "asset_class": AssetClass.EQUITY,
        "is_elss": False,
        "open_units": D("0"),
        "close_units": D("10.000"),
        "valuation": Valuation(date=date(2026, 11, 20), nav=D("120"), value=D("1200")),
        "transactions": (txn(),),
    }
    fields.update(overrides)
    return Scheme(**fields)


def portfolio(*folios: Folio, **overrides: Any) -> Portfolio:
    fields: dict[str, Any] = {
        "source": StatementSource.CAMS,
        "statement_from": date(2015, 1, 1),
        "statement_to": date(2026, 11, 20),
        "folios": folios or (Folio(folio_id="F1", amc="Sample Mutual Fund", schemes=(scheme(),)),),
    }
    fields.update(overrides)
    return Portfolio(**fields)


# ---------- Transaction ----------


@pytest.mark.parametrize("kind", sorted(UNIT_INFLOWS))
def test_inflow_kinds_reject_negative_units(kind: TxnKind) -> None:
    with pytest.raises(ValidationError, match="must add units"):
        txn(kind, "-1")


@pytest.mark.parametrize("kind", sorted(UNIT_OUTFLOWS))
def test_outflow_kinds_reject_positive_units(kind: TxnKind) -> None:
    with pytest.raises(ValidationError, match="must remove units"):
        txn(kind, "1")


@pytest.mark.parametrize("kind", list(TxnKind))
def test_zero_or_missing_units_are_allowed_for_every_kind(kind: TxnKind) -> None:
    assert txn(kind, "0").units == 0
    assert txn(kind, None).units is None


@pytest.mark.parametrize(
    "kind", [TxnKind.TAX, TxnKind.REVERSAL, TxnKind.OTHER, TxnKind.DIVIDEND_PAYOUT]
)
@pytest.mark.parametrize("units", ["5", "-5"])
def test_neutral_kinds_allow_either_sign(kind: TxnKind, units: str) -> None:
    assert txn(kind, units).units == D(units)


@pytest.mark.parametrize(
    ("units", "inflow", "outflow"),
    [("10", True, False), ("-10", False, True), ("0", False, False), (None, False, False)],
)
def test_flow_direction(units: str | None, inflow: bool, outflow: bool) -> None:
    kind = TxnKind.REVERSAL
    t = txn(kind, units)
    assert (t.is_unit_inflow, t.is_unit_outflow) == (inflow, outflow)


@pytest.mark.parametrize("field", ["amount", "units", "nav", "balance"])
def test_transaction_rejects_float(field: str) -> None:
    bad: dict[str, Any] = {field: 1.5}
    with pytest.raises(ValidationError, match="floats"):
        Transaction(date=date(2024, 1, 1), kind=TxnKind.OTHER, **bad)


def test_transaction_rejects_negative_nav() -> None:
    with pytest.raises(ValidationError, match="nav"):
        Transaction(date=date(2024, 1, 1), kind=TxnKind.OTHER, nav=D("-1"))


def test_transaction_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="description"):
        Transaction(date=date(2024, 1, 1), kind=TxnKind.OTHER, description="Purchase")  # type: ignore[call-arg]


def test_transaction_is_frozen() -> None:
    with pytest.raises(ValidationError, match="frozen"):
        txn().units = D("1")  # type: ignore[misc]


# ---------- Scheme ----------


def test_scheme_reconciles_when_units_match() -> None:
    s = scheme()
    assert s.unit_mismatch == 0
    assert s.units_reconcile


@pytest.mark.parametrize(
    ("close", "reconciles"),
    [("10.001", True), ("9.999", True), ("10.0015", True), ("10.002", False), ("9.990", False)],
)
def test_scheme_reconcile_tolerance(close: str, reconciles: bool) -> None:
    assert scheme(close_units=D(close)).units_reconcile is reconciles


def test_scheme_mismatch_accounts_for_open_units_and_outflows() -> None:
    s = scheme(
        open_units=D("5"),
        close_units=D("12"),
        transactions=(txn(units="10"), txn(TxnKind.REDEMPTION, "-3", on=date(2024, 2, 1))),
    )
    assert s.unit_mismatch == 0


def test_scheme_requires_chronological_transactions() -> None:
    with pytest.raises(ValidationError, match="date order"):
        scheme(transactions=(txn(on=date(2024, 2, 1)), txn(on=date(2024, 1, 1))))


@pytest.mark.parametrize("isin", ["INF000S0101", "US0378331005", "inf000s01011", "INF000S0101X"])
def test_scheme_rejects_bad_isin(isin: str) -> None:
    with pytest.raises(ValidationError, match="isin"):
        scheme(isin=isin)


@pytest.mark.parametrize("code", ["abc", "123456789", ""])
def test_scheme_rejects_bad_amfi_code(code: str) -> None:
    with pytest.raises(ValidationError, match="amfi_code"):
        scheme(amfi_code=code)


@pytest.mark.parametrize("scheme_id", ["S1", "F1", "F1-S", "f1-s1", "F1-S1 "])
def test_scheme_rejects_bad_ids(scheme_id: str) -> None:
    with pytest.raises(ValidationError, match="scheme_id"):
        scheme(scheme_id)


@pytest.mark.parametrize("name", ["", "x" * 201])
def test_scheme_name_length_is_bounded(name: str) -> None:
    with pytest.raises(ValidationError, match="name"):
        scheme(name=name)


@pytest.mark.parametrize("field", ["pan", "folio", "investor_name", "email", "nominees", "mobile"])
def test_scheme_has_no_pii_fields(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        scheme(**{field: "x"})


def test_negative_units_are_rejected() -> None:
    with pytest.raises(ValidationError, match="close_units"):
        scheme(close_units=D("-1"))


# ---------- Folio / Portfolio ----------


def test_folio_rejects_foreign_scheme_ids() -> None:
    with pytest.raises(ValidationError, match="does not belong"):
        Folio(folio_id="F2", amc="X", schemes=(scheme("F1-S1"),))


def test_folio_id_prefix_is_not_confused_with_longer_ids() -> None:
    with pytest.raises(ValidationError, match="does not belong"):
        Folio(folio_id="F1", amc="X", schemes=(scheme("F12-S1"),))


@pytest.mark.parametrize("field", ["folio", "PAN", "investor_info", "KYC"])
def test_folio_has_no_pii_fields(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        Folio(folio_id="F1", amc="X", schemes=(), **{field: "x"})


def test_portfolio_lists_and_finds_schemes() -> None:
    f1 = Folio(folio_id="F1", amc="A", schemes=(scheme("F1-S1"), scheme("F1-S2")))
    f2 = Folio(folio_id="F2", amc="B", schemes=(scheme("F2-S1"),))
    p = portfolio(f1, f2)
    assert [s.scheme_id for s in p.schemes] == ["F1-S1", "F1-S2", "F2-S1"]
    assert p.scheme("F2-S1").scheme_id == "F2-S1"
    with pytest.raises(KeyError):
        p.scheme("F9-S9")


def test_portfolio_rejects_duplicate_folio_ids() -> None:
    f = Folio(folio_id="F1", amc="A", schemes=())
    with pytest.raises(ValidationError, match="folio ids must be unique"):
        portfolio(f, f)


def test_portfolio_rejects_duplicate_scheme_ids() -> None:
    f = Folio(folio_id="F1", amc="A", schemes=(scheme("F1-S1"), scheme("F1-S1")))
    with pytest.raises(ValidationError, match="scheme ids must be unique"):
        portfolio(f)


def test_portfolio_rejects_inverted_period() -> None:
    with pytest.raises(ValidationError, match="statement_from"):
        portfolio(statement_from=date(2027, 1, 1))


def test_portfolio_warning_length_is_bounded() -> None:
    with pytest.raises(ValidationError, match="warnings"):
        portfolio(warnings=("x" * 501,))


def test_portfolio_json_round_trip() -> None:
    p = portfolio()
    assert Portfolio.model_validate_json(p.model_dump_json()) == p


# ---------- properties ----------

units_st = st.decimals(min_value=D("0.001"), max_value=D("100000"), places=3)


@pytest.mark.property
@given(buys=st.lists(units_st, min_size=1, max_size=30), sell_fraction=st.integers(0, 100))
def test_reconciles_for_any_buy_sell_history(buys: list[Decimal], sell_fraction: int) -> None:
    total = sum(buys, D(0))
    sold = (total * sell_fraction / 100).quantize(D("0.001"))
    rows = [txn(TxnKind.SIP, str(u), on=date(2020, 1, 1 + i % 28)) for i, u in enumerate(buys)]
    rows.sort(key=lambda t: t.date)
    if sold:
        rows.append(txn(TxnKind.REDEMPTION, str(-sold), on=date(2021, 1, 1)))
    s = scheme(close_units=total - sold, transactions=tuple(rows))
    assert s.units_reconcile
    assert s.unit_mismatch == 0
