"""Volatility features."""

from decimal import Decimal
from statistics import pstdev


def close_to_close_volatility(closes: list[Decimal] | tuple[Decimal, ...]) -> Decimal:
    if len(closes) < 3:
        raise ValueError("at least three closes are required")

    returns = [
        float(closes[index] / closes[index - 1] - Decimal("1"))
        for index in range(1, len(closes))
    ]
    return Decimal(str(pstdev(returns)))
