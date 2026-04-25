"""Portfolio allocation helpers."""

from decimal import Decimal


def equal_weight(symbols: tuple[str, ...] | list[str], *, gross_target: Decimal) -> dict[str, Decimal]:
    if not symbols:
        raise ValueError("symbols cannot be empty")
    weight = gross_target / Decimal(len(symbols))
    return {symbol: weight for symbol in symbols}
