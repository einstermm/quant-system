from datetime import UTC, datetime
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.core.models import Candle
from packages.data.market_data_refresh import (
    latest_closed_candle_end,
    refresh_binance_spot_candles,
)
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


class FakeKlineClient:
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self.candles = candles
        self.calls: list[dict[str, object]] = []

    def fetch_candles(
        self,
        *,
        trading_pair: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        self.calls.append(
            {
                "trading_pair": trading_pair,
                "interval": interval,
                "start": start,
                "end": end,
            }
        )
        return tuple(
            candle
            for candle in self.candles
            if candle.trading_pair == trading_pair
            and candle.interval == interval
            and start <= candle.timestamp < end
        )


class MarketDataRefreshTest(TestCase):
    def test_latest_closed_candle_end_uses_close_delay(self) -> None:
        end = latest_closed_candle_end(
            now=datetime(2026, 4, 26, 4, 0, 30, tzinfo=UTC),
            interval="4h",
            close_delay_seconds=Decimal("60"),
        )

        self.assertEqual(datetime(2026, 4, 26, 0, 0, tzinfo=UTC), end)

    def test_refresh_binance_spot_candles_upserts_incremental_rows(self) -> None:
        existing = _candle("BTC-USDT", datetime(2026, 1, 1, 0, tzinfo=UTC), "100")
        refreshed = (
            _candle("BTC-USDT", datetime(2026, 1, 1, 0, tzinfo=UTC), "101"),
            _candle("BTC-USDT", datetime(2026, 1, 1, 4, tzinfo=UTC), "104"),
            _candle("BTC-USDT", datetime(2026, 1, 1, 8, tzinfo=UTC), "108"),
        )
        client = FakeKlineClient(refreshed)

        with TemporaryDirectory() as directory:
            with SQLiteCandleRepository(f"{directory}/warehouse.sqlite") as repository:
                repository.add_many((existing,))
                results = refresh_binance_spot_candles(
                    repository=repository,
                    trading_pairs=("BTC-USDT",),
                    interval="4h",
                    now=datetime(2026, 1, 1, 12, tzinfo=UTC),
                    client=client,
                    overlap_bars=1,
                    close_delay_seconds=Decimal("0"),
                )
                candles = repository.list(
                    exchange="binance",
                    trading_pair="BTC-USDT",
                    interval="4h",
                )

        self.assertEqual("ok", results[0].status)
        self.assertEqual(3, results[0].fetched_candles)
        self.assertEqual(datetime(2026, 1, 1, 0, tzinfo=UTC), client.calls[0]["start"])
        self.assertEqual(datetime(2026, 1, 1, 12, tzinfo=UTC), client.calls[0]["end"])
        self.assertEqual(3, len(candles))
        self.assertEqual(Decimal("101"), candles[0].close)
        self.assertEqual(datetime(2026, 1, 1, 8, tzinfo=UTC), results[0].latest_after)

    def test_refresh_skips_when_repository_is_up_to_date(self) -> None:
        existing = _candle("BTC-USDT", datetime(2026, 1, 1, 8, tzinfo=UTC), "108")
        client = FakeKlineClient(())

        with TemporaryDirectory() as directory:
            with SQLiteCandleRepository(f"{directory}/warehouse.sqlite") as repository:
                repository.add_many((existing,))
                results = refresh_binance_spot_candles(
                    repository=repository,
                    trading_pairs=("BTC-USDT",),
                    interval="4h",
                    now=datetime(2026, 1, 1, 12, tzinfo=UTC),
                    client=client,
                    overlap_bars=0,
                    close_delay_seconds=Decimal("0"),
                )

        self.assertEqual("up_to_date", results[0].status)
        self.assertEqual(0, len(client.calls))


def _candle(symbol: str, timestamp: datetime, close: str) -> Candle:
    close_decimal = Decimal(close)
    return Candle(
        exchange="binance",
        trading_pair=symbol,
        interval="4h",
        timestamp=timestamp,
        open=close_decimal,
        high=close_decimal,
        low=close_decimal,
        close=close_decimal,
        volume=Decimal("1000"),
    )
