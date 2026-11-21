"""FIFO lot accounting: purchases become lots, redemptions consume the oldest first.

Indian mutual fund redemptions are matched first-in, first-out. Each remaining lot
keeps its own purchase date (for holding period) and cost (for gains).

Example:
    >>> book = build_lots(scheme)  # doctest: +SKIP
    >>> [lot.lot_id for lot in book.open_lots]
    ['F1-S1-L002', 'F1-S1-L003']
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from trailcut_engine.portfolio import Scheme, Transaction, TxnKind
from trailcut_engine.types import DecimalField

ZERO = Decimal(0)


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Lot(_Model):
    """Units bought together on one date, at one cost."""

    lot_id: Annotated[str, Field(pattern=r"^F[0-9]+-S[0-9]+-L[0-9]{3,}$")]
    scheme_id: str
    buy_date: date
    units: Annotated[DecimalField, Field(gt=0)]
    cost: Annotated[DecimalField, Field(ge=0)]
    """Total cost of acquisition, including stamp duty."""
    source: TxnKind
    cost_known: bool = True

    @property
    def cost_per_unit(self) -> Decimal:
        """Average cost of one unit in this lot."""
        return self.cost / self.units

    def take(self, units: Decimal) -> tuple[Lot, Lot | None]:
        """Split off ``units`` (taken, remainder), cost shared pro rata.

        Example:
            >>> taken, rest = lot.take(Decimal("4"))  # doctest: +SKIP
        """
        if units <= 0 or units > self.units:
            msg = f"cannot take {units} from {self.units} units"
            raise ValueError(msg)
        if units == self.units:
            return self, None
        cost_taken = self.cost * units / self.units
        taken = self.model_copy(update={"units": units, "cost": cost_taken})
        rest = self.model_copy(update={"units": self.units - units, "cost": self.cost - cost_taken})
        return taken, rest


class Disposal(_Model):
    """Part of a lot that left the scheme (redemption, switch-out, ...)."""

    lot_id: str
    buy_date: date
    sell_date: date
    units: Annotated[DecimalField, Field(gt=0)]
    cost: DecimalField
    proceeds: DecimalField | None
    kind: TxnKind


class LotBook(_Model):
    """All remaining lots of one scheme, oldest first, plus past disposals."""

    scheme_id: str
    open_lots: tuple[Lot, ...]
    disposals: tuple[Disposal, ...]
    warnings: tuple[str, ...] = ()

    @property
    def units(self) -> Decimal:
        """Units still held."""
        return sum((lot.units for lot in self.open_lots), ZERO)

    @property
    def cost(self) -> Decimal:
        """Cost of units still held."""
        return sum((lot.cost for lot in self.open_lots), ZERO)


def _lot_cost(t: Transaction, units: Decimal) -> tuple[Decimal, bool]:
    if t.amount is not None and t.amount > 0:
        return t.amount, True
    if t.nav is not None and t.nav > 0:
        return units * t.nav, True
    if t.kind in {TxnKind.SEGREGATION, TxnKind.GIFT_IN}:
        return ZERO, False
    return ZERO, False


def build_lots(scheme: Scheme) -> LotBook:
    """Replay a scheme's transactions into FIFO lots.

    - Rows that add units create a lot. Same-day stamp duty is added to that lot's cost.
    - Redemptions, switch-outs, merger-outs and gift-outs consume the OLDEST lots.
    - Negative reversals undo the NEWEST lots (a bounced purchase).
    - An opening balance without history becomes a lot with unknown cost.

    Never raises for messy statements; problems are returned as ``warnings``.
    """
    lots: list[Lot] = []
    disposals: list[Disposal] = []
    warnings: list[str] = []
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"{scheme.scheme_id}-L{counter:03d}"

    if scheme.open_units > 0:
        first = scheme.transactions[0].date if scheme.transactions else scheme.valuation.date
        lots.append(
            Lot(
                lot_id=next_id(),
                scheme_id=scheme.scheme_id,
                buy_date=first,
                units=scheme.open_units,
                cost=ZERO,
                source=TxnKind.OTHER,
                cost_known=False,
            )
        )
        warnings.append(
            f"{scheme.scheme_id}: {scheme.open_units} units held before the statement period "
            "have unknown purchase dates and cost."
        )

    for t in scheme.transactions:
        if t.units is None or t.units == 0:
            # Stamp duty is printed right after its purchase; it is part of that lot's cost.
            if (
                t.kind is TxnKind.TAX
                and t.amount
                and lots
                and lots[-1].buy_date == t.date
                and lots[-1].cost_known
            ):
                lots[-1] = lots[-1].model_copy(update={"cost": lots[-1].cost + abs(t.amount)})
            continue
        if t.units > 0:
            cost, known = _lot_cost(t, t.units)
            lots.append(
                Lot(
                    lot_id=next_id(),
                    scheme_id=scheme.scheme_id,
                    buy_date=t.date,
                    units=t.units,
                    cost=cost,
                    source=t.kind,
                    cost_known=known,
                )
            )
            if t.kind is TxnKind.MERGER_IN:
                warnings.append(
                    f"{scheme.scheme_id}: units from a scheme merger on {t.date.isoformat()} are "
                    "dated at the merger; the original purchase dates may be earlier."
                )
            continue

        remaining = -t.units
        newest_first = t.kind is TxnKind.REVERSAL
        while remaining > 0 and lots:
            index = len(lots) - 1 if newest_first else 0
            lot = lots[index]
            take = min(lot.units, remaining)
            taken, rest = lot.take(take)
            if rest is None:
                lots.pop(index)
            else:
                lots[index] = rest
            remaining -= take
            if not newest_first:
                proceeds = take * t.nav if t.nav is not None else None
                disposals.append(
                    Disposal(
                        lot_id=lot.lot_id,
                        buy_date=lot.buy_date,
                        sell_date=t.date,
                        units=take,
                        cost=taken.cost,
                        proceeds=proceeds,
                        kind=t.kind,
                    )
                )
        if remaining > 0:
            warnings.append(
                f"{scheme.scheme_id}: {t.kind.value} on {t.date.isoformat()} removes {remaining} "
                "more units than the statement shows were bought."
            )

    return LotBook(
        scheme_id=scheme.scheme_id,
        open_lots=tuple(lots),
        disposals=tuple(disposals),
        warnings=tuple(warnings),
    )
