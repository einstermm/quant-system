"""Performance report builder."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    total_return: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal | None = None
