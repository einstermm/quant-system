"""Shared enumerations for the quant system."""

from enum import Enum


class StringEnum(str, Enum):
    """String-valued enum with stable serialization."""

    def __str__(self) -> str:
        return self.value


class MarketType(StringEnum):
    SPOT = "spot"
    PERPETUAL = "perpetual"


class OrderSide(StringEnum):
    BUY = "buy"
    SELL = "sell"


class PositionSide(StringEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class OrderType(StringEnum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(StringEnum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    POST_ONLY = "post_only"


class SignalDirection(StringEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class RiskDecisionStatus(StringEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REDUCE_ONLY = "reduce_only"


class OrderStatus(StringEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    FAILED = "failed"
