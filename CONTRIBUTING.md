# Contributing

Thanks for helping. TrailCut handles people's money questions, so a few rules are firm.

## Ground rules

Read [CLAUDE.md](CLAUDE.md): it is the rule book for humans and AI alike. In short:

1. The AI never calculates; every figure comes from the engine.
2. Money is `Decimal`, never `float`.
3. Tax rates live only in `data/tax_rules/*.yaml`, with sources.
4. Never store or log PDFs or personal data.
5. Never weaken a test to make CI pass.

## Workflow

```bash
make install          # deps + pre-commit hook
make check && make test
```

- One logical change per commit, with its tests, using Conventional Commits
  (`feat(engine): ...`, `fix(api): ...`, `docs: ...`). The hook runs check and test.
- Recurring jobs have step-by-step guides in `.claude/skills/` (tax-rule change, engine
  feature, agent tool, UI component, eval run, release).
- UI changes: Blade components and tokens only, Lucide icons, four states per view,
  375 px, reduced motion. Include a screenshot in the PR.
- Never commit a real statement. Use the generators in `scripts/`.
