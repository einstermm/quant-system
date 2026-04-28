"""Run the Hummingbot sandbox session preflight gate."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from packages.adapters.hummingbot.sandbox_session import (
    build_sandbox_session_gate,
    load_json,
    write_session_gate_json,
    write_session_gate_markdown,
)

EXCHANGE_KEY_ENV_NAMES = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_SECRET_KEY",
    "EXCHANGE_API_KEY",
    "EXCHANGE_SECRET_KEY",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Hummingbot sandbox session preflight gate.")
    parser.add_argument("--manifest-json", required=True, help="Phase 5 sandbox manifest JSON")
    parser.add_argument("--prepare-json", required=True, help="Phase 5 sandbox preparation report JSON")
    parser.add_argument("--reconciliation-json", required=True, help="Phase 5.1 reconciliation report JSON")
    parser.add_argument("--event-jsonl", help="Sandbox event JSONL used for reconciliation")
    parser.add_argument("--session-id", required=True, help="Operator-visible sandbox session id")
    parser.add_argument("--event-source", choices=("replay", "hummingbot_export"), required=True)
    parser.add_argument("--allow-warnings", action="store_true", help="Allow upstream *_with_warnings gates")
    parser.add_argument("--live-trading-enabled", choices=("true", "false"), help="Override LIVE_TRADING_ENABLED")
    parser.add_argument("--global-kill-switch", choices=("true", "false"), help="Override GLOBAL_KILL_SWITCH")
    parser.add_argument("--output-json", required=True, help="Output session gate JSON")
    parser.add_argument("--output-md", required=True, help="Output session gate Markdown")
    args = parser.parse_args()

    event_path = Path(args.event_jsonl) if args.event_jsonl else None
    environment = {
        "live_trading_enabled": _bool_setting(args.live_trading_enabled, "LIVE_TRADING_ENABLED", default=False),
        "global_kill_switch": _bool_setting(args.global_kill_switch, "GLOBAL_KILL_SWITCH", default=True),
        "hummingbot_api_base_url_configured": bool(os.getenv("HUMMINGBOT_API_BASE_URL")),
        "exchange_key_env_detected": any(bool(os.getenv(name)) for name in EXCHANGE_KEY_ENV_NAMES),
    }
    artifacts = {
        "manifest_json": str(Path(args.manifest_json)),
        "prepare_json": str(Path(args.prepare_json)),
        "reconciliation_json": str(Path(args.reconciliation_json)),
        "event_jsonl": str(event_path) if event_path else None,
        "event_jsonl_exists": bool(event_path and event_path.exists()),
    }
    result = build_sandbox_session_gate(
        manifest=load_json(Path(args.manifest_json)),
        prepare_report=load_json(Path(args.prepare_json)),
        reconciliation_report=load_json(Path(args.reconciliation_json)),
        session_id=args.session_id,
        event_source=args.event_source,
        artifacts=artifacts,
        environment=environment,
        allow_warnings=args.allow_warnings,
    )
    json_path = write_session_gate_json(result, Path(args.output_json))
    md_path = write_session_gate_markdown(result, Path(args.output_md))
    print(
        f"decision={result.decision} session={result.session_id} "
        f"event_source={result.event_source} output={json_path} markdown={md_path}"
    )
    if result.decision == "blocked":
        raise SystemExit(1)


def _bool_setting(value: str | None, env_name: str, *, default: bool) -> bool:
    if value is not None:
        return value == "true"
    env_value = os.getenv(env_name)
    if env_value is None:
        return default
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    main()
