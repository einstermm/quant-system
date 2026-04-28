"""Generate a Hummingbot daily report from an event export."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.sandbox_reconciliation import load_event_jsonl
from packages.reporting.daily_report import (
    build_hummingbot_daily_report,
    load_json,
    write_hummingbot_daily_report_json,
    write_hummingbot_daily_report_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Hummingbot daily report.")
    parser.add_argument("--events-jsonl", required=True, help="Hummingbot event JSONL")
    parser.add_argument("--observation-review-json", required=True, help="Observation review JSON")
    parser.add_argument("--session-id", required=True, help="Daily report session id")
    parser.add_argument("--strategy-id", required=True, help="Strategy id")
    parser.add_argument("--quote-asset", default="USDT")
    parser.add_argument("--output-json", required=True, help="Output JSON path")
    parser.add_argument("--output-md", required=True, help="Output Markdown path")
    args = parser.parse_args()

    events_path = Path(args.events_jsonl)
    review_path = Path(args.observation_review_json)
    report = build_hummingbot_daily_report(
        events=load_event_jsonl(events_path),
        observation_review=load_json(review_path),
        session_id=args.session_id,
        strategy_id=args.strategy_id,
        quote_asset=args.quote_asset,
        artifacts={
            "events_jsonl": str(events_path),
            "observation_review_json": str(review_path),
        },
    )
    json_path = write_hummingbot_daily_report_json(report, Path(args.output_json))
    md_path = write_hummingbot_daily_report_markdown(report, Path(args.output_md))
    print(
        f"status={report.status} session={report.session_id} "
        f"events={report.event_window['event_count']} output={json_path} markdown={md_path}"
    )
    if report.status == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
