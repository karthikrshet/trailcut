# Thin wrapper: every target runs scripts/dev.py so Windows users without make
# can run the same thing with `uv run python scripts/dev.py <target>`.

RUN := uv run python scripts/dev.py

.PHONY: install check test test-unit test-api test-web e2e evals dev hooks

install: ## Install Python and web dependencies, and the git hook
	uv sync
	pnpm install
	git config core.hooksPath .githooks

check: ## ruff, ruff format, mypy --strict, eslint, tsc
	$(RUN) check

test: ## unit + property (engine coverage >= 90%), API, web
	$(RUN) test

test-unit:
	$(RUN) test-unit

test-api:
	$(RUN) test-api

test-web:
	$(RUN) test-web

e2e: ## Playwright end-to-end
	$(RUN) e2e

evals: ## agent eval scenarios x3
	$(RUN) evals

dev: ## API on :8000 and web on :5173
	$(RUN) dev

hooks: ## enable the pre-commit hook
	git config core.hooksPath .githooks
