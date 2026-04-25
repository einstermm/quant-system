"""Slippage models."""

from decimal import Decimal


def bps_slippage_price(*, reference_price: Decimal, side_sign: int, slippage_bps: Decimal) -> Decimal:
    if side_sign not in {-1, 1}:
        raise ValueError("side_sign must be -1 or 1")
    if slippage_bps < Decimal("0"):
        raise ValueError("slippage_bps cannot be negative")
    return reference_price * (Decimal("1") + Decimal(side_sign) * slippage_bps / Decimal("10000"))
