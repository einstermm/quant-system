"""Run Phase 6.9 initial closure and position lifecycle planning."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.live_initial_closure import (
    build_initial_closure_report,
    load_json,
    write_report_json,
    write_report_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6.9 initial closure review.")
    parser.add_argument("--post-trade-report-json", required=True, help="Phase 6.7 report JSON")
    parser.add_argument("--cooldown-review-json", required=True, help="Phase 6.8 review JSON")
    parser.add_argument("--session-id", required=True, help="Phase 6.9 session id")
    parser.add_argument("--output-json", required=True, help="Output JSON path")
    parser.add_argument("--output-md", required=True, help="Output Markdown path")
    args = parser.parse_args()

    post_trade_path = Path(args.post_trade_report_json)
    cooldown_path = Path(args.cooldown_review_json)
    artifacts = {
        "post_trade_report_json": str(post_trade_path),
        "cooldown_review_json": str(cooldown_path),
        "initial_closure_json": args.output_json,
        "initial_closure_md": args.output_md,
    }
    report = build_initial_closure_report(
        post_trade_report=load_json(post_trade_path),
        cooldown_review=load_json(cooldown_path),
        session_id=args.session_id,
        artifacts=artifacts,
    )
    json_path = write_report_json(report, Path(args.output_json))
    md_path = write_report_markdown(report, Path(args.output_md))
    print(
        f"status={report.status} next_live_decision={report.next_live_decision['decision']} "
        f"output={json_path} markdown={md_path}"
    )
    if report.status == "initial_closure_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
