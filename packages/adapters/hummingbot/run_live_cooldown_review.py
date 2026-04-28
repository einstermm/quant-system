"""Run Phase 6.8 live cooldown review."""

from __future__ import annotations

import argparse
import subprocess
from decimal import Decimal
from pathlib import Path

from packages.adapters.hummingbot.live_cooldown_review import (
    build_live_cooldown_review,
    load_json,
    write_review_json,
    write_review_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6.8 live cooldown review.")
    parser.add_argument("--post-trade-report-json", required=True, help="Phase 6.7 report JSON")
    parser.add_argument("--event-jsonl", required=True, help="Phase 6.6 live event JSONL")
    parser.add_argument("--runner-config-yml", required=True, help="Installed Phase 6.6 config")
    parser.add_argument("--manual-open-orders-check-json", help="Manual open orders check JSON")
    parser.add_argument("--session-id", required=True, help="Phase 6.8 session id")
    parser.add_argument("--minimum-cooldown-hours", default="24", help="Minimum cooldown window")
    parser.add_argument("--runner-container", default="quant-phase-6-6-live-one-batch-low-funds-50")
    parser.add_argument("--hummingbot-container", default="hummingbot")
    parser.add_argument("--output-json", required=True, help="Output JSON path")
    parser.add_argument("--output-md", required=True, help="Output Markdown path")
    args = parser.parse_args()

    post_trade_path = Path(args.post_trade_report_json)
    event_path = Path(args.event_jsonl)
    runner_config_path = Path(args.runner_config_yml)
    manual_check_path = (
        Path(args.manual_open_orders_check_json)
        if args.manual_open_orders_check_json
        else None
    )
    artifacts = {
        "post_trade_report_json": str(post_trade_path),
        "event_jsonl": str(event_path),
        "runner_config_yml": str(runner_config_path),
        "cooldown_review_json": args.output_json,
        "cooldown_review_md": args.output_md,
    }
    if manual_check_path is not None:
        artifacts["manual_open_orders_check_json"] = str(manual_check_path)
    review = build_live_cooldown_review(
        post_trade_report=load_json(post_trade_path),
        event_jsonl=event_path,
        runner_config_yml=runner_config_path,
        session_id=args.session_id,
        minimum_cooldown_hours=Decimal(args.minimum_cooldown_hours),
        manual_open_orders_check=load_json(manual_check_path) if manual_check_path else None,
        runner_container_status=_container_status(args.runner_container),
        hummingbot_container_status=_container_status(args.hummingbot_container),
        artifacts=artifacts,
    )
    json_path = write_review_json(review, Path(args.output_json))
    md_path = write_review_markdown(review, Path(args.output_md))
    print(
        f"status={review.status} cooldown_elapsed={review.cooldown_window['cooldown_elapsed']} "
        f"output={json_path} markdown={md_path}"
    )
    if review.status == "live_cooldown_blocked":
        raise SystemExit(1)


def _container_status(container_name: str) -> str:
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
