"""End to end on the synthetic sample: ingest -> engine plan. Guards the demo story."""

import json
from datetime import date
from pathlib import Path

import pytest

from trailcut_engine.market import SchemeMarket, market_for_portfolio
from trailcut_engine.planner import Action, Assumptions, Reason, SwitchPlan, plan_switch
from trailcut_engine.summary import summarize
from trailcut_engine.tax_rules import parse_tax_rules
from trailcut_ingest.pii import contains_pii
from trailcut_ingest.sample import load_sample_portfolio

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan() -> SwitchPlan:
    p = load_sample_portfolio()
    raw = json.loads((ROOT / "data" / "samples" / "sample_market.json").read_text(encoding="utf-8"))
    by_isin = {k: SchemeMarket.model_validate(v) for k, v in raw["schemes"].items()}
    rules = parse_tax_rules(
        (ROOT / "data" / "tax_rules" / "fy2026_27.yaml").read_text(encoding="utf-8")
    )
    return plan_switch(
        p, market_for_portfolio(p, by_isin), [rules], Assumptions(as_of=date(2026, 11, 20))
    )


def actions(plan: SwitchPlan, scheme_id: str) -> set[Action]:
    return {d.action for d in plan.decisions if d.scheme_id == scheme_id}


def test_every_market_entry_maps_to_a_sample_scheme(plan: SwitchPlan) -> None:
    assert all(d.reason is not Reason.NO_TER_DATA for d in plan.decisions)


def test_direct_index_fund_is_kept(plan: SwitchPlan) -> None:
    assert actions(plan, "F5-S1") == {Action.KEEP}


def test_debt_fund_is_kept_because_slab_tax_outweighs_the_gap(plan: SwitchPlan) -> None:
    assert {d.reason for d in plan.decisions if d.scheme_id == "F3-S1"} == {
        Reason.KEEP_COST_EXCEEDS_BENEFIT
    }


def test_small_cap_waits_until_long_term(plan: SwitchPlan) -> None:
    (d,) = [d for d in plan.decisions if d.scheme_id == "F6-S1"]
    assert (d.action, d.switch_on, d.reason) == (
        Action.WAIT,
        date(2026, 12, 16),
        Reason.WAIT_LONG_TERM,
    )
    assert d.explanation.startswith("Wait until 16 Dec 2026")


def test_balanced_advantage_waits_until_long_term(plan: SwitchPlan) -> None:
    (d,) = [d for d in plan.decisions if d.scheme_id == "F4-S1"]
    assert (d.action, d.switch_on) == (Action.WAIT, date(2027, 3, 11))


def test_elss_lots_switch_only_after_lock_in(plan: SwitchPlan) -> None:
    for d in plan.decisions:
        if d.scheme_id == "F2-S1" and d.switch_on is not None:
            assert d.switch_on >= d.buy_date.replace(year=d.buy_date.year + 3)


def test_flexi_cap_uses_both_years_exemptions(plan: SwitchPlan) -> None:
    reasons = {d.reason for d in plan.decisions if d.scheme_id == "F1-S1"}
    assert Reason.WAIT_NEXT_FY in reasons
    assert plan.fy_tax[0].exemption_used == plan.fy_tax[1].exemption_used == 125000


def test_plan_beats_switching_everything_now(plan: SwitchPlan) -> None:
    assert plan.totals.net_benefit > plan.switch_all_now.net_benefit
    assert plan.totals.tax < plan.switch_all_now.tax


def test_timeline_starts_now_and_is_monthly(plan: SwitchPlan) -> None:
    assert plan.timeline[0].label == "Now"
    assert plan.timeline[1].label == "Dec 2026"
    labels = [t.label for t in plan.timeline]
    assert len(labels) == len(set(labels))


def test_summary_and_plan_contain_no_pii(plan: SwitchPlan) -> None:
    summary = summarize(load_sample_portfolio())
    assert not contains_pii(plan.model_dump_json())
    assert not contains_pii(summary.model_dump_json())
