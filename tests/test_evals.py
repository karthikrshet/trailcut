"""The offline agent evals run in CI: routing, refusals, injection and figures."""

import json
from pathlib import Path

import pytest
from evals.runner import (
    BASELINE,
    Outcome,
    gate,
    load_scenarios,
    make_team,
    run,
    summarize,
)

SCENARIOS = load_scenarios()


def test_there_are_enough_scenarios_in_every_category() -> None:
    by_cat: dict[str, int] = {}
    for s in SCENARIOS:
        by_cat[s.category] = by_cat.get(s.category, 0) + 1
    assert len(SCENARIOS) >= 45
    assert set(by_cat) >= {"routing", "advice_refusal", "injection", "planning", "multilingual"}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_offline_scenario_passes(scenario: object) -> None:
    (outcome,) = run(make_team("offline"), [scenario], repeat=1)  # type: ignore[list-item]
    assert outcome.passed, outcome.failures
    assert outcome.invented == 0


def test_baseline_has_a_perfect_offline_pass_rate() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["offline"]["pass_rate"] == 1.0


def test_gate_blocks_drops_and_invented_numbers() -> None:
    baseline = {"offline": {"pass_rate": 1.0}}
    good = summarize([Outcome("a", "c", True)], "offline", 1)
    assert gate(good, baseline) == []
    worse = summarize([Outcome("a", "c", True), Outcome("b", "c", False, ["x"])], "offline", 1)
    assert "pass rate" in gate(worse, baseline)[0]
    invented = summarize([Outcome("a", "c", True, invented=1)], "offline", 1)
    assert "invented" in gate(invented, baseline)[0]


def test_unknown_expectation_keys_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "x.yaml").write_text(
        "- {id: a, question: q, expect: {agnet: teacher}}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unknown expect keys"):
        load_scenarios(tmp_path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "x.yaml").write_text(
        "- {id: a, question: q}\n- {id: a, question: r}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unique"):
        load_scenarios(tmp_path)
