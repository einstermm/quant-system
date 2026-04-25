"""Candle repository interfaces and in-memory implementation."""

from datetime import datetime

from packages.core.models import Candle


class InMemoryCandleRepository:
    def __init__(self) -> None:
        self._candles: list[Candle] = []

    def add_many(self, candles: list[Candle] | tuple[Candle, ...]) -> None:
        self._candles.extend(candles)
        self._candles.sort(key=lambda candle: candle.timestamp)

    def list(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[Candle, ...]:
        return tuple(
            candle
            for candle in self._candles
            if candle.exchange == exchange
            and candle.trading_pair == trading_pair
            and candle.interval == interval
            and (start is None or candle.timestamp >= start)
            and (end is None or candle.timestamp <= end)
        )

    def latest(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
    ) -> Candle | None:
        candles = self.list(exchange=exchange, trading_pair=trading_pair, interval=interval)
        if not candles:
            return None
        return candles[-1]
