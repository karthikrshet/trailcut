# TrailCut

> Cut the commission, not your returns.

TrailCut reads an Indian mutual fund CAS statement (CAMS / KFintech) and plans the
cheapest, tax-smart **Regular → Direct** switch, lot by lot: what to switch now, what
to wait on (and until which date), what to keep, and what it all costs in tax and exit
load versus what you save.

**TrailCut is a calculator and explainer, not investment advice.** It never places
orders and never names funds to buy.

## Status

Sprint 1 (foundation) is done: monorepo, tooling, CI, repo rules, the FY 2026-27 tax-rule
file with its typed loader, and the web shell. CAS ingestion, the engine and the agents
come in the next sprints.

## Layout

| Path | What lives there |
| --- | --- |
| `apps/web` | React + Vite + TypeScript UI (Razorpay Blade, Lucide icons, Motion) |
| `apps/api` | FastAPI service (Python 3.12, Pydantic v2) |
| `packages/engine` | Pure finance engine: no I/O, no LLM, Decimal money |
| `packages/agent` | Claude tool-calling agents and the response validator |
| `data/tax_rules` | Versioned tax rules (the only place rates live) |
| `evals` | Agent eval scenarios and runner |
| `tests` | Repo-wide policy tests |
| `docs/runbooks` | Operational runbooks |

## Run locally

Needs [uv](https://docs.astral.sh/uv/), Node 22 and pnpm.

```bash
make install        # uv sync, pnpm install, enable git hooks
make check          # ruff, mypy --strict, eslint, tsc
make test           # pytest + Hypothesis (engine coverage >= 90%), API, Vitest
make e2e            # Playwright, desktop + 375px
make dev            # API on :8000, web on :5173
```

No `make` (e.g. Windows)? Run `uv run python scripts/dev.py <target>` instead.
Every commit runs `check` and `test` through the pre-commit hook.

See [CLAUDE.md](CLAUDE.md) for the rules every change follows.

## License

MIT
