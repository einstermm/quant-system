"""Moving-average trend signal."""

from dataclasses import dataclass
from decimal import Decimal

from packages.core.enums import SignalDirection
from packages.core.models import Candle, Signal
from packages.features.indicators import simple_moving_average
from packages.signals.base_signal import BaseSignal


@dataclass(frozen=True, slots=True)
class MovingAverageTrendSignal(BaseSignal):
    strategy_id: str
    fast_window: int
    slow_window: int

    def generate(self, candles: tuple[Candle, ...]) -> Signal | None:
        if len(candles) < self.slow_window:
            return None

        closes = tuple(candle.close for candle in candles)
        fast = simple_moving_average(closes, self.fast_window)
        slow = simple_moving_average(closes, self.slow_window)
        latest = candles[-1]

        if fast > slow:
            return Signal(self.strategy_id, latest.trading_pair, SignalDirection.LONG, Decimal("0.6"))
        if fast < slow:
            return Signal(self.strategy_id, latest.trading_pair, SignalDirection.SHORT, Decimal("0.6"))
        return Signal(self.strategy_id, latest.trading_pair, SignalDirection.FLAT, Decimal("0.5"))
