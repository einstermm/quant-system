"""Technical indicators used by signal modules."""

from decimal import Decimal
from statistics import fmean


def simple_moving_average(values: list[Decimal] | tuple[Decimal, ...], window: int) -> Decimal:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        raise ValueError("not enough values for requested window")
    return Decimal(str(fmean(float(value) for value in values[-window:])))


def rolling_high(values: list[Decimal] | tuple[Decimal, ...], window: int) -> Decimal:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        raise ValueError("not enough values for requested window")
    return max(values[-window:])


def rolling_low(values: list[Decimal] | tuple[Decimal, ...], window: int) -> Decimal:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        raise ValueError("not enough values for requested window")
    return min(values[-window:])
