"""Run Phase 6.4 first live batch activation plan."""

from __future__ import annotations

import argparse
import os
from decimal import Decimal
from pathlib import Path

from packages.adapters.hummingbot.live_batch_activation_plan import (
    build_live_batch_activation_plan,
    load_json,
    load_risk_config,
    write_live_batch_activation_plan_json,
    write_live_batch_activation_plan_markdown,
)

EXCHANGE_KEY_ENV_NAMES = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_SECRET_KEY",
    "EXCHANGE_API_KEY",
    "EXCHANGE_SECRET_KEY",
)

ALERT_ENV_NAMES = (
    "ALERT_WEBHOOK_URL",
    "DISCORD_WEBHOOK_URL",
    "SMS_WEBHOOK_URL",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6.4 live batch activation plan.")
    parser.add_argument("--live-connector-preflight-json", required=True)
    parser.add_argument("--credential-allowlist-json", required=True)
    parser.add_argument("--operator-signoff-json", required=True)
    parser.add_argument("--live-risk-yml", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--allowed-pair", action="append", required=True)
    parser.add_argument("--max-batch-orders", type=int, default=2)
    parser.add_argument("--max-batch-notional", default="500")
    parser.add_argument("--final-operator-go", action="store_true")
    parser.add_argument("--env-file", action="append", default=[])
    parser.add_argument("--live-trading-enabled", choices=("true", "false"))
    parser.add_argument("--global-kill-switch", choices=("true", "false"))
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    env_values = _merged_environment(args.env_file)
    environment = {
        "live_trading_enabled": _bool_setting(
            args.live_trading_enabled,
            "LIVE_TRADING_ENABLED",
            default=False,
            env_values=env_values,
        ),
        "global_kill_switch": _bool_setting(
            args.global_kill_switch,
            "GLOBAL_KILL_SWITCH",
            default=True,
            env_values=env_values,
        ),
        "exchange_key_env_detected": any(
            bool(env_values.get(name)) for name in EXCHANGE_KEY_ENV_NAMES
        ),
        "alert_channel_configured": _alert_channel_configured(env_values),
    }
    preflight_path = Path(args.live_connector_preflight_json)
    credential_path = Path(args.credential_allowlist_json)
    signoff_path = Path(args.operator_signoff_json)
    risk_path = Path(args.live_risk_yml)
    report = build_live_batch_activation_plan(
        live_connector_preflight=load_json(preflight_path),
        credential_allowlist=load_json(credential_path),
        operator_signoff=load_json(signoff_path),
        live_risk_config=load_risk_config(risk_path),
        environment=environment,
        session_id=args.session_id,
        strategy_id=args.strategy_id,
        batch_id=args.batch_id,
        allowed_pairs=tuple(args.allowed_pair),
        max_batch_orders=args.max_batch_orders,
        max_batch_notional=Decimal(args.max_batch_notional),
        final_operator_go=args.final_operator_go,
        artifacts={
            "live_connector_preflight_json": str(preflight_path),
            "credential_allowlist_json": str(credential_path),
            "operator_signoff_json": str(signoff_path),
            "live_risk_yml": str(risk_path),
        },
    )
    json_path = write_live_batch_activation_plan_json(report, Path(args.output_json))
    md_path = write_live_batch_activation_plan_markdown(report, Path(args.output_md))
    print(
        f"decision={report.decision} session={report.session_id} "
        f"batch_id={report.batch_id} output={json_path} markdown={md_path}"
    )
    if report.decision == "live_batch_activation_plan_blocked":
        raise SystemExit(1)


def _merged_environment(env_files: list[str]) -> dict[str, str]:
    values = dict(os.environ)
    default_env = Path(".env")
    candidate_files = [str(default_env)] if default_env.exists() else []
    candidate_files.extend(env_files)
    for env_file in candidate_files:
        path = Path(env_file)
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _bool_setting(
    value: str | None,
    env_name: str,
    *,
    default: bool,
    env_values: dict[str, str],
) -> bool:
    if value is not None:
        return value == "true"
    env_value = env_values.get(env_name)
    if env_value is None:
        return default
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _alert_channel_configured(env_values: dict[str, str]) -> bool:
    webhook_configured = any(bool(env_values.get(name)) for name in ALERT_ENV_NAMES)
    telegram_configured = bool(env_values.get("TELEGRAM_BOT_TOKEN")) and bool(
        env_values.get("TELEGRAM_CHAT_ID")
    )
    email_configured = bool(env_values.get("EMAIL_SMTP_HOST")) and bool(env_values.get("EMAIL_TO"))
    return webhook_configured or telegram_configured or email_configured


if __name__ == "__main__":
    main()
