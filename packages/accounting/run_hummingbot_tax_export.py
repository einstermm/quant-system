"""Export Hummingbot filled trades for tax/reporting validation."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.accounting.tax_export import (
    build_trade_tax_export_rows_from_hummingbot_events,
    build_trade_tax_export_summary,
    write_trade_tax_export_csv,
    write_trade_tax_export_summary_json,
    write_trade_tax_export_summary_markdown,
)
from packages.adapters.hummingbot.sandbox_reconciliation import load_event_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Hummingbot filled trades for tax/reporting validation.")
    parser.add_argument("--events-jsonl", required=True, help="Hummingbot event JSONL")
    parser.add_argument("--account-id", required=True, help="Account id label for export rows")
    parser.add_argument("--strategy-id", required=True, help="Strategy id")
    parser.add_argument("--quote-asset", default="USDT")
    parser.add_argument("--cad-fx-rate", required=True, help="Quote-to-CAD FX rate")
    parser.add_argument("--fx-source", required=True, help="FX rate source label")
    parser.add_argument("--output-csv", required=True, help="Output CSV path")
    parser.add_argument("--summary-json", required=True, help="Output summary JSON path")
    parser.add_argument("--summary-md", required=True, help="Output summary Markdown path")
    args = parser.parse_args()

    events_path = Path(args.events_jsonl)
    csv_path = Path(args.output_csv)
    summary_json_path = Path(args.summary_json)
    summary_md_path = Path(args.summary_md)
    rows = build_trade_tax_export_rows_from_hummingbot_events(
        events=load_event_jsonl(events_path),
        account_id=args.account_id,
        strategy_id=args.strategy_id,
        cad_fx_rate=Decimal(args.cad_fx_rate),
        fx_source=args.fx_source,
    )
    write_trade_tax_export_csv(rows, csv_path)
    summary = build_trade_tax_export_summary(
        rows=rows,
        strategy_id=args.strategy_id,
        account_id=args.account_id,
        source="hummingbot_export",
        quote_asset=args.quote_asset,
        cad_fx_rate=Decimal(args.cad_fx_rate),
        fx_source=args.fx_source,
        artifacts={
            "events_jsonl": str(events_path),
            "tax_export_csv": str(csv_path),
        },
    )
    write_trade_tax_export_summary_json(summary, summary_json_path)
    write_trade_tax_export_summary_markdown(summary, summary_md_path)
    print(
        f"status={summary.status} rows={summary.row_count} "
        f"csv={csv_path} summary={summary_json_path}"
    )
    if summary.status == "tax_export_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
