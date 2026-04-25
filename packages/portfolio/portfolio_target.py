"""Portfolio target models."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioTarget:
    strategy_id: str
    symbol: str
    target_weight: Decimal
    max_notional: Decimal | None = None

    def __post_init__(self) -> None:
        if not Decimal("-1") <= self.target_weight <= Decimal("1"):
            raise ValueError("target_weight must be between -1 and 1")
