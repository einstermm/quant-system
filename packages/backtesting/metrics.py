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


def turnover(*, traded_notional: Decimal, average_equity: Decimal) -> Decimal:
    if average_equity <= Decimal("0"):
        raise ValueError("average_equity must be positive")
    return traded_notional / average_equity


def tail_loss(equity_curve: tuple[Decimal, ...] | list[Decimal]) -> Decimal:
    if not equity_curve:
        raise ValueError("equity_curve cannot be empty")
    if len(equity_curve) == 1:
        return Decimal("0")

    worst_period_return = Decimal("0")
    previous = equity_curve[0]
    for equity in equity_curve[1:]:
        if previous <= Decimal("0"):
            raise ValueError("equity values must be positive")
        period_return = equity / previous - Decimal("1")
        worst_period_return = min(worst_period_return, period_return)
        previous = equity
    return abs(worst_period_return)


def average(values: tuple[Decimal, ...] | list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("values cannot be empty")
    return sum(values, Decimal("0")) / Decimal(len(values))
