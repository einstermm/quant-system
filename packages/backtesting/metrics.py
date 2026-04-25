"""Backtest metrics."""

from decimal import Decimal


def total_return(*, start_equity: Decimal, end_equity: Decimal) -> Decimal:
    if start_equity <= Decimal("0"):
        raise ValueError("start_equity must be positive")
    return end_equity / start_equity - Decimal("1")


def max_drawdown(equity_curve: tuple[Decimal, ...] | list[Decimal]) -> Decimal:
    if not equity_curve:
        raise ValueError("equity_curve cannot be empty")

    peak = equity_curve[0]
    worst = Decimal("0")
    for equity in equity_curve:
        peak = max(peak, equity)
        drawdown = equity / peak - Decimal("1")
        worst = min(worst, drawdown)
    return abs(worst)
