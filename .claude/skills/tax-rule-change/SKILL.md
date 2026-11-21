---
name: tax-rule-change
description: Use for ANY change to tax rates, exemptions, holding periods, lock-ins, grandfathering dates or cess in TrailCut, including adding a new financial year. Edits only data/tax_rules/*.yaml with sources and golden tests on both sides of the effective date.
---

# Tax rule change

Tax figures live in exactly one place: `data/tax_rules/fyYYYY_YY.yaml`. Code never
hardcodes a rate (the repo policy test `test_tax_rates_are_not_hardcoded_in_source`
fails if it does).

## Steps

1. **Find the primary source.** Finance Act, Income-tax Act section, CBDT circular or
   notification. Secondary blogs are not sources. Note the exact effective date.
2. **Pick the file.**
   - The change applies from 1 April of a new FY → copy the latest file to
     `fyYYYY_YY.yaml`, update `financial_year`, `effective_from`, `effective_to`.
   - The change applies mid-year (e.g. Budget effective 23 Jul) → stop and flag it.
     Schema v1 has one value per FY. Plan a schema change with an engine-feature
     change first; do not fake it.
3. **Edit values as quoted strings** (`value: "0.125"`). Unquoted floats are rejected.
   Update `legal_ref` and `source_url` (https only) for every value you touch.
4. **Add golden tests** in `packages/engine/tests/test_tax_rules.py` (or a new
   `test_tax_rules_fyYYYY_YY.py`): the exact new values, plus `covers()` checks on the
   last day before and the first day of the period.
5. **Add engine golden cases** for any tax computation that uses the changed value:
   one lot sold the day before the effective date, one on the date.
6. Run `make check && make test`. Do not edit an existing expected value to make a
   test pass unless the source proves the old expectation was wrong; say so in the commit.
7. Commit: `feat(tax): <what changed> for FY YYYY-YY` with the source URL in the body.

## Never
- Put a rate, threshold or date in Python or TypeScript.
- Delete an old FY file (plans for past sales still need it).
- Mark a value changed without a primary source.
