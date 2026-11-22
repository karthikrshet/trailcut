"""Numeric-claim validator: no number reaches a user unless a tool produced it.

Every rupee amount, percentage, date and count in an answer is extracted and
normalized, then checked against the set of values present in that turn's tool
outputs (and the user's own message, so echoing "what if 8%?" is fine). One
unknown number rejects the whole answer.

Example:
    >>> v = validate("Your tax is ₹22,750.", [{"tax": "22750.00"}])
    >>> v.ok
    True
    >>> validate("Your tax is ₹9,999.", [{"tax": "22750.00"}]).invented
    ('₹9,999',)
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}
FREE_INTEGERS = frozenset(range(11))
THOUSAND = Decimal(1000)
"""Small counts ("two funds", "3 steps") read as prose, not figures."""

_MONEY = re.compile(
    r"(?:₹|\bRs\.?\s?|\bINR\s?)\s?(?P<num>\d[\d,]*(?:\.\d+)?)\s?(?P<unit>L\b|lakhs?\b|Cr\b|crores?\b|K\b)?",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"(?P<num>-?\d+(?:\.\d+)?)\s?(?:%|percent\b)", re.IGNORECASE)
_DATE = re.compile(r"\b(?P<d>\d{1,2})\s(?P<m>[A-Za-z]{3})[a-z]*\.?\s(?P<y>\d{4})\b")
_MONTH_YEAR = re.compile(
    r"\b(?P<m>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s(?P<y>\d{4})\b"
)
_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_FY = re.compile(r"\b(?:FY\s?)?(?P<a>\d{4})-(?P<b>\d{2})\b")
_NUMBER = re.compile(r"(?<![\w.₹])(?P<num>\d[\d,]*(?:\.\d+)?)(?![\w%])")

Key = tuple[str, str]


@dataclass(frozen=True)
class Claim:
    raw: str
    keys: tuple[Key, ...]
    """Any one matching key makes the claim supported."""


def _dec(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _compact(rupees: Decimal) -> str | None:
    """Lakh/crore short form to one decimal, as the UI shows it (3.8L, 1.2Cr)."""
    v = abs(rupees)
    if v >= Decimal(10_000_000):
        return (
            f"{(v / Decimal(10_000_000)).quantize(Decimal('0.1'), ROUND_HALF_UP).normalize():f}Cr"
        )
    if v >= Decimal(100_000):
        lakhs = (v / Decimal(100_000)).quantize(Decimal("0.1"), ROUND_HALF_UP)
        return "1Cr" if lakhs >= 100 else f"{lakhs.normalize():f}L"
    return None


def _money_keys(rupees: Decimal) -> set[Key]:
    keys: set[Key] = {("money", str(abs(rupees).quantize(Decimal(1), ROUND_HALF_UP)))}
    compact = _compact(rupees)
    if compact:
        keys.add(("money_compact", compact))
    if abs(rupees) >= THOUSAND:
        thousands = (abs(rupees) / THOUSAND).quantize(Decimal("0.1"), ROUND_HALF_UP).normalize()
        keys.add(("money_k", f"{thousands:f}"))
    return keys


def _percent_keys(fraction: Decimal) -> set[Key]:
    pct = fraction * 100
    return {
        ("percent", f"{pct.quantize(Decimal(1).scaleb(-p), ROUND_HALF_UP).normalize():f}")
        for p in (0, 1, 2)
    }


def _number_keys(value: Decimal) -> set[Key]:
    keys = {("number", f"{value.normalize():f}")}
    if value == value.to_integral_value():
        keys.add(("number", str(int(value))))
    keys.add(("number", f"{value.quantize(Decimal(1), ROUND_HALF_UP)}"))
    return keys


def _date_keys(d: date) -> set[Key]:
    return {
        ("date", d.isoformat()),
        ("month", f"{d.year}-{d.month:02d}"),
        ("number", str(d.year)),
        ("number", str(d.day)),
    }


# ---------- what the tools said ----------


def _walk(value: object) -> Iterator[object]:
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk(v)
    else:
        yield value


def allowed_keys(outputs: Iterable[Any], extra_text: str = "") -> set[Key]:
    """Every normalized figure present in tool outputs (and ``extra_text``)."""
    keys: set[Key] = set()
    for leaf in _walk(list(outputs)):
        if isinstance(leaf, bool) or leaf is None:
            continue
        if isinstance(leaf, int | Decimal):
            d = Decimal(leaf)
            keys |= _number_keys(d) | _money_keys(d) | _percent_keys(d)
            continue
        if not isinstance(leaf, str):
            continue
        iso = _ISO.fullmatch(leaf.strip())
        if iso:
            keys |= _date_keys(date(int(iso["y"]), int(iso["m"]), int(iso["d"])))
            continue
        parsed = _dec(leaf.strip()) if re.fullmatch(r"-?\d[\d,]*(\.\d+)?", leaf.strip()) else None
        if parsed is not None:
            keys |= _number_keys(parsed) | _money_keys(parsed) | _percent_keys(parsed)
            continue
        # Free text from tools (engine-written explanations) carries formatted figures.
        for claim in extract_claims(leaf):
            keys |= set(claim.keys)
    for claim in extract_claims(extra_text):
        keys |= set(claim.keys)
    return keys


# ---------- what the answer says ----------


def extract_claims(text: str) -> list[Claim]:  # noqa: PLR0912, PLR0915 - one scanner
    """Every figure in ``text`` with the keys that would support it."""
    claims: list[Claim] = []
    taken: list[tuple[int, int]] = []

    def free(span: tuple[int, int]) -> bool:
        return all(span[1] <= a or span[0] >= b for a, b in taken)

    for m in _MONEY.finditer(text):
        amount = _dec(m["num"])
        if amount is None:
            continue
        num = amount
        unit = (m["unit"] or "").lower()
        if unit.startswith(("l", "lakh")):
            keys: set[Key] = {
                ("money_compact", f"{num.quantize(Decimal('0.1'), ROUND_HALF_UP).normalize():f}L")
            }
        elif unit.startswith("c"):
            keys = {
                ("money_compact", f"{num.quantize(Decimal('0.1'), ROUND_HALF_UP).normalize():f}Cr")
            }
        elif unit == "k":
            keys = {("money_k", f"{num.quantize(Decimal('0.1'), ROUND_HALF_UP).normalize():f}")}
        else:
            # A full amount must match a tool amount to the rupee; short forms match short forms.
            keys = {("money", str(abs(num).quantize(Decimal(1), ROUND_HALF_UP)))}
        claims.append(Claim(m.group(0).strip(), tuple(sorted(keys))))
        taken.append(m.span())
    for m in _PERCENT.finditer(text):
        if not free(m.span()):
            continue
        pct = _dec(m["num"])
        if pct is not None:
            claims.append(Claim(m.group(0).strip(), (("percent", f"{pct.normalize():f}"),)))
            taken.append(m.span())
    for m in _DATE.finditer(text):
        month = MONTHS.get(m["m"].lower())
        if month is None or not free(m.span()):
            continue
        try:
            d = date(int(m["y"]), month, int(m["d"]))
        except ValueError:
            claims.append(Claim(m.group(0), (("invalid", m.group(0)),)))
            continue
        claims.append(Claim(m.group(0), (("date", d.isoformat()),)))
        taken.append(m.span())
    for m in _ISO.finditer(text):
        if free(m.span()):
            claims.append(Claim(m.group(0), (("date", m.group(0)),)))
            taken.append(m.span())
    for m in _MONTH_YEAR.finditer(text):
        if free(m.span()):
            month = MONTHS[m["m"][:3].lower()]
            claims.append(Claim(m.group(0), (("month", f"{m['y']}-{month:02d}"),)))
            taken.append(m.span())
    for m in _FY.finditer(text):
        if free(m.span()) and int(m["b"]) == (int(m["a"]) + 1) % 100:
            claims.append(Claim(m.group(0), (("fy", f"{m['a']}-{m['b']}"),)))
            taken.append(m.span())
    for m in _NUMBER.finditer(text):
        if not free(m.span()):
            continue
        plain = _dec(m["num"])
        if plain is None:
            continue
        if (
            plain == plain.to_integral_value()
            and int(plain) in FREE_INTEGERS
            and "," not in m["num"]
        ):
            continue
        claims.append(Claim(m.group(0), tuple(sorted(_number_keys(plain)))))
    return claims


@dataclass(frozen=True)
class Validation:
    ok: bool
    invented: tuple[str, ...]
    checked: int


def validate(answer: str, tool_outputs: Iterable[Any], user_message: str = "") -> Validation:
    """Accept ``answer`` only if every figure in it is backed by a tool output."""
    allowed = allowed_keys(tool_outputs, user_message)
    claims = extract_claims(answer)
    invented = tuple(c.raw for c in claims if not any(k in allowed for k in c.keys))
    return Validation(ok=not invented, invented=invented, checked=len(claims))
