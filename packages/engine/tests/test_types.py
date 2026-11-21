from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from trailcut_engine.types import DecimalField

ADAPTER: TypeAdapter[Decimal] = TypeAdapter(DecimalField)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1250.50", Decimal("1250.50")), (Decimal("0.001"), Decimal("0.001")), (7, Decimal(7))],
)
def test_accepts_exact_inputs(raw: object, expected: Decimal) -> None:
    assert ADAPTER.validate_python(raw) == expected


@pytest.mark.parametrize(
    ("raw", "match"), [(0.1, "floats"), (True, "booleans"), (False, "booleans")]
)
def test_rejects_inexact_inputs(raw: object, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        ADAPTER.validate_python(raw)


@pytest.mark.property
@given(value=st.decimals(allow_nan=False, allow_infinity=False, places=4))
def test_decimal_strings_round_trip_exactly(value: Decimal) -> None:
    assert ADAPTER.validate_python(str(value)) == value
