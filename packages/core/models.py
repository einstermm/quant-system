"""Core domain models.

These models are intentionally independent from Hummingbot so research, risk,
and reporting code can be tested without a live trading runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import (
    MarketType,
    OrderSide,
    OrderStatus,
    OrderType,
    SignalDirection,
    TimeInForce,
)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def require_positive(value: Decimal, name: str, *, allow_zero: bool = False) -> None:
    if allow_zero:
        valid = value >= Decimal("0")
    else:
        valid = value > Decimal("0")
    if not valid:
        comparator = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {comparator}")


@dataclass(frozen=True, slots=True)
class MarketSymbol:
    exchange: str
    base_asset: str
    quote_asset: str
    market_type: MarketType = MarketType.SPOT

    @property
    def trading_pair(self) -> str:
        return f"{self.base_asset}-{self.quote_asset}"

    @property
    def key(self) -> str:
        return f"{self.exchange}:{self.market_type.value}:{self.trading_pair}"


@dataclass(frozen=True, slots=True)
class Candle:
    exchange: str
    trading_pair: str
    interval: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        for field_name in ("open", "high", "low", "close"):
            require_positive(getattr(self, field_name), field_name)
        require_positive(self.volume, "volume", allow_zero=True)
        if self.low > self.high:
            raise ValueError("low cannot be greater than high")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be inside high/low range")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be inside high/low range")


@dataclass(frozen=True, slots=True)
class FundingRate:
    exchange: str
    trading_pair: str
    interval: str
    timestamp: datetime
    rate: Decimal

    def __post_init__(self) -> None:
        if not Decimal("-1") <= self.rate <= Decimal("1"):
            raise ValueError("funding rate must be between -1 and 1")


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        require_positive(self.price, "price")
        require_positive(self.quantity, "quantity")


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    exchange: str
    trading_pair: str
    timestamp: datetime
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]

    def __post_init__(self) -> None:
        if not self.bids:
            raise ValueError("bids cannot be empty")
        if not self.asks:
            raise ValueError("asks cannot be empty")

        for previous, current in zip(self.bids, self.bids[1:]):
            if previous.price < current.price:
                raise ValueError("bids must be sorted by descending price")

        for previous, current in zip(self.asks, self.asks[1:]):
            if previous.price > current.price:
                raise ValueError("asks must be sorted by ascending price")

        if self.bids[0].price >= self.asks[0].price:
            raise ValueError("best bid must be lower than best ask")


@dataclass(frozen=True, slots=True)
class Signal:
    strategy_id: str
    symbol: str
    direction: SignalDirection
    confidence: Decimal
    generated_at: datetime = field(default_factory=utc_now)
    target_weight: Decimal | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1")
        if self.target_weight is not None and not Decimal("-1") <= self.target_weight <= Decimal("1"):
            raise ValueError("target_weight must be between -1 and 1")


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        require_positive(abs(self.quantity), "absolute quantity")
        require_positive(self.entry_price, "entry_price")
        require_positive(self.mark_price, "mark_price")

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.mark_price


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    account_id: str
    equity: Decimal
    cash: Decimal
    positions: tuple[PortfolioPosition, ...] = ()
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_positive(self.equity, "equity")

    @property
    def gross_exposure(self) -> Decimal:
        return sum((abs(position.notional) for position in self.positions), Decimal("0"))

    def symbol_exposure(self, symbol: str) -> Decimal:
        return sum(
            (abs(position.notional) for position in self.positions if position.symbol == symbol),
            Decimal("0"),
        )


@dataclass(frozen=True, slots=True)
class OrderRequest:
    client_order_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False

    def __post_init__(self) -> None:
        require_positive(self.quantity, "quantity")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        if self.limit_price is not None:
            require_positive(self.limit_price, "limit_price")


@dataclass(frozen=True, slots=True)
class OrderState:
    client_order_id: str
    symbol: str
    status: OrderStatus
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_positive(self.filled_quantity, "filled_quantity", allow_zero=True)
        if self.average_fill_price is not None:
            require_positive(self.average_fill_price, "average_fill_price")
