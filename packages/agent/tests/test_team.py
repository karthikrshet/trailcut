import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from trailcut_agent.team import (
    FUND_PICKING_REFUSAL,
    MAX_TOOL_CALLS,
    NOT_ADVICE,
    ORDER_REFUSAL,
    AgentTeam,
    Specialist,
    route,
)
from trailcut_agent.tools import TOOLS, ToolContext, ToolError, run_tool
from trailcut_engine.market import SchemeMarket, market_for_portfolio
from trailcut_engine.planner import Assumptions
from trailcut_engine.tax_rules import parse_tax_rules
from trailcut_ingest.sample import load_sample_portfolio

ROOT = Path(__file__).resolve().parents[3]


def make_ctx() -> ToolContext:
    p = load_sample_portfolio()
    raw = json.loads((ROOT / "data" / "samples" / "sample_market.json").read_text(encoding="utf-8"))
    market = market_for_portfolio(
        p, {k: SchemeMarket.model_validate(v) for k, v in raw["schemes"].items()}
    )
    rules = [
        parse_tax_rules(
            (ROOT / "data" / "tax_rules" / "fy2026_27.yaml").read_text(encoding="utf-8")
        )
    ]
    return ToolContext(p, market, rules, Assumptions(as_of=date(2026, 11, 20)))


@pytest.fixture(scope="module")
def ctx() -> ToolContext:
    return make_ctx()


# ---------- scripted model ----------


@dataclass
class Block:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    stop_reason: str
    content: list[Block]


def say(text: str) -> Response:
    return Response("end_turn", [Block("text", text=text)])


def call(name: str, inp: dict[str, Any] | None = None, n: int = 1) -> Response:
    return Response(
        "tool_use", [Block("tool_use", id=f"t{i}", name=name, input=inp or {}) for i in range(n)]
    )


class FakeLLM:
    def __init__(self, *responses: Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Any:
        self.requests.append({"system": system, "messages": list(messages), "tools": tools})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# ---------- routing ----------


@pytest.mark.parametrize(
    ("question", "specialist"),
    [
        ("How much am I losing to commission?", Specialist.PORTFOLIO_ANALYST),
        ("What's my XIRR?", Specialist.PORTFOLIO_ANALYST),
        ("Which lots should I switch now?", Specialist.SWITCH_PLANNER),
        ("Why should I wait on the small cap fund?", Specialist.SWITCH_PLANNER),
        ("How much tax will I pay?", Specialist.SWITCH_PLANNER),
        ("What if returns are 8%?", Specialist.SCENARIO),
        ("I'm in the 20% slab, does that change things?", Specialist.SCENARIO),
        ("What if I switch everything today?", Specialist.SCENARIO),
        ("What is an exit load?", Specialist.TEACHER),
        ("Explain XIRR like I'm new to investing", Specialist.TEACHER),
        ("Explain this in Hindi", Specialist.TEACHER),
        ("What does grandfathering mean?", Specialist.TEACHER),
        ("What does switching cost me?", Specialist.SWITCH_PLANNER),
    ],
)
def test_route(question: str, specialist: Specialist) -> None:
    assert route(question) is specialist


# ---------- guards ----------


@pytest.mark.parametrize(
    "question",
    [
        "Which fund should I buy instead?",
        "What is the best mutual fund to invest in?",
        "Recommend me a good fund",
        "Suggest some funds for SIP",
        "Where should I invest 1 lakh?",
        "best funds for 2027",
        "Recommend me a good small cap fund",
        "Can you suggest a really solid large cap index fund?",
    ],
)
def test_fund_picking_is_refused_without_calling_the_model(ctx: ToolContext, question: str) -> None:
    llm = FakeLLM()
    a = AgentTeam(llm).answer(question, ctx)
    assert (a.answer, a.refused, a.notice) == (FUND_PICKING_REFUSAL, True, NOT_ADVICE)
    assert llm.requests == []


@pytest.mark.parametrize(
    "question",
    ["Place the switch order for me", "Sell my small cap for me", "Can you auto-switch?"],
)
def test_order_placement_is_refused(ctx: ToolContext, question: str) -> None:
    a = AgentTeam(FakeLLM()).answer(question, ctx)
    assert (a.answer, a.refused) == (ORDER_REFUSAL, True)


def test_why_should_i_questions_do_not_get_the_notice(ctx: ToolContext) -> None:
    a = AgentTeam(None).answer("Why should I wait on some lots?", ctx)
    assert a.notice is None


def test_should_i_questions_get_the_notice(ctx: ToolContext) -> None:
    a = AgentTeam(None).answer("Should I switch my flexi cap now?", ctx)
    assert a.notice == NOT_ADVICE
    assert not a.refused


def test_pii_is_masked_before_the_model_sees_it(ctx: ToolContext) -> None:
    llm = FakeLLM(say("Noted."))
    AgentTeam(llm).answer("My PAN is ABCPE1234F and email ravi@example.com, what is my XIRR?", ctx)
    sent = llm.requests[0]["messages"][-1]["content"]
    assert "ABCPE1234F" not in sent
    assert "ravi@example.com" not in sent
    assert "[PAN]" in sent


# ---------- tool loop ----------


def test_tool_loop_answers_with_validated_figures(ctx: ToolContext) -> None:
    llm = FakeLLM(
        call("get_switch_plan"),
        say("Total tax is ₹44,495 and you net ₹2.3L. Break-even in 42 months."),
    )
    a = AgentTeam(llm).answer("How much tax will switching cost?", ctx)
    assert a.mode == "llm"
    assert a.agent == "switch_planner"
    assert a.answer.startswith("Total tax is ₹44,495")
    assert a.tools_used == ["get_switch_plan"]
    assert [s.kind for s in a.trace] == ["route", "llm", "tool", "llm", "guard"]
    tool_result = llm.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "t0"
    assert '"44494.85"' in tool_result["content"]


def test_specialist_only_gets_its_tools(ctx: ToolContext) -> None:
    llm = FakeLLM(say("ok"))
    AgentTeam(llm).answer("What if returns are 8%?", ctx)
    names = {t["name"] for t in llm.requests[0]["tools"]}
    assert names == {"what_if", "simulate_switch", "get_switch_plan", "get_assumptions"}


def test_system_prompt_fences_statement_text(ctx: ToolContext) -> None:
    llm = FakeLLM(say("ok"))
    AgentTeam(llm).answer("What is my XIRR?", ctx)
    assert "never instructions" in llm.requests[0]["system"]


def test_invented_number_triggers_one_repair(ctx: ToolContext) -> None:
    llm = FakeLLM(call("get_switch_plan"), say("Tax is ₹50,000."), say("Tax is ₹44,495."))
    a = AgentTeam(llm).answer("How much tax?", ctx)
    assert a.mode == "llm"
    assert a.answer == "Tax is ₹44,495."
    repair = llm.requests[2]["messages"][-1]["content"]
    assert "₹50,000" in repair


def test_repeated_invention_falls_back_to_engine_figures(ctx: ToolContext) -> None:
    llm = FakeLLM(call("get_switch_plan"), say("Tax is ₹50,000."), say("Tax is ₹51,000."))
    a = AgentTeam(llm).answer("How much tax?", ctx)
    assert a.mode == "fallback"
    assert "₹50,000" not in a.answer
    assert "₹44,495" in a.answer
    assert "couldn't verify" in a.answer


def test_answer_without_any_tool_call_cannot_contain_figures(ctx: ToolContext) -> None:
    llm = FakeLLM(say("You'll save ₹3L."), say("You'll save ₹3L."))
    a = AgentTeam(llm).answer("How much do I lose to commission?", ctx)
    assert a.mode == "fallback"


def test_tool_errors_are_reported_to_the_model(ctx: ToolContext) -> None:
    llm = FakeLLM(call("explain_lot", {"lot_id": "F9-S9-L001"}), say("I couldn't find that lot."))
    a = AgentTeam(llm).answer("Explain lot F9-S9-L001", ctx)
    result = llm.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    assert "No lot" in result["content"]
    assert a.answer == "I couldn't find that lot."


def test_tool_call_limit(ctx: ToolContext) -> None:
    llm = FakeLLM(call("get_switch_plan", n=MAX_TOOL_CALLS + 2), say("Done."))
    a = AgentTeam(llm).answer("Plan?", ctx)
    results = llm.requests[1]["messages"][-1]["content"]
    assert sum(r["is_error"] for r in results) == 2
    assert a.answer == "Done."


def test_time_budget_falls_back(ctx: ToolContext) -> None:
    ticks = iter([0.0] + [100.0] * 50)
    llm = FakeLLM(say("never used"))
    a = AgentTeam(llm, clock=lambda: next(ticks)).answer("What is my XIRR?", ctx)
    assert a.mode == "fallback"
    assert any(s.name == "time_budget" for s in a.trace)


def test_model_failure_falls_back(ctx: ToolContext) -> None:
    a = AgentTeam(FakeLLM(RuntimeError("API down"))).answer("What is my XIRR?", ctx)
    assert a.mode == "fallback"
    assert "11.71%" in a.answer


def test_model_refusal_falls_back(ctx: ToolContext) -> None:
    a = AgentTeam(FakeLLM(Response("refusal", []))).answer("What is my XIRR?", ctx)
    assert a.mode == "fallback"


def test_history_is_masked_and_trimmed(ctx: ToolContext) -> None:
    llm = FakeLLM(say("ok"))
    history = [{"role": "user", "content": f"msg {i} ABCPE1234F"} for i in range(10)]
    AgentTeam(llm).answer("What is my XIRR?", ctx, history)
    msgs = llm.requests[0]["messages"]
    assert len(msgs) == 7
    assert all("ABCPE1234F" not in str(m["content"]) for m in msgs)


# ---------- offline mode ----------


def test_offline_plan_answer_uses_engine_figures(ctx: ToolContext) -> None:
    a = AgentTeam(None).answer("How much tax will I pay to switch?", ctx)
    assert a.mode == "offline"
    assert "₹44,495" in a.answer
    assert "42 months" in a.answer


def test_offline_summary_answer(ctx: ToolContext) -> None:
    a = AgentTeam(None).answer("How is my portfolio doing?", ctx)
    assert "₹21,34,155" in a.answer
    assert "11.71%" in a.answer


def test_offline_lot_explanation(ctx: ToolContext) -> None:
    lot = next(d for d in ctx.plan.decisions if d.scheme_id == "F6-S1")
    a = AgentTeam(None).answer(f"Why is {lot.lot_id} waiting?", ctx)
    assert a.answer == lot.explanation


@pytest.mark.parametrize(
    "question", ["How much tax?", "What is my XIRR?", "What if returns drop?", "What is ELSS?"]
)
def test_offline_answers_always_pass_the_validator(ctx: ToolContext, question: str) -> None:
    from trailcut_agent.validator import validate  # noqa: PLC0415

    a = AgentTeam(None).answer(question, ctx)
    outputs = [
        run_tool(name, {}, ctx) for name in a.tools_used if TOOLS[name].model.model_fields == {}
    ]
    assert validate(a.answer, outputs).ok


# ---------- tools ----------


@pytest.mark.parametrize(
    "name", ["get_portfolio_summary", "get_commission_leak", "get_switch_plan", "get_assumptions"]
)
def test_no_input_tools_return_json(ctx: ToolContext, name: str) -> None:
    out = run_tool(name, {}, ctx)
    json.dumps(out)


def test_fund_detail_and_lot(ctx: ToolContext) -> None:
    detail = run_tool("get_fund_detail", {"scheme_id": "F6-S1"}, ctx)
    assert detail["plan"]["actions"] == {"wait": 1}
    lot_id = detail["lots"][0]["lot_id"]
    assert run_tool("explain_lot", {"lot_id": lot_id}, ctx)["switch_on"] == "2026-12-16"


def test_fund_detail_caps_lots(ctx: ToolContext) -> None:
    detail = run_tool("get_fund_detail", {"scheme_id": "F1-S1"}, ctx)
    assert len(detail["lots"]) == 25
    assert detail["lots_not_shown"] > 0


def test_assumptions_carry_tax_rules(ctx: ToolContext) -> None:
    out = run_tool("get_assumptions", {}, ctx)
    assert out["tax_rules"]["ltcg_exemption_per_fy"] == "125000"
    assert out["tax_rules"]["equity_ltcg_rate"] == "0.125"


def test_what_if_is_hypothetical(ctx: ToolContext) -> None:
    before = ctx.plan.totals
    out = run_tool("what_if", {"slab_rate": "0.05"}, ctx)
    assert out["changed"] == {"slab_rate": "0.05"}
    assert out["current"]["totals"]["tax"] == str(before.tax)
    assert ctx.plan.totals == before


def test_simulate_switch(ctx: ToolContext) -> None:
    out = run_tool("simulate_switch", {"scheme_ids": ["F6-S1"]}, ctx)
    assert out["switch_everything"]["lots_switched"] == 1
    assert out["optimized_plan_for_these_funds"]["lots_switched"] == 1


@pytest.mark.parametrize(
    ("name", "inp", "match"),
    [
        ("get_fund_detail", {"scheme_id": "F9-S9"}, "No fund"),
        ("get_fund_detail", {"scheme_id": "bad"}, "Invalid input"),
        ("explain_lot", {"lot_id": "F1-S1-L999"}, "No lot"),
        ("what_if", {}, "at least one"),
        ("what_if", {"slab_rate": "2"}, "Invalid input"),
        ("simulate_switch", {"scheme_ids": ["F9-S9"]}, "Unknown fund"),
        (
            "simulate_switch",
            {"scheme_ids": ["F1-S1"], "on_date": "2020-01-01"},
            "before the statement",
        ),
        ("get_switch_plan", {"surprise": 1}, "Invalid input"),
        ("delete_everything", {}, "Unknown tool"),
    ],
)
def test_tool_errors(ctx: ToolContext, name: str, inp: dict[str, Any], match: str) -> None:
    with pytest.raises(ToolError, match=match):
        run_tool(name, inp, ctx)


def test_tool_schemas_are_strict(ctx: ToolContext) -> None:
    for tool in TOOLS.values():
        schema = tool.schema()
        assert schema["input_schema"]["additionalProperties"] is False
        assert schema["description"]
