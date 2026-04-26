from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest import TestCase

from packages.data.binance_klines import (
    BinanceSpotKlineClient,
    BinanceSpotKlineConfig,
    expected_candle_count,
    to_binance_symbol,
)


def ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def row(open_time: datetime, open_price: str) -> list[Any]:
    return [
        ms(open_time),
        open_price,
        str(Decimal(open_price) + Decimal("1")),
        str(Decimal(open_price) - Decimal("1")),
        open_price,
        "10",
        ms(open_time),
        "0",
        1,
        "0",
        "0",
        "0",
    ]


class BinanceKlinesTest(TestCase):
    def test_converts_system_pair_to_binance_symbol(self) -> None:
        self.assertEqual("BTCUSDT", to_binance_symbol("BTC-USDT"))
        self.assertEqual("ETHUSDT", to_binance_symbol("eth/usdt"))

    def test_expected_candle_count_uses_end_exclusive_range(self) -> None:
        count = expected_candle_count(
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2025, 1, 1, 12, tzinfo=UTC),
            interval="4h",
        )

        self.assertEqual(3, count)

    def test_fetch_candles_paginates_and_filters_end_exclusive(self) -> None:
        calls: list[dict[str, str | int]] = []
        payloads = [
            [
                row(datetime(2025, 1, 1, 0, tzinfo=UTC), "100"),
                row(datetime(2025, 1, 1, 4, tzinfo=UTC), "104"),
            ],
            [
                row(datetime(2025, 1, 1, 8, tzinfo=UTC), "108"),
                row(datetime(2025, 1, 1, 12, tzinfo=UTC), "112"),
            ],
        ]

        def getter(path: str, params: dict[str, str | int]) -> Any:
            self.assertEqual("/api/v3/klines", path)
            calls.append(params)
            return payloads[len(calls) - 1]

        client = BinanceSpotKlineClient(
            BinanceSpotKlineConfig(request_limit=2),
            json_getter=getter,
        )

        candles = client.fetch_candles(
            trading_pair="BTC-USDT",
            interval="4h",
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2025, 1, 1, 12, tzinfo=UTC),
        )

        self.assertEqual(3, len(candles))
        self.assertEqual("BTCUSDT", calls[0]["symbol"])
        self.assertEqual(ms(datetime(2025, 1, 1, tzinfo=UTC)), calls[0]["startTime"])
        self.assertEqual(ms(datetime(2025, 1, 1, 12, tzinfo=UTC)) - 1, calls[0]["endTime"])
        self.assertEqual(datetime(2025, 1, 1, 8, tzinfo=UTC), candles[-1].timestamp)
