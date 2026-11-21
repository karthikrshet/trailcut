"""Normalized portfolio models: the engine's input, produced by ``trailcut_ingest``.

These models deliberately have **no fields for PII**: no investor name, PAN,
email, phone, address, nominee or folio number. Folios and schemes are known
only by opaque ids (``F1``, ``F1-S2``) assigned in statement order.

Example:
    >>> txn = Transaction(
    ...     date=date(2024, 1, 10), kind=TxnKind.SIP,
    ...     amount=Decimal("5000"), units=Decimal("41.322"), nav=Decimal("121.00"),
    ... )
    >>> txn.is_unit_inflow
    True
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trailcut_engine.types import DecimalField

UNIT_TOLERANCE = Decimal("0.0015")
"""CAS prints units to 3 decimals; balances within this are considered equal."""

MAX_NAME_LENGTH = 200


class Plan(StrEnum):
    """Mutual fund plan: Regular plans pay distributor commission, Direct plans do not."""

    REGULAR = "regular"
    DIRECT = "direct"
    UNKNOWN = "unknown"


class SchemeOption(StrEnum):
    """Payout option of a scheme."""

    GROWTH = "growth"
    IDCW = "idcw"
    UNKNOWN = "unknown"


class AssetClass(StrEnum):
    """Broad tax-relevant asset class of a scheme."""

    EQUITY = "equity"
    DEBT = "debt"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class StatementSource(StrEnum):
    """Where the portfolio came from."""

    CAMS = "cams"
    KFINTECH = "kfintech"
    SAMPLE = "sample"


class TxnKind(StrEnum):
    """Normalized transaction kinds."""

    PURCHASE = "purchase"
    SIP = "sip"
    REDEMPTION = "redemption"
    SWITCH_IN = "switch_in"
    SWITCH_OUT = "switch_out"
    MERGER_IN = "merger_in"
    MERGER_OUT = "merger_out"
    DIVIDEND_REINVEST = "dividend_reinvest"
    DIVIDEND_PAYOUT = "dividend_payout"
    SEGREGATION = "segregation"
    GIFT_IN = "gift_in"
    GIFT_OUT = "gift_out"
    TAX = "tax"
    REVERSAL = "reversal"
    OTHER = "other"


UNIT_INFLOWS = frozenset(
    {
        TxnKind.PURCHASE,
        TxnKind.SIP,
        TxnKind.SWITCH_IN,
        TxnKind.MERGER_IN,
        TxnKind.DIVIDEND_REINVEST,
        TxnKind.SEGREGATION,
        TxnKind.GIFT_IN,
    }
)
"""Kinds that add units, so they create lots."""

UNIT_OUTFLOWS = frozenset(
    {TxnKind.REDEMPTION, TxnKind.SWITCH_OUT, TxnKind.MERGER_OUT, TxnKind.GIFT_OUT}
)
"""Kinds that remove units, so they consume lots FIFO."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


Name = Annotated[str, Field(min_length=1, max_length=MAX_NAME_LENGTH)]
Isin = Annotated[str, Field(pattern=r"^IN[A-Z0-9]{9}[0-9]$")]
AmfiCode = Annotated[str, Field(pattern=r"^[0-9]{1,8}$")]


class Transaction(_Model):
    """One statement row. Units are signed: positive adds units, negative removes them."""

    date: date
    kind: TxnKind
    amount: DecimalField | None = None
    units: DecimalField | None = None
    nav: Annotated[DecimalField, Field(ge=0)] | None = None
    balance: DecimalField | None = None

    @model_validator(mode="after")
    def _check_unit_sign(self) -> Self:
        if self.units is None or self.units == 0:
            return self
        if self.kind in UNIT_INFLOWS and self.units < 0:
            msg = f"{self.kind} must add units, got {self.units}"
            raise ValueError(msg)
        if self.kind in UNIT_OUTFLOWS and self.units > 0:
            msg = f"{self.kind} must remove units, got {self.units}"
            raise ValueError(msg)
        return self

    @property
    def is_unit_inflow(self) -> bool:
        """True if this row adds units (creates a lot)."""
        return self.units is not None and self.units > 0

    @property
    def is_unit_outflow(self) -> bool:
        """True if this row removes units (consumes lots FIFO)."""
        return self.units is not None and self.units < 0


class Valuation(_Model):
    """Closing valuation printed on the statement."""

    date: date
    nav: Annotated[DecimalField, Field(ge=0)]
    value: Annotated[DecimalField, Field(ge=0)]
    cost: DecimalField | None = None


class Scheme(_Model):
    """One scheme within a folio, with its full transaction history."""

    scheme_id: Annotated[str, Field(pattern=r"^F[0-9]+-S[0-9]+$")]
    name: Name
    amc: Name
    isin: Isin | None = None
    amfi_code: AmfiCode | None = None
    plan: Plan
    option: SchemeOption
    asset_class: AssetClass
    is_elss: bool
    open_units: Annotated[DecimalField, Field(ge=0)]
    close_units: Annotated[DecimalField, Field(ge=0)]
    valuation: Valuation
    transactions: tuple[Transaction, ...]

    @model_validator(mode="after")
    def _check_chronological(self) -> Self:
        dates = [t.date for t in self.transactions]
        if dates != sorted(dates):
            msg = f"{self.scheme_id}: transactions must be in date order"
            raise ValueError(msg)
        return self

    @property
    def unit_mismatch(self) -> Decimal:
        """Closing units minus (opening units + all unit movements).

        Example:
            >>> scheme.unit_mismatch  # doctest: +SKIP
            Decimal('0.000')
        """
        moved = sum((t.units for t in self.transactions if t.units is not None), Decimal(0))
        return self.close_units - (self.open_units + moved)

    @property
    def units_reconcile(self) -> bool:
        """True if the transactions explain the closing unit balance."""
        return abs(self.unit_mismatch) <= UNIT_TOLERANCE


class Folio(_Model):
    """A folio, known only by an opaque id. The real folio number is never kept."""

    folio_id: Annotated[str, Field(pattern=r"^F[0-9]+$")]
    amc: Name
    schemes: tuple[Scheme, ...]

    @model_validator(mode="after")
    def _check_scheme_ids(self) -> Self:
        for scheme in self.schemes:
            if not scheme.scheme_id.startswith(f"{self.folio_id}-"):
                msg = f"scheme {scheme.scheme_id} does not belong to folio {self.folio_id}"
                raise ValueError(msg)
        return self


class Portfolio(_Model):
    """A whole statement, normalized and free of PII."""

    source: StatementSource
    statement_from: date
    statement_to: date
    folios: tuple[Folio, ...]
    warnings: tuple[Annotated[str, Field(max_length=500)], ...] = ()

    @model_validator(mode="after")
    def _check_ids_and_period(self) -> Self:
        if self.statement_from > self.statement_to:
            msg = "statement_from must not be after statement_to"
            raise ValueError(msg)
        folio_ids = [f.folio_id for f in self.folios]
        if len(folio_ids) != len(set(folio_ids)):
            msg = "folio ids must be unique"
            raise ValueError(msg)
        scheme_ids = [s.scheme_id for s in self.schemes]
        if len(scheme_ids) != len(set(scheme_ids)):
            msg = "scheme ids must be unique"
            raise ValueError(msg)
        return self

    @property
    def schemes(self) -> tuple[Scheme, ...]:
        """All schemes across folios, in statement order."""
        return tuple(s for f in self.folios for s in f.schemes)

    def scheme(self, scheme_id: str) -> Scheme:
        """Look up a scheme by id.

        Raises:
            KeyError: if no scheme has that id.
        """
        for s in self.schemes:
            if s.scheme_id == scheme_id:
                return s
        raise KeyError(scheme_id)
