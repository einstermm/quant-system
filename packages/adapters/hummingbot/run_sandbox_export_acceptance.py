"""Run Phase 5.4 Hummingbot sandbox export acceptance."""

from __future__ import annotations

import argparse
import os
from decimal import Decimal
from pathlib import Path

from packages.adapters.hummingbot.sandbox_export_acceptance import (
    build_sandbox_export_acceptance,
    load_json,
)
from packages.adapters.hummingbot.sandbox_reconciliation import (
    SandboxReconciliationThresholds,
    load_event_jsonl,
)

EXCHANGE_KEY_ENV_NAMES = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_SECRET_KEY",
    "EXCHANGE_API_KEY",
    "EXCHANGE_SECRET_KEY",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Accept a Hummingbot sandbox event export.")
    parser.add_argument("--manifest-json", required=True, help="Phase 5 sandbox manifest JSON")
    parser.add_argument("--prepare-json", required=True, help="Phase 5 sandbox preparation report JSON")
    parser.add_argument("--events-jsonl", required=True, help="Hummingbot sandbox event JSONL")
    parser.add_argument("--output-dir", required=True, help="Output acceptance directory")
    parser.add_argument("--session-id", required=True, help="Sandbox session id")
    parser.add_argument("--event-source", choices=("replay", "hummingbot_export"), required=True)
    parser.add_argument("--starting-quote-balance", help="Starting quote balance for balance reconciliation")
    parser.add_argument("--quote-asset", default="USDT")
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--amount-tolerance", default="0.00000001")
    parser.add_argument("--price-warning-bps", default="50")
    parser.add_argument("--fee-tolerance", default="0.000001")
    parser.add_argument("--balance-tolerance", default="0.000001")
    parser.add_argument("--no-require-balance-event", action="store_true")
    parser.add_argument("--live-trading-enabled", choices=("true", "false"))
    parser.add_argument("--global-kill-switch", choices=("true", "false"))
    args = parser.parse_args()

    environment = {
        "live_trading_enabled": _bool_setting(args.live_trading_enabled, "LIVE_TRADING_ENABLED", default=False),
        "global_kill_switch": _bool_setting(args.global_kill_switch, "GLOBAL_KILL_SWITCH", default=True),
        "hummingbot_api_base_url_configured": bool(os.getenv("HUMMINGBOT_API_BASE_URL")),
        "exchange_key_env_detected": any(bool(os.getenv(name)) for name in EXCHANGE_KEY_ENV_NAMES),
    }
    result = build_sandbox_export_acceptance(
        manifest=load_json(Path(args.manifest_json)),
        prepare_report=load_json(Path(args.prepare_json)),
        events=load_event_jsonl(Path(args.events_jsonl)),
        event_jsonl=Path(args.events_jsonl),
        output_dir=Path(args.output_dir),
        session_id=args.session_id,
        event_source=args.event_source,
        starting_quote_balance=Decimal(args.starting_quote_balance) if args.starting_quote_balance else None,
        quote_asset=args.quote_asset,
        environment=environment,
        allow_warnings=args.allow_warnings,
        thresholds=SandboxReconciliationThresholds(
            amount_tolerance=Decimal(args.amount_tolerance),
            price_warning_bps=Decimal(args.price_warning_bps),
            fee_tolerance=Decimal(args.fee_tolerance),
            balance_tolerance=Decimal(args.balance_tolerance),
            require_balance_event=not args.no_require_balance_event,
        ),
    )
    print(
        f"decision={result.decision} session={result.session_id} "
        f"event_source={result.event_source} output_dir={result.output_dir}"
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
