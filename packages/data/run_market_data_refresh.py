"""Refresh strategy public market data into SQLite and write a JSON report."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from packages.core.models import utc_now
from packages.data.binance_klines import BinanceSpotKlineClient, BinanceSpotKlineConfig
from packages.data.market_data_refresh import refresh_binance_spot_candles
from packages.data.sqlite_candle_repository import SQLiteCandleRepository
from packages.data.strategy_data_config import load_strategy_data_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh recent public market data required by a strategy.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory containing config.yml/backtest.yml")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--output-json", required=True, help="Output refresh report JSON")
    parser.add_argument("--refresh-base-url", default="https://api.binance.com", help="Binance public API base URL")
    parser.add_argument("--overlap-bars", type=int, default=2, help="Closed candles to re-fetch per symbol")
    parser.add_argument("--bootstrap-bars", type=int, default=200, help="Bars to fetch when a symbol has no data")
    parser.add_argument("--close-delay-seconds", default="60", help="Delay before treating latest interval boundary as closed")
    parser.add_argument("--insecure-skip-tls-verify", action="store_true", help="Disable TLS verification for public data")
    args = parser.parse_args()

    config = load_strategy_data_config(Path(args.strategy_dir))
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = BinanceSpotKlineClient(
        BinanceSpotKlineConfig(
            base_url=args.refresh_base_url,
            verify_tls=not args.insecure_skip_tls_verify,
        )
    )
    with SQLiteCandleRepository(Path(args.db)) as repository:
        results = refresh_binance_spot_candles(
            repository=repository,
            trading_pairs=config.trading_pairs,
            interval=config.interval,
            now=utc_now(),
            exchange=config.exchange,
            client=client,
            overlap_bars=args.overlap_bars,
            bootstrap_bars=args.bootstrap_bars,
            close_delay_seconds=Decimal(str(args.close_delay_seconds)),
        )

    payload = {
        "strategy_id": config.strategy_id,
        "exchange": config.exchange,
        "interval": config.interval,
        "trading_pairs": list(config.trading_pairs),
        "status": "failed" if any(result.status == "failed" for result in results) else "ok",
        "results": [result.to_dict() for result in results],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"strategy={config.strategy_id} status={payload['status']} "
        f"pairs={len(results)} output={output_path}"
    )
    if payload["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
