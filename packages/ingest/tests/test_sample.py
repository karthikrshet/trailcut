from datetime import date

import pytest

from trailcut_engine.dates import add_years
from trailcut_engine.portfolio import AssetClass, Plan, Portfolio, StatementSource, TxnKind
from trailcut_ingest.pii import contains_pii
from trailcut_ingest.sample import load_sample_portfolio, sample_cas_dict

GRANDFATHER_CUTOFF = date(2018, 2, 1)
DEBT_CUTOFF = date(2023, 4, 1)


@pytest.fixture(scope="module")
def sample() -> Portfolio:
    return load_sample_portfolio()


def test_sample_is_marked_as_sample(sample: Portfolio) -> None:
    assert sample.source is StatementSource.SAMPLE


def test_sample_has_six_schemes_that_reconcile(sample: Portfolio) -> None:
    assert len(sample.schemes) == 6
    assert all(s.units_reconcile for s in sample.schemes)
    assert sample.warnings == ()


def test_sample_is_cached_and_immutable(sample: Portfolio) -> None:
    assert load_sample_portfolio() is sample


def test_sample_contains_no_pii(sample: Portfolio) -> None:
    dumped = sample.model_dump_json()
    for secret in ("Demo Investor", "demo@example.com", "AAAPZ0000Z", "DEMO10001", "Demo Nominee"):
        assert secret not in dumped
    assert not contains_pii(dumped)


def test_raw_sample_is_synthetic() -> None:
    raw = sample_cas_dict()
    assert raw["investor_info"]["email"].endswith("@example.com")
    for folio in raw["folios"]:
        for scheme in folio["schemes"]:
            assert scheme["scheme"].startswith("Sample ")
            assert scheme["isin"].startswith("INF000")


# The sample exists to exercise every planning case. Guard each one.


def test_has_pre_2018_grandfathered_equity_lots(sample: Portfolio) -> None:
    flexi = sample.scheme("F1-S1")
    assert flexi.asset_class is AssetClass.EQUITY
    assert any(t.date < GRANDFATHER_CUTOFF and t.is_unit_inflow for t in flexi.transactions)


def test_has_a_partial_redemption(sample: Portfolio) -> None:
    kinds = [t.kind for t in sample.scheme("F1-S1").transactions]
    assert TxnKind.REDEMPTION in kinds


def test_has_elss_lots_inside_and_outside_lock_in(sample: Portfolio) -> None:
    elss = sample.scheme("F2-S1")
    assert elss.is_elss
    buys = [t.date for t in elss.transactions if t.is_unit_inflow]
    as_of = sample.statement_to
    assert any(add_years(d, 3) <= as_of for d in buys)
    assert any(add_years(d, 3) > as_of for d in buys)


def test_has_debt_lots_before_and_after_april_2023(sample: Portfolio) -> None:
    debt = sample.scheme("F3-S1")
    assert debt.asset_class is AssetClass.DEBT
    buys = [t.date for t in debt.transactions if t.is_unit_inflow]
    assert any(d < DEBT_CUTOFF for d in buys)
    assert any(d >= DEBT_CUTOFF for d in buys)


def test_has_an_already_direct_fund(sample: Portfolio) -> None:
    assert sample.scheme("F5-S1").plan is Plan.DIRECT


def test_has_short_term_lots_under_one_year(sample: Portfolio) -> None:
    for scheme_id in ("F4-S1", "F6-S1"):
        (buy,) = [t for t in sample.scheme(scheme_id).transactions if t.is_unit_inflow]
        assert (sample.statement_to - buy.date).days < 365


def test_regular_schemes_dominate(sample: Portfolio) -> None:
    plans = [s.plan for s in sample.schemes]
    assert plans.count(Plan.REGULAR) == 5
    assert Plan.UNKNOWN not in plans
