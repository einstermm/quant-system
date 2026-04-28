"""Generate a Phase 4.3 paper observation review."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.reporting.paper_observation_review import (
    PaperObservationReviewThresholds,
    build_paper_observation_review,
    load_json,
    load_jsonl,
    write_review_json,
    write_review_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a 24h paper observation run.")
    parser.add_argument("--observation-jsonl", required=True, help="Paper observation JSONL")
    parser.add_argument("--ledger-jsonl", required=True, help="Paper order ledger JSONL")
    parser.add_argument("--readiness-json", help="Prior paper readiness JSON")
    parser.add_argument("--initial-equity", required=True, help="Initial paper equity")
    parser.add_argument("--output-json", required=True, help="Output review JSON")
    parser.add_argument("--output-md", required=True, help="Output review Markdown")
    parser.add_argument("--min-duration-hours", default="23.5", help="Minimum observation duration")
    parser.add_argument("--min-ok-cycle-ratio", default="0.99", help="Minimum OK cycle ratio")
    parser.add_argument("--max-drawdown", default="0.02", help="Paper drawdown warning threshold")
    args = parser.parse_args()

    thresholds = PaperObservationReviewThresholds(
        min_duration_hours=Decimal(args.min_duration_hours),
        min_ok_cycle_ratio=Decimal(args.min_ok_cycle_ratio),
        max_drawdown=Decimal(args.max_drawdown),
    )
    review = build_paper_observation_review(
        observation_records=load_jsonl(Path(args.observation_jsonl)),
        ledger_records=load_jsonl(Path(args.ledger_jsonl)),
        readiness_payload=load_json(Path(args.readiness_json)) if args.readiness_json else None,
        initial_equity=Decimal(args.initial_equity),
        thresholds=thresholds,
    )
    json_path = write_review_json(review, Path(args.output_json))
    md_path = write_review_markdown(review, Path(args.output_md))
    print(
        f"strategy={review.strategy_id} decision={review.decision} "
        f"alerts={len(review.alerts)} output={json_path} markdown={md_path}"
    )


if __name__ == "__main__":
    main()
