"""Trading cost models."""

from decimal import Decimal


def percentage_fee(*, notional: Decimal, fee_rate: Decimal) -> Decimal:
    if fee_rate < Decimal("0"):
        raise ValueError("fee_rate cannot be negative")
    return abs(notional) * fee_rate
