"""Prepare Hummingbot sandbox manifest from a Phase 4.3 review."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.sandbox import (
    load_json,
    load_jsonl,
    prepare_hummingbot_sandbox,
    write_manifest,
    write_prepare_result_json,
    write_prepare_result_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a Hummingbot sandbox manifest.")
    parser.add_argument("--review-json", required=True, help="Phase 4.3 observation review JSON")
    parser.add_argument("--ledger-jsonl", required=True, help="Paper order ledger JSONL")
    parser.add_argument("--connector-name", default="binance_paper_trade", help="Hummingbot sandbox connector")
    parser.add_argument(
        "--controller-name",
        default="quant_system_sandbox_order_controller",
        help="Hummingbot controller name for sandbox validation",
    )
    parser.add_argument("--allow-warnings", action="store_true", help="Allow sandbox_ready_with_warnings review")
    parser.add_argument("--manifest-json", required=True, help="Output sandbox manifest JSON")
    parser.add_argument("--report-json", required=True, help="Output preparation report JSON")
    parser.add_argument("--report-md", required=True, help="Output preparation report Markdown")
    args = parser.parse_args()

    result = prepare_hummingbot_sandbox(
        review_payload=load_json(Path(args.review_json)),
        ledger_records=load_jsonl(Path(args.ledger_jsonl)),
        connector_name=args.connector_name,
        controller_name=args.controller_name,
        allow_warnings=args.allow_warnings,
    )
    manifest_path = write_manifest(result.manifest, Path(args.manifest_json))
    json_path = write_prepare_result_json(result, Path(args.report_json))
    md_path = write_prepare_result_markdown(result, Path(args.report_md))
    print(
        f"decision={result.decision} orders={len(result.manifest.get('orders', []))} "
        f"manifest={manifest_path} report={json_path} markdown={md_path}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
