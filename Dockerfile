# TrailCut API: multi-stage, non-root, health-checked.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_FROZEN=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN uv sync --no-dev --package trailcut-api

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 trailcut
WORKDIR /app
COPY --from=build --chown=trailcut:trailcut /app /app
COPY --chown=trailcut:trailcut data ./data
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TRAILCUT_DATA_DIR=/app/data \
    TRAILCUT_CACHE_DIR=/tmp/trailcut-cache
USER trailcut
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
# --no-access-log: access logs would record session ids in URLs.
CMD ["uvicorn", "trailcut_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]
