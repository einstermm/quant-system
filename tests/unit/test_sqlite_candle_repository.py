import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from packages.data.csv_candle_source import parse_utc_datetime, read_candles_csv
from packages.data.load_candles_sqlite import main as load_candles_sqlite_main
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


SAMPLE_CSV = Path(__file__).parents[2] / "data" / "samples" / "binance_1h_candles.csv"


class SQLiteCandleRepositoryTest(TestCase):
    def test_add_many_upserts_and_queries_candles(self) -> None:
        result = read_candles_csv(SAMPLE_CSV)

        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "warehouse.sqlite"
            with SQLiteCandleRepository(db_path) as repository:
                repository.add_many(result.candles)
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
                latest = repository.latest(
                    exchange="binance",
                    trading_pair="BTC-USDT",
                    interval="1h",
                )

                self.assertEqual(8, repository.count())
                self.assertEqual(4, repository.count(trading_pair="BTC-USDT"))
                self.assertEqual(4, len(btc_candles))
                self.assertEqual(2, len(eth_candles))
                self.assertIsNotNone(latest)
                self.assertEqual("2024-01-01T03:00:00+00:00", latest.timestamp.isoformat())

    def test_load_candles_sqlite_cli_writes_db_and_quality_report(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "warehouse.sqlite"
            report_path = Path(directory) / "quality.json"
            argv = [
                "load_candles_sqlite",
                "--input",
                str(SAMPLE_CSV),
                "--db",
                str(db_path),
                "--quality-report",
                str(report_path),
            ]

            with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                load_candles_sqlite_main()

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            with SQLiteCandleRepository(db_path) as repository:
                total_rows = repository.count()
            db_exists = db_path.exists()

        self.assertTrue(db_exists)
        self.assertTrue(payload["ok"])
        self.assertEqual(8, total_rows)
