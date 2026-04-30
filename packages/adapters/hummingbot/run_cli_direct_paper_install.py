"""Install generated Hummingbot CLI direct paper handoff files."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.cli_direct_paper_install import install_cli_direct_paper_files
from packages.adapters.hummingbot.cli_direct_paper_install import load_handoff


def main() -> None:
    parser = argparse.ArgumentParser(description="Install generated Hummingbot CLI direct paper files.")
    parser.add_argument("--handoff-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--hummingbot-root", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--clean-event-log", action="store_true")
    args = parser.parse_args()

    result = install_cli_direct_paper_files(
        handoff=load_handoff(args.handoff_json),
        handoff_json=Path(args.handoff_json),
        output_dir=Path(args.output_dir),
        source_root=Path(args.source_root),
        session_id=args.session_id,
        hummingbot_root=Path(args.hummingbot_root),
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        clean_event_log=args.clean_event_log,
    )
    print(
        f"decision={result.decision} session={result.session_id} "
        f"hummingbot_root={result.hummingbot_root} output_dir={args.output_dir}"
    )
    if result.decision == "cli_direct_paper_install_blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
