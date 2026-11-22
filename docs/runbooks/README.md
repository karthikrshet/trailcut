# Runbooks

Short, step-by-step guides for operating TrailCut in production. Each runbook
answers: how do I know it is happening, what do I do first, how do I confirm it is
fixed, and who or what do I tell.

| Runbook | Trigger | Status |
| --- | --- | --- |
| [Bad tax-rule deploy](bad-tax-rule-deploy.md) | Wrong rate or date shipped in `data/tax_rules` | Ready |
| [LLM outage](llm-outage.md) | Claude API errors or timeouts; chat degraded | Ready |
| [AMFI data outage](amfi-data-outage.md) | NAV/TER refresh fails; stale-data alert | Ready |
| [Parser failures spike](parser-failures.md) | CAS parse error rate above baseline | Ready |

## Template

```markdown
# <Title>

**Detect:** alert name / symptom
**Impact:** what users see
**First 5 minutes:** numbered steps
**Fix:** numbered steps
**Verify:** how to confirm recovery
**Follow-up:** postmortem, tests to add
```

Runbooks must never ask anyone to look at a user's PDF, PAN, email, phone or folio
number. TrailCut does not keep them.
