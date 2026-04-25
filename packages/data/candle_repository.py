"""Candle repository interfaces and in-memory implementation."""

from datetime import datetime
from typing import Protocol

from packages.core.models import Candle


class CandleRepository(Protocol):
    def add_many(self, candles: list[Candle] | tuple[Candle, ...]) -> None:
        """Persist candles."""

    def list(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[Candle, ...]:
        """List candles sorted by timestamp."""

    def latest(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
    ) -> Candle | None:
        """Return the latest candle for a market."""


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

    def count(
        self,
        *,
        exchange: str | None = None,
        trading_pair: str | None = None,
        interval: str | None = None,
    ) -> int:
        return len(
            tuple(
                candle
                for candle in self._candles
                if (exchange is None or candle.exchange == exchange)
                and (trading_pair is None or candle.trading_pair == trading_pair)
                and (interval is None or candle.interval == interval)
            )
        )
