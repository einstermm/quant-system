import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.backtesting.config import BacktestConfig, PortfolioBacktestConfig, SignalBacktestConfig
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.parameter_scan import ParameterGrid
from packages.backtesting.train_test_validation import (
    TrainTestSplit,
    TrainTestValidationRunner,
    write_train_test_validation_csv,
    write_train_test_validation_json,
)
from packages.core.models import Candle
from packages.data.candle_repository import InMemoryCandleRepository
from packages.data.market_data_service import MarketDataService


class TrainTestValidationTest(TestCase):
    def test_split_rejects_overlap(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)

        with self.assertRaises(ValueError):
            TrainTestSplit(
                train_start=start,
                train_end=start + timedelta(hours=10),
                test_start=start + timedelta(hours=9),
                test_end=start + timedelta(hours=20),
            )

    def test_train_test_validation_writes_ranked_outputs(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        repository = InMemoryCandleRepository()
        repository.add_many(_sample_candles(start))
        service = MarketDataService(repository)
        engine = BacktestEngine(service, code_version="unit")
        runner = TrainTestValidationRunner(engine, code_version="unit")
        grid = ParameterGrid(
            fast_windows=(2, 3),
            slow_windows=(4,),
            fee_rates=(Decimal("0"),),
            slippage_bps_values=(Decimal("0"),),
        )
        split = TrainTestSplit(
            train_start=start,
            train_end=start + timedelta(hours=12),
            test_start=start + timedelta(hours=12),
            test_end=start + timedelta(hours=24),
        )

        result = runner.run(
            base_config=_config(start),
            grid=grid,
            split=split,
            experiment_id="unit_train_test",
        )

        with TemporaryDirectory() as directory:
            json_path = write_train_test_validation_json(result, Path(directory) / "validation.json")
            csv_path = write_train_test_validation_csv(result, Path(directory) / "validation.csv")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            with csv_path.open("r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual("unit_train_test", payload["experiment_id"])
        self.assertEqual(2, len(payload["runs"]))
        self.assertEqual(1, payload["best_train_run"]["rank"])
        self.assertIn("best_test_run", payload)
        self.assertEqual(2, len(rows))
        self.assertEqual("1", rows[0]["rank"])
        self.assertIn("test_total_return", rows[0])


def _config(start: datetime) -> BacktestConfig:
    return BacktestConfig(
        strategy_id="unit_momentum",
        exchange="binance",
        market_type="spot",
        trading_pairs=("BTC-USDT", "ETH-USDT"),
        interval="1h",
        start=start,
        end=start + timedelta(hours=24),
        initial_equity=Decimal("1000"),
        fee_rate=Decimal("0"),
        slippage_bps=Decimal("0"),
        signal=SignalBacktestConfig(
            signal_type="moving_average_trend",
            fast_window=2,
            slow_window=4,
        ),
        portfolio=PortfolioBacktestConfig(
            gross_target=Decimal("0.50"),
            max_symbol_weight=Decimal("0.25"),
            rebalance_threshold=Decimal("0"),
        ),
    )


def _sample_candles(start: datetime) -> tuple[Candle, ...]:
    candles = []
    for index in range(24):
        timestamp = start + timedelta(hours=index)
        btc_open = Decimal("100") + Decimal(index)
        eth_open = Decimal("200") - Decimal(index)
        candles.extend(
            (
                Candle(
                    exchange="binance",
                    trading_pair="BTC-USDT",
                    interval="1h",
                    timestamp=timestamp,
                    open=btc_open,
                    high=btc_open + Decimal("2"),
                    low=btc_open - Decimal("1"),
                    close=btc_open + Decimal("1"),
                    volume=Decimal("10"),
                ),
                Candle(
                    exchange="binance",
                    trading_pair="ETH-USDT",
                    interval="1h",
                    timestamp=timestamp,
                    open=eth_open,
                    high=eth_open + Decimal("1"),
                    low=eth_open - Decimal("2"),
                    close=eth_open - Decimal("1"),
                    volume=Decimal("10"),
                ),
            )
        )
    return tuple(candles)
