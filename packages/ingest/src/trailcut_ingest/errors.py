"""Ingestion errors with plain-language messages that are safe to show users.

Messages never contain the password, file contents or any PII.
"""

from __future__ import annotations

from typing import ClassVar


class IngestError(Exception):
    """Base class. ``code`` is stable for the API; ``user_message`` is shown as-is."""

    code: ClassVar[str] = "ingest_error"
    user_message: ClassVar[str] = "We couldn't read this statement."

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.user_message)


class EmptyFileError(IngestError):
    code = "empty_file"
    user_message = "The file is empty. Please upload your CAS PDF again."


class FileTooLargeError(IngestError):
    code = "file_too_large"
    user_message = "The file is 10 MB or larger. A CAS statement is usually under 2 MB."


class NotAPdfError(IngestError):
    code = "not_a_pdf"
    user_message = "This isn't a PDF. Upload the CAS PDF you received from CAMS or KFintech."


class WrongPasswordError(IngestError):
    code = "wrong_password"
    user_message = (
        "That password didn't open the PDF. It's the password you set when you "
        "requested the CAS (often your PAN in capitals)."
    )


class MFCentralStatementError(IngestError):
    code = "mf_central_statement"
    user_message = (
        "This looks like an MF Central statement, which we can't read yet. Download the "
        "Detailed CAS from CAMS (camsonline.com) or KFintech instead; it's free and takes "
        "about two minutes."
    )


class SummaryStatementError(IngestError):
    code = "summary_statement"
    user_message = (
        "This is a Summary CAS, which has no transaction history. Request the Detailed "
        "statement (with transactions) from CAMS or KFintech."
    )


class DepositoryStatementError(IngestError):
    code = "depository_statement"
    user_message = (
        "This is an NSDL/CDSL depository statement. It doesn't list mutual fund purchases "
        "lot by lot. Download the Detailed CAS from CAMS or KFintech instead."
    )


class UnrecognizedStatementError(IngestError):
    code = "unrecognized_statement"
    user_message = (
        "We couldn't recognise this PDF as a CAMS or KFintech Consolidated Account "
        "Statement. Please upload the Detailed CAS you received by email."
    )


class StatementParseError(IngestError):
    code = "parse_failed"
    user_message = (
        "We recognised the statement but couldn't read all of it. Try downloading a fresh "
        "copy of the Detailed CAS. Re-printed or edited PDFs often fail."
    )


ALL_ERRORS: tuple[type[IngestError], ...] = (
    EmptyFileError,
    FileTooLargeError,
    NotAPdfError,
    WrongPasswordError,
    MFCentralStatementError,
    SummaryStatementError,
    DepositoryStatementError,
    UnrecognizedStatementError,
    StatementParseError,
)
