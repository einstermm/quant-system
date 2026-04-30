"""Generate an external alert outbox payload."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.observability.external_alert_outbox import build_external_alert_outbox


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate external alert outbox payload.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--channel", default="ops_webhook")
    parser.add_argument("--severity", default="WARN")
    parser.add_argument("--title", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--dispatch-enabled", action="store_true")
    args = parser.parse_args()

    result = build_external_alert_outbox(
        output_dir=Path(args.output_dir),
        channel=args.channel,
        severity=args.severity,
        title=args.title,
        message=args.message,
        dispatch_enabled=args.dispatch_enabled,
    )
    print(f"status={result.status} severity={result.severity} title={result.title}")
    if result.status == "external_alert_dispatch_blocked_requires_worker":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
