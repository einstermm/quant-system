"""Run Phase 5.6 Hummingbot CLI paper handoff generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.cli_paper_handoff import (
    build_cli_paper_handoff,
    load_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Hummingbot CLI paper-mode handoff files.")
    parser.add_argument("--manifest-json", required=True, help="Phase 5 sandbox manifest JSON")
    parser.add_argument("--runtime-preflight-json", required=True, help="Phase 5.5 runtime preflight JSON")
    parser.add_argument("--output-dir", required=True, help="Output handoff directory")
    parser.add_argument("--session-id", required=True, help="Hummingbot CLI paper session id")
    parser.add_argument("--hummingbot-root", required=True, help="Host Hummingbot root with conf/controllers/scripts/data")
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--event-log-path", default="/home/hummingbot/data/crypto_relative_strength_v1_phase_5_6_hummingbot_events.jsonl")
    args = parser.parse_args()

    result = build_cli_paper_handoff(
        manifest=load_json(args.manifest_json),
        runtime_preflight=load_json(args.runtime_preflight_json),
        output_dir=Path(args.output_dir),
        session_id=args.session_id,
        hummingbot_root=Path(args.hummingbot_root),
        allow_warnings=args.allow_warnings,
        event_log_path=args.event_log_path,
    )
    print(
        f"decision={result.decision} session={result.session_id} "
        f"script_config={result.script_config_name} output_dir={result.output_dir}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
