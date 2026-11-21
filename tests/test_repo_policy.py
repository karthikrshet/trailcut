"""Repo-wide guardrails for CLAUDE.md hard rules. These run on every commit."""

import ast
import re
import subprocess
from pathlib import Path

import pytest

from trailcut_engine.tax_rules import parse_tax_rules

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SRC = ROOT / "packages" / "engine" / "src" / "trailcut_engine"
TAX_RULES = ROOT / "data" / "tax_rules"

# The engine is pure: no file, network, process, database or LLM access.
FORBIDDEN_ENGINE_IMPORTS = {
    "os",
    "pathlib",
    "io",
    "shutil",
    "socket",
    "subprocess",
    "sqlite3",
    "urllib",
    "http",
    "requests",
    "httpx",
    "anthropic",
    "openai",
    "redis",
    "logging",
    "random",
    "time",
}
FORBIDDEN_ENGINE_CALLS = {"open", "print", "input", "eval", "exec", "float"}


def engine_files() -> list[Path]:
    files = sorted(ENGINE_SRC.rglob("*.py"))
    assert files, "engine sources not found"
    return files


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@pytest.mark.parametrize("path", engine_files(), ids=lambda p: p.name)
def test_engine_has_no_io_or_llm_imports(path: Path) -> None:
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        else:
            continue
        for name in names:
            assert name.split(".")[0] not in FORBIDDEN_ENGINE_IMPORTS, f"{path.name}: {name}"


@pytest.mark.parametrize("path", engine_files(), ids=lambda p: p.name)
def test_engine_never_uses_float_or_side_effect_builtins(path: Path) -> None:
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Constant) and type(node.value) is float:
            pytest.fail(f"{path.name}:{node.lineno}: float literal {node.value!r}")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_ENGINE_CALLS:
            # `float` may appear only as an isinstance() target used to REJECT floats.
            if node.id == "float" and _is_isinstance_target(path, node):
                continue
            pytest.fail(f"{path.name}:{node.lineno}: forbidden name {node.id!r}")


def _is_isinstance_target(path: Path, target: ast.Name) -> bool:
    for node in ast.walk(parse(path)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Name)
            and node.args[1].id == "float"
            and node.args[1].lineno == target.lineno
            and node.args[1].col_offset == target.col_offset
        ):
            return True
    return False


def tax_rule_files() -> list[Path]:
    files = sorted(TAX_RULES.glob("*.yaml"))
    assert files, "no tax rule files found"
    return files


@pytest.mark.parametrize("path", tax_rule_files(), ids=lambda p: p.name)
def test_tax_rule_files_are_valid_and_named_by_year(path: Path) -> None:
    rules = parse_tax_rules(path.read_text(encoding="utf-8"))
    start, end = rules.financial_year.split("-")
    assert path.name == f"fy{start}_{end}.yaml"


def test_tax_rule_files_do_not_overlap() -> None:
    years = [
        parse_tax_rules(p.read_text(encoding="utf-8")).financial_year for p in tax_rule_files()
    ]
    assert len(years) == len(set(years))


RATE_IN_CODE = re.compile(r"""(?<![\w.])(?:0\.125|0\.20?|125000|125_000|1_25_000)(?![\w.])""")


@pytest.mark.parametrize(
    "path",
    sorted(p for base in ("packages", "apps/api") for p in (ROOT / base).rglob("src/**/*.py")),
    ids=lambda p: p.name,
)
def test_tax_rates_are_not_hardcoded_in_source(path: Path) -> None:
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Constant) and isinstance(node.value, int | str):
            assert not RATE_IN_CODE.fullmatch(str(node.value)), (
                f"{path.name}:{node.lineno}: tax figure {node.value!r} belongs in data/tax_rules"
            )


def _git_ls_files(*patterns: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", *patterns],  # noqa: S607
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [line for line in result.stdout.splitlines() if line]


def test_no_real_statements_are_committed() -> None:
    tracked = _git_ls_files("*.pdf", "*.PDF")
    allowed = [f for f in tracked if Path(f).name.startswith("synthetic_")]
    assert tracked == allowed, f"PDFs must never be committed: {set(tracked) - set(allowed)}"


@pytest.mark.parametrize(
    "path",
    [
        "apps/api",
        "packages/engine",
        "packages/agent",
        "data/tax_rules",
        "evals",
        "tests",
        "docs/runbooks",
    ],
)
def test_monorepo_layout_exists(path: str) -> None:
    assert (ROOT / path).is_dir()
