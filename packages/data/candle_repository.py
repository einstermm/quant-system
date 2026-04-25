"""Candle repository interfaces and in-memory implementation."""

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
    ) -> tuple[Candle, ...]:
        return tuple(
            candle
            for candle in self._candles
            if candle.exchange == exchange
            and candle.trading_pair == trading_pair
            and candle.interval == interval
        )
