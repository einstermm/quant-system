"""Run live position exit plan generation."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.adapters.hummingbot.live_position_exit_plan import build_live_position_exit_plan
from packages.adapters.hummingbot.live_position_exit_plan import load_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a non-executing live position exit plan.")
    parser.add_argument("--initial-closure-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--max-exit-notional", default="50")
    parser.add_argument("--exit-reason", default="operator_requested_exit_review")
    args = parser.parse_args()

    plan = build_live_position_exit_plan(
        initial_closure=load_json(args.initial_closure_json),
        output_dir=Path(args.output_dir),
        session_id=args.session_id,
        max_exit_notional=Decimal(args.max_exit_notional),
        exit_reason=args.exit_reason,
    )
    print(f"status={plan.status} pair={plan.trading_pair} qty={plan.quantity} output_dir={args.output_dir}")
    if plan.status == "live_position_exit_plan_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
