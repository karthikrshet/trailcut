"""Run the agent eval scenarios against the sample portfolio.

Usage::

    uv run python -m evals.runner                 # live if ANTHROPIC_API_KEY is set, else offline
    uv run python -m evals.runner --mode offline  # no model: routing, guards, figures
    uv run python -m evals.runner --repeat 3 --write-baseline

A scenario passes only if every repeat passes. The run fails if the pass rate is
below the baseline for that mode, or if any answer contained an invented number
(the validator rejected it and the user got the fallback).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from trailcut_agent.team import AgentTeam, ChatAnswer
from trailcut_agent.tools import ToolContext
from trailcut_engine.market import SchemeMarket, market_for_portfolio
from trailcut_engine.planner import Assumptions
from trailcut_engine.tax_rules import parse_tax_rules
from trailcut_ingest.sample import load_sample_portfolio

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "evals" / "scenarios"
RESULTS = ROOT / "evals" / "results"
BASELINE = ROOT / "evals" / "baseline.json"
EXPECT_KEYS = {"agent", "refused", "notice", "must_contain", "must_not_contain", "tools_any"}


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str
    question: str
    expect: dict[str, Any]


@dataclass
class Outcome:
    id: str
    category: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    invented: int = 0


def load_scenarios(directory: Path = SCENARIOS) -> list[Scenario]:
    """Every scenario in ``evals/scenarios/*.yaml`` (category = file name)."""
    out: list[Scenario] = []
    for path in sorted(directory.glob("*.yaml")):
        for item in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            expect = dict(item.get("expect") or {})
            unknown = set(expect) - EXPECT_KEYS
            if unknown:
                msg = f"{item.get('id')}: unknown expect keys {sorted(unknown)}"
                raise ValueError(msg)
            out.append(Scenario(str(item["id"]), path.stem, str(item["question"]), expect))
    ids = [s.id for s in out]
    if len(ids) != len(set(ids)):
        msg = "scenario ids must be unique"
        raise ValueError(msg)
    return out


def sample_context() -> ToolContext:
    p = load_sample_portfolio()
    raw = json.loads((ROOT / "data" / "samples" / "sample_market.json").read_text(encoding="utf-8"))
    market = market_for_portfolio(
        p, {k: SchemeMarket.model_validate(v) for k, v in raw["schemes"].items()}
    )
    rules = [
        parse_tax_rules(f.read_text(encoding="utf-8"))
        for f in sorted((ROOT / "data" / "tax_rules").glob("*.yaml"))
    ]
    return ToolContext(p, market, rules, Assumptions(as_of=date(2026, 11, 20)))


def check(s: Scenario, a: ChatAnswer) -> list[str]:
    """Why ``a`` fails scenario ``s`` (empty list = pass)."""
    e = s.expect
    failures = []
    if "agent" in e and a.agent != e["agent"]:
        failures.append(f"agent {a.agent} != {e['agent']}")
    if "refused" in e and a.refused != e["refused"]:
        failures.append(f"refused {a.refused} != {e['refused']}")
    if "notice" in e and (a.notice is not None) != e["notice"]:
        failures.append("notice missing" if e["notice"] else "unexpected notice")
    failures += [f"missing {t!r}" for t in e.get("must_contain", []) if t not in a.answer]
    failures += [f"contains {t!r}" for t in e.get("must_not_contain", []) if t in a.answer]
    if "tools_any" in e and not set(e["tools_any"]) & set(a.tools_used):
        failures.append(f"none of {e['tools_any']} used")
    return failures


def invented_numbers(a: ChatAnswer) -> int:
    return sum(
        1 for t in a.trace if t.kind == "guard" and t.name == "numeric_claims" and t.detail != "ok"
    )


def run(team: AgentTeam, scenarios: list[Scenario], repeat: int) -> list[Outcome]:
    ctx = sample_context()
    outcomes = []
    for s in scenarios:
        failures: list[str] = []
        invented = 0
        for _ in range(repeat):
            answer = team.answer(s.question, ctx)
            failures += check(s, answer)
            invented += invented_numbers(answer)
        outcomes.append(Outcome(s.id, s.category, not failures, sorted(set(failures)), invented))
    return outcomes


def summarize(outcomes: list[Outcome], mode: str, repeat: int) -> dict[str, Any]:
    passed = sum(o.passed for o in outcomes)
    by_cat: dict[str, list[int]] = {}
    for o in outcomes:
        by_cat.setdefault(o.category, [0, 0])
        by_cat[o.category][0] += o.passed
        by_cat[o.category][1] += 1
    return {
        "mode": mode,
        "repeat": repeat,
        "scenarios": len(outcomes),
        "passed": passed,
        "pass_rate": round(passed / len(outcomes), 4) if outcomes else 0,
        "invented_numbers": sum(o.invented for o in outcomes),
        "by_category": {k: {"passed": v[0], "total": v[1]} for k, v in sorted(by_cat.items())},
        "failures": [asdict(o) for o in outcomes if not o.passed],
    }


def make_team(mode: str) -> AgentTeam:
    if mode == "offline":
        return AgentTeam(llm=None)
    from trailcut_agent.llm import ClaudeLLM  # noqa: PLC0415 - only needed for live runs

    return AgentTeam(
        llm=ClaudeLLM(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            model=os.environ.get("TRAILCUT_MODEL", "claude-opus-5-5"),
        )
    )


def gate(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Reasons the run should fail CI."""
    problems = []
    base = baseline.get(summary["mode"])
    if base and summary["pass_rate"] < base["pass_rate"]:
        problems.append(f"pass rate {summary['pass_rate']} < baseline {base['pass_rate']}")
    if summary["invented_numbers"]:
        problems.append(f"{summary['invented_numbers']} answer(s) had invented numbers")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TrailCut agent evals.")
    parser.add_argument(
        "--mode",
        choices=["offline", "live"],
        default="live" if os.environ.get("ANTHROPIC_API_KEY") else "offline",
    )
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args(argv)

    scenarios = load_scenarios()
    summary = summarize(run(make_team(args.mode), scenarios, args.repeat), args.mode, args.repeat)
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (RESULTS / f"{stamp}-{args.mode}.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8"
    )

    print(
        f"{args.mode}: {summary['passed']}/{summary['scenarios']} passed (x{args.repeat}), "
        f"invented numbers: {summary['invented_numbers']}"
    )
    for cat, v in summary["by_category"].items():
        print(f"  {cat:16} {v['passed']}/{v['total']}")
    for f in summary["failures"]:
        print(f"  FAIL {f['id']}: {'; '.join(f['failures'])}")

    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    if args.write_baseline:
        baseline[args.mode] = {"pass_rate": summary["pass_rate"], "scenarios": summary["scenarios"]}
        BASELINE.write_text(json.dumps(baseline, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline for {args.mode} written")
        return 0
    problems = gate(summary, baseline)
    for p in problems:
        print(f"BLOCK: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
