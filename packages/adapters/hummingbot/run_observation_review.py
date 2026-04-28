"""Run Phase 5.8 Hummingbot paper observation-window review."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.adapters.hummingbot.observation_review import (
    HummingbotObservationThresholds,
    build_hummingbot_observation_review,
    load_acceptance_reconciliation,
    load_json,
    write_observation_review_json,
    write_observation_review_markdown,
)
from packages.adapters.hummingbot.sandbox_reconciliation import load_event_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a Hummingbot paper export before a longer observation window.")
    parser.add_argument("--acceptance-json", required=True, help="Phase 5.4 acceptance JSON from a real Hummingbot export")
    parser.add_argument("--events-jsonl", required=True, help="Hummingbot paper event JSONL")
    parser.add_argument("--session-id", required=True, help="Observation review session id")
    parser.add_argument("--target-window-hours", default="2", help="Target duration for the next observation window")
    parser.add_argument("--allow-warnings", action="store_true", help="Allow accepted upstream warning decisions")
    parser.add_argument("--output-json", required=True, help="Output review JSON")
    parser.add_argument("--output-md", required=True, help="Output review Markdown")
    args = parser.parse_args()

    acceptance_path = Path(args.acceptance_json)
    events_path = Path(args.events_jsonl)
    acceptance = load_json(acceptance_path)
    reconciliation = load_acceptance_reconciliation(acceptance)
    result = build_hummingbot_observation_review(
        acceptance_report=acceptance,
        reconciliation_report=reconciliation,
        events=load_event_jsonl(events_path),
        session_id=args.session_id,
        allow_warnings=args.allow_warnings,
        thresholds=HummingbotObservationThresholds(
            target_window_hours=Decimal(args.target_window_hours),
        ),
        artifacts={
            "acceptance_json": str(acceptance_path),
            "events_jsonl": str(events_path),
            "reconciliation_json": str(acceptance.get("artifacts", {}).get("reconciliation_json", "")),
        },
    )
    json_path = write_observation_review_json(result, Path(args.output_json))
    md_path = write_observation_review_markdown(result, Path(args.output_md))
    print(
        f"decision={result.decision} session={result.session_id} "
        f"events={result.event_window['event_count']} output={json_path} markdown={md_path}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
