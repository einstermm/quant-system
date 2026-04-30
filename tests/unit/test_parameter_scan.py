import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.backtesting.config import BacktestConfig, PortfolioBacktestConfig, SignalBacktestConfig
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.parameter_scan import (
    ParameterGrid,
    ParameterScanRunner,
    SelectionPolicy,
    write_parameter_scan_csv,
    write_parameter_scan_json,
)
from packages.backtesting.run_backtest import _apply_overrides
from packages.core.models import Candle
from packages.data.candle_repository import InMemoryCandleRepository
from packages.data.market_data_service import MarketDataService


class ParameterScanTest(TestCase):
    def test_grid_skips_invalid_window_pairs(self) -> None:
        grid = ParameterGrid(
            fast_windows=(2, 4),
            slow_windows=(3, 4),
            fee_rates=(Decimal("0"),),
            slippage_bps_values=(Decimal("0"),),
        )

        combinations = grid.combinations()

        self.assertEqual(2, len(combinations))
        self.assertEqual((2, 3), (combinations[0].fast_window, combinations[0].slow_window))
        self.assertEqual((2, 4), (combinations[1].fast_window, combinations[1].slow_window))

    def test_grid_expands_regime_filter_parameters(self) -> None:
        grid = ParameterGrid(
            fast_windows=(2,),
            slow_windows=(4,),
            fee_rates=(Decimal("0"),),
            slippage_bps_values=(Decimal("0"),),
            min_trend_strength_values=(Decimal("0"), Decimal("0.01")),
            max_volatility_values=(None, Decimal("0.04")),
        )

        combinations = grid.combinations()

        self.assertEqual(4, len(combinations))
        self.assertFalse(combinations[0].uses_regime_filter)
        self.assertTrue(combinations[-1].uses_regime_filter)
        self.assertIn("trend_0p01", combinations[-1].run_id)

    def test_grid_expands_relative_strength_parameters(self) -> None:
        grid = ParameterGrid(
            fast_windows=(0,),
            slow_windows=(0,),
            fee_rates=(Decimal("0.001"),),
            slippage_bps_values=(Decimal("2"),),
            lookback_windows=(24, 72),
            top_n_values=(1, 2),
            min_momentum_values=(Decimal("0"), Decimal("0.02")),
        )

        combinations = grid.combinations()

        self.assertEqual(8, len(combinations))
        self.assertEqual(24, combinations[0].lookback_window)
        self.assertEqual(1, combinations[0].top_n)
        self.assertEqual(2, combinations[2].top_n)
        self.assertEqual(Decimal("0.02"), combinations[-1].min_momentum)
        self.assertIn("lookback_72", combinations[-1].run_id)
        self.assertIn("top_2", combinations[-1].run_id)

    def test_risk_adjusted_policy_prefers_constraint_passing_run(self) -> None:
        policy = SelectionPolicy(
            mode="risk_adjusted",
            min_return=Decimal("0"),
            max_drawdown=Decimal("0.10"),
            max_turnover=Decimal("10"),
            max_tail_loss=Decimal("0.03"),
        )
        high_return_high_risk = {
            "total_return": Decimal("0.20"),
            "max_drawdown": Decimal("0.20"),
            "turnover": Decimal("25"),
            "tail_loss": Decimal("0.05"),
        }
        lower_return_lower_risk = {
            "total_return": Decimal("0.05"),
            "max_drawdown": Decimal("0.06"),
            "turnover": Decimal("5"),
            "tail_loss": Decimal("0.02"),
        }

        self.assertLess(
            policy.ranking_key(lower_return_lower_risk),
            policy.ranking_key(high_return_high_risk),
        )

    def test_parameter_scan_writes_ranked_json_and_csv(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        repository = InMemoryCandleRepository()
        repository.add_many(_sample_candles(start))
        service = MarketDataService(repository)
        engine = BacktestEngine(service, code_version="unit")
        runner = ParameterScanRunner(engine, code_version="unit")
        grid = ParameterGrid(
            fast_windows=(2, 3),
            slow_windows=(4,),
            fee_rates=(Decimal("0"),),
            slippage_bps_values=(Decimal("0"),),
        )

        result = runner.run(
            base_config=_config(start),
            grid=grid,
            experiment_id="unit_scan",
        )

        with TemporaryDirectory() as directory:
            json_path = write_parameter_scan_json(result, Path(directory) / "scan.json")
            csv_path = write_parameter_scan_csv(result, Path(directory) / "scan.csv")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            with csv_path.open("r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual("unit_scan", payload["experiment_id"])
        self.assertEqual("return_first", payload["selection_policy"]["mode"])
        self.assertEqual(2, len(payload["runs"]))
        self.assertEqual(1, payload["best_run"]["rank"])
        self.assertEqual(2, len(rows))
        self.assertEqual("1", rows[0]["rank"])

    def test_backtest_overrides_can_replay_scan_parameters(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        config = _config(start)

        updated = _apply_overrides(
            config,
            initial_equity=None,
            start=None,
            end=None,
            fee_rate="0.0006",
            slippage_bps="2",
            fast_window=3,
            slow_window=6,
            lookback_window=None,
            top_n=None,
            min_momentum=None,
            min_trend_strength="0.01",
            max_volatility="0.04",
        )

        self.assertEqual(Decimal("0.0006"), updated.fee_rate)
        self.assertEqual(Decimal("2"), updated.slippage_bps)
        self.assertEqual(3, updated.signal.fast_window)
        self.assertEqual(6, updated.signal.slow_window)
        self.assertTrue(updated.regime_filter.enabled)
        self.assertEqual(Decimal("0.04"), updated.regime_filter.max_volatility)


def _config(start: datetime) -> BacktestConfig:
    return BacktestConfig(
        strategy_id="unit_momentum",
        exchange="binance",
        market_type="spot",
        trading_pairs=("BTC-USDT", "ETH-USDT"),
        interval="1h",
        start=start,
        end=start + timedelta(hours=10),
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
    for index in range(10):
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
