"""Load candle CSV files into a SQLite warehouse."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.data.csv_candle_source import read_candles_csv
from packages.data.data_quality import build_candle_quality_report, write_quality_report
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Load local candle CSV data into SQLite.")
    parser.add_argument("--input", required=True, help="Input candle CSV path")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--quality-report", required=True, help="Output quality report JSON path")
    parser.add_argument(
        "--allow-quality-issues",
        action="store_true",
        help="Load data even if quality checks produce issues.",
    )
    args = parser.parse_args()

    result = read_candles_csv(Path(args.input))
    report = build_candle_quality_report(result.candles)
    report_path = write_quality_report(report, Path(args.quality_report))

    if not report.ok and not args.allow_quality_issues:
        raise SystemExit(f"quality report has issues; aborting SQLite load: {report_path}")

    with SQLiteCandleRepository(Path(args.db)) as repository:
        repository.add_many(result.candles)
        total_rows = repository.count()

    print(
        f"loaded {len(result.candles)} candles into {args.db}; "
        f"total_rows={total_rows}; quality_ok={report.ok}; report={report_path}"
    )


if __name__ == "__main__":
    main()
