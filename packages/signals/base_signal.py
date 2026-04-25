"""Base signal interface."""

from abc import ABC, abstractmethod

from packages.core.models import Candle, Signal


class BaseSignal(ABC):
    strategy_id: str

    @abstractmethod
    def generate(self, candles: tuple[Candle, ...]) -> Signal | None:
        """Generate a signal from recent market data."""
