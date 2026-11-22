"""Generate the synthetic sample CAS used by "Try a sample portfolio".

Deterministic: running it twice produces byte-identical JSON. Every fund, NAV,
name and identifier is fictional. Run with:

    uv run python scripts/make_sample.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "packages" / "ingest" / "src" / "trailcut_ingest" / "samples" / "sample_cas.json"
MARKET_OUT = ROOT / "data" / "samples" / "sample_market.json"
STATEMENT_DATE = date(2026, 11, 20)
STAMP_DUTY_FROM = date(2020, 7, 1)
STAMP_DUTY_RATE = Decimal("0.00005")  # 0.005% on purchases since 1 Jul 2020
# Small deterministic wiggle so NAV paths are not perfectly smooth.
WOBBLE = [Decimal(x) for x in ("1.000", "0.985", "1.012", "0.993", "1.021", "0.978", "1.004")]

Q2, Q3, Q4 = Decimal("0.01"), Decimal("0.001"), Decimal("0.0001")


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


@dataclass
class Fund:
    name: str
    amc: str
    folio: str
    isin: str
    amfi: str
    kind: str  # casparser 'type'
    advisor: str
    nav_start: Decimal
    nav_start_date: date
    monthly_growth: Decimal
    buys: list[tuple[date, Decimal]] = field(default_factory=list)
    sells: list[tuple[date, Decimal]] = field(default_factory=list)  # (date, amount)

    def nav(self, on: date) -> Decimal:
        n = months_between(self.nav_start_date, on)
        growth = (1 + self.monthly_growth) ** n
        return (self.nav_start * growth * WOBBLE[n % len(WOBBLE)]).quantize(Q4, ROUND_HALF_UP)


def monthly(start: date, end: date, day: int, amount: Decimal) -> list[tuple[date, Decimal]]:
    out = []
    y, m = start.year, start.month
    while date(y, m, day) <= end:
        out.append((date(y, m, day), amount))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def fmt(d: date) -> str:
    return d.strftime("%d-%b-%Y")


def build_scheme(f: Fund) -> dict[str, object]:
    events: list[tuple[date, str, Decimal]] = [(d, "buy", a) for d, a in f.buys]
    events += [(d, "sell", a) for d, a in f.sells]
    events.sort(key=lambda e: (e[0], e[1]))
    txns: list[dict[str, object]] = []
    lots: list[list[Decimal]] = []  # [units, cost]
    balance = Decimal(0)
    for d, kind, amount in events:
        nav = f.nav(d)
        if kind == "buy":
            duty = (
                (amount * STAMP_DUTY_RATE).quantize(Q2, ROUND_HALF_UP)
                if d >= STAMP_DUTY_FROM
                else Decimal(0)
            )
            units = ((amount - duty) / nav).quantize(Q3, ROUND_HALF_UP)
            balance += units
            lots.append([units, amount])
            is_sip = len(f.buys) > 3
            txns.append(
                {
                    "date": fmt(d),
                    "description": "Purchase - Systematic Investment" if is_sip else "Purchase",
                    "amount": str(amount - duty),
                    "units": str(units),
                    "nav": str(nav),
                    "balance": str(balance),
                    "type": "PURCHASE_SIP" if is_sip else "PURCHASE",
                }
            )
            if duty:
                txns.append(
                    {
                        "date": fmt(d),
                        "description": "*** Stamp Duty ***",
                        "amount": str(duty),
                        "units": None,
                        "nav": None,
                        "balance": None,
                        "type": "STAMP_DUTY_TAX",
                    }
                )
        else:
            units = (amount / nav).quantize(Q3, ROUND_HALF_UP)
            balance -= units
            remaining = units
            while remaining > 0:
                lot_units, lot_cost = lots[0]
                take = min(lot_units, remaining)
                lots[0] = [lot_units - take, lot_cost - (lot_cost * take / lot_units)]
                if lots[0][0] == 0:
                    lots.pop(0)
                remaining -= take
            txns.append(
                {
                    "date": fmt(d),
                    "description": "Redemption",
                    "amount": str(-amount),
                    "units": str(-units),
                    "nav": str(nav),
                    "balance": str(balance),
                    "type": "REDEMPTION",
                }
            )
    nav_now = f.nav(STATEMENT_DATE)
    cost = sum((c for _, c in lots), Decimal(0)).quantize(Q2, ROUND_HALF_UP)
    return {
        "scheme": f.name,
        "advisor": f.advisor,
        "rta_code": f.amfi,
        "rta": "CAMS",
        "type": f.kind,
        "isin": f.isin,
        "amfi": f.amfi,
        "nominees": ["Demo Nominee"],
        "open": "0.000",
        "close": str(balance),
        "close_calculated": str(balance),
        "valuation": {
            "date": fmt(STATEMENT_DATE),
            "nav": str(nav_now),
            "value": str((balance * nav_now).quantize(Q2, ROUND_HALF_UP)),
            "cost": str(cost),
        },
        "transactions": txns,
    }


FUNDS = [
    Fund(
        "Sample Flexi Cap Fund - Regular Plan - Growth",
        "Sample Mutual Fund",
        "DEMO10001/01",
        "INF000S01011",
        "900001",
        "EQUITY",
        "ARN-000001",
        Decimal("40.00"),
        date(2016, 1, 1),
        Decimal("0.0100"),
        monthly(date(2016, 1, 5), date(2026, 11, 5), 5, Decimal(5000)),
        [(date(2022, 6, 15), Decimal(150000))],
    ),
    Fund(
        "Sample ELSS Tax Saver Fund - Regular Plan - Growth",
        "Sample Mutual Fund",
        "DEMO10002/01",
        "INF000S01029",
        "900002",
        "EQUITY",
        "ARN-000001",
        Decimal("60.00"),
        date(2023, 6, 1),
        Decimal("0.0120"),
        monthly(date(2023, 6, 10), date(2026, 11, 10), 10, Decimal(2000)),
    ),
    Fund(
        "Sample Corporate Bond Fund - Regular Plan - Growth",
        "Sample Debt Mutual Fund",
        "DEMO20001/02",
        "INF000D01017",
        "900003",
        "DEBT",
        "ARN-000001",
        Decimal("25.00"),
        date(2021, 8, 1),
        Decimal("0.0055"),
        [(date(2021, 8, 10), Decimal(200000)), (date(2024, 2, 15), Decimal(100000))],
    ),
    Fund(
        "Sample Balanced Advantage Fund - Regular Plan - Growth",
        "Sample Mutual Fund",
        "DEMO10003/01",
        "INF000S01037",
        "900004",
        "EQUITY",
        "ARN-000001",
        Decimal("30.00"),
        date(2026, 3, 1),
        Decimal("0.0080"),
        [(date(2026, 3, 10), Decimal(150000))],
    ),
    Fund(
        "Sample Nifty 50 Index Fund - Direct Plan - Growth",
        "Sample Index Mutual Fund",
        "DEMO30001/01",
        "INF000I01015",
        "900005",
        "EQUITY",
        "INA000000001",
        Decimal("15.00"),
        date(2022, 1, 1),
        Decimal("0.0090"),
        monthly(date(2022, 1, 7), date(2026, 11, 7), 7, Decimal(3000)),
    ),
    Fund(
        "Sample Small Cap Fund - Regular Plan - Growth",
        "Sample Mutual Fund",
        "DEMO10004/01",
        "INF000S01045",
        "900006",
        "EQUITY",
        "ARN-000001",
        Decimal("80.00"),
        date(2025, 12, 1),
        Decimal("0.0150"),
        [(date(2025, 12, 15), Decimal(100000))],
    ),
]


def build() -> dict[str, object]:
    folios: dict[str, dict[str, object]] = {}
    for f in FUNDS:
        folio = folios.setdefault(
            f.folio,
            {
                "folio": f.folio,
                "amc": f.amc,
                "name": "Demo Investor",
                "PAN": "AAAPZ0000Z",
                "KYC": "OK",
                "PANKYC": "OK",
                "schemes": [],
            },
        )
        folio["schemes"].append(build_scheme(f))  # type: ignore[attr-defined]
    return {
        "statement_period": {"from": "01-Jan-2016", "to": fmt(STATEMENT_DATE)},
        "folios": list(folios.values()),
        "investor_info": {
            "name": "Demo Investor",
            "email": "demo@example.com",
            "address": "1 Sample Street, Demo City 000000",
            "mobile": "+91 90000 00000",
        },
        "cas_type": "DETAILED",
        "file_type": "CAMS",
        "parse_warnings": [],
    }


# Fictional expense ratios (yearly) and exit loads for the sample funds, keyed by ISIN.
MARKET_TERMS: dict[str, tuple[str, str, int | None, str | None]] = {
    "INF000S01011": ("0.0165", "0.0070", 365, "0.01"),
    "INF000S01029": ("0.0180", "0.0075", None, None),
    "INF000D01017": ("0.0065", "0.0035", None, None),
    "INF000S01037": ("0.0170", "0.0080", 365, "0.01"),
    "INF000I01015": ("0.0020", "0.0020", None, None),
    "INF000S01045": ("0.0175", "0.0065", 365, "0.01"),
}


def build_market() -> dict[str, object]:
    schemes: dict[str, object] = {}
    for f in FUNDS:
        ter_regular, ter_direct, days, rate = MARKET_TERMS[f.isin]
        tiers = [] if days is None else [{"within_days": days, "rate": rate}]
        entry: dict[str, object] = {
            "ter_regular": ter_regular,
            "ter_direct": ter_direct,
            "direct_name": f.name.replace("Regular Plan", "Direct Plan"),
            "exit_load": {"tiers": tiers, "source": "synthetic sample"},
            "source": "synthetic sample",
            "as_of": STATEMENT_DATE.isoformat(),
        }
        if f.nav_start_date <= date(2018, 1, 31):
            entry["fmv_2018_per_unit"] = str(f.nav(date(2018, 1, 31)))
        schemes[f.isin] = entry
    return {"as_of": STATEMENT_DATE.isoformat(), "source": "synthetic sample", "schemes": schemes}


def main() -> None:
    for path, data in ((OUT, build()), (MARKET_OUT, build_market())):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
