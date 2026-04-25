import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.core.models import Candle
from packages.data.candle_repository import InMemoryCandleRepository
from packages.data.csv_candle_source import parse_utc_datetime, read_candles_csv
from packages.data.data_quality import build_candle_quality_report, write_quality_report


SAMPLE_CSV = Path(__file__).parents[2] / "data" / "samples" / "binance_1h_candles.csv"


class CandleCSVImportTest(TestCase):
    def test_reads_sample_btc_eth_1h_candles(self) -> None:
        result = read_candles_csv(SAMPLE_CSV)

        self.assertEqual(8, len(result.candles))
        self.assertEqual((), result.row_errors)
        self.assertEqual({"BTC-USDT", "ETH-USDT"}, {candle.trading_pair for candle in result.candles})

    def test_imported_candles_are_queryable_by_repository(self) -> None:
        result = read_candles_csv(SAMPLE_CSV)
        repository = InMemoryCandleRepository()
        repository.add_many(result.candles)

        btc_candles = repository.list(
            exchange="binance",
            trading_pair="BTC-USDT",
            interval="1h",
        )
        eth_candles = repository.list(
            exchange="binance",
            trading_pair="ETH-USDT",
            interval="1h",
            start=parse_utc_datetime("2024-01-01T01:00:00+00:00"),
            end=parse_utc_datetime("2024-01-01T02:00:00+00:00"),
        )

        self.assertEqual(4, len(btc_candles))
        self.assertEqual(2, len(eth_candles))
        self.assertEqual("BTC-USDT", repository.latest(
            exchange="binance",
            trading_pair="BTC-USDT",
            interval="1h",
        ).trading_pair)

    def test_quality_report_can_be_written_to_file(self) -> None:
        result = read_candles_csv(SAMPLE_CSV)
        report = build_candle_quality_report(result.candles)

        with TemporaryDirectory() as directory:
            report_path = write_quality_report(report, Path(directory) / "quality.json")
            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertTrue(report.ok)
        self.assertEqual(8, payload["candles_checked"])
        self.assertEqual(2, payload["groups_checked"])
        self.assertEqual([], payload["issues"])

    def test_quality_report_flags_duplicate_gap_and_zero_volume(self) -> None:
        candles = (
            Candle(
                exchange="binance",
                trading_pair="BTC-USDT",
                interval="1h",
                timestamp=datetime(2024, 1, 1, 0, tzinfo=UTC),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("10"),
            ),
            Candle(
                exchange="binance",
                trading_pair="BTC-USDT",
                interval="1h",
                timestamp=datetime(2024, 1, 1, 0, tzinfo=UTC),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("0"),
            ),
            Candle(
                exchange="binance",
                trading_pair="BTC-USDT",
                interval="1h",
                timestamp=datetime(2024, 1, 1, 2, tzinfo=UTC),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("10"),
            ),
        )

        report = build_candle_quality_report(candles)
        codes = {issue.code for issue in report.issues}

        self.assertFalse(report.ok)
        self.assertIn("duplicate_timestamp", codes)
        self.assertIn("missing_candle", codes)
        self.assertIn("zero_volume", codes)
