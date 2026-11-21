---
name: release
description: Use when shipping a TrailCut version (tagging vX.Y.Z). Covers changelog, version bump across Python and web packages, full test and eval run, demo GIF refresh and the deploy checklist.
---

# Release

## Steps
1. **Branch is green.** `main` CI passes (lint/types, unit+property, API+web, Playwright).
2. **Version bump** (SemVer) in all of:
   `packages/engine/pyproject.toml`, `packages/agent/pyproject.toml`,
   `apps/api/pyproject.toml`, the matching `__version__` strings, `apps/web/package.json`.
3. **Changelog.** Add a section to `CHANGELOG.md` grouped by feat / fix / docs from
   Conventional Commit messages since the last tag. Call out any tax-rule changes with
   their sources.
4. **Full run locally:** `make check && make test && make e2e`.
5. **Evals:** `make evals`; the pass rate is at or above the baseline with 0 invented numbers.
6. **Demo assets:** if the UI changed, re-record the 60-second demo GIF and update
   README screenshots.
7. **Commit** `chore(release): vX.Y.Z`, then tag `git tag -a vX.Y.Z -m "vX.Y.Z"`.
8. **Deploy checklist** (production deploys only from tags):
   - [ ] Staging deployed from `main` and smoke-tested with the sample portfolio
   - [ ] Secrets present in the platform secret manager (none in the repo)
   - [ ] `/health` OK on the new release; rollback target noted
   - [ ] "Data as of" date on the report is current
   - [ ] Not-investment-advice notice visible on landing, report and chat
9. Push the tag only after the user confirms.
