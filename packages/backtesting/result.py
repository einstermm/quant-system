"""Backtest result models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


def decimal_to_str(value: Decimal) -> str:
    return format(value, "f")


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    timestamp: datetime
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    notional: Decimal
    fee: Decimal
    target_weight: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": decimal_to_str(self.quantity),
            "price": decimal_to_str(self.price),
            "notional": decimal_to_str(self.notional),
            "fee": decimal_to_str(self.fee),
            "target_weight": decimal_to_str(self.target_weight),
        }


@dataclass(frozen=True, slots=True)
class EquityPoint:
    timestamp: datetime
    equity: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": decimal_to_str(self.equity),
        }


@dataclass(frozen=True, slots=True)
class BacktestResult:
    strategy_id: str
    parameters: dict[str, Any]
    data: dict[str, Any]
    metrics: dict[str, Decimal | int]
    equity_curve: tuple[EquityPoint, ...]
    trades: tuple[BacktestTrade, ...]
    code_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "code_version": self.code_version,
            "parameters": self.parameters,
            "data": self.data,
            "metrics": {
                key: decimal_to_str(value) if isinstance(value, Decimal) else value
                for key, value in self.metrics.items()
            },
            "equity_curve": [point.to_dict() for point in self.equity_curve],
            "trades": [trade.to_dict() for trade in self.trades],
        }
