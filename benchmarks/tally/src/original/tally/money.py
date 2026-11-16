"""Parsing and formatting of money amounts."""

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

CENT = Decimal("0.01")


def parse_amount(text: str) -> Decimal:
    """Parse an amount such as ``1,234.56``, ``-12.5`` or ``(12.50)`` (negative).

    Raises ``ValueError`` for anything that is not a finite number.
    """
    cleaned = text.strip().replace(",", "")
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"invalid amount {text!r}") from None
    if not value.is_finite():
        raise ValueError(f"invalid amount {text!r}")
    return -value if negative else value


def quantize(value: Decimal) -> Decimal:
    """Round to cents, half to even."""
    rounded = value.quantize(CENT, rounding=ROUND_HALF_EVEN)
    return rounded if rounded != 0 else Decimal("0.00")


def format_amount(value: Decimal) -> str:
    """Format with thousands separators and two decimals, e.g. ``-1,234.50``."""
    return f"{quantize(value):,.2f}"
