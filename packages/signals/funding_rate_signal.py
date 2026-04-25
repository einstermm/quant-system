"""Funding-rate signal placeholder."""

from dataclasses import dataclass
from decimal import Decimal

from packages.core.enums import SignalDirection
from packages.core.models import Signal


@dataclass(frozen=True, slots=True)
class FundingRateSignal:
    strategy_id: str
    positive_threshold: Decimal
    negative_threshold: Decimal

    def generate_from_rate(self, *, symbol: str, funding_rate: Decimal) -> Signal:
        if funding_rate >= self.positive_threshold:
            return Signal(self.strategy_id, symbol, SignalDirection.SHORT, Decimal("0.55"))
        if funding_rate <= self.negative_threshold:
            return Signal(self.strategy_id, symbol, SignalDirection.LONG, Decimal("0.55"))
        return Signal(self.strategy_id, symbol, SignalDirection.FLAT, Decimal("0.5"))
