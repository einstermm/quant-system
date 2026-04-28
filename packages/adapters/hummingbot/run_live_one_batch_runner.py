"""Run Phase 6.6 live one-batch runner package generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.live_one_batch_runner import (
    build_live_one_batch_runner_package,
    load_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 6.6 live one-batch runner.")
    parser.add_argument("--candidate-package-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--hummingbot-root", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--exchange-state-confirmed", action="store_true")
    parser.add_argument("--no-install", action="store_true")
    parser.add_argument("--script-config-name")
    parser.add_argument("--event-log-path")
    args = parser.parse_args()

    kwargs = {}
    if args.script_config_name:
        kwargs["script_config_name"] = args.script_config_name
    if args.event_log_path:
        kwargs["event_log_path"] = args.event_log_path

    package = build_live_one_batch_runner_package(
        candidate_package=load_json(args.candidate_package_json),
        output_dir=Path(args.output_dir),
        hummingbot_root=Path(args.hummingbot_root),
        session_id=args.session_id,
        exchange_state_confirmed=args.exchange_state_confirmed,
        install=not args.no_install,
        **kwargs,
    )
    print(
        f"decision={package.decision} session={package.session_id} "
        f"script_config={package.script_config_name} output_dir={package.output_dir}"
    )
    if package.decision == "live_one_batch_runner_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
