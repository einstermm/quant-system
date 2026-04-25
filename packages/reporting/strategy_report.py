"""Strategy report builder."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class StrategyReport:
    strategy_id: str
    pnl: Decimal
    turnover: Decimal
    max_drawdown: Decimal
