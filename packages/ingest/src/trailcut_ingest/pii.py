"""PII masking for any text that leaves ingestion (warnings, scheme names, LLM input).

Two layers:

1. **Known values.** Exact PAN, folio numbers, names, email, phone and address
   lines read from the statement header are replaced wherever they appear.
2. **Patterns.** Anything that *looks like* a PAN, email, Indian phone number or a
   ``Folio No: ...`` reference is replaced even if it was not in the header.

Example:
    >>> mask_text("Folio No: 1234567/89 PAN ABCPE1234F mail a.b@x.in")
    'Folio No: [FOLIO] PAN [PAN] mail [EMAIL]'
"""

from __future__ import annotations

import re
from collections.abc import Iterable

PAN_MASK = "[PAN]"
EMAIL_MASK = "[EMAIL]"
PHONE_MASK = "[PHONE]"
FOLIO_MASK = "[FOLIO]"
REDACTED_MASK = "[REDACTED]"

MIN_KNOWN_LENGTH = 4
"""Known values shorter than this are not masked (too likely to hit ordinary words)."""

# 4th character encodes holder type (P person, C company, H HUF, F firm, A AOP, ...).
PAN_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]{3}[ABCFGHLJPTabcfghljpt][A-Za-z][0-9]{4}[A-Za-z](?![A-Za-z0-9])"
)
EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# Indian mobile: optional +91 / 91 / 0 prefix, 10 digits starting 6-9, optional separators.
PHONE_RE = re.compile(r"(?<![\d.,])(?:(?:\+|00)?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?![\d.,])")
FOLIO_RE = re.compile(
    r"(?i)(\bfolio\b\s*(?:no\.?|number|num\.?|#)?\s*[:.\-]?\s*)"
    r"([A-Za-z0-9]{3,}(?:\s*/\s*[A-Za-z0-9]+)?)"
)


def _variants(value: str) -> set[str]:
    """Spellings of a known value as it may appear elsewhere in a statement."""
    cleaned = " ".join(value.split())
    out = {cleaned}
    if "/" in cleaned:
        parts = [p.strip() for p in cleaned.split("/")]
        out.add("/".join(parts))
        out.add(" / ".join(parts))
        out.add(parts[0])
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) >= 10 and len(digits) == len(re.sub(r"[\s+\-]", "", cleaned)):
        out.add(digits[-10:])
    return {v for v in out if len(v) >= MIN_KNOWN_LENGTH}


def mask_text(text: str) -> str:
    """Mask anything that looks like PII using patterns only."""
    text = FOLIO_RE.sub(lambda m: f"{m.group(1)}{FOLIO_MASK}", text)
    text = EMAIL_RE.sub(EMAIL_MASK, text)
    text = PAN_RE.sub(PAN_MASK, text)
    return PHONE_RE.sub(PHONE_MASK, text)


class PiiMasker:
    """Masks known statement values first, then pattern matches.

    Example:
        >>> PiiMasker(["Ravi Kumar"]).mask("Holder: Ravi Kumar")
        'Holder: [REDACTED]'
    """

    def __init__(self, known_values: Iterable[str | None] = ()) -> None:
        variants: set[str] = set()
        for value in known_values:
            if value:
                variants |= _variants(value)
        # Longest first so "1234567/89" is replaced before "1234567".
        ordered = sorted(variants, key=len, reverse=True)
        self._known = (
            re.compile("|".join(re.escape(v) for v in ordered), re.IGNORECASE) if ordered else None
        )

    def mask(self, text: str) -> str:
        """Return ``text`` with every known value and PII-shaped token replaced."""
        if self._known is not None:
            text = self._known.sub(REDACTED_MASK, text)
        return mask_text(text)


def contains_pii(text: str) -> bool:
    """True if ``text`` still contains something PII-shaped (masking would change it)."""
    return mask_text(text) != text
