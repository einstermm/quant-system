"""Phase 6 live trading readiness preflight."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str
from packages.data.simple_yaml import load_simple_yaml
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class LiveReadinessThresholds:
    min_observation_hours: Decimal = Decimal("2")
    max_failed_orders: int = 0
    max_canceled_orders: int = 0
    max_unknown_order_ids: int = 0
    max_missing_terminal_orders: int = 0
    max_initial_live_order_notional: Decimal = Decimal("250")
    require_live_disabled: bool = True
    require_global_kill_switch: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "min_observation_hours": decimal_to_str(self.min_observation_hours),
            "max_failed_orders": self.max_failed_orders,
            "max_canceled_orders": self.max_canceled_orders,
            "max_unknown_order_ids": self.max_unknown_order_ids,
            "max_missing_terminal_orders": self.max_missing_terminal_orders,
            "max_initial_live_order_notional": decimal_to_str(self.max_initial_live_order_notional),
            "require_live_disabled": self.require_live_disabled,
            "require_global_kill_switch": self.require_global_kill_switch,
        }


@dataclass(frozen=True, slots=True)
class LiveReadinessReport:
    decision: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    observation_summary: dict[str, object]
    acceptance_summary: dict[str, object]
    daily_report_summary: dict[str, object]
    risk_limits: dict[str, object]
    environment: dict[str, object]
    thresholds: LiveReadinessThresholds
    alerts: tuple[Alert, ...]
    runbook: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "observation_summary": self.observation_summary,
            "acceptance_summary": self.acceptance_summary,
            "daily_report_summary": self.daily_report_summary,
            "risk_limits": _json_safe(self.risk_limits),
            "environment": self.environment,
            "thresholds": self.thresholds.to_dict(),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "runbook": list(self.runbook),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.1 Live Readiness Preflight",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            "",
            "## Observation",
            "",
            f"- Decision: `{self.observation_summary['decision']}`",
            f"- Duration hours: `{self.observation_summary['duration_hours']}`",
            f"- Events: `{self.observation_summary['event_count']}`",
            f"- Submitted/Filled/Terminal: `{self.observation_summary['submitted_orders']}/{self.observation_summary['filled_orders']}/{self.observation_summary['terminal_orders']}`",
            f"- Failed/Canceled/Unknown/Missing terminal: `{self.observation_summary['failed_orders']}/{self.observation_summary['canceled_orders']}/{self.observation_summary['unknown_order_ids']}/{self.observation_summary['missing_terminal_orders']}`",
            "",
            "## Acceptance",
            "",
            f"- Decision: `{self.acceptance_summary['decision']}`",
            f"- Event source: `{self.acceptance_summary['event_source']}`",
            f"- Session gate: `{self.acceptance_summary['session_gate_decision']}`",
            "",
            "## Daily Report",
            "",
            f"- Status: `{self.daily_report_summary['status']}`",
            f"- Filled orders: `{self.daily_report_summary['filled_orders']}`",
            f"- Quote balance delta: `{self.daily_report_summary['quote_balance_delta']}`",
            f"- Total fee quote: `{self.daily_report_summary['total_fee_quote']}`",
            "",
            "## Risk And Environment",
            "",
            f"- Risk limits: `{_json_safe(self.risk_limits)}`",
            f"- Live trading enabled: `{self.environment['live_trading_enabled']}`",
            f"- Global kill switch: `{self.environment['global_kill_switch']}`",
            f"- Exchange key env detected: `{self.environment['exchange_key_env_detected']}`",
            f"- Hummingbot API configured: `{self.environment['hummingbot_api_base_url_configured']}`",
            f"- Alert channel configured: `{self.environment['alert_channel_configured']}`",
            "",
            "## Alerts",
            "",
        ]
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Activation Runbook", ""])
        lines.extend(f"- {step}" for step in self.runbook)
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_readiness_report(
    *,
    observation_review: dict[str, Any],
    acceptance_report: dict[str, Any],
    daily_report: dict[str, Any],
    risk_config: dict[str, Any],
    environment: dict[str, object],
    session_id: str,
    strategy_id: str,
    allow_warnings: bool,
    thresholds: LiveReadinessThresholds | None = None,
    artifacts: dict[str, str] | None = None,
) -> LiveReadinessReport:
    limits = thresholds or LiveReadinessThresholds()
    observation_summary = _observation_summary(observation_review)
    acceptance_summary = _acceptance_summary(acceptance_report)
    daily_report_summary = _daily_report_summary(daily_report)
    risk_limits = _risk_limits(risk_config)
    alerts = _build_alerts(
        observation_summary=observation_summary,
        acceptance_summary=acceptance_summary,
        daily_report_summary=daily_report_summary,
        risk_limits=risk_limits,
        environment=environment,
        thresholds=limits,
        allow_warnings=allow_warnings,
    )
    decision = _decision(alerts)
    return LiveReadinessReport(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=strategy_id,
        observation_summary=observation_summary,
        acceptance_summary=acceptance_summary,
        daily_report_summary=daily_report_summary,
        risk_limits=risk_limits,
        environment=environment,
        thresholds=limits,
        alerts=tuple(alerts),
        runbook=_runbook(decision),
        artifacts=artifacts or {},
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_risk_config(path: str | Path) -> dict[str, Any]:
    return load_simple_yaml(path)


def write_live_readiness_json(report: LiveReadinessReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_live_readiness_markdown(report: LiveReadinessReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def _observation_summary(report: dict[str, Any]) -> dict[str, object]:
    reconciliation = _dict(report.get("reconciliation_summary"))
    event_window = _dict(report.get("event_window"))
    return {
        "decision": str(report.get("decision", "unknown")),
        "duration_hours": str(event_window.get("duration_hours", "0")),
        "event_count": _int(event_window.get("event_count")),
        "submitted_orders": _int(reconciliation.get("submitted_orders")),
        "filled_orders": _int(reconciliation.get("filled_orders")),
        "terminal_orders": _int(reconciliation.get("terminal_orders")),
        "failed_orders": _int(reconciliation.get("failed_orders")),
        "canceled_orders": _int(reconciliation.get("canceled_orders")),
        "unknown_order_ids": len(_list(reconciliation.get("unknown_client_order_ids"))),
        "missing_terminal_orders": len(_list(reconciliation.get("missing_terminal_orders"))),
    }


def _acceptance_summary(report: dict[str, Any]) -> dict[str, object]:
    session_gate = _dict(report.get("session_gate_summary"))
    return {
        "decision": str(report.get("decision", "unknown")),
        "event_source": str(report.get("event_source", "unknown")),
        "session_gate_decision": str(session_gate.get("decision", "unknown")),
        "live_trading_enabled": bool(session_gate.get("live_trading_enabled")),
        "exchange_key_env_detected": bool(session_gate.get("exchange_key_env_detected")),
    }


def _daily_report_summary(report: dict[str, Any]) -> dict[str, object]:
    trading = _dict(report.get("trading_summary"))
    balances = _dict(report.get("balance_summary"))
    return {
        "status": str(report.get("status", "unknown")),
        "filled_orders": _int(trading.get("filled_orders")),
        "total_fee_quote": str(trading.get("total_fee_quote", "0")),
        "quote_balance_delta": str(balances.get("quote_balance_delta", "0")),
        "alert_count": len(_list(report.get("alerts"))),
    }


def _risk_limits(config: dict[str, Any]) -> dict[str, object]:
    required = (
        "max_order_notional",
        "max_symbol_notional",
        "max_gross_notional",
        "max_daily_loss",
        "max_drawdown_pct",
    )
    result: dict[str, object] = {}
    for key in required:
        value = config.get(key)
        result[key] = str(value) if value is not None else ""
        try:
            result[f"{key}_decimal"] = Decimal(str(value))
        except Exception:
            result[f"{key}_decimal"] = None
    return result


def _build_alerts(
    *,
    observation_summary: dict[str, object],
    acceptance_summary: dict[str, object],
    daily_report_summary: dict[str, object],
    risk_limits: dict[str, object],
    environment: dict[str, object],
    thresholds: LiveReadinessThresholds,
    allow_warnings: bool,
) -> list[Alert]:
    alerts: list[Alert] = []
    _decision_alert(alerts, "Observation review", str(observation_summary["decision"]), allow_warnings)
    _decision_alert(alerts, "Export acceptance", str(acceptance_summary["decision"]), allow_warnings)
    if acceptance_summary["event_source"] != "hummingbot_export":
        alerts.append(critical_alert("Real export missing", "Phase 6.1 requires a real Hummingbot export."))

    duration = Decimal(str(observation_summary["duration_hours"]))
    if duration < thresholds.min_observation_hours:
        alerts.append(critical_alert("Observation window too short", "Phase 6.1 requires a completed 2 hour observation."))
    _limit_alert(alerts, observation_summary, "failed_orders", thresholds.max_failed_orders, "Failed orders")
    _limit_alert(alerts, observation_summary, "canceled_orders", thresholds.max_canceled_orders, "Canceled orders")
    _limit_alert(alerts, observation_summary, "unknown_order_ids", thresholds.max_unknown_order_ids, "Unknown order ids")
    _limit_alert(
        alerts,
        observation_summary,
        "missing_terminal_orders",
        thresholds.max_missing_terminal_orders,
        "Missing terminal orders",
    )

    daily_status = str(daily_report_summary["status"])
    if daily_status == "blocked":
        alerts.append(critical_alert("Daily report blocked", "Daily report generation reported a blocked status."))
    elif daily_status.endswith("_with_warnings"):
        alerts.append(warning_alert("Daily report has warnings", f"Daily report status is {daily_status}."))
    elif daily_status not in {"daily_report_ready"}:
        alerts.append(critical_alert("Daily report missing", f"Unexpected daily report status: {daily_status}."))

    _risk_alerts(alerts, risk_limits, thresholds)
    if thresholds.require_live_disabled and bool(environment.get("live_trading_enabled")):
        alerts.append(critical_alert("Live trading enabled", "Phase 6.1 is a pre-activation audit; LIVE_TRADING_ENABLED must remain false."))
    if thresholds.require_global_kill_switch and not bool(environment.get("global_kill_switch")):
        alerts.append(critical_alert("Kill switch disabled", "GLOBAL_KILL_SWITCH must remain true before manual activation."))
    if bool(environment.get("exchange_key_env_detected")):
        alerts.append(warning_alert("Exchange key env detected", "Credential environment variables are present; values were not read or emitted."))
    else:
        alerts.append(info_alert("No exchange keys detected", "No exchange credential environment variables were detected in this shell."))
    if not bool(environment.get("hummingbot_api_base_url_configured")):
        alerts.append(warning_alert("Hummingbot API URL missing", "HUMMINGBOT_API_BASE_URL is not configured in the current environment."))
    if not bool(environment.get("alert_channel_configured")):
        alerts.append(warning_alert("Alert channel missing", "Configure Telegram, Discord, email, SMS, or webhook alerts before live activation."))

    alerts.append(info_alert("No live orders submitted", "Phase 6.1 only builds readiness artifacts and does not submit orders."))
    return alerts


def _decision_alert(alerts: list[Alert], label: str, decision: str, allow_warnings: bool) -> None:
    if decision in {"blocked", "unknown", ""}:
        alerts.append(critical_alert(f"{label} blocked", f"{label} decision is {decision}."))
    elif decision.endswith("_with_warnings"):
        alert_fn = warning_alert if allow_warnings else critical_alert
        alerts.append(alert_fn(f"{label} has warnings", f"{label} decision is {decision}."))


def _limit_alert(alerts: list[Alert], values: dict[str, object], key: str, limit: int, title: str) -> None:
    value = _int(values.get(key))
    if value > limit:
        alerts.append(critical_alert(title, f"{key}={value} exceeds limit {limit}."))


def _risk_alerts(alerts: list[Alert], risk_limits: dict[str, object], thresholds: LiveReadinessThresholds) -> None:
    decimal_keys = (
        "max_order_notional_decimal",
        "max_symbol_notional_decimal",
        "max_gross_notional_decimal",
        "max_daily_loss_decimal",
        "max_drawdown_pct_decimal",
    )
    for key in decimal_keys:
        value = risk_limits.get(key)
        if not isinstance(value, Decimal):
            alerts.append(critical_alert("Risk config invalid", f"{key.removesuffix('_decimal')} is missing or invalid."))
            continue
        if value <= Decimal("0"):
            alerts.append(critical_alert("Risk config invalid", f"{key.removesuffix('_decimal')} must be positive."))
    drawdown = risk_limits.get("max_drawdown_pct_decimal")
    if isinstance(drawdown, Decimal) and drawdown >= Decimal("1"):
        alerts.append(critical_alert("Risk config invalid", "max_drawdown_pct must be below 1."))
    max_order = risk_limits.get("max_order_notional_decimal")
    if isinstance(max_order, Decimal) and max_order > thresholds.max_initial_live_order_notional:
        alerts.append(
            warning_alert(
                "Initial live order cap high",
                (
                    "Configured max_order_notional is above the Phase 6.1 initial live cap; "
                    "lower it before small-funds activation."
                ),
            )
        )


def _decision(alerts: tuple[Alert, ...] | list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "live_preflight_blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "live_preflight_ready_with_warnings"
    return "live_preflight_ready"


def _runbook(decision: str) -> tuple[str, ...]:
    if decision == "live_preflight_blocked":
        return (
            "Do not enable live trading.",
            "Resolve every CRITICAL alert and rerun Phase 6.1.",
            "Keep GLOBAL_KILL_SWITCH=true while preparing live configuration.",
        )
    return (
        "Keep LIVE_TRADING_ENABLED=false until the manual activation checklist is signed off.",
        "Reduce initial live risk limits to the approved small-funds cap before activation.",
        "Configure an external alert channel and verify a test alert.",
        "Regenerate the Hummingbot handoff with a live connector only after credentials, allowlist, and kill switch are verified.",
        "Start with one small live order batch; rerun daily report, reconciliation, and tax export immediately after completion.",
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _json_safe(values: dict[str, object]) -> dict[str, object]:
    return {
        key: decimal_to_str(value) if isinstance(value, Decimal) else value
        for key, value in values.items()
    }
