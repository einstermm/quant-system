"""Run train/test parameter validation for a local SQLite-backed strategy."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import load_backtest_config
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.parameter_scan import ParameterGrid
from packages.backtesting.result import decimal_to_str
from packages.backtesting.run_backtest import _git_version
from packages.backtesting.run_parameter_scan import (
    _parse_decimal_tuple,
    _parse_int_tuple,
    _parse_optional_decimal_tuple,
    _selection_policy_from_args,
)
from packages.backtesting.train_test_validation import (
    TrainTestSplit,
    TrainTestValidationRunner,
    write_train_test_validation_csv,
    write_train_test_validation_json,
)
from packages.data.csv_candle_source import parse_utc_datetime
from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run train/test parameter validation.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--summary-csv", help="Optional output CSV summary path")
    parser.add_argument("--experiment-id", default="crypto_momentum_v1_phase_3_2", help="Experiment id")
    parser.add_argument("--train-start", default="2025-01-01", help="Train start, inclusive")
    parser.add_argument("--train-end", default="2025-07-01", help="Train end, exclusive")
    parser.add_argument("--test-start", default="2025-07-01", help="Test start, inclusive")
    parser.add_argument("--test-end", default="2026-01-01", help="Test end, exclusive")
    parser.add_argument("--fast-windows", default="12,24,36", help="Comma-separated fast windows")
    parser.add_argument("--slow-windows", default="72,96,144", help="Comma-separated slow windows")
    parser.add_argument("--fee-rates", help="Comma-separated fee rates. Defaults to strategy backtest.yml")
    parser.add_argument("--slippage-bps", help="Comma-separated slippage bps. Defaults to strategy backtest.yml")
    parser.add_argument("--min-trend-strengths", default="0", help="Comma-separated trend strength filters")
    parser.add_argument(
        "--max-volatility",
        default="none",
        help="Comma-separated volatility caps, use none to disable",
    )
    parser.add_argument("--lookback-windows", help="Comma-separated lookback windows for relative strength")
    parser.add_argument("--rotation-top-n-values", help="Comma-separated top_n values for relative strength")
    parser.add_argument("--min-momentum", default="0", help="Comma-separated minimum momentum filters")
    parser.add_argument(
        "--selection-mode",
        choices=("return_first", "risk_adjusted"),
        default="return_first",
        help="Parameter selection mode",
    )
    parser.add_argument("--selection-min-return", help="Minimum train return required by risk_adjusted selection")
    parser.add_argument("--selection-max-drawdown", help="Maximum train drawdown allowed by risk_adjusted selection")
    parser.add_argument("--selection-max-turnover", help="Maximum train turnover allowed by risk_adjusted selection")
    parser.add_argument("--selection-max-tail-loss", help="Maximum train period tail loss allowed by risk_adjusted selection")
    parser.add_argument("--drawdown-penalty", default="1", help="Risk-adjusted drawdown penalty")
    parser.add_argument("--turnover-penalty", default="0.01", help="Risk-adjusted turnover penalty")
    parser.add_argument("--tail-loss-penalty", default="2", help="Risk-adjusted tail loss penalty")
    parser.add_argument("--top-n", type=int, default=10, help="Number of ranked runs to print")
    args = parser.parse_args()

    base_config = load_backtest_config(Path(args.strategy_dir))
    split = TrainTestSplit(
        train_start=parse_utc_datetime(args.train_start),
        train_end=parse_utc_datetime(args.train_end),
        test_start=parse_utc_datetime(args.test_start),
        test_end=parse_utc_datetime(args.test_end),
    )
    grid = ParameterGrid(
        fast_windows=_parse_int_tuple(args.fast_windows),
        slow_windows=_parse_int_tuple(args.slow_windows),
        fee_rates=_parse_decimal_tuple(args.fee_rates) if args.fee_rates else (base_config.fee_rate,),
        slippage_bps_values=_parse_decimal_tuple(args.slippage_bps)
        if args.slippage_bps
        else (base_config.slippage_bps,),
        min_trend_strength_values=_parse_decimal_tuple(args.min_trend_strengths),
        max_volatility_values=_parse_optional_decimal_tuple(args.max_volatility),
        lookback_windows=_parse_int_tuple(args.lookback_windows) if args.lookback_windows else None,
        top_n_values=_parse_int_tuple(args.rotation_top_n_values)
        if args.rotation_top_n_values
        else None,
        min_momentum_values=_parse_decimal_tuple(args.min_momentum),
    )
    selection_policy = _selection_policy_from_args(args)

    code_version = _git_version()
    with SQLiteCandleRepository(Path(args.db)) as repository:
        service = MarketDataService(repository)
        engine = BacktestEngine(service, code_version=code_version)
        runner = TrainTestValidationRunner(engine, code_version=code_version)
        result = runner.run(
            base_config=base_config,
            grid=grid,
            split=split,
            experiment_id=args.experiment_id,
            selection_policy=selection_policy,
        )

    json_path = write_train_test_validation_json(result, Path(args.output))
    csv_path = write_train_test_validation_csv(result, Path(args.summary_csv)) if args.summary_csv else None

    best_test = result.best_test_run
    print(
        f"experiment={result.experiment_id} strategy={result.strategy_id} "
        f"runs={len(result.runs)} output={json_path}"
        + (f" csv={csv_path}" if csv_path is not None else "")
    )
    print(
        f"best_test run_id={best_test.run_id} "
        f"test_return={decimal_to_str(_decimal(best_test.test_metrics['total_return']))} "
        f"test_drawdown={decimal_to_str(_decimal(best_test.test_metrics['max_drawdown']))}"
    )
    for run in result.runs[: args.top_n]:
        print(
            f"rank={run.rank} run_id={run.run_id} "
            f"train_return={decimal_to_str(_decimal(run.train_metrics['total_return']))} "
            f"test_return={decimal_to_str(_decimal(run.test_metrics['total_return']))} "
            f"return_gap={decimal_to_str(run.return_gap)} "
            f"test_drawdown={decimal_to_str(_decimal(run.test_metrics['max_drawdown']))} "
            f"test_positive={run.test_positive}"
        )


def _decimal(value: Decimal | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(value)


if __name__ == "__main__":
    main()
