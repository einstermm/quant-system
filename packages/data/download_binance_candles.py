"""Download Binance spot candles into the local CSV format."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.data.binance_klines import (
    BinanceSpotKlineClient,
    BinanceSpotKlineConfig,
    expected_candle_count,
)
from packages.data.csv_candle_source import parse_utc_datetime, write_candles_csv
from packages.data.data_quality import build_candle_quality_report, write_quality_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Binance spot klines to CSV.")
    parser.add_argument("--symbols", nargs="+", required=True, help="System trading pairs, e.g. BTC-USDT")
    parser.add_argument("--interval", required=True, help="Kline interval, e.g. 4h")
    parser.add_argument("--start", required=True, help="Inclusive UTC start, e.g. 2025-01-01")
    parser.add_argument("--end", required=True, help="Exclusive UTC end, e.g. 2026-01-01")
    parser.add_argument("--output", required=True, help="Output candle CSV path")
    parser.add_argument("--quality-report", required=True, help="Output quality report JSON path")
    parser.add_argument("--base-url", default="https://api.binance.com", help="Binance API base URL")
    parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS certificate verification. Use only for public data behind local CA interception.",
    )
    args = parser.parse_args()

    start = parse_utc_datetime(args.start)
    end = parse_utc_datetime(args.end)
    client = BinanceSpotKlineClient(
        BinanceSpotKlineConfig(
            base_url=args.base_url,
            verify_tls=not args.insecure_skip_tls_verify,
        )
    )

    candles = []
    expected_per_symbol = expected_candle_count(start=start, end=end, interval=args.interval)
    for symbol in args.symbols:
        symbol_candles = client.fetch_candles(
            trading_pair=symbol,
            interval=args.interval,
            start=start,
            end=end,
        )
        candles.extend(symbol_candles)
        print(f"downloaded {len(symbol_candles)}/{expected_per_symbol} candles for {symbol}")

    candle_path = write_candles_csv(candles, Path(args.output))
    report = build_candle_quality_report(candles, expected_start=start, expected_end=end)
    report_path = write_quality_report(report, Path(args.quality_report))

    print(
        f"wrote {len(candles)} candles to {candle_path}; "
        f"quality_ok={report.ok}; report={report_path}"
    )


if __name__ == "__main__":
    main()
