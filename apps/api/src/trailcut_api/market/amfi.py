"""Parse AMFI's daily ``NAVAll.txt`` and pair Regular schemes with their Direct twins.

File shape (semicolon-separated, with AMC and category header lines)::

    Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
    Open Ended Schemes(Equity Scheme - Flexi Cap Fund)
    Sample Mutual Fund
    900001;INF000S01011;-;Sample Flexi Cap Fund - Regular Plan - Growth;150.1234;20-Nov-2026

Example:
    >>> records = parse_navall(text)  # doctest: +SKIP
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_PLAN_WORDS = re.compile(r"\b(direct|regular|retail|plan|option)\b", re.I)
_OPTION_WORDS = re.compile(
    r"\b(growth|idcw|dividend|payout|reinvest(ment)?|cumulative|gr|div|income distribution cum "
    r"capital withdrawal)\b",
    re.I,
)
_IDCW = re.compile(r"\b(idcw|dividend|payout|reinvest(ment)?|div)\b", re.I)
_NON_WORD = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class NavRecord:
    amfi_code: str
    isins: tuple[str, ...]
    name: str
    nav: Decimal | None
    nav_date: date | None
    amc: str
    category: str

    @property
    def is_direct(self) -> bool:
        return bool(re.search(r"\bdirect\b", self.name, re.I))


def parse_navall(text: str) -> list[NavRecord]:
    """Parse NAVAll.txt into records. Malformed lines are skipped."""
    records: list[NavRecord] = []
    amc = ""
    category = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) == 6 and parts[0].isdigit():
            code, isin_a, isin_b, name, nav_text, date_text = parts
            try:
                nav: Decimal | None = Decimal(nav_text)
            except InvalidOperation:
                nav = None
            try:
                nav_date: date | None = datetime.strptime(date_text, "%d-%b-%Y").date()  # noqa: DTZ007
            except ValueError:
                nav_date = None
            isins = tuple(i for i in (isin_a, isin_b) if re.fullmatch(r"IN[A-Z0-9]{9}[0-9]", i))
            records.append(NavRecord(code, isins, name, nav, nav_date, amc, category))
        elif line.startswith(("Scheme Code", "Scheme Code;")):
            continue
        elif "Schemes(" in line or (line.endswith(")") and "Scheme" in line):
            category = line
        elif ";" not in line:
            amc = line
    return records


def normalize_name(name: str) -> str:
    """Scheme name without plan and option words, for matching Regular to Direct.

    Example:
        >>> normalize_name("Sample Flexi Cap Fund - Regular Plan - Growth")
        'sample flexi cap fund'
    """
    text = _PLAN_WORDS.sub(" ", name)
    text = _OPTION_WORDS.sub(" ", text)
    return " ".join(_NON_WORD.sub(" ", text.lower()).split())


def option_key(name: str) -> str:
    return "idcw" if _IDCW.search(name) else "growth"


def pair_direct(records: Sequence[NavRecord]) -> dict[str, NavRecord]:
    """Map every Regular-plan ISIN to the Direct record of the same scheme and option."""
    direct: dict[tuple[str, str, str], NavRecord] = {}
    for r in records:
        if r.is_direct:
            direct.setdefault((r.amc.lower(), normalize_name(r.name), option_key(r.name)), r)
    out: dict[str, NavRecord] = {}
    for r in records:
        if r.is_direct:
            continue
        twin = direct.get((r.amc.lower(), normalize_name(r.name), option_key(r.name)))
        if twin is not None:
            for isin in r.isins:
                out[isin] = twin
    return out


def by_isin(records: Iterable[NavRecord]) -> dict[str, NavRecord]:
    """Index records by every ISIN they carry."""
    return {isin: r for r in records for isin in r.isins}
