from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from trailcut_engine.market import ExitLoadRule, ExitLoadTier, MarketData, SchemeMarket
from trailcut_engine.planner import (
    Action,
    Assumptions,
    Reason,
    SwitchPlan,
    plan_switch,
    rules_for,
)
from trailcut_engine.portfolio import AssetClass, Folio, Plan, Portfolio, Scheme, StatementSource
from trailcut_engine.tax import TaxRegime
from trailcut_engine.tax_rules import TaxRules, parse_tax_rules
from trailcut_engine.testing import buy, make_scheme, sell

D = Decimal
RULES: TaxRules = parse_tax_rules(
    (Path(__file__).resolve().parents[3] / "data" / "tax_rules" / "fy2026_27.yaml").read_text(
        encoding="utf-8"
    )
)
AS_OF = date(2026, 11, 20)
ONE_YEAR_LOAD = ExitLoadRule(tiers=(ExitLoadTier(within_days=365, rate=D("0.01")),))
EQUITY_MARKET = SchemeMarket(
    ter_regular=D("0.0175"), ter_direct=D("0.0075"), exit_load=ONE_YEAR_LOAD
)


def portfolio(*schemes: Scheme) -> Portfolio:
    folios = tuple(
        Folio(
            folio_id=f"F{i}",
            amc="Sample",
            schemes=(s.model_copy(update={"scheme_id": f"F{i}-S1"}),),
        )
        for i, s in enumerate(schemes, start=1)
    )
    return Portfolio(
        source=StatementSource.SAMPLE,
        statement_from=date(2015, 1, 1),
        statement_to=AS_OF,
        folios=folios,
    )


def market(*entries: SchemeMarket) -> MarketData:
    return MarketData(schemes={f"F{i}-S1": m for i, m in enumerate(entries, start=1)})


def plan(p: Portfolio, m: MarketData, **assumptions: object) -> SwitchPlan:
    a = Assumptions(as_of=assumptions.pop("as_of", AS_OF), **assumptions)  # type: ignore[arg-type]
    return plan_switch(p, m, [RULES], a)


def only(sp: SwitchPlan):  # type: ignore[no-untyped-def]
    (d,) = sp.decisions
    return d


# ---------- fixed decisions ----------


def test_direct_plan_is_kept() -> None:
    d = only(
        plan(
            portfolio(make_scheme([buy(date(2020, 1, 1), "10")], plan=Plan.DIRECT)),
            market(EQUITY_MARKET),
        )
    )
    assert (d.action, d.reason) == (Action.KEEP, Reason.ALREADY_DIRECT)
    assert d.switch_on is None
    assert d.tax == 0


def test_missing_ter_needs_review() -> None:
    d = only(
        plan(
            portfolio(make_scheme([buy(date(2020, 1, 1), "10")])),
            market(SchemeMarket(ter_regular=D("0.02"))),
        )
    )
    assert (d.action, d.reason) == (Action.REVIEW, Reason.NO_TER_DATA)


def test_unknown_cost_needs_review() -> None:
    d = only(plan(portfolio(make_scheme([], open_units="10")), market(EQUITY_MARKET)))
    assert (d.action, d.reason) == (Action.REVIEW, Reason.UNKNOWN_COST)


def test_no_ter_gap_is_kept() -> None:
    m = SchemeMarket(ter_regular=D("0.01"), ter_direct=D("0.01"))
    d = only(plan(portfolio(make_scheme([buy(date(2020, 1, 1), "10")])), market(m)))
    assert (d.action, d.reason) == (Action.KEEP, Reason.NO_TER_GAP)


# ---------- switch now ----------


def test_old_lot_inside_exemption_switches_now_for_free() -> None:
    # Gain 500 per unit x 10 = 5,000: inside the exemption, no exit load.
    d = only(
        plan(
            portfolio(make_scheme([buy(date(2020, 1, 1), "10")], nav="150")), market(EQUITY_MARKET)
        )
    )
    assert (d.action, d.reason, d.switch_on) == (Action.SWITCH_NOW, Reason.SWITCH_FREE, AS_OF)
    assert (d.tax, d.exit_load, d.regime) == (D(0), D(0), TaxRegime.EQUITY_LTCG)
    assert d.exemption_used == D(500)
    assert d.net_benefit > 0
    assert d.explanation == "Switch now: no tax and no exit load."


def test_lot_at_a_loss_switches_now() -> None:
    d = only(
        plan(
            portfolio(make_scheme([buy(date(2026, 6, 1), "100")], nav="80")),
            market(SchemeMarket(ter_regular=D("0.02"), ter_direct=D("0.01"))),
        )
    )
    assert d.action is Action.SWITCH_NOW
    assert d.gain < 0
    assert d.tax == 0


def test_big_long_term_gain_switches_now_and_pays_tax() -> None:
    # 2,000 units bought at 100, now 250: gain 3 lakh, 1.75 lakh above exemption.
    s = make_scheme([buy(date(2019, 1, 1), "2000")], nav="250")
    sp = plan(portfolio(s), market(EQUITY_MARKET), use_next_fy_exemption=False)
    d = only(sp)
    assert (d.action, d.reason) == (Action.SWITCH_NOW, Reason.SWITCH_WORTH_IT)
    # (3,00,000 - 1,25,000) x 12.5% x 1.04 = 22,750.
    assert d.tax == D("22750.00")
    assert sp.totals.tax == D("22750.00")
    assert sp.fy_tax[0].tax == D("22750.00")
    assert sp.totals.break_even_months is not None
    assert "₹22,750" in d.explanation


# ---------- wait ----------


def test_short_term_lot_with_exit_load_waits_until_long_term() -> None:
    # Bought 15 Dec 2025: STCG 20% and 1% exit load until 16 Dec 2026, 26 days away.
    s = make_scheme([buy(date(2025, 12, 15), "1000")], nav="150")
    d = only(plan(portfolio(s), market(EQUITY_MARKET)))
    assert d.action is Action.WAIT
    assert d.switch_on == date(2026, 12, 16)
    assert d.reason is Reason.WAIT_LONG_TERM
    assert d.regime is TaxRegime.EQUITY_LTCG
    assert d.exit_load == 0
    assert d.explanation.startswith("Wait until 16 Dec 2026")


def test_elss_never_switches_before_lock_in() -> None:
    s = make_scheme([buy(date(2025, 6, 10), "100")], nav="150", is_elss=True)
    d = only(plan(portfolio(s), market(SchemeMarket(ter_regular=D("0.02"), ter_direct=D("0.01")))))
    assert d.action is Action.WAIT
    assert d.switch_on is not None
    assert d.switch_on >= date(2028, 6, 10)
    assert d.reason is Reason.WAIT_LOCK_IN
    assert "lock-in" in d.explanation


def test_elss_lock_in_past_horizon_is_kept() -> None:
    s = make_scheme([buy(date(2026, 11, 10), "100")], nav="150", is_elss=True)
    sp = plan(
        portfolio(s),
        market(SchemeMarket(ter_regular=D("0.02"), ter_direct=D("0.01"))),
        horizon_years=1,
    )
    d = only(sp)
    assert (d.action, d.reason) == (Action.KEEP, Reason.KEEP_LOCKED_PAST_HORIZON)


def test_switch_all_now_baseline_marks_locked_elss() -> None:
    s = make_scheme([buy(date(2025, 6, 10), "100")], nav="150", is_elss=True)
    sp = plan(portfolio(s), market(SchemeMarket(ter_regular=D("0.02"), ter_direct=D("0.01"))))
    assert sp.switch_all_now.lots_switched == 0


def test_second_lot_waits_for_next_years_exemption() -> None:
    # Two lots, each with 1 lakh LTCG, 11 days before 1 April: the first uses this
    # year's exemption; the second is better off switching on 1 April.
    rows = [buy(date(2020, 1, 1), "1000", "100"), buy(date(2020, 2, 1), "1000", "100")]
    s = make_scheme(rows, nav="200", on=date(2027, 3, 21))
    sp = plan(
        portfolio(s),
        market(SchemeMarket(ter_regular=D("0.02"), ter_direct=D("0.01"))),
        as_of=date(2027, 3, 21),
    )
    first, second = sp.decisions
    assert first.action is Action.SWITCH_NOW
    assert first.exemption_used == D(100000)
    assert second.action is Action.WAIT
    assert (second.switch_on, second.reason) == (date(2027, 4, 1), Reason.WAIT_NEXT_FY)
    assert second.tax == 0
    assert [f.financial_year for f in sp.fy_tax] == ["2026-27", "2027-28"]
    assert sp.fy_tax[1].rules_assumed
    assert any("2027-28" in n for n in sp.notes)
    assert [step.label for step in sp.timeline] == ["Now", "Apr 2027"]
    assert sp.timeline[1].on == date(2027, 4, 1)


def test_disabling_next_fy_exemption_switches_both_now() -> None:
    rows = [buy(date(2020, 1, 1), "1000", "100"), buy(date(2020, 2, 1), "1000", "100")]
    s = make_scheme(rows, nav="200", on=date(2027, 3, 21))
    sp = plan(
        portfolio(s),
        market(SchemeMarket(ter_regular=D("0.02"), ter_direct=D("0.01"))),
        as_of=date(2027, 3, 21),
        use_next_fy_exemption=False,
    )
    assert [d.action for d in sp.decisions] == [Action.SWITCH_NOW, Action.SWITCH_NOW]
    assert sum((d.exemption_used for d in sp.decisions), D(0)) == D(125000)


def test_other_ltcg_reduces_available_exemption() -> None:
    s = make_scheme([buy(date(2020, 1, 1), "1000")], nav="200")
    sp = plan(
        portfolio(s),
        market(EQUITY_MARKET),
        other_equity_ltcg_this_fy=D(125000),
        use_next_fy_exemption=False,
    )
    d = only(sp)
    assert d.exemption_used == 0
    assert d.tax == D("13000.00")  # 1,00,000 x 12.5% x 1.04


# ---------- keep ----------


def test_debt_with_big_slab_gain_and_tiny_gap_is_kept() -> None:
    s = make_scheme([buy(date(2024, 1, 1), "1000", "10")], nav="100", asset_class=AssetClass.DEBT)
    d = only(
        plan(portfolio(s), market(SchemeMarket(ter_regular=D("0.006"), ter_direct=D("0.004"))))
    )
    assert (d.action, d.reason) == (Action.KEEP, Reason.KEEP_COST_EXCEEDS_BENEFIT)
    assert d.tax == 0
    assert d.net_benefit == 0
    assert "Keep" in d.explanation


def test_grandfathered_lot_uses_fmv() -> None:
    s = make_scheme([buy(date(2017, 1, 1), "2000", "50")], nav="200")
    m = EQUITY_MARKET.model_copy(update={"fmv_2018_per_unit": D(150)})
    d = only(plan(portfolio(s), market(m), use_next_fy_exemption=False))
    assert d.grandfathered
    assert d.gain == D(2000 * 200 - 2000 * 150)


# ---------- totals and baselines ----------


def test_totals_add_up_and_baselines_exist() -> None:
    s1 = make_scheme([buy(date(2020, 1, 1), "100")], nav="150")
    s2 = make_scheme([buy(date(2025, 12, 15), "1000")], nav="150")
    sp = plan(portfolio(s1, s2), market(EQUITY_MARKET, EQUITY_MARKET))
    switching = [d for d in sp.decisions if d.switch_on]
    assert sp.totals.lots_switched == len(switching)
    assert sp.totals.tax == sum((d.tax for d in switching), D(0))
    assert sp.totals.net_benefit == sum((d.net_benefit for d in switching), D(0))
    assert sp.never_switch.net_benefit == 0
    assert sp.totals.net_benefit >= sp.switch_all_now.net_benefit
    assert [x.scheme_id for x in sp.schemes] == ["F1-S1", "F2-S1"]
    assert sp.schemes[0].yearly_leak == D("150.00")  # 15,000 x 1%


def test_plan_is_deterministic() -> None:
    s = make_scheme(
        [buy(date(2020, 1, 1), "100"), buy(date(2025, 12, 15), "50"), sell(date(2021, 1, 1), "30")]
    )
    m = market(EQUITY_MARKET)
    assert plan(portfolio(s), m) == plan(portfolio(s), m)


def test_surcharge_note_always_present() -> None:
    sp = plan(portfolio(make_scheme([buy(date(2020, 1, 1), "10")])), market(EQUITY_MARKET))
    assert any("surcharge" in n for n in sp.notes)


def test_rules_for_falls_back_to_latest() -> None:
    assert rules_for(date(2026, 6, 1), [RULES]) == (RULES, False)
    assert rules_for(date(2030, 6, 1), [RULES]) == (RULES, True)
    assert rules_for(date(2020, 6, 1), [RULES]) == (RULES, True)
    with pytest.raises(ValueError, match="at least one"):
        rules_for(date(2026, 6, 1), [])


# ---------- properties ----------


@st.composite
def random_portfolios(draw: st.DrawFn) -> tuple[Portfolio, MarketData]:
    schemes = []
    markets = []
    for _ in range(draw(st.integers(1, 4))):
        rows = []
        for _ in range(draw(st.integers(1, 6))):
            days_ago = draw(st.integers(1, 365 * 10))
            units = draw(st.integers(1, 3000))
            nav = draw(st.integers(10, 300))
            rows.append(buy(AS_OF - timedelta(days=days_ago), str(units), str(nav)))
        schemes.append(
            make_scheme(
                rows,
                nav=str(draw(st.integers(10, 400))),
                is_elss=draw(st.booleans()),
                asset_class=draw(
                    st.sampled_from([AssetClass.EQUITY, AssetClass.DEBT, AssetClass.HYBRID])
                ),
                plan=draw(st.sampled_from([Plan.REGULAR, Plan.REGULAR, Plan.DIRECT])),
            )
        )
        ter_d = D(draw(st.integers(1, 100))) / 10000
        markets.append(
            SchemeMarket(
                ter_regular=ter_d + D(draw(st.integers(0, 150))) / 10000,
                ter_direct=ter_d,
                exit_load=draw(st.sampled_from([None, ONE_YEAR_LOAD])),
            )
        )
    return portfolio(*schemes), market(*markets)


@pytest.mark.property
@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
@given(pm=random_portfolios())
def test_plan_invariants(pm: tuple[Portfolio, MarketData]) -> None:
    p, m = pm
    sp = plan(p, m)
    lot_ids = [d.lot_id for d in sp.decisions]
    assert len(lot_ids) == len(set(lot_ids))
    elss = {s.scheme_id for s in p.schemes if s.is_elss}
    for d in sp.decisions:
        if d.switch_on is None:
            assert (d.tax, d.exit_load, d.net_benefit) == (D(0), D(0), D(0))
            continue
        assert d.switch_on >= AS_OF
        assert d.tax >= 0
        assert d.net_benefit > 0 or d.action is Action.SWITCH_NOW
        if d.scheme_id in elss:
            assert d.switch_on >= d.buy_date.replace(year=d.buy_date.year + 3) - timedelta(days=1)
    # The yearly exemption is never over-used.
    for f in sp.fy_tax:
        assert f.exemption_used <= RULES.equity.ltcg_exemption_per_fy.value
    used: dict[str, Decimal] = {}
    for d in sp.decisions:
        if d.switch_on:
            key = str(d.switch_on.year if d.switch_on.month >= 4 else d.switch_on.year - 1)
            used[key] = used.get(key, D(0)) + d.exemption_used
    assert all(v <= D(125000) for v in used.values())
    # Never worse than switching everything eligible today.
    assert sp.totals.net_benefit >= sp.switch_all_now.net_benefit


@pytest.mark.property
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
@given(pm=random_portfolios())
def test_plan_is_deterministic_for_random_inputs(pm: tuple[Portfolio, MarketData]) -> None:
    p, m = pm
    assert plan(p, m) == plan(p, m)
