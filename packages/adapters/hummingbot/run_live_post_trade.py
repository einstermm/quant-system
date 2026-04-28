"""Run Phase 6.7 live post-trade reconciliation and exports."""

from __future__ import annotations

import argparse
import subprocess
from decimal import Decimal
from pathlib import Path

from packages.adapters.hummingbot.live_post_trade import (
    build_live_post_trade_report,
    load_json,
    write_daily_report_json,
    write_daily_report_markdown,
    write_report_json,
    write_report_markdown,
    write_tax_summary_json,
    write_tax_summary_markdown,
    write_trade_tax_csv,
    write_trades_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6.7 live post-trade reconciliation.")
    parser.add_argument("--event-jsonl", required=True, help="Phase 6.6 live runner event JSONL")
    parser.add_argument(
        "--sqlite-db",
        required=True,
        help="Hummingbot SQLite DB for the live session",
    )
    parser.add_argument("--log-file", required=True, help="Hummingbot live session log file")
    parser.add_argument(
        "--candidate-package-json",
        required=True,
        help="Phase 6.5 candidate package JSON",
    )
    parser.add_argument(
        "--runner-package-json",
        required=True,
        help="Phase 6.6 runner package JSON",
    )
    parser.add_argument("--session-id", required=True, help="Phase 6.7 session id")
    parser.add_argument("--account-id", required=True, help="Account id label for reporting")
    parser.add_argument("--strategy-id", required=True, help="Strategy id")
    parser.add_argument("--cad-fx-rate", required=True, help="Validation CAD FX rate")
    parser.add_argument("--fx-source", required=True, help="FX source label")
    parser.add_argument("--runner-container", default="", help="Optional runner container name")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    report_json = output_dir / "post_trade_report.json"
    report_md = output_dir / "post_trade_report.md"
    daily_report_json = output_dir / "daily_report.json"
    daily_report_md = output_dir / "daily_report.md"
    trades_jsonl = output_dir / "normalized_live_trades.jsonl"
    tax_csv = output_dir / "trade_tax_export.csv"
    tax_summary_json = output_dir / "trade_tax_export_summary.json"
    tax_summary_md = output_dir / "trade_tax_export_summary.md"

    artifacts = {
        "event_jsonl": str(Path(args.event_jsonl)),
        "sqlite_db": str(Path(args.sqlite_db)),
        "log_file": str(Path(args.log_file)),
        "candidate_package_json": str(Path(args.candidate_package_json)),
        "runner_package_json": str(Path(args.runner_package_json)),
        "post_trade_report_json": str(report_json),
        "post_trade_report_md": str(report_md),
        "daily_report_json": str(daily_report_json),
        "daily_report_md": str(daily_report_md),
        "normalized_live_trades_jsonl": str(trades_jsonl),
        "trade_tax_export_csv": str(tax_csv),
        "trade_tax_export_summary_json": str(tax_summary_json),
        "trade_tax_export_summary_md": str(tax_summary_md),
    }
    report, fills = build_live_post_trade_report(
        event_jsonl=Path(args.event_jsonl),
        sqlite_db=Path(args.sqlite_db),
        log_file=Path(args.log_file),
        candidate_package=load_json(args.candidate_package_json),
        runner_package=load_json(args.runner_package_json),
        session_id=args.session_id,
        account_id=args.account_id,
        strategy_id=args.strategy_id,
        cad_fx_rate=Decimal(args.cad_fx_rate),
        fx_source=args.fx_source,
        runner_container_status=_container_status(args.runner_container),
        artifacts=artifacts,
    )
    write_trades_jsonl(fills, trades_jsonl)
    write_trade_tax_csv(fills, tax_csv)
    write_report_json(report, report_json)
    write_report_markdown(report, report_md)
    write_daily_report_json(report, daily_report_json)
    write_daily_report_markdown(report, daily_report_md)
    write_tax_summary_json(report, tax_summary_json)
    write_tax_summary_markdown(report, tax_summary_md)
    print(
        f"status={report.status} fills={report.order_checks['filled_orders']} "
        f"report={report_json} tax_csv={tax_csv}"
    )
    if report.status == "live_post_trade_blocked":
        raise SystemExit(1)


def _container_status(container_name: str) -> str:
    if not container_name:
        return ""
    completed = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return f"docker_status_unavailable: {completed.stderr.strip()}"
    for line in completed.stdout.splitlines():
        name, _, status = line.partition("\t")
        if name == container_name:
            return status
    return "not_found"


if __name__ == "__main__":
    main()
