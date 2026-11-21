# Bad tax-rule deploy

**Detect:** a user or reviewer reports a wrong tax figure; golden tests fail on `main`;
a `data/tax_rules/*.yaml` change shipped without a matching source.

**Impact:** switch plans show the wrong tax, net benefit or break-even. Plans are
advisory calculations, so nothing is executed, but the numbers are wrong until rolled back.

**First 5 minutes**

1. Find the last commit that touched `data/tax_rules/`:
   `git log --oneline -- data/tax_rules/`
2. Revert it on a branch: `git revert <sha>`.
3. Run `make check && make test`. The tax-rule golden tests must pass.
4. Merge and deploy the revert as a normal tagged release.

**Fix**

1. Reproduce the error with a golden test that fails on the bad value.
2. Correct the YAML following `.claude/skills/tax-rule-change/SKILL.md`
   (source URL, legal reference, effective date, tests on both sides of the date).
3. Ship through the normal PR flow.

**Verify:** the report footer shows the expected rule-set version; golden tests pass in CI.

**Follow-up:** blameless note in the PR; add the missing test case to the golden set.
