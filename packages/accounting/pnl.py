"""PnL helpers."""

from decimal import Decimal


def linear_realized_pnl(
    *,
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
    side_sign: int,
) -> Decimal:
    if side_sign not in {-1, 1}:
        raise ValueError("side_sign must be -1 or 1")
    return (exit_price - entry_price) * quantity * Decimal(side_sign)
