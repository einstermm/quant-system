"""Refresh recent public market data into the local warehouse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from packages.core.models import Candle
from packages.data.binance_klines import BinanceSpotKlineClient
from packages.data.candle_repository import CandleRepository
from packages.data.timeframes import floor_datetime_to_interval, interval_to_timedelta


class KlineClient(Protocol):
    def fetch_candles(
        self,
        *,
        trading_pair: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        """Fetch candles in an end-exclusive time range."""


@dataclass(frozen=True, slots=True)
class MarketDataRefreshResult:
    exchange: str
    trading_pair: str
    interval: str
    status: str
    start: datetime | None
    end: datetime
    latest_before: datetime | None
    latest_after: datetime | None
    fetched_candles: int
    stored_candles: int
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "exchange": self.exchange,
            "trading_pair": self.trading_pair,
            "interval": self.interval,
            "status": self.status,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat(),
            "latest_before": self.latest_before.isoformat() if self.latest_before else None,
            "latest_after": self.latest_after.isoformat() if self.latest_after else None,
            "fetched_candles": self.fetched_candles,
            "stored_candles": self.stored_candles,
            "error": self.error,
        }


def refresh_binance_spot_candles(
    *,
    repository: CandleRepository,
    trading_pairs: tuple[str, ...],
    interval: str,
    now: datetime,
    exchange: str = "binance",
    client: KlineClient | None = None,
    overlap_bars: int = 2,
    bootstrap_bars: int = 200,
    close_delay_seconds: Decimal = Decimal("60"),
) -> tuple[MarketDataRefreshResult, ...]:
    if overlap_bars < 0:
        raise ValueError("overlap_bars cannot be negative")
    if bootstrap_bars <= 0:
        raise ValueError("bootstrap_bars must be positive")
    if close_delay_seconds < Decimal("0"):
        raise ValueError("close_delay_seconds cannot be negative")

    kline_client = client or BinanceSpotKlineClient()
    interval_delta = interval_to_timedelta(interval)
    end = latest_closed_candle_end(
        now=now,
        interval=interval,
        close_delay_seconds=close_delay_seconds,
    )
    results = []
    for trading_pair in trading_pairs:
        results.append(
            _refresh_trading_pair(
                repository=repository,
                client=kline_client,
                exchange=exchange,
                trading_pair=trading_pair,
                interval=interval,
                end=end,
                interval_delta=interval_delta,
                overlap_bars=overlap_bars,
                bootstrap_bars=bootstrap_bars,
            )
        )
    return tuple(results)


def latest_closed_candle_end(
    *,
    now: datetime,
    interval: str,
    close_delay_seconds: Decimal = Decimal("60"),
) -> datetime:
    delayed_now = now - timedelta(seconds=float(close_delay_seconds))
    return floor_datetime_to_interval(delayed_now, interval)


def _refresh_trading_pair(
    *,
    repository: CandleRepository,
    client: KlineClient,
    exchange: str,
    trading_pair: str,
    interval: str,
    end: datetime,
    interval_delta: timedelta,
    overlap_bars: int,
    bootstrap_bars: int,
) -> MarketDataRefreshResult:
    latest_before_candle = repository.latest(
        exchange=exchange,
        trading_pair=trading_pair,
        interval=interval,
    )
    latest_before = latest_before_candle.timestamp if latest_before_candle else None
    start = _refresh_start(
        latest_before=latest_before,
        end=end,
        interval_delta=interval_delta,
        overlap_bars=overlap_bars,
        bootstrap_bars=bootstrap_bars,
    )
    if start >= end:
        return MarketDataRefreshResult(
            exchange=exchange,
            trading_pair=trading_pair,
            interval=interval,
            status="up_to_date",
            start=start,
            end=end,
            latest_before=latest_before,
            latest_after=latest_before,
            fetched_candles=0,
            stored_candles=0,
        )

    try:
        candles = client.fetch_candles(
            trading_pair=trading_pair,
            interval=interval,
            start=start,
            end=end,
        )
        repository.add_many(candles)
        latest_after_candle = repository.latest(
            exchange=exchange,
            trading_pair=trading_pair,
            interval=interval,
        )
        latest_after = latest_after_candle.timestamp if latest_after_candle else None
    except Exception as exc:
        return MarketDataRefreshResult(
            exchange=exchange,
            trading_pair=trading_pair,
            interval=interval,
            status="failed",
            start=start,
            end=end,
            latest_before=latest_before,
            latest_after=latest_before,
            fetched_candles=0,
            stored_candles=0,
            error=str(exc),
        )

    return MarketDataRefreshResult(
        exchange=exchange,
        trading_pair=trading_pair,
        interval=interval,
        status="ok",
        start=start,
        end=end,
        latest_before=latest_before,
        latest_after=latest_after,
        fetched_candles=len(candles),
        stored_candles=len(candles),
    )


def _refresh_start(
    *,
    latest_before: datetime | None,
    end: datetime,
    interval_delta: timedelta,
    overlap_bars: int,
    bootstrap_bars: int,
) -> datetime:
    if latest_before is None:
        return end - (interval_delta * bootstrap_bars)
    if overlap_bars == 0:
        return latest_before + interval_delta
    return latest_before - (interval_delta * (overlap_bars - 1))
