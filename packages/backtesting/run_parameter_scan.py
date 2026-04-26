"""Run a parameter scan for a local SQLite-backed strategy."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import load_backtest_config
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.parameter_scan import (
    ParameterGrid,
    ParameterScanRunner,
    SelectionPolicy,
    write_parameter_scan_csv,
    write_parameter_scan_json,
)
from packages.backtesting.result import decimal_to_str
from packages.backtesting.run_backtest import _git_version
from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a parameter scan for a local strategy.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--summary-csv", help="Optional output CSV summary path")
    parser.add_argument("--experiment-id", default="crypto_momentum_v1_phase_3_1", help="Experiment id")
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
    parser.add_argument("--selection-min-return", help="Minimum return required by risk_adjusted selection")
    parser.add_argument("--selection-max-drawdown", help="Maximum drawdown allowed by risk_adjusted selection")
    parser.add_argument("--selection-max-turnover", help="Maximum turnover allowed by risk_adjusted selection")
    parser.add_argument("--selection-max-tail-loss", help="Maximum period tail loss allowed by risk_adjusted selection")
    parser.add_argument("--drawdown-penalty", default="1", help="Risk-adjusted drawdown penalty")
    parser.add_argument("--turnover-penalty", default="0.01", help="Risk-adjusted turnover penalty")
    parser.add_argument("--tail-loss-penalty", default="2", help="Risk-adjusted tail loss penalty")
    parser.add_argument("--top-n", type=int, default=5, help="Number of ranked runs to print")
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

    code_version = _git_version()
    with SQLiteCandleRepository(Path(args.db)) as repository:
        service = MarketDataService(repository)
        engine = BacktestEngine(service, code_version=code_version)
        runner = ParameterScanRunner(engine, code_version=code_version)
        scan_result = runner.run(
            base_config=base_config,
            grid=grid,
            experiment_id=args.experiment_id,
            selection_policy=selection_policy,
        )

    json_path = write_parameter_scan_json(scan_result, Path(args.output))
    csv_path = write_parameter_scan_csv(scan_result, Path(args.summary_csv)) if args.summary_csv else None

    print(
        f"experiment={scan_result.experiment_id} strategy={scan_result.strategy_id} "
        f"runs={len(scan_result.runs)} output={json_path}"
        + (f" csv={csv_path}" if csv_path is not None else "")
    )
    for run in scan_result.runs[: args.top_n]:
        metrics = run.metrics
        print(
            f"rank={run.rank} run_id={run.run_id} "
            f"return={decimal_to_str(metrics['total_return'])} "
            f"drawdown={decimal_to_str(metrics['max_drawdown'])} "
            f"turnover={decimal_to_str(metrics['turnover'])} "
            f"trades={metrics['trade_count']}"
        )


def _parse_int_tuple(value: str) -> tuple[int, ...]:
    parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not parsed:
        raise ValueError("expected at least one integer")
    return parsed


def _parse_decimal_tuple(value: str) -> tuple[Decimal, ...]:
    parsed = tuple(Decimal(item.strip()) for item in value.split(",") if item.strip())
    if not parsed:
        raise ValueError("expected at least one decimal")
    return parsed


def _parse_optional_decimal_tuple(value: str) -> tuple[Decimal | None, ...]:
    parsed: list[Decimal | None] = []
    for item in value.split(","):
        normalized = item.strip().lower()
        if not normalized:
            continue
        if normalized in {"none", "null", "off"}:
            parsed.append(None)
        else:
            parsed.append(Decimal(normalized))
    if not parsed:
        raise ValueError("expected at least one decimal or none")
    return tuple(parsed)


def _parse_optional_decimal_arg(value: str | None) -> Decimal | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"", "none", "null", "off"}:
        return None
    return Decimal(normalized)


def _selection_policy_from_args(args: argparse.Namespace) -> SelectionPolicy:
    return SelectionPolicy(
        mode=args.selection_mode,
        min_return=_parse_optional_decimal_arg(args.selection_min_return),
        max_drawdown=_parse_optional_decimal_arg(args.selection_max_drawdown),
        max_turnover=_parse_optional_decimal_arg(args.selection_max_turnover),
        max_tail_loss=_parse_optional_decimal_arg(args.selection_max_tail_loss),
        drawdown_penalty=Decimal(args.drawdown_penalty),
        turnover_penalty=Decimal(args.turnover_penalty),
        tail_loss_penalty=Decimal(args.tail_loss_penalty),
    )


if __name__ == "__main__":
    main()
