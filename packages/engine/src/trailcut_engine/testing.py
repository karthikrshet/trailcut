"""Builders for synthetic schemes and transactions, shared by tests across packages.

Example:
    >>> scheme = make_scheme([buy(date(2024, 1, 1), "10")])
    >>> scheme.close_units
    Decimal('10')
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from trailcut_engine.portfolio import (
    AssetClass,
    Plan,
    Scheme,
    SchemeOption,
    Transaction,
    TxnKind,
    Valuation,
)

D = Decimal


def tx(
    on: date,
    kind: TxnKind,
    units: str | None,
    nav: str | None = "100",
    amount: str | None = None,
) -> Transaction:
    """A transaction; amount defaults to |units| x nav."""
    if amount is None and units is not None and nav is not None:
        amount = str(abs(D(units)) * D(nav))
    return Transaction(
        date=on,
        kind=kind,
        units=None if units is None else D(units),
        nav=None if nav is None else D(nav),
        amount=None if amount is None else D(amount),
    )


def buy(on: date, units: str, nav: str = "100", amount: str | None = None) -> Transaction:
    return tx(on, TxnKind.PURCHASE, units, nav, amount)


def sell(on: date, units: str, nav: str = "100") -> Transaction:
    return tx(on, TxnKind.REDEMPTION, f"-{units}", nav)


def make_scheme(
    transactions: Sequence[Transaction] = (),
    *,
    scheme_id: str = "F1-S1",
    open_units: str = "0",
    nav: str = "150",
    on: date = date(2026, 11, 20),
    asset_class: AssetClass = AssetClass.EQUITY,
    is_elss: bool = False,
    plan: Plan = Plan.REGULAR,
    **overrides: object,
) -> Scheme:
    rows = tuple(sorted(transactions, key=lambda t: t.date))
    close = D(open_units) + sum((t.units for t in rows if t.units is not None), D(0))
    fields: dict[str, Any] = {
        "scheme_id": scheme_id,
        "name": "Sample Fund - Regular Plan - Growth",
        "amc": "Sample Mutual Fund",
        "plan": plan,
        "option": SchemeOption.GROWTH,
        "asset_class": asset_class,
        "is_elss": is_elss,
        "open_units": D(open_units),
        "close_units": max(close, D(0)),
        "valuation": Valuation(date=on, nav=D(nav), value=max(close, D(0)) * D(nav)),
        "transactions": rows,
    }
    fields.update(overrides)
    return Scheme(**fields)
