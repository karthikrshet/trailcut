"""Guard the CI pipeline shape and the engine coverage gate against silent weakening."""

import importlib.util
from pathlib import Path
from types import ModuleType

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_dev_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dev_script", ROOT / "scripts" / "dev.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ci() -> dict[str, object]:
    raw = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def test_engine_coverage_gate_is_at_least_90() -> None:
    assert load_dev_script().ENGINE_COVERAGE_MIN >= 90


def test_ci_stages_run_in_order() -> None:
    jobs = load_ci()["jobs"]
    assert isinstance(jobs, dict)
    assert list(jobs) == ["lint-types", "unit-property", "api-web", "e2e"]
    assert "needs" not in jobs["lint-types"]
    assert jobs["unit-property"]["needs"] == "lint-types"
    assert jobs["api-web"]["needs"] == "unit-property"
    assert jobs["e2e"]["needs"] == "api-web"


def test_ci_runs_the_same_tasks_as_make() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for task in ("check", "test-unit", "test-api", "test-web", "e2e"):
        assert f"scripts/dev.py {task}" in text, task


def test_ci_never_skips_or_tolerates_failures() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "continue-on-error" not in text
    assert "--no-verify" not in text
    assert "|| true" not in text


def test_dev_script_exposes_make_targets() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    tasks = load_dev_script().TASKS
    for target in ("check", "test", "e2e", "evals", "dev"):
        assert target in tasks
        assert f"\n{target}:" in makefile
