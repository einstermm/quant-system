"""Normalized order intent passed from portfolio/risk to execution."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from packages.core.models import OrderRequest, require_positive, utc_now


@dataclass(frozen=True, slots=True)
class OrderIntent:
    intent_id: str
    account_id: str
    request: OrderRequest
    estimated_price: Decimal
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_positive(self.estimated_price, "estimated_price")

    @property
    def symbol(self) -> str:
        return self.request.symbol

    @property
    def notional(self) -> Decimal:
        return self.request.quantity * self.estimated_price
