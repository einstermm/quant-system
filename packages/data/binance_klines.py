"""Binance spot kline downloader."""

from __future__ import annotations

import json
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from packages.core.models import Candle
from packages.data.timeframes import expected_interval_count, interval_to_timedelta


JSONGetter = Callable[[str, dict[str, str | int]], Any]


@dataclass(frozen=True, slots=True)
class BinanceSpotKlineConfig:
    base_url: str = "https://api.binance.com"
    request_limit: int = 1000
    timeout_seconds: int = 30
    verify_tls: bool = True


class BinanceKlineDownloadError(RuntimeError):
    """Raised when Binance kline data cannot be downloaded or parsed."""


class BinanceSpotKlineClient:
    def __init__(
        self,
        config: BinanceSpotKlineConfig | None = None,
        *,
        json_getter: JSONGetter | None = None,
    ) -> None:
        self._config = config or BinanceSpotKlineConfig()
        self._json_getter = json_getter or self._default_json_getter

    def fetch_candles(
        self,
        *,
        trading_pair: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if start >= end:
            raise ValueError("start must be before end")

        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        interval_delta = interval_to_timedelta(interval)
        interval_ms = int(interval_delta.total_seconds() * 1000)

        next_open_ms = _datetime_to_ms(start_utc)
        end_exclusive_ms = _datetime_to_ms(end_utc)
        candles: list[Candle] = []

        while next_open_ms < end_exclusive_ms:
            payload = self._json_getter(
                "/api/v3/klines",
                {
                    "symbol": to_binance_symbol(trading_pair),
                    "interval": interval,
                    "startTime": next_open_ms,
                    "endTime": end_exclusive_ms - 1,
                    "limit": self._config.request_limit,
                },
            )
            rows = _ensure_kline_rows(payload)
            if not rows:
                break

            last_open_ms = next_open_ms
            for row in rows:
                candle = _row_to_candle(
                    row,
                    exchange="binance",
                    trading_pair=trading_pair,
                    interval=interval,
                )
                open_ms = _datetime_to_ms(candle.timestamp)
                last_open_ms = max(last_open_ms, open_ms)
                if start_utc <= candle.timestamp < end_utc:
                    candles.append(candle)

            next_open_ms = last_open_ms + interval_ms

            if len(rows) < self._config.request_limit:
                break

        return tuple(sorted(candles, key=lambda candle: candle.timestamp))

    def _default_json_getter(self, path: str, params: dict[str, str | int]) -> Any:
        url = f"{self._config.base_url.rstrip('/')}{path}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "quant-system/0.1"})
        context = None if self._config.verify_tls else ssl._create_unverified_context()
        try:
            with urlopen(request, timeout=self._config.timeout_seconds, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except OSError as exc:
            raise BinanceKlineDownloadError(f"failed to request Binance klines: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise BinanceKlineDownloadError("Binance returned invalid JSON") from exc


def to_binance_symbol(trading_pair: str) -> str:
    return trading_pair.replace("-", "").replace("/", "").upper()


def expected_candle_count(*, start: datetime, end: datetime, interval: str) -> int:
    return expected_interval_count(start=start, end=end, interval=interval)


def _datetime_to_ms(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp() * 1000)


def _ms_to_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _ensure_kline_rows(payload: Any) -> list[list[Any]]:
    if not isinstance(payload, list):
        raise BinanceKlineDownloadError("Binance kline response must be a list")
    return payload


def _row_to_candle(
    row: list[Any],
    *,
    exchange: str,
    trading_pair: str,
    interval: str,
) -> Candle:
    if len(row) < 6:
        raise BinanceKlineDownloadError("Binance kline row has fewer than 6 fields")

    return Candle(
        exchange=exchange,
        trading_pair=trading_pair,
        interval=interval,
        timestamp=_ms_to_datetime(int(row[0])),
        open=Decimal(str(row[1])),
        high=Decimal(str(row[2])),
        low=Decimal(str(row[3])),
        close=Decimal(str(row[4])),
        volume=Decimal(str(row[5])),
    )


def iter_expected_opens(*, start: datetime, end: datetime, interval: str) -> tuple[datetime, ...]:
    if start >= end:
        raise ValueError("start must be before end")
    step = interval_to_timedelta(interval)
    opens: list[datetime] = []
    current = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    while current < end_utc:
        opens.append(current)
        current = current + step
    return tuple(opens)
