"""Parse an uploaded CAS PDF, entirely in memory.

Example:
    >>> portfolio = parse_cas_pdf(bytearray(upload), SecretStr(password))  # doctest: +SKIP

Guarantees:

- The PDF is never written to disk; the password is never logged or echoed.
- A ``bytearray`` buffer is zeroed after parsing (success or failure).
- Every failure becomes an :class:`~trailcut_ingest.errors.IngestError` with a
  plain-language message; parser messages (which may contain PII) are dropped.
"""

from __future__ import annotations

import io
from collections.abc import Callable

import pypdfium2 as pdfium
from pydantic import SecretStr

from trailcut_engine.portfolio import Portfolio
from trailcut_ingest.errors import (
    EmptyFileError,
    FileTooLargeError,
    IngestError,
    MFCentralStatementError,
    NotAPdfError,
    StatementParseError,
    UnrecognizedStatementError,
    WrongPasswordError,
)
from trailcut_ingest.normalize import normalize_cas

MAX_PDF_BYTES = 10 * 1024 * 1024
"""Uploads of 10 MB or more are rejected."""

PDF_MAGIC = b"%PDF-"
MF_CENTRAL_MARKERS = ("mfcentral", "mf central", "mfcentral.com")

Parser = Callable[[io.BytesIO, str], object]
TextSniffer = Callable[[bytes, str], str]


def check_upload(data: bytes | bytearray) -> None:
    """Reject empty, oversized or non-PDF uploads before any parsing.

    Example:
        >>> check_upload(b"%PDF-1.7 ...")
    """
    if not data:
        raise EmptyFileError
    if len(data) >= MAX_PDF_BYTES:
        raise FileTooLargeError
    # Allow a little leading junk, as the PDF spec does (first 1 KB).
    if PDF_MAGIC not in bytes(data[:1024]):
        raise NotAPdfError


def first_page_text(data: bytes, password: str) -> str:
    """Text of the first page, or ``""`` if the PDF can't be opened."""
    try:
        doc = pdfium.PdfDocument(data, password=password or None)
    except Exception:
        return ""
    try:
        if len(doc) == 0:
            return ""
        page = doc[0]
        textpage = page.get_textpage()
        return str(textpage.get_text_bounded())
    except Exception:
        return ""
    finally:
        doc.close()


def is_mf_central(text: str) -> bool:
    """True if statement text looks like an MF Central CAS.

    Example:
        >>> is_mf_central("Consolidated Account Statement ... MFCentral")
        True
    """
    lowered = " ".join(text.lower().split())
    return any(marker in lowered for marker in MF_CENTRAL_MARKERS)


def _default_parser(stream: io.BytesIO, password: str) -> object:
    import casparser  # noqa: PLC0415 - heavy import, only when parsing a real PDF

    return casparser.read_cas_pdf(stream, password)


def _error_kind(exc: Exception) -> str:
    """Classify a casparser exception by class name (avoids importing casparser)."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    if "IncorrectPasswordError" in names:
        return "password"
    if names & {"CASParseError", "HeaderParseError"}:
        return "unrecognised"
    if "ParserException" in names:
        return "parse"
    message = str(exc).lower()
    if "password" in message:
        return "password"
    return "parse"


def parse_cas_pdf(
    data: bytes | bytearray,
    password: SecretStr | str,
    *,
    parser: Parser | None = None,
    sniffer: TextSniffer = first_page_text,
) -> Portfolio:
    """Parse a CAMS/KFintech Detailed CAS PDF into a PII-free :class:`Portfolio`.

    Args:
        data: the uploaded file. Pass a ``bytearray`` to have it zeroed afterwards.
        password: the PDF password.
        parser: injectable for tests; defaults to ``casparser.read_cas_pdf``.
        sniffer: injectable first-page text extractor (MF Central detection).

    Raises:
        IngestError: a subclass describing exactly what went wrong.
    """
    secret = password.get_secret_value() if isinstance(password, SecretStr) else password
    try:
        check_upload(data)
        payload = bytes(data)
        try:
            result = (parser or _default_parser)(io.BytesIO(payload), secret)
        except IngestError:
            raise
        except Exception as exc:
            kind = _error_kind(exc)
            if kind == "password":
                raise WrongPasswordError from None
            if is_mf_central(sniffer(payload, secret)):
                raise MFCentralStatementError from None
            if kind == "unrecognised":
                raise UnrecognizedStatementError from None
            raise StatementParseError(type(exc).__name__) from None
        dumped = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result
        if not isinstance(dumped, dict):
            raise StatementParseError("parser returned no data")
        return normalize_cas(dumped)
    finally:
        if isinstance(data, bytearray):
            data[:] = bytes(len(data))
