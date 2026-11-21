# TrailCut

> Cut the commission, not your returns.

TrailCut reads an Indian mutual fund CAS statement (CAMS / KFintech) and plans the
cheapest, tax-smart **Regular → Direct** switch, lot by lot: what to switch now, what
to wait on (and until which date), what to keep, and what it all costs in tax and exit
load versus what you save.

**TrailCut is a calculator and explainer, not investment advice.** It never places
orders and never names funds to buy.

## Status

Sprint 1 (foundation): monorepo, tooling, CI, repo rules. The product itself is not built yet.

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

```bash
uv sync
pnpm install
make check && make test
```

See [CLAUDE.md](CLAUDE.md) for the rules every change follows.

## License

MIT
