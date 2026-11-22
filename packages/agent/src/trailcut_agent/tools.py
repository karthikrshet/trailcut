"""Agent tools: thin, typed adapters from a tool call to engine functions.

Tools are the only way an agent gets a number. Each handler takes validated input,
calls the engine, and returns JSON-ready data. No arithmetic happens here beyond
selecting fields. Outputs never contain PII (the portfolio has none to give).

Example:
    >>> ctx = ToolContext(portfolio, market, rules, assumptions)  # doctest: +SKIP
    >>> run_tool("get_switch_plan", {}, ctx)["totals"]["tax"]  # doctest: +SKIP
    '44494.85'
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trailcut_engine.market import MarketData
from trailcut_engine.planner import Assumptions, SwitchPlan, plan_switch
from trailcut_engine.portfolio import Folio, Portfolio
from trailcut_engine.report import Report, build_report
from trailcut_engine.tax_rules import TaxRules

MAX_LOTS_IN_TOOL_OUTPUT = 25


class ToolError(ValueError):
    """A tool call that can't be served (bad id, bad input). Shown to the model."""


@dataclass
class ToolContext:
    portfolio: Portfolio
    market: MarketData
    rules: Sequence[TaxRules]
    assumptions: Assumptions
    _plan: SwitchPlan | None = field(default=None, repr=False)
    _report: Report | None = field(default=None, repr=False)

    @property
    def plan(self) -> SwitchPlan:
        if self._plan is None:
            self._plan = plan_switch(self.portfolio, self.market, self.rules, self.assumptions)
        return self._plan

    @property
    def report(self) -> Report:
        if self._report is None:
            self._report = build_report(
                self.portfolio, self.market, expected_return=self.assumptions.expected_return
            )
        return self._report

    def scheme_ids(self) -> set[str]:
        return {s.scheme_id for s in self.portfolio.schemes}


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoInput(_Input):
    pass


SchemeId = Annotated[str, Field(pattern=r"^F[0-9]+-S[0-9]+$", description="Fund id such as F1-S1")]


class FundInput(_Input):
    scheme_id: SchemeId


class LotInput(_Input):
    lot_id: Annotated[
        str, Field(pattern=r"^F[0-9]+-S[0-9]+-L[0-9]{3,}$", description="Lot id such as F1-S1-L004")
    ]


class WhatIfInput(_Input):
    expected_return: Annotated[Decimal, Field(ge=Decimal("-0.5"), le=Decimal("0.5"))] | None = (
        Field(
            default=None, description="Yearly return before fees as a fraction, e.g. 0.10 for 10%"
        )
    )
    slab_rate: Annotated[Decimal, Field(ge=0, le=1)] | None = Field(
        default=None, description="Income-tax slab as a fraction, e.g. 0.2 for 20%"
    )
    horizon_years: Annotated[int, Field(ge=1, le=40)] | None = None
    use_next_fy_exemption: bool | None = None


class SimulateInput(_Input):
    scheme_ids: Annotated[list[SchemeId], Field(min_length=1, max_length=20)]
    on_date: date | None = Field(default=None, description="ISO date; defaults to the plan date")


# ---------- handlers ----------


def get_portfolio_summary(_: NoInput, ctx: ToolContext) -> dict[str, Any]:
    s = ctx.report.summary
    return {
        "as_of": s.as_of.isoformat(),
        "value": str(s.value),
        "invested": str(s.invested),
        "gain": str(s.gain),
        "xirr": None if s.xirr is None else str(s.xirr),
        "regular_value": str(s.regular_value),
        "direct_value": str(s.direct_value),
        "funds": [
            {
                "scheme_id": f.scheme_id,
                "name": f.name,
                "plan": f.plan.value,
                "asset_class": f.asset_class.value,
                "is_elss": f.is_elss,
                "value": str(f.value),
                "invested": str(f.invested),
                "xirr": None if f.xirr is None else str(f.xirr),
            }
            for f in s.schemes
        ],
    }


def get_commission_leak(_: NoInput, ctx: ToolContext) -> dict[str, Any]:
    r = ctx.report
    return {
        "projection_years": [10, 20],
        "yearly_leak": str(r.yearly_leak),
        "leak_10y": str(r.leak_10y),
        "leak_20y": str(r.leak_20y),
        "regular_share": str(r.regular_share),
        "expected_return": str(r.expected_return),
        "funds_without_expense_ratio": list(r.missing_ter),
        "funds": [_dump(x) for x in r.leaks],
    }


def get_switch_plan(_: NoInput, ctx: ToolContext) -> dict[str, Any]:
    p = ctx.plan
    return {
        "as_of": p.as_of.isoformat(),
        "totals": _dump(p.totals),
        "switch_all_now": _dump(p.switch_all_now),
        "fy_tax": [_dump(f) for f in p.fy_tax],
        "timeline": [_dump(t) for t in p.timeline],
        "funds": [_dump(s) for s in p.schemes],
        "notes": list(p.notes),
    }


def get_fund_detail(inp: FundInput, ctx: ToolContext) -> dict[str, Any]:
    if inp.scheme_id not in ctx.scheme_ids():
        raise ToolError(f"No fund with id {inp.scheme_id}. Known ids: {sorted(ctx.scheme_ids())}")
    summary = next(s for s in ctx.report.summary.schemes if s.scheme_id == inp.scheme_id)
    leak = next(x for x in ctx.report.leaks if x.scheme_id == inp.scheme_id)
    plan = next(x for x in ctx.plan.schemes if x.scheme_id == inp.scheme_id)
    lots = [d for d in ctx.plan.decisions if d.scheme_id == inp.scheme_id]
    return {
        "summary": _dump(summary),
        "commission": _dump(leak),
        "plan": _dump(plan),
        "lots": [_dump(d) for d in lots[:MAX_LOTS_IN_TOOL_OUTPUT]],
        "lots_not_shown": max(0, len(lots) - MAX_LOTS_IN_TOOL_OUTPUT),
    }


def explain_lot(inp: LotInput, ctx: ToolContext) -> dict[str, Any]:
    for d in ctx.plan.decisions:
        if d.lot_id == inp.lot_id:
            return _dump(d)
    raise ToolError(f"No lot with id {inp.lot_id}.")


def get_assumptions(_: NoInput, ctx: ToolContext) -> dict[str, Any]:
    rules = next((r for r in ctx.rules if r.covers(ctx.assumptions.as_of)), ctx.rules[-1])
    eq, debt = rules.equity, rules.debt
    return {
        "assumptions": _dump(ctx.assumptions),
        "tax_rules": {
            "financial_year": rules.financial_year,
            "equity_stcg_rate": str(eq.stcg_rate.value),
            "equity_ltcg_rate": str(eq.ltcg_rate.value),
            "ltcg_exemption_per_fy": str(eq.ltcg_exemption_per_fy.value),
            "equity_long_term_after_months": eq.long_term_after_months.value,
            "elss_lock_in_years": eq.elss_lock_in_years.value,
            "grandfathering_fmv_date": eq.grandfathering_fmv_date.value.isoformat(),
            "debt_specified_fund_cutoff_date": debt.specified_fund_cutoff_date.value.isoformat(),
            "debt_legacy_long_term_after_months": debt.legacy_long_term_after_months.value,
            "debt_legacy_ltcg_rate": str(debt.legacy_ltcg_rate.value),
            "cess_rate": str(rules.surcharge_and_cess.health_education_cess_rate.value),
        },
    }


def what_if(inp: WhatIfInput, ctx: ToolContext) -> dict[str, Any]:
    changes = inp.model_dump(exclude_none=True)
    if not changes:
        raise ToolError("Give at least one assumption to change.")
    alt = ctx.assumptions.model_copy(update=changes)
    plan = plan_switch(ctx.portfolio, ctx.market, ctx.rules, alt)
    report = build_report(ctx.portfolio, ctx.market, expected_return=alt.expected_return)
    return {
        "note": "Hypothetical only; your saved plan is unchanged.",
        "changed": {k: str(v) for k, v in changes.items()},
        "current": {"totals": _dump(ctx.plan.totals), "leak_20y": str(ctx.report.leak_20y)},
        "what_if": {
            "totals": _dump(plan.totals),
            "leak_20y": str(report.leak_20y),
            "timeline": [_dump(t) for t in plan.timeline],
        },
    }


def simulate_switch(inp: SimulateInput, ctx: ToolContext) -> dict[str, Any]:
    unknown = set(inp.scheme_ids) - ctx.scheme_ids()
    if unknown:
        raise ToolError(f"Unknown fund ids: {sorted(unknown)}")
    wanted = set(inp.scheme_ids)
    folios = tuple(
        Folio(
            folio_id=f.folio_id,
            amc=f.amc,
            schemes=tuple(s for s in f.schemes if s.scheme_id in wanted),
        )
        for f in ctx.portfolio.folios
    )
    sub = ctx.portfolio.model_copy(update={"folios": tuple(f for f in folios if f.schemes)})
    on = inp.on_date or ctx.assumptions.as_of
    if on < ctx.portfolio.statement_to:
        raise ToolError("on_date can't be before the statement date.")
    plan = plan_switch(sub, ctx.market, ctx.rules, ctx.assumptions.model_copy(update={"as_of": on}))
    return {
        "note": "Switching every eligible lot of these funds on this date, at the statement NAV.",
        "on_date": on.isoformat(),
        "funds": sorted(wanted),
        "switch_everything": _dump(plan.switch_all_now),
        "optimized_plan_for_these_funds": _dump(plan.totals),
    }


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    model: type[_Input]
    handler: Callable[[Any, ToolContext], dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        schema = self.model.model_json_schema()
        schema.pop("title", None)
        schema.setdefault("properties", {})
        schema["additionalProperties"] = False
        return {"name": self.name, "description": self.description, "input_schema": schema}


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "get_portfolio_summary",
            "Current value, invested amount, gain and XIRR for the portfolio and each fund.",
            NoInput,
            get_portfolio_summary,
        ),
        Tool(
            "get_commission_leak",
            "Yearly, 10-year and 20-year cost of staying in Regular plans, per fund and in total.",
            NoInput,
            get_commission_leak,
        ),
        Tool(
            "get_switch_plan",
            "The lot-by-lot switch plan: totals (tax, exit load, net benefit, break-even), "
            "per-financial-year tax, timeline, per-fund action counts, and the "
            "switch-everything-now baseline.",
            NoInput,
            get_switch_plan,
        ),
        Tool(
            "get_fund_detail",
            "Everything about one fund: summary, commission, plan and its lots with reasons.",
            FundInput,
            get_fund_detail,
        ),
        Tool(
            "explain_lot",
            "The decision for one lot: action, switch date, tax, exit load and the reason.",
            LotInput,
            explain_lot,
        ),
        Tool(
            "get_assumptions",
            "The planning assumptions in use and the tax rules (rates, limits, holding periods).",
            NoInput,
            get_assumptions,
        ),
        Tool(
            "what_if",
            "Re-run the plan with different assumptions (return, slab, horizon, exemption use). "
            "Hypothetical: does not change the saved plan.",
            WhatIfInput,
            what_if,
        ),
        Tool(
            "simulate_switch",
            "Cost and benefit of switching every eligible lot of chosen funds on one date.",
            SimulateInput,
            simulate_switch,
        ),
    ]
}


def run_tool(name: str, raw_input: object, ctx: ToolContext) -> dict[str, Any]:
    """Validate input and run a tool. Raises ToolError with a model-readable message."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool {name!r}.")
    try:
        inp = tool.model.model_validate(raw_input if isinstance(raw_input, dict) else {})
    except ValidationError as exc:
        raise ToolError(f"Invalid input for {name}: {exc.error_count()} problem(s).") from None
    return tool.handler(inp, ctx)
