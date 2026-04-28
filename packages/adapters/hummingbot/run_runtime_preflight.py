"""Run Phase 5.5 local Hummingbot runtime preflight."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.runtime_preflight import (
    build_runtime_preflight,
    write_runtime_preflight_json,
    write_runtime_preflight_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local Hummingbot runtime mounts before sandbox startup.")
    parser.add_argument("--scan-root", action="append", required=True, help="Hummingbot mount root to scan")
    parser.add_argument("--session-id", required=True, help="Runtime preflight session id")
    parser.add_argument("--expected-connector", default="binance_paper_trade")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    result = build_runtime_preflight(
        scan_roots=tuple(Path(root) for root in args.scan_root),
        session_id=args.session_id,
        expected_connector=args.expected_connector,
    )
    write_runtime_preflight_json(result, args.output_json)
    write_runtime_preflight_markdown(result, args.output_md)
    print(
        f"decision={result.decision} session={result.session_id} "
        f"connectors={len(result.connector_configs)} output_json={args.output_json}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
