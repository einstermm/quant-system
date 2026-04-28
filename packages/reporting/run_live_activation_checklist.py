"""Run Phase 6.2 live activation checklist."""

from __future__ import annotations

import argparse
import os
from decimal import Decimal
from pathlib import Path

from packages.reporting.live_activation import (
    build_live_activation_checklist,
    load_json,
    load_risk_config,
    write_activation_checklist_json,
    write_activation_checklist_markdown,
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
    parser = argparse.ArgumentParser(description="Run Phase 6.2 live activation checklist.")
    parser.add_argument("--live-readiness-json", required=True, help="Phase 6.1 live readiness JSON")
    parser.add_argument("--daily-report-json", required=True, help="Phase 6.1 daily report JSON")
    parser.add_argument("--tax-export-summary-json", required=True, help="Trade tax export summary JSON")
    parser.add_argument("--live-risk-yml", required=True, help="Strict live risk config")
    parser.add_argument("--session-id", required=True, help="Checklist session id")
    parser.add_argument("--strategy-id", required=True, help="Strategy id")
    parser.add_argument("--max-initial-live-order-notional", default="250")
    parser.add_argument("--env-file", action="append", default=[], help="Optional .env file to read for key presence")
    parser.add_argument("--live-trading-enabled", choices=("true", "false"))
    parser.add_argument("--global-kill-switch", choices=("true", "false"))
    parser.add_argument("--manual-credentials-reviewed", action="store_true")
    parser.add_argument("--manual-exchange-allowlist-reviewed", action="store_true")
    parser.add_argument("--manual-operator-signoff", action="store_true")
    parser.add_argument("--output-json", required=True, help="Output JSON path")
    parser.add_argument("--output-md", required=True, help="Output Markdown path")
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
        "exchange_key_env_detected": any(bool(env_values.get(name)) for name in EXCHANGE_KEY_ENV_NAMES),
        "alert_channel_configured": _alert_channel_configured(env_values),
    }
    live_readiness_path = Path(args.live_readiness_json)
    daily_report_path = Path(args.daily_report_json)
    tax_summary_path = Path(args.tax_export_summary_json)
    live_risk_path = Path(args.live_risk_yml)
    report = build_live_activation_checklist(
        live_readiness=load_json(live_readiness_path),
        daily_report=load_json(daily_report_path),
        tax_export_summary=load_json(tax_summary_path),
        live_risk_config=load_risk_config(live_risk_path),
        environment=environment,
        session_id=args.session_id,
        strategy_id=args.strategy_id,
        max_initial_live_order_notional=Decimal(args.max_initial_live_order_notional),
        manual_credentials_reviewed=args.manual_credentials_reviewed,
        manual_exchange_allowlist_reviewed=args.manual_exchange_allowlist_reviewed,
        manual_operator_signoff=args.manual_operator_signoff,
        artifacts={
            "live_readiness_json": str(live_readiness_path),
            "daily_report_json": str(daily_report_path),
            "tax_export_summary_json": str(tax_summary_path),
            "live_risk_yml": str(live_risk_path),
        },
    )
    json_path = write_activation_checklist_json(report, Path(args.output_json))
    md_path = write_activation_checklist_markdown(report, Path(args.output_md))
    print(f"decision={report.decision} session={report.session_id} output={json_path} markdown={md_path}")


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


def _bool_setting(value: str | None, env_name: str, *, default: bool, env_values: dict[str, str]) -> bool:
    if value is not None:
        return value == "true"
    env_value = env_values.get(env_name)
    if env_value is None:
        return default
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _alert_channel_configured(env_values: dict[str, str]) -> bool:
    webhook_configured = any(bool(env_values.get(name)) for name in ALERT_ENV_NAMES)
    telegram_configured = bool(env_values.get("TELEGRAM_BOT_TOKEN")) and bool(env_values.get("TELEGRAM_CHAT_ID"))
    email_configured = bool(env_values.get("EMAIL_SMTP_HOST")) and bool(env_values.get("EMAIL_TO"))
    return webhook_configured or telegram_configured or email_configured


if __name__ == "__main__":
    main()
