"""HTTP request and response models. Money serializes as decimal strings."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from trailcut_engine.planner import Assumptions, SwitchPlan
from trailcut_engine.report import Report
from trailcut_engine.types import DecimalField

DISCLAIMER = (
    "TrailCut is a calculator and explainer, not investment advice. It never places orders "
    "or recommends funds to buy. Check figures with your AMC or a SEBI-registered adviser "
    "before acting."
)


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class SessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    is_sample: bool
    expires_in_seconds: int
    report: Report
    plan: SwitchPlan
    assumptions: Assumptions
    notes: tuple[str, ...]
    disclaimer: str = DISCLAIMER


Percent = Annotated[DecimalField, Field(ge=0, le=10)]


class TerOverride(BaseModel):
    """Expense ratios the user read off a factsheet, in percent (1.65 = 1.65%)."""

    model_config = ConfigDict(extra="forbid")

    regular_percent: Percent
    direct_percent: Percent


class AssumptionsUpdate(BaseModel):
    """Partial update; omitted fields keep their current values."""

    model_config = ConfigDict(extra="forbid")

    expected_return: (
        Annotated[DecimalField, Field(ge=Decimal("-0.5"), le=Decimal("0.5"))] | None
    ) = None
    slab_rate: Annotated[DecimalField, Field(ge=0, le=1)] | None = None
    horizon_years: Annotated[int, Field(ge=1, le=40)] | None = None
    other_equity_ltcg_this_fy: Annotated[DecimalField, Field(ge=0)] | None = None
    use_next_fy_exemption: bool | None = None
    ter_overrides: dict[str, TerOverride] | None = None


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=2000)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, Field(min_length=1, max_length=1000)]
    history: Annotated[list[ChatTurn], Field(max_length=12)] = Field(default_factory=list)


class TraceStepOut(BaseModel):
    kind: str
    name: str
    ms: int
    detail: str


class ChatResponse(BaseModel):
    answer: str
    agent: str
    mode: str
    refused: bool
    notice: str | None
    tools_used: list[str]
    trace: list[TraceStepOut]
    turns_left: int
    disclaimer: str = DISCLAIMER


class Meta(BaseModel):
    disclaimer: str
    tax_years: tuple[str, ...]
    max_upload_mb: int
    session_ttl_seconds: int
    chat_enabled: bool
    chat_mode: Literal["llm", "offline"]
    data_sources: tuple[str, ...]
