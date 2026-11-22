from datetime import date
from decimal import Decimal

from trailcut_engine.market import MarketData, SchemeMarket
from trailcut_engine.portfolio import Folio, Plan, Portfolio, Scheme, StatementSource
from trailcut_engine.projection import commission_leak
from trailcut_engine.report import build_report
from trailcut_engine.testing import buy, make_scheme

D = Decimal
ON = date(2026, 11, 20)


def portfolio(*schemes: Scheme) -> Portfolio:
    folios = tuple(
        Folio(folio_id=f"F{i}", amc="A", schemes=(s.model_copy(update={"scheme_id": f"F{i}-S1"}),))
        for i, s in enumerate(schemes, start=1)
    )
    return Portfolio(
        source=StatementSource.SAMPLE,
        statement_from=date(2020, 1, 1),
        statement_to=ON,
        folios=folios,
    )


REG = make_scheme([buy(date(2022, 1, 1), "1000")], nav="100")  # value 1,00,000
DIRECT = make_scheme([buy(date(2022, 1, 1), "500")], nav="100", plan=Plan.DIRECT)
TER = SchemeMarket(ter_regular=D("0.02"), ter_direct=D("0.01"))


def test_leak_for_one_regular_fund() -> None:
    r = build_report(portfolio(REG), MarketData(schemes={"F1-S1": TER}))
    expected = commission_leak(D(100000), D("0.02"), D("0.01"), D("0.12"), years=20)
    assert r.yearly_leak == D("1000.00")
    assert r.leak_20y == expected.leak
    (leak,) = r.leaks
    assert (leak.yearly_leak, leak.leak_20y) == (D("1000.00"), expected.leak)
    assert r.missing_ter == ()
    assert r.regular_share == D(1)


def test_direct_funds_have_zero_leak_and_count_in_share() -> None:
    r = build_report(portfolio(REG, DIRECT), MarketData(schemes={"F1-S1": TER}))
    assert r.leaks[1].yearly_leak == 0
    assert r.regular_share == D("0.6667")
    assert r.summary.value == D(150000)


def test_missing_ter_is_listed_not_guessed() -> None:
    r = build_report(portfolio(REG), MarketData())
    assert r.missing_ter == ("F1-S1",)
    assert r.leaks[0].yearly_leak is None
    assert r.yearly_leak == 0


def test_growth_chart_covers_20_years_and_gap_matches_leak() -> None:
    r = build_report(portfolio(REG), MarketData(schemes={"F1-S1": TER}))
    assert [p.year for p in r.growth] == list(range(21))
    assert r.growth[0].regular == r.growth[0].direct == D(100000)
    assert r.growth[-1].direct - r.growth[-1].regular == r.leak_20y


def test_expected_return_is_reported_and_used() -> None:
    low = build_report(
        portfolio(REG), MarketData(schemes={"F1-S1": TER}), expected_return=D("0.06")
    )
    high = build_report(
        portfolio(REG), MarketData(schemes={"F1-S1": TER}), expected_return=D("0.14")
    )
    assert low.expected_return == D("0.06")
    assert high.leak_20y > low.leak_20y


def test_empty_portfolio_report() -> None:
    r = build_report(portfolio(), MarketData())
    assert (r.yearly_leak, r.leak_10y, r.regular_share) == (D(0), D(0), D(0))
    assert len(r.growth) == 21
