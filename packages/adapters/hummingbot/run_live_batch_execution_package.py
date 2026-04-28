"""Run Phase 6.5 candidate live batch execution package generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.live_batch_execution_package import (
    build_live_batch_execution_package,
    load_json,
    load_json_list,
    load_risk_config,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 6.5 candidate live batch package.")
    parser.add_argument("--activation-plan-json", required=True)
    parser.add_argument("--market-data-refresh-json", required=True)
    parser.add_argument("--live-risk-yml", required=True)
    parser.add_argument("--strategy-dir", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--allowed-pair", action="append", required=True)
    args = parser.parse_args()

    package = build_live_batch_execution_package(
        activation_plan=load_json(args.activation_plan_json),
        market_data_refresh=load_json_list(args.market_data_refresh_json),
        live_risk_config=load_risk_config(args.live_risk_yml),
        strategy_dir=Path(args.strategy_dir),
        db_path=Path(args.db),
        output_dir=Path(args.output_dir),
        session_id=args.session_id,
        allowed_pairs=tuple(args.allowed_pair),
    )
    print(
        f"decision={package.decision} session={package.session_id} "
        f"orders={len(package.candidate_orders)} output_dir={args.output_dir}"
    )
    if package.decision == "live_batch_execution_package_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
