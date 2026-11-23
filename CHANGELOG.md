# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Monorepo with uv and pnpm workspaces, strict linting and typing, a pre-commit hook and
  a four-stage CI pipeline with an engine coverage gate.
- FY 2026-27 tax rules in YAML with legal references and a typed, float-rejecting loader.
- Ingestion: in-memory CAS parsing via casparser, plain-language errors (MF Central,
  Summary, NSDL/CDSL, wrong password), PII masking and PII-free models.
- Engine: XIRR, FIFO lots with stamp duty and reversals, capital-gains classification
  and tax with set-off and the yearly exemption, 2018 grandfathering, exit loads,
  Regular-vs-Direct projections, commission-leak report.
- Switch optimizer: lot-by-lot Switch now / Wait until / Keep / Review with reasons,
  per-FY tax, timeline, break-even and baselines.
- API: sample and upload sessions, report, plan, editable assumptions, chat, delete;
  rate limits, TTL sessions and security headers.
- Web: landing, report, switch plan, assumptions, expense-ratio entry and chat drawer on
  Razorpay Blade with motion that honours reduced-motion settings.
- Agents: four specialists over eight engine tools, fund-picking and order refusals,
  numeric-claim validator with prompt-injection hardening, offline fallback, evals.
- Docs: user guide, testing guide, agent design, API reference, runbooks.

- Quick commission estimate without a statement (`POST /v1/estimate` and a landing
  section), CSV export and print view of the plan, dark mode, and a 3D landing hero.

### Security
- Figures inside statement text are never accepted as evidence by the validator.
