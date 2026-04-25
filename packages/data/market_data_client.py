"""Market data client contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from packages.core.models import Candle


class MarketDataClient(Protocol):
    def get_candles(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        """Fetch historical candles from an exchange or data vendor."""
