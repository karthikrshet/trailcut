---
name: eval-run
description: Use before merging ANY change to TrailCut agent prompts, tool descriptions, routing, the validator or the Claude model. Runs all eval scenarios x3, compares with the baseline and blocks on a pass-rate drop or any invented number.
---

# Eval run

## When
- Any change under `packages/agent/` that touches prompts, tool schemas or
  descriptions, routing or the Compliance Guard.
- Any model ID change.
- Nightly in CI (automatic).

## Steps
1. Make sure `ANTHROPIC_API_KEY` is set in your environment (never commit it).
2. Run `make evals`. Every scenario runs 3 times; a scenario passes only if all 3 pass.
3. Read the summary: pass rate overall and per category, invented-number count,
   wrong-tool count, refusal accuracy.
4. Compare with `evals/baseline.json`:
   - **Block** if the overall pass rate drops, any category drops by more than one
     scenario, or **any** invented number appears.
   - Improvements: update the baseline in the same PR, and say why in the body.
5. Paste the summary table into the PR description.

## Never
- Delete or loosen a failing scenario to recover the pass rate. Fix the prompt, tool or
  validator. A scenario can only be retired with a written reason and a replacement.
- Run evals against real user data. Scenarios use synthetic portfolios only.
