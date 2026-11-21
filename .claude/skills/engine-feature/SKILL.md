---
name: engine-feature
description: Use when adding or changing logic in packages/engine (XIRR, FIFO lots, tax classification, exit loads, TER projections, switch optimizer). Enforces pure functions, Pydantic types, Decimal money, parametrized tests and a Hypothesis property.
---

# Engine feature

`packages/engine` (`trailcut_engine`) is the only place numbers are computed.
Everything the UI or the agent shows comes from here.

## Rules
- **Pure.** No file, network, DB, clock, randomness, logging or LLM. Take `today: date`
  as a parameter instead of reading the clock. Repo policy tests enforce the imports.
- **Typed.** Pydantic v2 models (`frozen=True, extra="forbid"`) in and out;
  `mypy --strict` clean.
- **Decimal money.** Never `float` (not even as a literal). Units and NAVs are
  `Decimal` too. Quantize only at the edge with an explicit rounding mode; document it.
- **Rules from data.** Read rates from a `TaxRules` argument, never constants.
- **Deterministic.** Same input → same output, including ordering (sort by stable keys
  such as `(date, lot_id)`).

## Steps
1. Write the model(s) and function signature with a docstring that includes an example.
2. Write parametrized golden tests first: normal cases, boundaries (day 365/366,
   31 Mar/1 Apr, zero units, single cashflow), and invalid input raising a typed error.
3. Add at least one Hypothesis property (`@pytest.mark.property`), for example:
   lots after FIFO never go negative; plan cost ≤ "switch everything now" cost;
   total units in = units out + units remaining.
4. Implement until tests pass.
5. `uv run pytest packages/engine -q --cov=trailcut_engine` stays ≥ 90%.
6. `make check && make test`, then commit `feat(engine): ...` with code and tests together.

## Review checklist
- [ ] No `float`, no I/O, no hardcoded tax figure
- [ ] Docstring with example
- [ ] Boundary dates tested on both sides
- [ ] Property test added or a reason given in the commit body
