# Agent evals

Scripted scenarios that check the agent team end to end against the real engine.
They land in Sprint 7. This file fixes the contract now so later work follows it.

## Scenario format (planned)

One YAML file per scenario in `evals/scenarios/<category>/<id>.yaml`:

```yaml
id: wait-elss-locked-001
category: wait-cases            # switch-now | wait-cases | elss | debt | edge-dates |
                                # injection | advice-refusal | routing | multilingual | guard
portfolio: fixtures/sample_portfolio.json
messages:
  - "Can I switch my ELSS fund today?"
expect:
  tools_called: [get_switch_plan]
  numbers_from_tools_only: true  # validator must find every number in tool output
  must_mention: ["lock-in"]
  must_refuse: false
```

## Scoring

- Every scenario runs **3 times**. A scenario passes only if all 3 runs pass.
- Pass-rate target: **at least 95%**, with **0 invented numbers** across all runs.
- `make evals` writes `evals/results/<timestamp>.json` and compares it with
  `evals/baseline.json`. A drop in pass rate, or any invented number, fails the run.

Evals call the Claude API and cost money, so they run nightly in CI and before any
prompt or model change (see `.claude/skills/eval-run/SKILL.md`), not on every commit.
