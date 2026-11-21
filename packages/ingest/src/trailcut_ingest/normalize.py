"""Normalize casparser output into a PII-free engine :class:`Portfolio`.

The input is the dict form of ``casparser.CASData`` (``model_dump()``), validated
here with our own lenient models so we depend only on the fields we use.

Example:
    >>> portfolio = normalize_cas(cas_dict)  # doctest: +SKIP
    >>> portfolio.folios[0].folio_id
    'F1'
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from trailcut_engine.portfolio import (
    MAX_NAME_LENGTH,
    UNIT_INFLOWS,
    UNIT_OUTFLOWS,
    Folio,
    Portfolio,
    Scheme,
    StatementSource,
    Transaction,
    TxnKind,
    Valuation,
)
from trailcut_ingest.classify import (
    detect_asset_class,
    detect_option,
    detect_plan,
    is_elss,
    map_transaction_type,
)
from trailcut_ingest.errors import (
    DepositoryStatementError,
    StatementParseError,
    SummaryStatementError,
    UnrecognizedStatementError,
)
from trailcut_ingest.pii import PiiMasker

DATE_FORMATS = ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y")
ISIN_RE = re.compile(r"^IN[A-Z0-9]{9}[0-9]$")
AMFI_RE = re.compile(r"^[0-9]{1,8}$")
MAX_WARNING_LENGTH = 500


def parse_date(value: date | str) -> date:
    """Parse a statement date in any format casparser emits.

    Example:
        >>> parse_date("05-Jan-2016")
        datetime.date(2016, 1, 5)
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 - calendar date only
        except ValueError:
            continue
    msg = f"unrecognised date: {text[:20]!r}"
    raise ValueError(msg)


def clean_text(value: str, limit: int = MAX_NAME_LENGTH) -> str:
    """Strip control/format characters, collapse whitespace and cap the length.

    PDF text is untrusted: this removes invisible characters that could hide
    content, but does not interpret the text in any way.
    """
    kept = "".join(
        " " if unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"} else ch for ch in value
    )
    return " ".join(kept.split())[:limit].strip()


# ---------- lenient input models (casparser.CASData subset) ----------


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RawTransaction(_Raw):
    date: date | str
    type: str = "UNKNOWN"
    amount: Decimal | None = None
    units: Decimal | None = None
    nav: Decimal | None = None
    balance: Decimal | None = None

    @field_validator("type", mode="before")
    @classmethod
    def _enum_to_str(cls, v: object) -> object:
        return getattr(v, "value", v)


class RawValuation(_Raw):
    date: date | str
    nav: Decimal
    value: Decimal
    cost: Decimal | None = None


class RawScheme(_Raw):
    scheme: str
    advisor: str | None = None
    type: str | None = None
    isin: str | None = None
    amfi: str | None = None
    nominees: list[str] = Field(default_factory=list)
    open: Decimal = Decimal(0)
    close: Decimal
    valuation: RawValuation
    transactions: list[RawTransaction] = Field(default_factory=list)


class RawFolio(_Raw):
    folio: str = ""
    amc: str = ""
    name: str | None = None
    PAN: str | None = None
    schemes: list[RawScheme] = Field(default_factory=list)


class RawInvestor(_Raw):
    name: str = ""
    email: str = ""
    address: str = ""
    mobile: str = ""


class RawPeriod(_Raw):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    from_: str = Field(alias="from")
    to: str


class RawCAS(_Raw):
    statement_period: RawPeriod
    folios: list[RawFolio]
    investor_info: RawInvestor = Field(default_factory=RawInvestor)
    cas_type: str = "UNKNOWN"
    file_type: str = "UNKNOWN"
    parse_warnings: list[str] = Field(default_factory=list)

    @field_validator("cas_type", "file_type", mode="before")
    @classmethod
    def _enum_to_str(cls, v: object) -> object:
        return str(getattr(v, "value", v)).upper()


# ---------- normalization ----------


def _known_pii(raw: RawCAS) -> list[str | None]:
    info = raw.investor_info
    values: list[str | None] = [info.name, info.email, info.mobile, info.address]
    values += [line for line in re.split(r"[\n,]", info.address) if len(line.strip()) >= 6]
    for folio in raw.folios:
        values += [folio.folio, folio.PAN, folio.name]
        for scheme in folio.schemes:
            values += scheme.nominees
    return values


def _transaction(raw: RawTransaction) -> Transaction:
    kind = map_transaction_type(raw.type)
    units = raw.units
    # A row whose unit sign contradicts its type is a reversal in practice
    # (e.g. a bounced SIP printed as a negative purchase).
    if units is not None and (
        (kind in UNIT_INFLOWS and units < 0) or (kind in UNIT_OUTFLOWS and units > 0)
    ):
        kind = TxnKind.REVERSAL
    nav = raw.nav if raw.nav is not None and raw.nav >= 0 else None
    return Transaction(
        date=parse_date(raw.date),
        kind=kind,
        amount=raw.amount,
        units=units,
        nav=nav,
        balance=raw.balance,
    )


def normalize_cas(
    data: Mapping[str, Any],
    *,
    source: StatementSource | None = None,
) -> Portfolio:
    """Convert casparser ``CASData`` (as a dict) into a PII-free :class:`Portfolio`.

    Raises:
        SummaryStatementError: for a Summary CAS (no transactions).
        DepositoryStatementError: for NSDL/CDSL statements.
        UnrecognizedStatementError: for any other issuer.
        StatementParseError: if the data is structurally unusable.
    """
    file_type = str(getattr(data.get("file_type"), "value", data.get("file_type", ""))).upper()
    if file_type in {"NSDL", "CDSL"}:
        raise DepositoryStatementError
    try:
        raw = RawCAS.model_validate(data)
    except ValidationError as exc:
        raise StatementParseError(f"unusable parser output ({exc.error_count()} errors)") from None
    if source is None:
        if raw.file_type == "CAMS":
            source = StatementSource.CAMS
        elif raw.file_type == "KFINTECH":
            source = StatementSource.KFINTECH
        else:
            raise UnrecognizedStatementError
    if raw.cas_type == "SUMMARY":
        raise SummaryStatementError
    if raw.cas_type != "DETAILED":
        raise UnrecognizedStatementError

    masker = PiiMasker(_known_pii(raw))
    try:
        folios = tuple(_folios(raw.folios, masker))
        warnings = list(_warnings(raw.parse_warnings, masker))
        for folio in folios:
            for scheme in folio.schemes:
                if not scheme.units_reconcile:
                    explained = scheme.close_units - scheme.unit_mismatch
                    warnings.append(
                        f"{scheme.scheme_id}: transactions explain {explained} of "
                        f"{scheme.close_units} units; some rows may be missing from the statement."
                    )
        return Portfolio(
            source=source,
            statement_from=parse_date(raw.statement_period.from_),
            statement_to=parse_date(raw.statement_period.to),
            folios=folios,
            warnings=tuple(w[:MAX_WARNING_LENGTH] for w in warnings),
        )
    except (ValidationError, ValueError) as exc:
        # Never echo parser values: they may contain PII.
        raise StatementParseError(type(exc).__name__) from None


def _folios(raw_folios: Iterable[RawFolio], masker: PiiMasker) -> Iterable[Folio]:
    for f_index, raw_folio in enumerate(raw_folios, start=1):
        folio_id = f"F{f_index}"
        amc = clean_text(masker.mask(clean_text(raw_folio.amc, limit=1000))) or "Unknown AMC"
        schemes = tuple(
            _build_scheme(s, f"{folio_id}-S{s_index}", amc, masker)
            for s_index, s in enumerate(raw_folio.schemes, start=1)
        )
        yield Folio(folio_id=folio_id, amc=amc, schemes=schemes)


def _build_scheme(raw: RawScheme, scheme_id: str, amc: str, masker: PiiMasker) -> Scheme:
    name = clean_text(masker.mask(clean_text(raw.scheme, limit=1000))) or "Unnamed scheme"
    isin = (raw.isin or "").strip().upper()
    amfi = (raw.amfi or "").strip()
    transactions = sorted((_transaction(t) for t in raw.transactions), key=lambda t: t.date)
    v = raw.valuation
    return Scheme(
        scheme_id=scheme_id,
        name=name,
        amc=amc,
        isin=isin if ISIN_RE.match(isin) else None,
        amfi_code=amfi if AMFI_RE.match(amfi) else None,
        plan=detect_plan(name, raw.advisor),
        option=detect_option(name),
        asset_class=detect_asset_class(name, raw.type),
        is_elss=is_elss(name),
        open_units=max(raw.open, Decimal(0)),
        close_units=max(raw.close, Decimal(0)),
        valuation=Valuation(
            date=parse_date(v.date),
            nav=max(v.nav, Decimal(0)),
            value=max(v.value, Decimal(0)),
            cost=v.cost,
        ),
        transactions=tuple(transactions),
    )


def _warnings(raw_warnings: Iterable[str], masker: PiiMasker) -> Iterable[str]:
    for w in raw_warnings:
        text = clean_text(masker.mask(clean_text(w, limit=2000)), limit=MAX_WARNING_LENGTH)
        if text:
            yield text
