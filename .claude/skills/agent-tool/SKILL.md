---
name: agent-tool
description: Use when adding or changing a TrailCut agent tool in packages/agent (get_portfolio_summary, get_switch_plan, simulate_switch, explain_lot, etc.). Requires a strict JSON schema, a typed handler that calls the engine, validator coverage and 3 new eval scenarios.
---

# Agent tool

Tools are the only way an agent gets a number. A tool is a thin, typed adapter
from a Claude tool call to an engine function.

## Steps
1. **Schema.** Define the input as a Pydantic model; generate the JSON schema from it.
   Use `additionalProperties: false`, enums for closed sets and bounds on numbers.
   Keep the description short, factual and free of advice language.
2. **Handler.** `def handle(input: XInput, session: Session) -> XOutput` calls engine
   functions only. No arithmetic in the handler beyond selecting fields.
3. **Output.** Return a Pydantic model. Every number the agent may quote must be in
   it, already formatted by the engine's display helpers where needed, so the
   validator can match it exactly.
4. **PII.** Outputs never contain PAN, email, phone or folio numbers. Scheme names
   from the PDF are wrapped as data (see the injection-fencing helper) before they
   reach the model.
5. **Validator coverage.** Add tests showing the numeric-claim validator accepts an
   answer quoting this tool's numbers and rejects one with a changed number.
6. **Agent access.** Add the tool to the right specialist's allow-list only
   (see CLAUDE.md agent table). The Compliance Guard is never bypassed.
7. **Evals.** Add 3 scenarios in `evals/scenarios/` that need this tool: a normal use,
   an edge case and a misuse/refusal case. Run `make evals` (see the eval-run skill).
8. `make check && make test`, then commit `feat(agent): add <tool> tool`.

## Never
- Let a tool return free text containing numbers the engine did not compute.
- Add a tool that places orders or names a fund to buy.
