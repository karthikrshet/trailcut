"""Typed, validated tax rules parsed from ``data/tax_rules/*.yaml`` text.

The engine never reads files. Callers read the YAML and pass the text to
:func:`parse_tax_rules`, which returns a frozen :class:`TaxRules` model.

Example:
    >>> rules = parse_tax_rules(yaml_text)  # text of data/tax_rules/fy2026_27.yaml
    >>> rules.equity.stcg_rate.value
    Decimal('0.20')
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Self

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)

SUPPORTED_SCHEMA_VERSION = 1


class TaxRulesError(ValueError):
    """Raised when tax-rule YAML is malformed or violates the schema."""


def _reject_float(value: object) -> object:
    """Refuse floats and booleans so rates are never rounded through binary floats."""
    if isinstance(value, bool):
        msg = f"booleans are not valid rule values: {value!r}"
        raise ValueError(msg)
    if isinstance(value, float):
        msg = f"floats are not allowed in tax rules; quote the value: {value!r}"
        raise ValueError(msg)
    return value


def _require_https(url: HttpUrl) -> HttpUrl:
    if url.scheme != "https":
        msg = f"source_url must use https: {url}"
        raise ValueError(msg)
    return url


def _fraction(value: Decimal) -> Decimal:
    if not Decimal(0) <= value <= Decimal(1):
        msg = f"rate must be between 0 and 1, got {value}"
        raise ValueError(msg)
    return value


def _non_negative(value: Decimal) -> Decimal:
    if value < 0:
        msg = f"amount must not be negative, got {value}"
        raise ValueError(msg)
    return value


NoFloat = BeforeValidator(_reject_float)
Rate = Annotated[Decimal, AfterValidator(_fraction), NoFloat]
Rupees = Annotated[Decimal, AfterValidator(_non_negative), NoFloat]
PositiveInt = Annotated[int, Field(gt=0), NoFloat]
HttpsUrl = Annotated[HttpUrl, AfterValidator(_require_https)]


class _Sourced(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    legal_ref: Annotated[str, Field(min_length=1)]
    source_url: HttpsUrl


class SourcedRate(_Sourced):
    """A tax rate as a fraction (``0.20`` = 20%) with its legal source."""

    value: Rate


class SourcedRupees(_Sourced):
    """A rupee amount with its legal source."""

    value: Rupees


class SourcedCount(_Sourced):
    """A positive whole number (months, years) with its legal source."""

    value: PositiveInt


class SourcedDate(_Sourced):
    """A calendar date with its legal source."""

    value: Annotated[date, NoFloat]


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EquityRules(_Section):
    """Capital-gains rules for listed equity and equity-oriented funds."""

    stcg_rate: SourcedRate
    ltcg_rate: SourcedRate
    ltcg_exemption_per_fy: SourcedRupees
    long_term_after_months: SourcedCount
    equity_oriented_min_equity_share: SourcedRate
    grandfathering_fmv_date: SourcedDate
    elss_lock_in_years: SourcedCount


class DebtRules(_Section):
    """Capital-gains rules for debt (specified) mutual fund units."""

    specified_fund_cutoff_date: SourcedDate
    legacy_long_term_after_months: SourcedCount
    legacy_ltcg_rate: SourcedRate


class SurchargeAndCessRules(_Section):
    """Levies applied on top of computed income tax."""

    health_education_cess_rate: SourcedRate


def fy_label(start_year: int) -> str:
    """Return the Indian financial-year label for a year starting 1 April.

    Example:
        >>> fy_label(2026)
        '2026-27'
    """
    return f"{start_year}-{(start_year + 1) % 100:02d}"


class TaxRules(BaseModel):
    """All tax rules for one Indian financial year (1 Apr - 31 Mar)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Annotated[int, NoFloat]
    financial_year: Annotated[str, Field(pattern=r"^\d{4}-\d{2}$")]
    effective_from: date
    effective_to: date
    equity: EquityRules
    debt: DebtRules
    surcharge_and_cess: SurchargeAndCessRules

    @model_validator(mode="after")
    def _check_financial_year(self) -> Self:
        if self.schema_version != SUPPORTED_SCHEMA_VERSION:
            msg = f"unsupported schema_version {self.schema_version}"
            raise ValueError(msg)
        start = self.effective_from
        if (start.month, start.day) != (4, 1):
            msg = f"effective_from must be 1 April, got {start.isoformat()}"
            raise ValueError(msg)
        if self.effective_to != date(start.year + 1, 3, 31):
            msg = f"effective_to must be 31 March {start.year + 1}"
            raise ValueError(msg)
        if self.financial_year != fy_label(start.year):
            msg = (
                f"financial_year {self.financial_year!r} does not match "
                f"dates (expected {fy_label(start.year)!r})"
            )
            raise ValueError(msg)
        return self

    def covers(self, on: date) -> bool:
        """Return True if ``on`` falls inside this rule set's financial year.

        Example:
            >>> rules.covers(date(2026, 4, 1)), rules.covers(date(2027, 4, 1))
            (True, False)
        """
        return self.effective_from <= on <= self.effective_to


def parse_tax_rules(text: str) -> TaxRules:
    """Parse tax-rule YAML text into a validated :class:`TaxRules`.

    Raises:
        TaxRulesError: if the YAML is invalid or breaks the schema.
    """
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        msg = f"invalid YAML: {exc}"
        raise TaxRulesError(msg) from exc
    if not isinstance(raw, dict):
        msg = "tax rules must be a YAML mapping"
        raise TaxRulesError(msg)
    try:
        return TaxRules.model_validate(raw)
    except ValidationError as exc:
        raise TaxRulesError(str(exc)) from exc
