"""Inspect strategy market data availability from SQLite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository
from packages.data.strategy_data_config import load_strategy_data_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Query SQLite candles required by a strategy config.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory containing config.yml")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text summary")
    parser.add_argument("--output-json", help="Write JSON payload to a file")
    args = parser.parse_args()

    strategy_config = load_strategy_data_config(Path(args.strategy_dir))
    queries = strategy_config.candle_queries()

    with SQLiteCandleRepository(Path(args.db)) as repository:
        service = MarketDataService(repository)
        results = service.load_many(queries)

    payload = {
        "strategy_id": strategy_config.strategy_id,
        "results": [result.summary() for result in results.values()],
    }
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(f"strategy={strategy_config.strategy_id}")
    for result in results.values():
        summary = result.summary()
        print(
            f"{summary['key']} candles={summary['candles']}/{summary['expected']} "
            f"complete={summary['complete']} first={summary['first_timestamp']} "
            f"last={summary['last_timestamp']} quality_ok={summary['quality_ok']}"
        )


if __name__ == "__main__":
    main()
