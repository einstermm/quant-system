"""Generate or record Hummingbot direct paper session control actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.adapters.hummingbot.paper_session_control import SESSION_STATE_PATH
from packages.adapters.hummingbot.paper_session_control import build_paper_session_control


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate/record Hummingbot direct paper session control.")
    parser.add_argument("--install-report-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--state-json", default=str(SESSION_STATE_PATH))
    parser.add_argument("--mode", required=True, choices=("start_plan", "record_started", "stop_plan", "record_stopped"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--container-name", default="quant-system-hummingbot-paper")
    parser.add_argument("--hummingbot-image", default="hummingbot/hummingbot:latest")
    parser.add_argument("--operator-note", default="")
    args = parser.parse_args()

    install_report = json.loads(Path(args.install_report_json).read_text(encoding="utf-8"))
    result = build_paper_session_control(
        install_report=install_report,
        output_dir=Path(args.output_dir),
        state_path=Path(args.state_json),
        mode=args.mode,
        session_id=args.session_id,
        container_name=args.container_name,
        hummingbot_image=args.hummingbot_image,
        operator_note=args.operator_note,
    )
    print(f"decision={result.decision} mode={result.mode} session={result.session_id} output_dir={args.output_dir}")
    if result.decision == "paper_session_control_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
