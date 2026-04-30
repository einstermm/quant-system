"""Collect Hummingbot paper event JSONL into a web job directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.paper_event_collection import collect_paper_events
from packages.adapters.hummingbot.paper_session_control import SESSION_STATE_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Hummingbot paper events for web acceptance.")
    parser.add_argument("--state-json", default=str(SESSION_STATE_PATH))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--source-path", default="auto_from_session_state")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--max-lines", type=int, default=50000)
    args = parser.parse_args()

    result = collect_paper_events(
        state_path=Path(args.state_json),
        output_dir=Path(args.output_dir),
        source_path=args.source_path,
        source_root=Path(args.source_root),
        session_id=args.session_id,
        max_lines=args.max_lines,
    )
    print(
        f"decision={result.decision} session={result.session_id} "
        f"events={result.summary.get('event_count')} output={result.events_jsonl}"
    )
    if result.decision == "paper_event_collection_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
