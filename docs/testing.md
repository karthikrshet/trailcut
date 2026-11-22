# Testing

Every commit runs `make check && make test` through the pre-commit hook, and CI runs the
same stages plus Playwright and a Docker build.

| Command | Runs |
| --- | --- |
| `make check` | ruff, ruff format, mypy `--strict`, ESLint (type-checked + jsx-a11y), tsc |
| `make test` | pytest (engine, ingest, agent, API, repo policy) with the engine coverage gate (≥ 90%), then Vitest |
| `make e2e` | Playwright: landing smoke + full sample journey against the real API, desktop and 375 px |
| `make evals` | Agent scenarios ×3 (offline without a key, live with `ANTHROPIC_API_KEY`) |

## What each layer proves

| Layer | Where | Highlights |
| --- | --- | --- |
| Tax rules | `packages/engine/tests/test_tax_rules.py` | Every value sourced; floats, http sources, wrong FY dates rejected |
| Engine | `packages/engine/tests/` | 12-month and 24-month boundaries day by day, grandfathering, loss set-off order, exemption sharing; XIRR golden cases vs spreadsheet values |
| Optimizer properties | `test_planner.py` | On random portfolios: never sells locked ELSS, never over-uses the exemption, never worse than switch-all-now, deterministic |
| Ingestion | `packages/ingest/tests/` | Real one-page PDFs built in memory and run through casparser; MF Central detection; Hypothesis plants PII everywhere and proves none reaches output |
| Agent | `packages/agent/tests/` | Scripted model: tool loop, limits, repair, fallback, refusals, PII masking; validator properties (engine-formatted figures always pass, shifted ones fail); prompt injection through fund names |
| API | `apps/api/tests/` | Routes, error codes, size and rate limits, session expiry with a fake clock, security headers, no echo of passwords or PII |
| Web | `apps/web/src/**/*.test.tsx` | Every view's empty/loading/error/data states, real engine output from a generated fixture, reduced motion, accessible roles |
| Repo policy | `tests/` | Engine purity (no I/O, no floats), no hardcoded tax figures, no logging in ingestion, no PDFs committed, CI shape and coverage gate |

## Fixtures are generated, never hand-typed

- `scripts/make_sample.py` writes the fictional sample statement and its market data.
- `scripts/make_web_fixture.py` writes the web test fixture from the real API.

Tests fail if a committed fixture drifts from its generator.

## Rules

- Never weaken, skip or delete a test to make CI pass; fix the code.
- New engine functions come with parametrized tests and a Hypothesis property.
- Any prompt, tool or model change runs `make evals`; the pass rate must not drop and
  invented numbers must stay at zero.
