"""FastAPI application.

Run locally with ``uv run uvicorn trailcut_api.main:app --reload --no-access-log``
(access logs would record session ids in URLs).
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, SecretStr

from trailcut_api import __version__
from trailcut_api.market.service import MarketService
from trailcut_api.ratelimit import RateLimiter
from trailcut_api.schemas import (
    DISCLAIMER,
    AssumptionsUpdate,
    ErrorResponse,
    Meta,
    SessionResponse,
)
from trailcut_api.sessions import Session, SessionNotFoundError, SessionStore
from trailcut_api.settings import Settings
from trailcut_engine.planner import Assumptions, SwitchPlan, plan_switch
from trailcut_engine.report import Report, build_report
from trailcut_engine.tax_rules import TaxRules, parse_tax_rules
from trailcut_ingest.errors import IngestError
from trailcut_ingest.pdf import MAX_PDF_BYTES, parse_cas_pdf
from trailcut_ingest.sample import load_sample_portfolio

HUNDRED = Decimal(100)
MAX_PASSWORD_LENGTH = 128
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}


class HealthResponse(BaseModel):
    """Liveness payload. Contains no user data."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    version: str


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.headers = status, code, message, headers or {}


def load_rules(data_dir: Path) -> list[TaxRules]:
    """Every ``data/tax_rules/*.yaml``, validated."""
    return [
        parse_tax_rules(p.read_text(encoding="utf-8"))
        for p in sorted((data_dir / "tax_rules").glob("*.yaml"))
    ]


@dataclass
class AppContext:
    settings: Settings
    sessions: SessionStore
    limiter: RateLimiter
    market: MarketService
    rules: list[TaxRules]
    today: Callable[[], date]


def _error(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorResponse.model_validate({"error": {"code": code, "message": message}})
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


def create_app(  # noqa: PLR0915 - route table
    settings: Settings | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
    today: Callable[[], date] = date.today,
    market: MarketService | None = None,
) -> FastAPI:
    """Build the TrailCut API.

    Example:
        >>> create_app().title
        'TrailCut API'
    """
    s = settings or Settings.from_env()
    ctx = AppContext(
        settings=s,
        sessions=SessionStore(
            ttl_seconds=s.session_ttl_seconds, max_sessions=s.max_sessions, clock=clock
        ),
        limiter=RateLimiter(per_minute=s.rate_limit_per_minute, clock=clock),
        market=market or MarketService(s.data_dir, s.cache_dir, online=s.online),
        rules=load_rules(s.data_dir),
        today=today,
    )
    app = FastAPI(
        title="TrailCut API",
        version=__version__,
        description=(
            "Plans a tax-smart Regular to Direct mutual fund switch. "
            "A calculator and explainer, not investment advice."
        ),
    )
    app.state.ctx = ctx
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(s.allowed_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", "")[:64] or secrets.token_hex(8)
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_PDF_BYTES + 64 * 1024:
            response: Response = _error(413, "file_too_large", "The file is 10 MB or larger.")
        else:
            response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApiError)
    async def on_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message, exc.headers)

    @app.exception_handler(IngestError)
    async def on_ingest_error(_: Request, exc: IngestError) -> JSONResponse:
        return _error(422, exc.code, exc.user_message)

    @app.exception_handler(SessionNotFoundError)
    async def on_missing_session(_: Request, __: SessionNotFoundError) -> JSONResponse:
        return _error(
            404,
            "session_expired",
            "This session has expired or was deleted. Upload your statement again.",
        )

    @app.exception_handler(RequestValidationError)
    async def on_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo submitted values back (they could include a password).
        fields = sorted({".".join(str(p) for p in e.get("loc", ())[1:]) for e in exc.errors()})
        return _error(422, "invalid_request", f"Check these fields: {', '.join(fields) or 'body'}.")

    def rate_limit(request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        if not ctx.limiter.allow(key):
            raise ApiError(
                429,
                "rate_limited",
                "Too many requests. Please wait a moment.",
                {"Retry-After": str(ctx.limiter.retry_after(key))},
            )

    def build(session: Session) -> tuple[Report, SwitchPlan]:
        a = session.assumptions
        report = build_report(session.portfolio, session.market, expected_return=a.expected_return)
        plan = plan_switch(session.portfolio, session.market, ctx.rules, a)
        return report, plan

    def respond(session: Session) -> SessionResponse:
        report, plan = build(session)
        return SessionResponse(
            session_id=session.session_id,
            is_sample=session.is_sample,
            expires_in_seconds=ctx.settings.session_ttl_seconds,
            report=report,
            plan=plan,
            assumptions=session.assumptions,
            notes=session.notes + session.portfolio.warnings,
        )

    @app.get("/health", tags=["ops"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/v1/meta", tags=["meta"])
    def meta() -> Meta:
        return Meta(
            disclaimer=DISCLAIMER,
            tax_years=tuple(r.financial_year for r in ctx.rules),
            max_upload_mb=MAX_PDF_BYTES // (1024 * 1024),
            session_ttl_seconds=ctx.settings.session_ttl_seconds,
            chat_enabled=ctx.settings.anthropic_api_key is not None,
            data_sources=("AMFI (NAV, TER)", "casparser (CAS parsing, MIT)", "data/tax_rules"),
        )

    @app.post("/v1/sessions/sample", tags=["sessions"], status_code=201)
    def create_sample() -> SessionResponse:
        portfolio = load_sample_portfolio()
        session = ctx.sessions.create(
            portfolio,
            ctx.market.sample_market(portfolio),
            Assumptions(as_of=portfolio.statement_to),
            is_sample=True,
            notes=(
                "Sample portfolio: all funds and numbers are fictional, as of "
                f"{portfolio.statement_to.strftime('%d %b %Y').lstrip('0')}.",
            ),
        )
        return respond(session)

    @app.post(
        "/v1/sessions/upload",
        tags=["sessions"],
        status_code=201,
        responses={
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    def upload(
        request: Request,
        file: Annotated[UploadFile, File(description="CAMS/KFintech Detailed CAS PDF")],
        password: Annotated[str, Form(max_length=MAX_PASSWORD_LENGTH)] = "",
    ) -> SessionResponse:
        rate_limit(request)
        buffer = bytearray(file.file.read(MAX_PDF_BYTES + 1))
        try:
            portfolio = parse_cas_pdf(buffer, SecretStr(password))
        finally:
            buffer[:] = bytes(len(buffer))
            file.file.close()
        session = ctx.sessions.create(
            portfolio, ctx.market.market_for(portfolio), Assumptions(as_of=ctx.today())
        )
        return respond(session)

    @app.get("/v1/sessions/{session_id}", tags=["sessions"])
    def get_session(session_id: str) -> SessionResponse:
        return respond(ctx.sessions.get(session_id))

    @app.get("/v1/sessions/{session_id}/report", tags=["sessions"])
    def get_report(session_id: str) -> Report:
        return build(ctx.sessions.get(session_id))[0]

    @app.get("/v1/sessions/{session_id}/plan", tags=["sessions"])
    def get_plan(session_id: str) -> SwitchPlan:
        return build(ctx.sessions.get(session_id))[1]

    @app.patch("/v1/sessions/{session_id}/assumptions", tags=["sessions"])
    def update_assumptions(session_id: str, update: AssumptionsUpdate) -> SessionResponse:
        session = ctx.sessions.get(session_id)
        changes = update.model_dump(exclude_none=True, exclude={"ter_overrides"})
        assumptions = session.assumptions.model_copy(update=changes)
        Assumptions.model_validate(assumptions.model_dump())
        market = session.market
        if update.ter_overrides:
            unknown = set(update.ter_overrides) - {x.scheme_id for x in session.portfolio.schemes}
            if unknown:
                raise ApiError(
                    422,
                    "unknown_scheme",
                    "Expense ratios were sent for a fund not in this portfolio.",
                )
            market = ctx.market.with_overrides(
                market,
                {
                    k: (v.regular_percent / HUNDRED, v.direct_percent / HUNDRED)
                    for k, v in update.ter_overrides.items()
                },
            )
        session = ctx.sessions.update(replace(session, assumptions=assumptions, market=market))
        return respond(session)

    @app.delete("/v1/sessions/{session_id}", tags=["sessions"], status_code=204)
    def delete_session(session_id: str) -> Response:
        ctx.sessions.delete(session_id)
        return Response(status_code=204)

    return app


app = create_app()
