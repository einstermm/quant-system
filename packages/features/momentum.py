"""Momentum features."""

from decimal import Decimal


def rate_of_change(values: list[Decimal] | tuple[Decimal, ...], window: int) -> Decimal:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) <= window:
        raise ValueError("not enough values for requested window")
    start = values[-window - 1]
    end = values[-1]
    if start == Decimal("0"):
        raise ValueError("start value cannot be zero")
    return end / start - Decimal("1")
