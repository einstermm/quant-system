"""Run a local paper trading observation loop."""

from __future__ import annotations

import argparse
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import load_backtest_config
from packages.core.models import utc_now
from packages.data.binance_klines import BinanceSpotKlineClient, BinanceSpotKlineConfig
from packages.data.market_data_refresh import (
    latest_closed_candle_end,
    refresh_binance_spot_candles,
)
from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository
from packages.paper_trading.cycle import PaperTradingCycle
from packages.paper_trading.ledger import PaperLedger
from packages.paper_trading.observation import PaperObservationLoop
from packages.paper_trading.runtime import assert_readiness, load_kill_switch, load_risk_limits


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local paper trading observation loop.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--readiness-json", required=True, help="Paper readiness JSON gate")
    parser.add_argument("--allow-readiness-warnings", action="store_true", help="Allow paper_ready_with_warnings")
    parser.add_argument("--ledger", required=True, help="Paper JSONL ledger path")
    parser.add_argument("--observation-log", required=True, help="Paper observation JSONL path")
    parser.add_argument("--summary-json", required=True, help="Observation summary JSON path")
    parser.add_argument("--report-md", required=True, help="Observation Markdown report path")
    parser.add_argument("--account-id", default="paper-main", help="Paper account id")
    parser.add_argument("--initial-equity", default="2000", help="Initial paper equity")
    parser.add_argument("--kill-switch-file", help="Optional JSON kill switch state")
    parser.add_argument("--cycles", type=int, help="Maximum cycles to run")
    parser.add_argument("--duration-hours", help="Optional maximum runtime in hours")
    parser.add_argument("--interval-seconds", default="60", help="Sleep interval between cycles")
    parser.add_argument(
        "--refresh-market-data",
        action="store_true",
        help="Refresh recent Binance spot klines into SQLite before each cycle",
    )
    parser.add_argument("--refresh-base-url", default="https://api.binance.com", help="Binance API base URL")
    parser.add_argument("--refresh-overlap-bars", type=int, default=2, help="Closed candles to re-fetch per symbol")
    parser.add_argument("--refresh-bootstrap-bars", type=int, default=200, help="Bars to fetch when a symbol has no data")
    parser.add_argument(
        "--refresh-close-delay-seconds",
        default="60",
        help="Delay before treating the latest interval boundary as closed",
    )
    parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS verification for Binance public data requests",
    )
    args = parser.parse_args()

    assert_readiness(Path(args.readiness_json), allow_warnings=args.allow_readiness_warnings)
    strategy_dir = Path(args.strategy_dir)
    config = load_backtest_config(strategy_dir)
    risk_limits = load_risk_limits(strategy_dir / "risk.yml")
    ledger = PaperLedger(Path(args.ledger))
    kill_switch_path = Path(args.kill_switch_file) if args.kill_switch_file else None
    max_runtime_seconds = _duration_hours_to_seconds(args.duration_hours)
    cycles = args.cycles if args.cycles is not None else (None if max_runtime_seconds else 1)

    with SQLiteCandleRepository(Path(args.db)) as repository:
        service = MarketDataService(repository)
        latest_runtime_end = None
        refresh_failed = False
        refresh_client = BinanceSpotKlineClient(
            BinanceSpotKlineConfig(
                base_url=args.refresh_base_url,
                verify_tls=not args.insecure_skip_tls_verify,
            )
        )

        def pre_cycle_hook() -> dict[str, object] | None:
            nonlocal latest_runtime_end, refresh_failed
            if not args.refresh_market_data:
                refresh_failed = False
                return None
            now = utc_now()
            latest_runtime_end = latest_closed_candle_end(
                now=now,
                interval=config.interval,
                close_delay_seconds=Decimal(str(args.refresh_close_delay_seconds)),
            )
            results = refresh_binance_spot_candles(
                repository=repository,
                trading_pairs=config.trading_pairs,
                interval=config.interval,
                now=now,
                exchange=config.exchange,
                client=refresh_client,
                overlap_bars=args.refresh_overlap_bars,
                bootstrap_bars=args.refresh_bootstrap_bars,
                close_delay_seconds=Decimal(str(args.refresh_close_delay_seconds)),
            )
            refresh_failed = any(result.status == "failed" for result in results)
            return {
                "market_data_refresh": [result.to_dict() for result in results],
                "refresh_failed": refresh_failed,
                "runtime_end": latest_runtime_end.isoformat(),
            }

        def cycle_factory() -> PaperTradingCycle:
            runtime_config = config
            if args.refresh_market_data:
                if refresh_failed:
                    raise RuntimeError("market data refresh failed")
                runtime_end = latest_runtime_end or latest_closed_candle_end(
                    now=utc_now(),
                    interval=config.interval,
                    close_delay_seconds=Decimal(str(args.refresh_close_delay_seconds)),
                )
                if runtime_end <= config.start:
                    raise RuntimeError("runtime end must be after config start")
                runtime_config = replace(config, end=runtime_end)
            return PaperTradingCycle(
                market_data_service=service,
                config=runtime_config,
                risk_limits=risk_limits,
                ledger=ledger,
                account_id=args.account_id,
                initial_equity=Decimal(args.initial_equity),
                kill_switch=load_kill_switch(kill_switch_path),
            )

        loop = PaperObservationLoop(
            cycle_factory=cycle_factory,
            observation_log=Path(args.observation_log),
            summary_json=Path(args.summary_json),
            report_md=Path(args.report_md),
            cycles=cycles,
            interval_seconds=Decimal(str(args.interval_seconds)),
            max_runtime_seconds=max_runtime_seconds,
            pre_cycle_hook=pre_cycle_hook,
        )
        summary = loop.run()

    print(
        f"paper_observation status={summary.status} cycles={summary.cycles} "
        f"ok={summary.ok_cycles} failed={summary.failed_cycles} "
        f"orders={summary.routed_orders} approved={summary.approved_orders} "
        f"rejected={summary.rejected_orders} summary={args.summary_json} "
        f"report={args.report_md}"
    )


def _duration_hours_to_seconds(duration_hours: str | None) -> Decimal | None:
    if duration_hours is None:
        return None
    return Decimal(str(duration_hours)) * Decimal("3600")


if __name__ == "__main__":
    main()
