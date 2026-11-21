"""Cross-platform task runner behind the Makefile.

Usage: ``uv run python scripts/dev.py <task>``. The Makefile targets call this, so
``make check`` and ``uv run python scripts/dev.py check`` are identical (the
latter works on Windows without make).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
ENGINE_COVERAGE_MIN = 90

PY_TYPED_PATHS = [
    "packages/engine/src",
    "packages/agent/src",
    "apps/api/src",
    "packages/engine/tests",
    "packages/agent/tests",
    "apps/api/tests",
    "tests",
    "scripts",
]


def run(cmd: Sequence[str], cwd: Path = ROOT) -> None:
    """Run a command, echoing it, and exit with its code on failure."""
    print(f"\n$ {' '.join(cmd)}", flush=True)
    code = subprocess.run(list(cmd), cwd=cwd, check=False).returncode
    if code != 0:
        print(f"\nFAILED ({code}): {' '.join(cmd)}", file=sys.stderr)
        sys.exit(code)


def pnpm(*args: str) -> list[str]:
    exe = shutil.which("pnpm")
    if exe is None:
        sys.exit("pnpm not found. Install it with: corepack enable")
    return [exe, *args]


# ---------- tasks ----------


def check() -> None:
    """Lint and type-check everything."""
    run([PY, "-m", "ruff", "check", "."])
    run([PY, "-m", "ruff", "format", "--check", "."])
    run([PY, "-m", "mypy", *PY_TYPED_PATHS])
    run(pnpm("--filter", "web", "lint"))
    run(pnpm("--filter", "web", "typecheck"))


def test_unit() -> None:
    """Engine, agent and repo-policy tests (incl. Hypothesis) with the engine coverage gate."""
    run(
        [
            PY,
            "-m",
            "pytest",
            "packages/engine/tests",
            "packages/agent/tests",
            "tests",
            "-q",
            "--cov=trailcut_engine",
            "--cov-report=term-missing",
            "--cov-report=xml",
            f"--cov-fail-under={ENGINE_COVERAGE_MIN}",
        ]
    )


def test_api() -> None:
    """FastAPI tests."""
    run([PY, "-m", "pytest", "apps/api/tests", "-q"])


def test_web() -> None:
    """Vitest component and unit tests."""
    run(pnpm("--filter", "web", "test"))


def test() -> None:
    """All fast tests: unit + property, API, web."""
    test_unit()
    test_api()
    test_web()


def e2e() -> None:
    """Playwright end-to-end tests (needs `pnpm --filter web exec playwright install`)."""
    run(pnpm("--filter", "web", "e2e"))


def evals() -> None:
    """Agent eval scenarios x3 (Sprint 7)."""
    scenarios = ROOT / "evals" / "scenarios"
    if not scenarios.is_dir() or not any(scenarios.rglob("*.yaml")):
        print("No eval scenarios yet (they arrive in Sprint 7). Nothing to run.")
        return
    run([PY, "-m", "evals.runner", "--repeat", "3"])


def dev() -> None:
    """Run the API (:8000) and web (:5173) dev servers until Ctrl+C."""
    api = subprocess.Popen(
        [PY, "-m", "uvicorn", "trailcut_api.main:app", "--reload", "--port", "8000"], cwd=ROOT
    )
    web = subprocess.Popen(pnpm("--filter", "web", "dev"), cwd=ROOT)
    try:
        while api.poll() is None and web.poll() is None:
            try:
                api.wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (api, web):
            if proc.poll() is None:
                proc.terminate()


TASKS: dict[str, Callable[[], None]] = {
    "check": check,
    "test": test,
    "test-unit": test_unit,
    "test-api": test_api,
    "test-web": test_web,
    "e2e": e2e,
    "evals": evals,
    "dev": dev,
}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("task", choices=sorted(TASKS))
    args = parser.parse_args(argv)
    TASKS[args.task]()


if __name__ == "__main__":
    main()
