"""Run a strategy backtest from SQLite market data."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import load_backtest_config
from packages.backtesting.engine import BacktestEngine
from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local SQLite-backed strategy backtest.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--output", required=True, help="Output JSON result path")
    parser.add_argument("--initial-equity", help="Optional initial equity override")
    args = parser.parse_args()

    config = load_backtest_config(Path(args.strategy_dir))
    if args.initial_equity:
        config = replace(config, initial_equity=Decimal(args.initial_equity))
    with SQLiteCandleRepository(Path(args.db)) as repository:
        service = MarketDataService(repository)
        engine = BacktestEngine(service, code_version=_git_version())
        result = engine.run(config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    metrics = result.metrics
    print(
        f"strategy={result.strategy_id} "
        f"total_return={metrics['total_return']} "
        f"max_drawdown={metrics['max_drawdown']} "
        f"turnover={metrics['turnover']} "
        f"fees={metrics['total_fees']} "
        f"trades={metrics['trade_count']} "
        f"output={output_path}"
    )


def _git_version() -> str:
    try:
        rev_parse = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"

    version = rev_parse.stdout.strip() or "unknown"
    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return version
    if status.stdout.strip():
        return f"{version}-dirty"
    return version


if __name__ == "__main__":
    main()
