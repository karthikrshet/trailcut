# Agent team

`packages/agent` answers questions about a portfolio in plain language without ever
producing a number of its own.

```
question ─▶ guard ─▶ router ─▶ specialist + tools (Claude) ─▶ validator ─▶ answer + trace
             │                      │                            │
             └ refuse fund-picking  └ ≤ 8 tool calls, 20 s        └ reject → 1 repair → fallback
               and order placement     budget, 6 rounds              to engine figures
```

## Pieces

| Piece | File | What it does |
| --- | --- | --- |
| Tools | `tools.py` | 8 typed tools over the engine: `get_portfolio_summary`, `get_commission_leak`, `get_switch_plan`, `get_fund_detail`, `explain_lot`, `get_assumptions`, `what_if`, `simulate_switch`. Strict JSON schemas (`additionalProperties: false`). |
| Router | `team.py` `route()` | Deterministic keyword router to four specialists: Portfolio Analyst, Switch Planner, Scenario, Teacher. Each sees only its own tools. |
| Guards | `team.py` | Fund-picking and order-placement requests are refused **before** any model call. "Should I…" answers carry the not-advice notice. User text and history are PII-masked before reaching the model. |
| Validator | `validator.py` | Extracts every ₹ amount (full, lakh/crore, K), %, date, month, FY and count from the answer and accepts it only if each is in that turn's tool output or the user's own message. Figures inside statement text (fund/AMC names) never count as evidence. |
| Fallback | `team.py` `_offline()` | With no API key, a model failure, a refusal, a blown time budget, or an answer that fails validation twice, the user gets the engine's own formatted figures instead. |
| Model | `llm.py` | Claude Opus 5.5 via the official SDK, cached system prompt, medium effort, server-side refusal fallback. |

## Why a hand-written loop

The SDK's tool runner would drive the loop for us, but every answer must pass the
validator and the loop has hard caps on tool calls, rounds and wall-clock time, so
`team.py` runs the `tool_use → tool_result` loop itself.

## Trace

Every answer returns its steps (`route`, `llm`, `tool`, `guard`, `limit`, `error`) with
timings. The chat drawer shows them under **How I got this**.

## Evals

`evals/scenarios/*.yaml` (routing, advice refusal, injection, planning figures,
multilingual). `make evals` runs them ×3; offline mode needs no API key and runs in
CI as a unit test. Any prompt, tool or model change must not lower the pass rate in
`evals/baseline.json` and must produce zero invented numbers.
