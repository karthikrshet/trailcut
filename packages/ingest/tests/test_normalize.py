from collections.abc import Callable
from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from casparser.types import CASData
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from trailcut_engine.portfolio import AssetClass, Plan, SchemeOption, StatementSource, TxnKind
from trailcut_ingest.errors import (
    DepositoryStatementError,
    StatementParseError,
    SummaryStatementError,
    UnrecognizedStatementError,
)
from trailcut_ingest.normalize import clean_text, normalize_cas, parse_date
from trailcut_ingest.pii import contains_pii

MakeCas = Callable[..., dict[str, Any]]


def scheme_with(make_cas: MakeCas, **changes: Any) -> dict[str, Any]:
    cas = make_cas()
    cas["folios"][0]["schemes"][0].update(changes)
    return cas


# ---------- happy path ----------


def test_normalizes_a_cams_detailed_statement(make_cas: MakeCas) -> None:
    p = normalize_cas(make_cas())
    assert p.source is StatementSource.CAMS
    assert (p.statement_from, p.statement_to) == (date(2015, 1, 1), date(2026, 11, 20))
    (folio,) = p.folios
    assert folio.folio_id == "F1"
    assert folio.amc == "Sample Mutual Fund"
    (s,) = folio.schemes
    assert s.scheme_id == "F1-S1"
    assert s.plan is Plan.REGULAR
    assert s.option is SchemeOption.GROWTH
    assert s.asset_class is AssetClass.EQUITY
    assert not s.is_elss
    assert s.isin == "INF000S01011"
    assert s.amfi_code == "100001"
    assert s.close_units == Decimal("30.000")
    assert s.valuation.value == Decimal("4500.00")
    assert [t.kind for t in s.transactions] == [TxnKind.SIP, TxnKind.SIP, TxnKind.TAX, TxnKind.SIP]
    assert s.units_reconcile
    assert p.warnings == ()


def test_kfintech_source(make_cas: MakeCas) -> None:
    assert normalize_cas(make_cas(file_type="KFINTECH")).source is StatementSource.KFINTECH


def test_explicit_source_overrides(make_cas: MakeCas) -> None:
    p = normalize_cas(make_cas(file_type="UNKNOWN"), source=StatementSource.SAMPLE)
    assert p.source is StatementSource.SAMPLE


def test_ids_are_sequential_across_folios(make_cas: MakeCas) -> None:
    p = normalize_cas(make_cas(extra_folios=2))
    assert [f.folio_id for f in p.folios] == ["F1", "F2", "F3"]
    assert [s.scheme_id for s in p.schemes] == ["F1-S1", "F2-S1", "F3-S1"]


def test_accepts_casparser_model_dump(make_cas: MakeCas) -> None:
    """Our adapter reads casparser's real output type, enums included."""
    model = CASData.model_validate(make_cas())
    p = normalize_cas(model.model_dump(by_alias=True))
    assert p.schemes[0].close_units == Decimal("30.000")


def test_accepts_casparser_dump_without_aliases(make_cas: MakeCas) -> None:
    model = CASData.model_validate(make_cas())
    dumped = model.model_dump()
    dumped["statement_period"] = {"from": "01-Jan-2015", "to": "20-Nov-2026"}
    assert normalize_cas(dumped).source is StatementSource.CAMS


# ---------- statement type errors ----------


@pytest.mark.parametrize("file_type", ["NSDL", "CDSL", "nsdl"])
def test_depository_statements_are_rejected(make_cas: MakeCas, file_type: str) -> None:
    with pytest.raises(DepositoryStatementError):
        normalize_cas(make_cas(file_type=file_type))


def test_summary_statement_is_rejected(make_cas: MakeCas) -> None:
    with pytest.raises(SummaryStatementError):
        normalize_cas(make_cas(cas_type="SUMMARY"))


@pytest.mark.parametrize(("file_type", "cas_type"), [("UNKNOWN", "DETAILED"), ("CAMS", "UNKNOWN")])
def test_unknown_statements_are_rejected(make_cas: MakeCas, file_type: str, cas_type: str) -> None:
    with pytest.raises(UnrecognizedStatementError):
        normalize_cas(make_cas(file_type=file_type, cas_type=cas_type))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.pop("folios"),
        lambda c: c.pop("statement_period"),
        lambda c: c["folios"][0]["schemes"][0].pop("valuation"),
        lambda c: c["folios"][0]["schemes"][0].update(close="not-a-number"),
        lambda c: c["folios"][0]["schemes"][0]["transactions"][0].update(date="31-Feb-2024"),
        lambda c: c.update(statement_period={"from": "garbage", "to": "20-Nov-2026"}),
    ],
)
def test_structurally_broken_data_raises_parse_error(make_cas: MakeCas, mutate: Any) -> None:
    cas = make_cas()
    mutate(cas)
    with pytest.raises(StatementParseError) as info:
        normalize_cas(cas)
    assert "ABCPE1234F" not in str(info.value)
    assert "Ravi" not in str(info.value)


# ---------- privacy ----------


def test_output_contains_no_header_pii(make_cas: MakeCas) -> None:
    dumped = normalize_cas(make_cas()).model_dump_json()
    for secret in [
        "Ravi Shankar Kumar",
        "ravi.kumar@example.com",
        "98765",
        "ABCPE1234F",
        "1234567/89",
        "1234567",
        "Asha Kumar",
        "Lakeview",
        "560001",
    ]:
        assert secret not in dumped, secret
    assert not contains_pii(dumped)


def test_pii_inside_scheme_names_is_masked(make_cas: MakeCas) -> None:
    cas = scheme_with(make_cas, scheme="Ravi Shankar Kumar ABCPE1234F Fund - Regular - Growth")
    name = normalize_cas(cas).schemes[0].name
    assert "Ravi" not in name
    assert "ABCPE1234F" not in name
    assert "[REDACTED]" in name


def test_pii_inside_parser_warnings_is_masked(make_cas: MakeCas) -> None:
    cas = make_cas(warnings=["Folio 1234567/89 (PAN ABCPE1234F, ravi.kumar@example.com) mismatch"])
    (warning,) = normalize_cas(cas).warnings
    assert "1234567" not in warning
    assert "ABCPE1234F" not in warning
    assert "example.com" not in warning


def test_pii_in_amc_name_is_masked(make_cas: MakeCas) -> None:
    cas = make_cas()
    cas["folios"][0]["amc"] = "Sample MF (contact 9876543210)"
    assert "9876543210" not in normalize_cas(cas).folios[0].amc


pans = st.from_regex(r"[A-Z]{3}[PCHF][A-Z][0-9]{4}[A-Z]", fullmatch=True)
folios = st.from_regex(r"[0-9]{6,11}(/[0-9]{2})?", fullmatch=True)
emails = st.from_regex(r"[a-z]{3,8}\.[a-z]{3,8}@[a-z]{4,8}\.(com|in)", fullmatch=True)
phones = st.from_regex(r"[6-9][0-9]{9}", fullmatch=True)
names = st.from_regex(r"[A-Z][a-z]{3,8} [A-Z][a-z]{3,8}", fullmatch=True)


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pan=pans, folio=folios, email=emails, phone=phones, name=names)
def test_planted_pii_never_reaches_output(
    make_cas: MakeCas, pan: str, folio: str, email: str, phone: str, name: str
) -> None:
    cas = make_cas(folio=folio, pan=pan, warnings=[f"{name} folio {folio} {pan} {email} {phone}"])
    cas["investor_info"].update(name=name, email=email, mobile=phone)
    s = cas["folios"][0]["schemes"][0]
    s["scheme"] = f"{name} Flexi Cap Fund {folio} - Regular Plan - Growth"
    s["nominees"] = [name]
    cas["folios"][0]["amc"] = f"Sample MF {email}"
    dumped = normalize_cas(cas).model_dump_json()
    for secret in (pan, folio, email, phone, name):
        assert secret not in dumped
    assert not contains_pii(dumped)


# ---------- transactions and fields ----------


def test_transactions_are_sorted_by_date_stably(make_cas: MakeCas) -> None:
    cas = make_cas()
    txns = cas["folios"][0]["schemes"][0]["transactions"]
    txns.reverse()
    out = normalize_cas(cas).schemes[0].transactions
    assert [t.date for t in out] == sorted(t.date for t in out)


@pytest.mark.parametrize(
    ("raw_type", "units", "expected"),
    [
        ("PURCHASE", "-10", TxnKind.REVERSAL),
        ("PURCHASE_SIP", "-10", TxnKind.REVERSAL),
        ("REDEMPTION", "5", TxnKind.REVERSAL),
        ("REDEMPTION", "-5", TxnKind.REDEMPTION),
        ("DIVIDEND_REINVEST", "1.5", TxnKind.DIVIDEND_REINVEST),
    ],
)
def test_contradictory_unit_signs_become_reversals(
    make_cas: MakeCas, raw_type: str, units: str, expected: TxnKind
) -> None:
    cas = make_cas()
    cas["folios"][0]["schemes"][0]["transactions"].append(
        {
            "date": "10-Mar-2024",
            "description": "x",
            "amount": "1",
            "units": units,
            "nav": "100",
            "balance": "0",
            "type": raw_type,
        }
    )
    assert normalize_cas(cas).schemes[0].transactions[-1].kind is expected


def test_negative_nav_is_dropped(make_cas: MakeCas) -> None:
    cas = make_cas()
    cas["folios"][0]["schemes"][0]["transactions"][0]["nav"] = "-1"
    assert normalize_cas(cas).schemes[0].transactions[0].nav is None


@pytest.mark.parametrize(
    ("isin", "expected"),
    [
        ("INF000S01011", "INF000S01011"),
        ("inf000s01011", "INF000S01011"),
        ("BAD", None),
        ("", None),
        (None, None),
    ],
)
def test_isin_is_validated(make_cas: MakeCas, isin: str | None, expected: str | None) -> None:
    assert normalize_cas(scheme_with(make_cas, isin=isin)).schemes[0].isin == expected


@pytest.mark.parametrize(("amfi", "expected"), [("100001", "100001"), ("12A", None), (None, None)])
def test_amfi_code_is_validated(make_cas: MakeCas, amfi: str | None, expected: str | None) -> None:
    assert normalize_cas(scheme_with(make_cas, amfi=amfi)).schemes[0].amfi_code == expected


def test_direct_plan_by_advisor_code(make_cas: MakeCas) -> None:
    cas = scheme_with(make_cas, scheme="Sample Flexi Cap Fund - Growth", advisor="INA000000001")
    assert normalize_cas(cas).schemes[0].plan is Plan.DIRECT


def test_elss_detected(make_cas: MakeCas) -> None:
    cas = scheme_with(make_cas, scheme="Sample ELSS Tax Saver Fund - Regular Plan - Growth")
    s = normalize_cas(cas).schemes[0]
    assert s.is_elss
    assert s.asset_class is AssetClass.EQUITY


def test_unreconciled_scheme_adds_warning(make_cas: MakeCas) -> None:
    cas = scheme_with(make_cas, close="45.000")
    p = normalize_cas(cas)
    assert not p.schemes[0].units_reconcile
    (warning,) = p.warnings
    assert warning.startswith("F1-S1:")
    assert "45.000" in warning


def test_empty_scheme_name_gets_placeholder(make_cas: MakeCas) -> None:
    assert (
        normalize_cas(scheme_with(make_cas, scheme="\u200b \n")).schemes[0].name == "Unnamed scheme"
    )


def test_negative_closing_units_are_clamped(make_cas: MakeCas) -> None:
    cas = scheme_with(make_cas, close="-0.001", transactions=[])
    assert normalize_cas(cas).schemes[0].close_units == 0


def test_scheme_without_transactions_is_kept(make_cas: MakeCas) -> None:
    cas = scheme_with(make_cas, open="30.000", transactions=[])
    s = normalize_cas(cas).schemes[0]
    assert s.transactions == ()
    assert s.units_reconcile


def test_folio_without_schemes_is_kept(make_cas: MakeCas) -> None:
    p = normalize_cas(make_cas(schemes=[]))
    assert p.folios[0].schemes == ()


def test_input_is_not_mutated(make_cas: MakeCas) -> None:
    cas = make_cas()
    before = deepcopy(cas)
    normalize_cas(cas)
    assert cas == before


# ---------- helpers ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("05-Jan-2016", date(2016, 1, 5)),
        ("2016-01-05", date(2016, 1, 5)),
        ("05-01-2016", date(2016, 1, 5)),
        ("05/01/2016", date(2016, 1, 5)),
        ("05 Jan 2016", date(2016, 1, 5)),
        (" 05-Jan-2016 ", date(2016, 1, 5)),
        (date(2016, 1, 5), date(2016, 1, 5)),
    ],
)
def test_parse_date(raw: str | date, expected: date) -> None:
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", "Jan 2016", "2016/13/45", "yesterday"])
def test_parse_date_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError, match="unrecognised date"):
        parse_date(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Sample   Fund \n Growth ", "Sample Fund Growth"),
        ("Sample\u200bFund", "Sample Fund"),  # zero-width space (format char)
        ("Sample\u202eFund", "Sample Fund"),  # right-to-left override
        ("Sample\x00Fund\x07", "Sample Fund"),
        ("\u20b9 Fund \u2013 Growth", "\u20b9 Fund \u2013 Growth"),
    ],
)
def test_clean_text(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


def test_clean_text_caps_length() -> None:
    assert len(clean_text("x" * 500)) == 200
    assert len(clean_text("x" * 500, limit=10)) == 10


@pytest.mark.property
@given(text=st.text(max_size=400))
def test_clean_text_output_is_safe(text: str) -> None:
    out = clean_text(text)
    assert len(out) <= 200
    assert out == out.strip()
    assert "\n" not in out
    assert "  " not in out
