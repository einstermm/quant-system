from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.data.csv_candle_source import parse_utc_datetime, read_candles_csv
from packages.data.market_data_service import CandleQuery, MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository
from packages.data.strategy_data_config import load_strategy_data_config


SAMPLE_CSV = Path(__file__).parents[2] / "data" / "samples" / "binance_1h_candles.csv"


class MarketDataServiceTest(TestCase):
    def test_load_candles_uses_end_exclusive_query_range(self) -> None:
        result = read_candles_csv(SAMPLE_CSV)

        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "warehouse.sqlite"
            with SQLiteCandleRepository(db_path) as repository:
                repository.add_many(result.candles)
                service = MarketDataService(repository)
                query = CandleQuery(
                    exchange="binance",
                    trading_pair="ETH-USDT",
                    interval="1h",
                    start=parse_utc_datetime("2024-01-01T01:00:00+00:00"),
                    end=parse_utc_datetime("2024-01-01T03:00:00+00:00"),
                )

                query_result = service.load_candles(query)

        self.assertTrue(query_result.complete)
        self.assertEqual(2, query.expected_count)
        self.assertEqual(2, len(query_result.candles))
        self.assertEqual("2024-01-01T01:00:00+00:00", query_result.first_timestamp.isoformat())
        self.assertEqual("2024-01-01T02:00:00+00:00", query_result.last_timestamp.isoformat())

    def test_load_candles_marks_missing_end_as_incomplete(self) -> None:
        result = read_candles_csv(SAMPLE_CSV)

        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "warehouse.sqlite"
            with SQLiteCandleRepository(db_path) as repository:
                repository.add_many(result.candles)
                service = MarketDataService(repository)
                query = CandleQuery(
                    exchange="binance",
                    trading_pair="BTC-USDT",
                    interval="1h",
                    start=parse_utc_datetime("2024-01-01T00:00:00+00:00"),
                    end=parse_utc_datetime("2024-01-01T06:00:00+00:00"),
                )

                query_result = service.load_candles(query)

        codes = {issue.code for issue in query_result.quality_report.issues}
        self.assertFalse(query_result.complete)
        self.assertIn("missing_end", codes)
        self.assertEqual(6, query.expected_count)
        self.assertEqual(4, len(query_result.candles))

    def test_strategy_data_config_builds_queries(self) -> None:
        config = load_strategy_data_config(Path(__file__).parents[2] / "strategies" / "crypto_momentum_v1")
        queries = config.candle_queries()

        self.assertEqual("crypto_momentum_v1", config.strategy_id)
        self.assertEqual("binance", config.exchange)
        self.assertEqual(("BTC-USDT", "ETH-USDT"), config.trading_pairs)
        self.assertEqual("4h", config.interval)
        self.assertEqual(2, len(queries))
        self.assertEqual("binance:BTC-USDT:4h", queries[0].key)
        self.assertEqual("2025-01-01T00:00:00+00:00", queries[0].start.isoformat())
        self.assertEqual("2026-01-01T00:00:00+00:00", queries[0].end.isoformat())
