"""Run a strategy backtest from SQLite market data."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import RegimeFilterBacktestConfig
from packages.backtesting.config import SignalBacktestConfig
from packages.backtesting.config import load_backtest_config
from packages.backtesting.engine import BacktestEngine
from packages.data.csv_candle_source import parse_utc_datetime
from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local SQLite-backed strategy backtest.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--output", required=True, help="Output JSON result path")
    parser.add_argument("--initial-equity", help="Optional initial equity override")
    parser.add_argument("--start", help="Optional inclusive UTC start override")
    parser.add_argument("--end", help="Optional exclusive UTC end override")
    parser.add_argument("--fee-rate", help="Optional fee rate override")
    parser.add_argument("--slippage-bps", help="Optional slippage bps override")
    parser.add_argument("--fast-window", type=int, help="Optional moving-average fast window override")
    parser.add_argument("--slow-window", type=int, help="Optional moving-average slow window override")
    parser.add_argument("--lookback-window", type=int, help="Optional relative-strength lookback window override")
    parser.add_argument("--top-n", type=int, help="Optional relative-strength rotation top_n override")
    parser.add_argument("--min-momentum", help="Optional relative-strength minimum momentum override")
    parser.add_argument("--min-trend-strength", help="Optional regime filter trend threshold override")
    parser.add_argument("--max-volatility", help="Optional regime filter volatility cap override; use none to disable")
    args = parser.parse_args()

    config = load_backtest_config(Path(args.strategy_dir))
    config = _apply_overrides(
        config,
        initial_equity=args.initial_equity,
        start=args.start,
        end=args.end,
        fee_rate=args.fee_rate,
        slippage_bps=args.slippage_bps,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        lookback_window=args.lookback_window,
        top_n=args.top_n,
        min_momentum=args.min_momentum,
        min_trend_strength=args.min_trend_strength,
        max_volatility=args.max_volatility,
    )
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


def _apply_overrides(
    config,
    *,
    initial_equity: str | None,
    start: str | None,
    end: str | None,
    fee_rate: str | None = None,
    slippage_bps: str | None = None,
    fast_window: int | None = None,
    slow_window: int | None = None,
    lookback_window: int | None = None,
    top_n: int | None = None,
    min_momentum: str | None = None,
    min_trend_strength: str | None = None,
    max_volatility: str | None = None,
):
    if initial_equity:
        config = replace(config, initial_equity=Decimal(initial_equity))
    if start:
        config = replace(config, start=parse_utc_datetime(start))
    if end:
        config = replace(config, end=parse_utc_datetime(end))
    if fee_rate:
        config = replace(config, fee_rate=Decimal(fee_rate))
    if slippage_bps:
        config = replace(config, slippage_bps=Decimal(slippage_bps))

    signal = config.signal
    if any(value is not None for value in (fast_window, slow_window, lookback_window, top_n, min_momentum)):
        signal = SignalBacktestConfig(
            signal_type=signal.signal_type,
            fast_window=fast_window if fast_window is not None else signal.fast_window,
            slow_window=slow_window if slow_window is not None else signal.slow_window,
            lookback_window=lookback_window if lookback_window is not None else signal.lookback_window,
            top_n=top_n if top_n is not None else signal.top_n,
            min_momentum=Decimal(min_momentum) if min_momentum is not None else signal.min_momentum,
        )
        config = replace(config, signal=signal)

    if min_trend_strength is not None or max_volatility is not None:
        trend = Decimal(min_trend_strength) if min_trend_strength is not None else config.regime_filter.min_trend_strength
        volatility = (
            _parse_optional_decimal(max_volatility)
            if max_volatility is not None
            else config.regime_filter.max_volatility
        )
        config = replace(
            config,
            regime_filter=RegimeFilterBacktestConfig(
                enabled=trend > Decimal("0") or volatility is not None,
                min_trend_strength=trend,
                max_volatility=volatility,
                volatility_window=config.regime_filter.volatility_window,
            ),
        )

    if config.start >= config.end:
        raise ValueError("start must be before end")
    if config.signal.fast_window is not None and config.signal.slow_window is not None:
        if config.signal.fast_window >= config.signal.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
    return config


def _parse_optional_decimal(value: str) -> Decimal | None:
    normalized = value.strip().lower()
    if normalized in {"", "none", "null", "off"}:
        return None
    return Decimal(normalized)


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
