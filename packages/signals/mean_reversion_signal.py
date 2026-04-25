"""Mean reversion signal placeholder."""

from dataclasses import dataclass
from decimal import Decimal

from packages.core.enums import SignalDirection
from packages.core.models import Candle, Signal
from packages.features.indicators import simple_moving_average
from packages.signals.base_signal import BaseSignal


@dataclass(frozen=True, slots=True)
class MeanReversionSignal(BaseSignal):
    strategy_id: str
    lookback_window: int
    entry_threshold_pct: Decimal

    def generate(self, candles: tuple[Candle, ...]) -> Signal | None:
        if len(candles) < self.lookback_window:
            return None

        closes = tuple(candle.close for candle in candles)
        average = simple_moving_average(closes, self.lookback_window)
        latest = candles[-1]
        distance = latest.close / average - Decimal("1")

        if distance <= -self.entry_threshold_pct:
            return Signal(self.strategy_id, latest.trading_pair, SignalDirection.LONG, Decimal("0.55"))
        if distance >= self.entry_threshold_pct:
            return Signal(self.strategy_id, latest.trading_pair, SignalDirection.SHORT, Decimal("0.55"))
        return Signal(self.strategy_id, latest.trading_pair, SignalDirection.FLAT, Decimal("0.5"))
