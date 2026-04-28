"""Run Hummingbot sandbox event reconciliation."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.adapters.hummingbot.sandbox import load_json
from packages.adapters.hummingbot.sandbox_reconciliation import (
    SandboxReconciliationThresholds,
    build_sandbox_reconciliation,
    load_event_jsonl,
    replay_sandbox_events_from_manifest,
    write_events_jsonl,
    write_reconciliation_json,
    write_reconciliation_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile Hummingbot sandbox events.")
    parser.add_argument("--manifest-json", required=True, help="Phase 5 Hummingbot sandbox manifest JSON")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--events-jsonl", help="Hummingbot sandbox event JSONL export")
    source.add_argument("--replay-from-manifest", action="store_true", help="Generate replay events from the manifest")
    parser.add_argument("--output-events-jsonl", help="Write normalized/replay event JSONL")
    parser.add_argument("--output-json", required=True, help="Output reconciliation JSON")
    parser.add_argument("--output-md", required=True, help="Output reconciliation Markdown")
    parser.add_argument("--starting-quote-balance", help="Starting quote balance for balance reconciliation")
    parser.add_argument("--quote-asset", default="USDT", help="Quote asset used for cash balance reconciliation")
    parser.add_argument("--amount-tolerance", default="0.00000001", help="Allowed fill amount difference")
    parser.add_argument("--price-warning-bps", default="50", help="Fill price warning threshold in bps")
    parser.add_argument("--fee-tolerance", default="0.000001", help="Allowed fee difference")
    parser.add_argument("--balance-tolerance", default="0.000001", help="Allowed balance difference")
    parser.add_argument(
        "--no-require-balance-event",
        action="store_true",
        help="Do not block if Hummingbot balance events are missing",
    )
    args = parser.parse_args()

    manifest = load_json(Path(args.manifest_json))
    starting_quote_balance = (
        Decimal(args.starting_quote_balance) if args.starting_quote_balance is not None else None
    )
    if args.replay_from_manifest:
        events = replay_sandbox_events_from_manifest(
            manifest=manifest,
            starting_quote_balance=starting_quote_balance,
            quote_asset=args.quote_asset,
        )
    else:
        events = load_event_jsonl(Path(args.events_jsonl))

    if args.output_events_jsonl:
        write_events_jsonl(events, Path(args.output_events_jsonl))

    result = build_sandbox_reconciliation(
        manifest=manifest,
        events=events,
        starting_quote_balance=starting_quote_balance,
        quote_asset=args.quote_asset,
        thresholds=SandboxReconciliationThresholds(
            amount_tolerance=Decimal(args.amount_tolerance),
            price_warning_bps=Decimal(args.price_warning_bps),
            fee_tolerance=Decimal(args.fee_tolerance),
            balance_tolerance=Decimal(args.balance_tolerance),
            require_balance_event=not args.no_require_balance_event,
        ),
    )
    json_path = write_reconciliation_json(result, Path(args.output_json))
    md_path = write_reconciliation_markdown(result, Path(args.output_md))
    print(
        f"decision={result.decision} events={sum(result.event_counts.values())} "
        f"orders={result.order_checks['expected_orders']} output={json_path} markdown={md_path}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
