"""Builders for synthetic casparser-shaped statements (no real data anywhere)."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

INVESTOR = {
    "name": "Ravi Shankar Kumar",
    "email": "ravi.kumar@example.com",
    "address": "Flat 12, Lakeview Apartments\nMG Road, Bengaluru 560001",
    "mobile": "+91 98765 43210",
}

BASE_SCHEME: dict[str, Any] = {
    "scheme": "Sample Flexi Cap Fund - Regular Plan - Growth",
    "advisor": "ARN-000001",
    "rta_code": "S1",
    "rta": "CAMS",
    "type": "EQUITY",
    "isin": "INF000S01011",
    "amfi": "100001",
    "nominees": ["Asha Kumar"],
    "open": "0",
    "close": "30.000",
    "close_calculated": "30.000",
    "valuation": {"date": "20-Nov-2026", "nav": "150.0000", "value": "4500.00", "cost": "3000.00"},
    "transactions": [
        {
            "date": "05-Jan-2024",
            "description": "SIP",
            "amount": "1000",
            "units": "10.000",
            "nav": "100.0000",
            "balance": "10.000",
            "type": "PURCHASE_SIP",
        },
        {
            "date": "05-Feb-2024",
            "description": "SIP",
            "amount": "1000",
            "units": "10.000",
            "nav": "100.0000",
            "balance": "20.000",
            "type": "PURCHASE_SIP",
        },
        {
            "date": "05-Feb-2024",
            "description": "Stamp Duty",
            "amount": "0.05",
            "units": None,
            "nav": None,
            "balance": None,
            "type": "STAMP_DUTY_TAX",
        },
        {
            "date": "05-Mar-2024",
            "description": "SIP",
            "amount": "1000",
            "units": "10.000",
            "nav": "100.0000",
            "balance": "30.000",
            "type": "PURCHASE_SIP",
        },
    ],
}


def build_cas(
    *,
    file_type: str = "CAMS",
    cas_type: str = "DETAILED",
    schemes: list[dict[str, Any]] | None = None,
    folio: str = "1234567/89",
    pan: str = "ABCPE1234F",
    warnings: list[str] | None = None,
    extra_folios: int = 0,
) -> dict[str, Any]:
    scheme_list = deepcopy(schemes) if schemes is not None else [deepcopy(BASE_SCHEME)]
    folios = [
        {
            "folio": folio,
            "amc": "Sample Mutual Fund",
            "name": INVESTOR["name"],
            "PAN": pan,
            "KYC": "OK",
            "PANKYC": "OK",
            "schemes": scheme_list,
        }
    ]
    for i in range(extra_folios):
        folios.append(
            {
                "folio": f"99887{i:03d}",
                "amc": f"Other AMC {i}",
                "PAN": pan,
                "schemes": [deepcopy(BASE_SCHEME)],
            }
        )
    return {
        "statement_period": {"from": "01-Jan-2015", "to": "20-Nov-2026"},
        "folios": folios,
        "investor_info": deepcopy(INVESTOR),
        "cas_type": cas_type,
        "file_type": file_type,
        "parse_warnings": warnings or [],
    }


@pytest.fixture
def make_cas() -> Callable[..., dict[str, Any]]:
    return build_cas
