"""Run Phase 5.7 direct Hummingbot CLI paper handoff generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.cli_direct_paper_handoff import (
    build_cli_direct_paper_handoff,
    load_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a direct Hummingbot CLI paper-order script.")
    parser.add_argument("--manifest-json", required=True)
    parser.add_argument("--runtime-preflight-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--hummingbot-root", required=True)
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--event-log-path", default=None)
    parser.add_argument("--script-config-name", default=None)
    parser.add_argument("--observation-min-runtime-seconds", type=int, default=0)
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=60)
    parser.add_argument("--balance-snapshot-interval-seconds", type=int, default=300)
    args = parser.parse_args()

    kwargs = {}
    if args.event_log_path:
        kwargs["event_log_path"] = args.event_log_path
    if args.script_config_name:
        kwargs["script_config_name"] = args.script_config_name

    result = build_cli_direct_paper_handoff(
        manifest=load_json(args.manifest_json),
        runtime_preflight=load_json(args.runtime_preflight_json),
        output_dir=Path(args.output_dir),
        session_id=args.session_id,
        hummingbot_root=Path(args.hummingbot_root),
        allow_warnings=args.allow_warnings,
        observation_min_runtime_seconds=args.observation_min_runtime_seconds,
        heartbeat_interval_seconds=args.heartbeat_interval_seconds,
        balance_snapshot_interval_seconds=args.balance_snapshot_interval_seconds,
        **kwargs,
    )
    print(
        f"decision={result.decision} session={result.session_id} "
        f"script_config={result.script_config_name} output_dir={result.output_dir}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
