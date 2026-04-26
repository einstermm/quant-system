"""Run walk-forward parameter validation."""

from __future__ import annotations

import argparse
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
from packages.backtesting.walk_forward import (
    WalkForwardRunner,
    build_walk_forward_folds,
    write_walk_forward_csv,
    write_walk_forward_json,
)
from packages.data.csv_candle_source import parse_utc_datetime
from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run walk-forward parameter validation.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--summary-csv", help="Optional output CSV summary path")
    parser.add_argument("--experiment-id", default="crypto_momentum_v1_phase_3_3", help="Experiment id")
    parser.add_argument("--start", default="2023-01-01", help="Walk-forward start")
    parser.add_argument("--end", default="2026-01-01", help="Walk-forward end")
    parser.add_argument("--train-months", type=int, default=6, help="Training window length in months")
    parser.add_argument("--test-months", type=int, default=3, help="Test window length in months")
    parser.add_argument("--step-months", type=int, default=3, help="Fold step size in months")
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
    parser.add_argument("--top-n", type=int, default=20, help="Number of folds to print")
    args = parser.parse_args()

    base_config = load_backtest_config(Path(args.strategy_dir))
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
    folds = build_walk_forward_folds(
        start=parse_utc_datetime(args.start),
        end=parse_utc_datetime(args.end),
        train_months=args.train_months,
        test_months=args.test_months,
        step_months=args.step_months,
    )

    code_version = _git_version()
    with SQLiteCandleRepository(Path(args.db)) as repository:
        service = MarketDataService(repository)
        engine = BacktestEngine(service, code_version=code_version)
        runner = WalkForwardRunner(engine, code_version=code_version)
        result = runner.run(
            base_config=base_config,
            grid=grid,
            folds=folds,
            experiment_id=args.experiment_id,
            selection_policy=selection_policy,
        )

    json_path = write_walk_forward_json(result, Path(args.output))
    csv_path = write_walk_forward_csv(result, Path(args.summary_csv)) if args.summary_csv else None
    summary = result.summary()

    print(
        f"experiment={result.experiment_id} strategy={result.strategy_id} "
        f"folds={summary['folds']} selected_positive_folds={summary['selected_positive_folds']} "
        f"avg_selected_test_return={summary['average_selected_test_return']} "
        f"median_selected_test_return={summary['median_selected_test_return']} "
        f"worst_selected_test_return={summary['worst_selected_test_return']} "
        f"worst_selected_test_drawdown={summary['worst_selected_test_drawdown']} "
        f"worst_selected_test_tail_loss={summary['worst_selected_test_tail_loss']} "
        f"output={json_path}"
        + (f" csv={csv_path}" if csv_path is not None else "")
    )
    for fold_result in result.folds[: args.top_n]:
        selected = fold_result.selected_run
        print(
            f"fold={fold_result.fold.fold_id} selected={selected.run_id} "
            f"train_return={decimal_to_str(selected.train_metrics['total_return'])} "
            f"test_return={decimal_to_str(selected.test_metrics['total_return'])} "
            f"test_drawdown={decimal_to_str(selected.test_metrics['max_drawdown'])} "
            f"test_positive={selected.test_positive}"
        )


if __name__ == "__main__":
    main()
