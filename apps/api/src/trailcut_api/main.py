"""FastAPI application factory.

Run locally with ``uv run uvicorn trailcut_api.main:app --reload``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from trailcut_api import __version__


class HealthResponse(BaseModel):
    """Liveness payload. Contains no user data."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    version: str


def create_app() -> FastAPI:
    """Build the TrailCut API.

    Example:
        >>> app = create_app()
        >>> app.title
        'TrailCut API'
    """
    app = FastAPI(
        title="TrailCut API",
        version=__version__,
        description=(
            "Plans a tax-smart Regular to Direct mutual fund switch. "
            "A calculator and explainer, not investment advice."
        ),
    )

    @app.get("/health", tags=["ops"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
