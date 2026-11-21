from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from trailcut_engine.tax_rules import TaxRules, TaxRulesError, fy_label, parse_tax_rules

RULES_DIR = Path(__file__).resolve().parents[3] / "data" / "tax_rules"
FY2026_27_TEXT = (RULES_DIR / "fy2026_27.yaml").read_text(encoding="utf-8")


def load_raw() -> dict[str, Any]:
    raw = yaml.safe_load(FY2026_27_TEXT)
    assert isinstance(raw, dict)
    return raw


def dump(raw: object) -> str:
    return yaml.safe_dump(raw, allow_unicode=True)


@pytest.fixture(scope="module")
def rules() -> TaxRules:
    return parse_tax_rules(FY2026_27_TEXT)


# ---------- the shipped FY2026-27 file ----------


@pytest.mark.parametrize(
    ("section", "name", "expected"),
    [
        ("equity", "stcg_rate", Decimal("0.20")),
        ("equity", "ltcg_rate", Decimal("0.125")),
        ("equity", "ltcg_exemption_per_fy", Decimal(125000)),
        ("equity", "long_term_after_months", 12),
        ("equity", "equity_oriented_min_equity_share", Decimal("0.65")),
        ("equity", "grandfathering_fmv_date", date(2018, 1, 31)),
        ("equity", "elss_lock_in_years", 3),
        ("debt", "specified_fund_cutoff_date", date(2023, 4, 1)),
        ("debt", "legacy_long_term_after_months", 24),
        ("debt", "legacy_ltcg_rate", Decimal("0.125")),
        ("surcharge_and_cess", "health_education_cess_rate", Decimal("0.04")),
    ],
)
def test_fy2026_27_values(rules: TaxRules, section: str, name: str, expected: object) -> None:
    value = getattr(getattr(rules, section), name).value
    assert value == expected
    assert type(value) is type(expected)


def test_fy2026_27_period(rules: TaxRules) -> None:
    assert rules.financial_year == "2026-27"
    assert rules.effective_from == date(2026, 4, 1)
    assert rules.effective_to == date(2027, 3, 31)


def test_every_rule_has_https_source_and_legal_ref(rules: TaxRules) -> None:
    for section in (rules.equity, rules.debt, rules.surcharge_and_cess):
        for name in type(section).model_fields:
            rule = getattr(section, name)
            assert rule.source_url.scheme == "https", name
            assert rule.legal_ref.strip(), name


def test_rules_are_immutable(rules: TaxRules) -> None:
    with pytest.raises(ValueError, match="frozen"):
        rules.equity.stcg_rate.value = Decimal("0.15")  # type: ignore[misc]


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (date(2026, 3, 31), False),
        (date(2026, 4, 1), True),
        (date(2026, 12, 31), True),
        (date(2027, 3, 31), True),
        (date(2027, 4, 1), False),
    ],
)
def test_covers_boundaries(rules: TaxRules, on: date, expected: bool) -> None:
    assert rules.covers(on) is expected


@pytest.mark.property
@given(on=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
def test_covers_matches_period(on: date) -> None:
    rules = parse_tax_rules(FY2026_27_TEXT)
    assert rules.covers(on) == (rules.effective_from <= on <= rules.effective_to)


@pytest.mark.parametrize(
    ("start_year", "label"),
    [(2026, "2026-27"), (2099, "2099-00"), (2009, "2009-10"), (2000, "2000-01")],
)
def test_fy_label(start_year: int, label: str) -> None:
    assert fy_label(start_year) == label


# ---------- schema enforcement ----------


def test_unquoted_float_is_rejected() -> None:
    text = FY2026_27_TEXT.replace('value: "0.20"', "value: 0.20", 1)
    with pytest.raises(TaxRulesError, match="floats are not allowed"):
        parse_tax_rules(text)


@pytest.mark.parametrize(
    ("section", "name"), [("equity", "elss_lock_in_years"), ("equity", "stcg_rate")]
)
def test_boolean_value_is_rejected(section: str, name: str) -> None:
    raw = load_raw()
    raw[section][name]["value"] = True
    with pytest.raises(TaxRulesError, match="booleans"):
        parse_tax_rules(dump(raw))


@pytest.mark.parametrize("field", ["source_url", "legal_ref", "value"])
def test_missing_rule_field_is_rejected(field: str) -> None:
    raw = load_raw()
    del raw["equity"]["stcg_rate"][field]
    with pytest.raises(TaxRulesError, match=field):
        parse_tax_rules(dump(raw))


def test_empty_legal_ref_is_rejected() -> None:
    raw = load_raw()
    raw["equity"]["stcg_rate"]["legal_ref"] = ""
    with pytest.raises(TaxRulesError, match="legal_ref"):
        parse_tax_rules(dump(raw))


@pytest.mark.parametrize("url", ["http://example.gov.in/act", "ftp://example.gov.in", "not a url"])
def test_non_https_source_is_rejected(url: str) -> None:
    raw = load_raw()
    raw["equity"]["stcg_rate"]["source_url"] = url
    with pytest.raises(TaxRulesError, match="source_url"):
        parse_tax_rules(dump(raw))


@pytest.mark.parametrize("value", ["-0.01", "1.01", "20"])
def test_rate_out_of_range_is_rejected(value: str) -> None:
    raw = load_raw()
    raw["equity"]["stcg_rate"]["value"] = value
    with pytest.raises(TaxRulesError, match="between 0 and 1"):
        parse_tax_rules(dump(raw))


@pytest.mark.parametrize("value", ["0", "1"])
def test_rate_edges_are_allowed(value: str) -> None:
    raw = load_raw()
    raw["equity"]["stcg_rate"]["value"] = value
    assert parse_tax_rules(dump(raw)).equity.stcg_rate.value == Decimal(value)


def test_negative_exemption_is_rejected() -> None:
    raw = load_raw()
    raw["equity"]["ltcg_exemption_per_fy"]["value"] = "-1"
    with pytest.raises(TaxRulesError, match="negative"):
        parse_tax_rules(dump(raw))


@pytest.mark.parametrize("value", ["0", "-3"])
def test_non_positive_count_is_rejected(value: str) -> None:
    raw = load_raw()
    raw["equity"]["elss_lock_in_years"]["value"] = value
    with pytest.raises(TaxRulesError, match="greater than 0"):
        parse_tax_rules(dump(raw))


def test_unknown_rule_is_rejected() -> None:
    raw = load_raw()
    raw["equity"]["surprise_rate"] = {
        "value": "0.1",
        "legal_ref": "x",
        "source_url": "https://example.gov.in",
    }
    with pytest.raises(TaxRulesError, match="surprise_rate"):
        parse_tax_rules(dump(raw))


@pytest.mark.parametrize("section", ["equity", "debt", "surcharge_and_cess"])
def test_missing_section_is_rejected(section: str) -> None:
    raw = load_raw()
    del raw[section]
    with pytest.raises(TaxRulesError, match=section):
        parse_tax_rules(dump(raw))


def test_wrong_schema_version_is_rejected() -> None:
    raw = load_raw()
    raw["schema_version"] = 2
    with pytest.raises(TaxRulesError, match="schema_version"):
        parse_tax_rules(dump(raw))


@pytest.mark.parametrize(
    ("start", "end", "label", "match"),
    [
        (date(2026, 4, 2), date(2027, 3, 31), "2026-27", "1 April"),
        (date(2026, 4, 1), date(2027, 4, 1), "2026-27", "31 March 2027"),
        (date(2026, 4, 1), date(2027, 3, 31), "2025-26", "does not match"),
        (date(2026, 4, 1), date(2027, 3, 31), "FY27", "pattern"),
    ],
)
def test_financial_year_inconsistency_is_rejected(
    start: date, end: date, label: str, match: str
) -> None:
    raw = load_raw()
    raw.update(effective_from=start, effective_to=end, financial_year=label)
    with pytest.raises(TaxRulesError, match=match):
        parse_tax_rules(dump(raw))


@pytest.mark.property
@given(start_year=st.integers(min_value=2000, max_value=2200))
def test_any_well_formed_financial_year_is_accepted(start_year: int) -> None:
    raw = load_raw()
    raw.update(
        effective_from=date(start_year, 4, 1),
        effective_to=date(start_year + 1, 3, 31),
        financial_year=fy_label(start_year),
    )
    rules = parse_tax_rules(dump(raw))
    assert rules.covers(date(start_year, 4, 1))
    assert not rules.covers(date(start_year + 1, 4, 1))


@pytest.mark.parametrize("text", ["", "- a\n- b\n", "just a string", "key: [unclosed"])
def test_non_mapping_or_invalid_yaml_is_rejected(text: str) -> None:
    with pytest.raises(TaxRulesError):
        parse_tax_rules(text)
