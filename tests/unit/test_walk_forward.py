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
from packages.backtesting.train_test_validation import TrainTestSplit
from packages.backtesting.walk_forward import (
    WalkForwardFold,
    WalkForwardRunner,
    build_walk_forward_folds,
    write_walk_forward_csv,
    write_walk_forward_json,
)
from packages.core.models import Candle
from packages.data.candle_repository import InMemoryCandleRepository
from packages.data.market_data_service import MarketDataService


class WalkForwardTest(TestCase):
    def test_build_walk_forward_folds(self) -> None:
        folds = build_walk_forward_folds(
            start=datetime(2023, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 1, tzinfo=UTC),
            train_months=6,
            test_months=3,
            step_months=3,
        )

        self.assertEqual(2, len(folds))
        self.assertEqual(1, folds[0].fold_id)
        self.assertEqual(datetime(2023, 1, 1, tzinfo=UTC), folds[0].split.train_start)
        self.assertEqual(datetime(2023, 10, 1, tzinfo=UTC), folds[0].split.test_end)
        self.assertEqual(datetime(2023, 4, 1, tzinfo=UTC), folds[1].split.train_start)

    def test_walk_forward_runner_writes_outputs(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        repository = InMemoryCandleRepository()
        repository.add_many(_sample_candles(start))
        service = MarketDataService(repository)
        engine = BacktestEngine(service, code_version="unit")
        runner = WalkForwardRunner(engine, code_version="unit")
        grid = ParameterGrid(
            fast_windows=(2, 3),
            slow_windows=(4,),
            fee_rates=(Decimal("0"),),
            slippage_bps_values=(Decimal("0"),),
        )
        folds = (
            WalkForwardFold(
                fold_id=1,
                split=TrainTestSplit(
                    train_start=start,
                    train_end=start + timedelta(hours=16),
                    test_start=start + timedelta(hours=16),
                    test_end=start + timedelta(hours=28),
                ),
            ),
            WalkForwardFold(
                fold_id=2,
                split=TrainTestSplit(
                    train_start=start + timedelta(hours=8),
                    train_end=start + timedelta(hours=24),
                    test_start=start + timedelta(hours=24),
                    test_end=start + timedelta(hours=36),
                ),
            ),
        )

        result = runner.run(
            base_config=_config(start),
            grid=grid,
            folds=folds,
            experiment_id="unit_walk_forward",
        )

        with TemporaryDirectory() as directory:
            json_path = write_walk_forward_json(result, Path(directory) / "wf.json")
            csv_path = write_walk_forward_csv(result, Path(directory) / "wf.csv")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            with csv_path.open("r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual("unit_walk_forward", payload["experiment_id"])
        self.assertEqual(2, payload["summary"]["folds"])
        self.assertEqual(2, len(payload["folds"]))
        self.assertEqual(2, len(rows))
        self.assertIn("selected_test_total_return", rows[0])


def _config(start: datetime) -> BacktestConfig:
    return BacktestConfig(
        strategy_id="unit_momentum",
        exchange="binance",
        market_type="spot",
        trading_pairs=("BTC-USDT", "ETH-USDT"),
        interval="1h",
        start=start,
        end=start + timedelta(hours=36),
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
    for index in range(36):
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
