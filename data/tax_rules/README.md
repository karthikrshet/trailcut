# Tax rules

One YAML file per financial year, named `fyYYYY_YY.yaml`. These files are the only
place TrailCut stores tax rates, exemptions and holding periods.

Rules:

- Every value is a **quoted string** (parsed to `Decimal`, `int` or `date`). Unquoted
  floats are rejected so no rate is ever rounded through binary floating point.
- Every value has a `legal_ref` and an `https` `source_url`.
- `effective_from` / `effective_to` must span exactly one Indian financial year.
- Changes go through `.claude/skills/tax-rule-change/SKILL.md`, with golden tests on
  both sides of any effective date.

The schema is enforced by `trailcut_engine.tax_rules.parse_tax_rules`.

> **Before Sprint 3 relies on these values:** a human must confirm each `source_url`
> points at the exact section text (the current URLs point at the Act index page).
