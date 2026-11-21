"""Shared field types for engine models.

Money, units and NAVs are :class:`~decimal.Decimal`. Floats are rejected at the
model boundary so no value is ever rounded through binary floating point.

Example:
    >>> from pydantic import TypeAdapter
    >>> TypeAdapter(DecimalField).validate_python("1250.50")
    Decimal('1250.50')
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator


def reject_float(value: object) -> object:
    """Refuse floats and booleans where an exact number is required."""
    if isinstance(value, bool):
        msg = f"booleans are not valid numbers here: {value!r}"
        raise ValueError(msg)
    if isinstance(value, float):
        msg = f"floats are not allowed; pass a string or Decimal: {value!r}"
        raise ValueError(msg)
    return value


NoFloat = BeforeValidator(reject_float)

DecimalField = Annotated[Decimal, NoFloat]
"""An exact decimal number (money, units, NAV). Floats are rejected."""
