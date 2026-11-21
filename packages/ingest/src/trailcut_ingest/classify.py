"""Classify schemes and transactions from statement text into engine enums.

Scheme names come from the PDF and are untrusted. These functions only look for
keywords; they never act on the text.

Example:
    >>> detect_plan("Sample Flexi Cap Fund - Direct Plan - Growth")
    <Plan.DIRECT: 'direct'>
"""

from __future__ import annotations

import re

from trailcut_engine.portfolio import AssetClass, Plan, SchemeOption, TxnKind

_DIRECT = re.compile(r"\bdirect\b", re.IGNORECASE)
_REGULAR = re.compile(r"\b(regular|retail)\b", re.IGNORECASE)
_IDCW = re.compile(
    r"\b(idcw|dividend|div|payout|reinvest(ment)?|bonus|income distribution)\b", re.IGNORECASE
)
_GROWTH = re.compile(r"\b(growth|gr|cumulative)\b", re.IGNORECASE)
_ELSS = re.compile(r"\b(elss|tax\s*saver|tax\s*saving|tax\s*plan|taxsaver)\b", re.IGNORECASE)

# Order matters: the first matching rule wins.
_ASSET_RULES: tuple[tuple[re.Pattern[str], AssetClass], ...] = (
    # Equity-oriented for tax (at least 65% listed equity by mandate).
    (re.compile(r"\b(arbitrage|equity\s*savings|aggressive\s*hybrid)\b", re.I), AssetClass.EQUITY),
    (re.compile(r"\bbalanced\s*advantage|dynamic\s*asset\s*allocation\b", re.I), AssetClass.EQUITY),
    # Funds of funds and overseas funds: tax treatment depends on the underlying.
    (
        re.compile(
            r"\b(fund\s*of\s*funds?|fof|overseas|international|global|nasdaq|us\s*equity)\b", re.I
        ),
        AssetClass.UNKNOWN,
    ),
    (re.compile(r"\b(gold|silver)\b", re.I), AssetClass.UNKNOWN),
    (
        re.compile(r"\b(conservative\s*hybrid|multi[\s-]*asset|hybrid|balanced)\b", re.I),
        AssetClass.HYBRID,
    ),
    (
        re.compile(
            r"\b(liquid|overnight|gilt|bond|debt|money\s*market|credit\s*risk|banking\s*(and|&)\s*psu|"
            r"duration|floater|floating\s*rate|income|treasury|savings|psu|target\s*maturity|"
            r"sdl|g[\s-]*sec|fixed\s*maturity|fmp|interval)\b",
            re.I,
        ),
        AssetClass.DEBT,
    ),
    (
        re.compile(
            r"\b(equity|cap|flexi|focused|value|contra|dividend\s*yield|index|nifty|sensex|elss|"
            r"tax\s*saver|bluechip|opportunit|sector|thematic|infrastructure|pharma|banking|"
            r"technology|consumption|manufacturing|psu\s*equity|momentum|quality)\w*\b",
            re.I,
        ),
        AssetClass.EQUITY,
    ),
)


def detect_plan(name: str, advisor: str | None = None) -> Plan:
    """Regular or Direct plan, from the scheme name, else the advisor code.

    Direct plans show advisor ``INA...``/``DIRECT``; Regular plans an ``ARN-`` code.

    Example:
        >>> detect_plan("XYZ Fund - Growth", advisor="ARN-12345")
        <Plan.REGULAR: 'regular'>
    """
    if _DIRECT.search(name):
        return Plan.DIRECT
    if _REGULAR.search(name):
        return Plan.REGULAR
    code = (advisor or "").strip().upper()
    if code.startswith(("INA", "DIRECT", "INZ")):
        return Plan.DIRECT
    if code.startswith("ARN"):
        return Plan.REGULAR
    return Plan.UNKNOWN


def detect_option(name: str) -> SchemeOption:
    """Growth or IDCW (dividend) option.

    Example:
        >>> detect_option("XYZ Fund - Regular Plan - IDCW Payout")
        <SchemeOption.IDCW: 'idcw'>
    """
    if _IDCW.search(name):
        return SchemeOption.IDCW
    if _GROWTH.search(name):
        return SchemeOption.GROWTH
    return SchemeOption.UNKNOWN


def is_elss(name: str) -> bool:
    """True for ELSS / tax-saver schemes (3-year lock-in per purchase).

    Example:
        >>> is_elss("XYZ ELSS Tax Saver Fund - Regular - Growth")
        True
    """
    return bool(_ELSS.search(name))


def detect_asset_class(name: str, statement_type: str | None = None) -> AssetClass:
    """Broad asset class for tax purposes.

    Name rules win (they are more specific). Otherwise the parser's
    ``EQUITY``/``DEBT`` type is used. Anything unclear is ``UNKNOWN`` so the UI can
    ask the user instead of guessing.

    Example:
        >>> detect_asset_class("XYZ Corporate Bond Fund - Regular - Growth")
        <AssetClass.DEBT: 'debt'>
    """
    if is_elss(name):
        return AssetClass.EQUITY
    for pattern, asset in _ASSET_RULES:
        if pattern.search(name):
            return asset
    kind = (statement_type or "").strip().upper()
    if kind == "EQUITY":
        return AssetClass.EQUITY
    if kind == "DEBT":
        return AssetClass.DEBT
    return AssetClass.UNKNOWN


_TXN_MAP: dict[str, TxnKind] = {
    "PURCHASE": TxnKind.PURCHASE,
    "PURCHASE_SIP": TxnKind.SIP,
    "REDEMPTION": TxnKind.REDEMPTION,
    "DIVIDEND_PAYOUT": TxnKind.DIVIDEND_PAYOUT,
    "DIVIDEND_REINVEST": TxnKind.DIVIDEND_REINVEST,
    "SWITCH_IN": TxnKind.SWITCH_IN,
    "SWITCH_IN_MERGER": TxnKind.MERGER_IN,
    "SWITCH_OUT": TxnKind.SWITCH_OUT,
    "SWITCH_OUT_MERGER": TxnKind.MERGER_OUT,
    "STT_TAX": TxnKind.TAX,
    "STAMP_DUTY_TAX": TxnKind.TAX,
    "TDS_TAX": TxnKind.TAX,
    "SEGREGATION": TxnKind.SEGREGATION,
    "GIFT_IN": TxnKind.GIFT_IN,
    "GIFT_OUT": TxnKind.GIFT_OUT,
    "REVERSAL": TxnKind.REVERSAL,
    "MISC": TxnKind.OTHER,
    "UNKNOWN": TxnKind.OTHER,
}


def map_transaction_type(raw_type: str) -> TxnKind:
    """Map a casparser transaction type to :class:`TxnKind` (unknown → ``OTHER``).

    Example:
        >>> map_transaction_type("PURCHASE_SIP")
        <TxnKind.SIP: 'sip'>
    """
    value = raw_type.rsplit(".", maxsplit=1)[-1].strip().upper()
    return _TXN_MAP.get(value, TxnKind.OTHER)
