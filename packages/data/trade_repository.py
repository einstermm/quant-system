"""Trade repository primitives."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from packages.core.models import require_positive


@dataclass(frozen=True, slots=True)
class Trade:
    exchange: str
    trading_pair: str
    trade_id: str
    timestamp: datetime
    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        require_positive(self.price, "price")
        require_positive(self.quantity, "quantity")


class InMemoryTradeRepository:
    def __init__(self) -> None:
        self._trades: list[Trade] = []

    def add_many(self, trades: list[Trade] | tuple[Trade, ...]) -> None:
        self._trades.extend(trades)
        self._trades.sort(key=lambda trade: trade.timestamp)

    def list(self, *, exchange: str, trading_pair: str) -> tuple[Trade, ...]:
        return tuple(
            trade
            for trade in self._trades
            if trade.exchange == exchange and trade.trading_pair == trading_pair
        )
