"""Command-line importer for local candle CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.data.candle_repository import InMemoryCandleRepository
from packages.data.csv_candle_source import read_candles_csv
from packages.data.data_quality import build_candle_quality_report, write_quality_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local candle CSV data and write a quality report.")
    parser.add_argument("--input", required=True, help="CSV file path")
    parser.add_argument("--quality-report", required=True, help="Output JSON report path")
    args = parser.parse_args()

    result = read_candles_csv(Path(args.input))
    repository = InMemoryCandleRepository()
    repository.add_many(result.candles)

    report = build_candle_quality_report(result.candles)
    output_path = write_quality_report(report, args.quality_report)

    print(
        "imported "
        f"{len(result.candles)} candles across {report.groups_checked} groups; "
        f"quality_ok={report.ok}; report={output_path}"
    )


if __name__ == "__main__":
    main()
