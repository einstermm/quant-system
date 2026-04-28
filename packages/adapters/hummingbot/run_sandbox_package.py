"""Build a Hummingbot sandbox handoff package."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.adapters.hummingbot.sandbox_package import build_sandbox_package, load_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Hummingbot sandbox handoff package.")
    parser.add_argument("--manifest-json", required=True, help="Phase 5 sandbox manifest JSON")
    parser.add_argument("--session-gate-json", required=True, help="Phase 5.2 sandbox session gate JSON")
    parser.add_argument("--output-dir", required=True, help="Output package directory")
    parser.add_argument("--allow-warnings", action="store_true", help="Allow upstream warning decisions")
    args = parser.parse_args()

    result = build_sandbox_package(
        manifest=load_json(Path(args.manifest_json)),
        session_gate=load_json(Path(args.session_gate_json)),
        output_dir=Path(args.output_dir),
        allow_warnings=args.allow_warnings,
    )
    print(
        f"decision={result.decision} session={result.session_id} "
        f"artifacts={len(result.artifacts)} output_dir={result.output_dir}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
