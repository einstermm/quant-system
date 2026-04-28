"""Review a real Hummingbot paper export before a longer observation window."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.sandbox_reconciliation import SandboxRuntimeEvent, load_event_jsonl
from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class HummingbotObservationThresholds:
    target_window_hours: Decimal = Decimal("2")
    require_hummingbot_export: bool = True
    require_balance_events: bool = True
    max_failed_orders: int = 0
    max_canceled_orders: int = 0
    max_unknown_order_ids: int = 0
    max_missing_terminal_orders: int = 0
    max_order_exception_events: int = 0
    max_disconnect_events: int = 0
    max_balance_anomaly_events: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "target_window_hours": decimal_to_str(self.target_window_hours),
            "require_hummingbot_export": self.require_hummingbot_export,
            "require_balance_events": self.require_balance_events,
            "max_failed_orders": self.max_failed_orders,
            "max_canceled_orders": self.max_canceled_orders,
            "max_unknown_order_ids": self.max_unknown_order_ids,
            "max_missing_terminal_orders": self.max_missing_terminal_orders,
            "max_order_exception_events": self.max_order_exception_events,
            "max_disconnect_events": self.max_disconnect_events,
            "max_balance_anomaly_events": self.max_balance_anomaly_events,
        }


@dataclass(frozen=True, slots=True)
class HummingbotObservationReview:
    decision: str
    generated_at: datetime
    session_id: str
    acceptance_summary: dict[str, object]
    reconciliation_summary: dict[str, object]
    event_window: dict[str, object]
    carry_forward_warnings: dict[str, object]
    thresholds: HummingbotObservationThresholds
    alerts: tuple[Alert, ...]
    runbook: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "acceptance_summary": self.acceptance_summary,
            "reconciliation_summary": self.reconciliation_summary,
            "event_window": self.event_window,
            "carry_forward_warnings": self.carry_forward_warnings,
            "thresholds": self.thresholds.to_dict(),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "runbook": list(self.runbook),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Observation Window Review",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Event source: `{self.acceptance_summary['event_source']}`",
            f"- Acceptance: `{self.acceptance_summary['decision']}`",
            "",
            "## Event Window",
            "",
            f"- Started at: `{self.event_window['started_at']}`",
            f"- Completed at: `{self.event_window['completed_at']}`",
            f"- Duration hours: `{self.event_window['duration_hours']}`",
            f"- Event counts: `{self.event_window['event_counts']}`",
            f"- Trading pairs: `{self.event_window['trading_pairs']}`",
            "",
            "## Orders",
            "",
            f"- Expected: `{self.reconciliation_summary['expected_orders']}`",
            f"- Submitted: `{self.reconciliation_summary['submitted_orders']}`",
            f"- Filled: `{self.reconciliation_summary['filled_orders']}`",
            f"- Terminal: `{self.reconciliation_summary['terminal_orders']}`",
            f"- Failed: `{self.reconciliation_summary['failed_orders']}`",
            f"- Canceled: `{self.reconciliation_summary['canceled_orders']}`",
            f"- Unknown ids: `{self.reconciliation_summary['unknown_client_order_ids']}`",
            f"- Missing terminal: `{self.reconciliation_summary['missing_terminal_orders']}`",
            "",
            "## Carry Forward Warnings",
            "",
            f"- Submitted amount adjustments: `{self.carry_forward_warnings['submitted_amount_adjustments']}`",
            f"- Price warnings: `{self.carry_forward_warnings['price_warnings']}`",
            f"- Fee warnings: `{self.carry_forward_warnings['fee_warnings']}`",
            f"- Balance status: `{self.carry_forward_warnings['balance_status']}`",
            "",
            "## Alerts",
            "",
        ]
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Longer Window Runbook", ""])
        lines.extend(f"- {step}" for step in self.runbook)
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_hummingbot_observation_review(
    *,
    acceptance_report: dict[str, Any],
    reconciliation_report: dict[str, Any],
    events: tuple[SandboxRuntimeEvent, ...],
    session_id: str,
    allow_warnings: bool,
    thresholds: HummingbotObservationThresholds | None = None,
    artifacts: dict[str, str] | None = None,
) -> HummingbotObservationReview:
    limits = thresholds or HummingbotObservationThresholds()
    acceptance_summary = _acceptance_summary(acceptance_report)
    reconciliation_summary = _reconciliation_summary(reconciliation_report)
    event_window = _event_window(events)
    carry_forward_warnings = _carry_forward_warnings(reconciliation_report)
    alerts = _build_alerts(
        acceptance_summary=acceptance_summary,
        reconciliation_summary=reconciliation_summary,
        event_window=event_window,
        carry_forward_warnings=carry_forward_warnings,
        thresholds=limits,
        allow_warnings=allow_warnings,
    )
    decision = _decision(alerts)
    return HummingbotObservationReview(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        acceptance_summary=acceptance_summary,
        reconciliation_summary=reconciliation_summary,
        event_window=event_window,
        carry_forward_warnings=carry_forward_warnings,
        thresholds=limits,
        alerts=tuple(alerts),
        runbook=_runbook(decision, limits),
        artifacts=artifacts or {},
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_acceptance_reconciliation(acceptance_report: dict[str, Any]) -> dict[str, Any]:
    artifacts = acceptance_report.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("acceptance report artifacts must be a dictionary")
    reconciliation_json = artifacts.get("reconciliation_json")
    if not reconciliation_json:
        raise ValueError("acceptance report does not include artifacts.reconciliation_json")
    return load_json(Path(str(reconciliation_json)))


def write_observation_review_json(review: HummingbotObservationReview, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_observation_review_markdown(review: HummingbotObservationReview, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(review.to_markdown(), encoding="utf-8")
    return output_path


def _acceptance_summary(report: dict[str, Any]) -> dict[str, object]:
    session_gate = report.get("session_gate_summary", {})
    if not isinstance(session_gate, dict):
        session_gate = {}
    return {
        "decision": str(report.get("decision", "unknown")),
        "event_source": str(report.get("event_source", "unknown")),
        "output_dir": str(report.get("output_dir", "")),
        "session_gate_decision": str(session_gate.get("decision", "unknown")),
        "live_trading_enabled": bool(session_gate.get("live_trading_enabled")),
        "exchange_key_env_detected": bool(session_gate.get("exchange_key_env_detected")),
    }


def _reconciliation_summary(report: dict[str, Any]) -> dict[str, object]:
    order_checks = _dict(report.get("order_checks"))
    balance_checks = _dict(report.get("balance_checks"))
    event_counts = _dict(report.get("event_counts"))
    return {
        "decision": str(report.get("decision", "unknown")),
        "event_counts": event_counts,
        "expected_orders": _int(order_checks.get("expected_orders")),
        "submitted_orders": _int(order_checks.get("submitted_orders")),
        "filled_orders": _int(order_checks.get("filled_orders")),
        "terminal_orders": _int(order_checks.get("terminal_orders")),
        "failed_orders": _int(order_checks.get("failed_orders")),
        "canceled_orders": _int(order_checks.get("canceled_orders")),
        "unknown_client_order_ids": _list(order_checks.get("unknown_client_order_ids")),
        "missing_submissions": _list(order_checks.get("missing_submissions")),
        "missing_terminal_orders": _list(order_checks.get("missing_terminal_orders")),
        "order_exception_events": _int(order_checks.get("order_exception_events")),
        "disconnect_events": _int(order_checks.get("disconnect_events")),
        "balance_anomaly_events": _int(order_checks.get("balance_anomaly_events")),
        "balance_events": _int(balance_checks.get("balance_events")),
        "balance_status": str(balance_checks.get("status", "unknown")),
        "balance_mismatches": _list(balance_checks.get("balance_mismatches")),
    }


def _event_window(events: tuple[SandboxRuntimeEvent, ...]) -> dict[str, object]:
    event_counts = Counter(event.event_type for event in events)
    order_events = [event for event in events if event.event_type in {"submitted", "filled", "completed"}]
    timestamps = [event.created_at for event in events]
    if timestamps:
        started_at = min(timestamps)
        completed_at = max(timestamps)
        duration_hours = Decimal(str((completed_at - started_at).total_seconds())) / Decimal("3600")
    else:
        started_at = None
        completed_at = None
        duration_hours = Decimal("0")
    return {
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "duration_hours": decimal_to_str(duration_hours),
        "event_counts": dict(event_counts),
        "event_count": len(events),
        "trading_pairs": sorted({str(event.trading_pair) for event in order_events if event.trading_pair}),
        "client_order_ids": sorted({str(event.client_order_id) for event in order_events if event.client_order_id}),
    }


def _carry_forward_warnings(report: dict[str, Any]) -> dict[str, object]:
    fill_checks = _dict(report.get("fill_checks"))
    balance_checks = _dict(report.get("balance_checks"))
    return {
        "submitted_amount_adjustments": _list(fill_checks.get("submitted_amount_adjustments")),
        "price_warnings": _list(fill_checks.get("price_warnings")),
        "fee_warnings": _list(fill_checks.get("fee_warnings")),
        "balance_status": str(balance_checks.get("status", "unknown")),
        "balance_mismatches": _list(balance_checks.get("balance_mismatches")),
    }


def _build_alerts(
    *,
    acceptance_summary: dict[str, object],
    reconciliation_summary: dict[str, object],
    event_window: dict[str, object],
    carry_forward_warnings: dict[str, object],
    thresholds: HummingbotObservationThresholds,
    allow_warnings: bool,
) -> list[Alert]:
    alerts: list[Alert] = []
    acceptance_decision = str(acceptance_summary["decision"])
    reconciliation_decision = str(reconciliation_summary["decision"])
    _decision_alert(alerts, "Acceptance", acceptance_decision, allow_warnings)
    _decision_alert(alerts, "Reconciliation", reconciliation_decision, allow_warnings)

    if thresholds.require_hummingbot_export and acceptance_summary["event_source"] != "hummingbot_export":
        alerts.append(critical_alert("Real Hummingbot export missing", "Phase 5.8 requires event_source=hummingbot_export."))
    if acceptance_summary["live_trading_enabled"]:
        alerts.append(critical_alert("Live trading enabled", "Live trading must remain disabled for Phase 5.8."))
    if acceptance_summary["exchange_key_env_detected"]:
        alerts.append(critical_alert("Exchange key env detected", "Do not run Phase 5.8 with exchange key environment variables loaded."))

    expected_orders = int(reconciliation_summary["expected_orders"])
    if expected_orders == 0:
        alerts.append(critical_alert("No expected orders", "Reconciliation reported zero expected Hummingbot paper orders."))
    for key, label in (
        ("submitted_orders", "submitted"),
        ("filled_orders", "filled"),
        ("terminal_orders", "terminal"),
    ):
        if int(reconciliation_summary[key]) != expected_orders:
            alerts.append(critical_alert(f"Order {label} mismatch", f"{label} orders do not match expected order count."))

    _limit_alert(alerts, reconciliation_summary, "failed_orders", thresholds.max_failed_orders, "Failed paper orders")
    _limit_alert(alerts, reconciliation_summary, "canceled_orders", thresholds.max_canceled_orders, "Canceled paper orders")
    _limit_alert(alerts, reconciliation_summary, "order_exception_events", thresholds.max_order_exception_events, "Order exception events")
    _limit_alert(alerts, reconciliation_summary, "disconnect_events", thresholds.max_disconnect_events, "Disconnect events")
    _limit_alert(alerts, reconciliation_summary, "balance_anomaly_events", thresholds.max_balance_anomaly_events, "Balance anomaly events")
    if len(reconciliation_summary["unknown_client_order_ids"]) > thresholds.max_unknown_order_ids:
        alerts.append(critical_alert("Unknown order ids", "Observed unknown Hummingbot client order ids."))
    if len(reconciliation_summary["missing_terminal_orders"]) > thresholds.max_missing_terminal_orders:
        alerts.append(critical_alert("Missing terminal orders", "Some Hummingbot paper orders did not reach a terminal state."))
    if thresholds.require_balance_events and int(reconciliation_summary["balance_events"]) == 0:
        alerts.append(critical_alert("Balance events missing", "No Hummingbot paper balance event was exported."))
    if reconciliation_summary["balance_mismatches"]:
        alerts.append(critical_alert("Balance mismatches", "Reconciliation reported balance mismatches."))

    duration_hours = Decimal(str(event_window["duration_hours"]))
    if duration_hours < thresholds.target_window_hours:
        alerts.append(
            warning_alert(
                "Observation window short",
                f"Export duration {decimal_to_str(duration_hours)}h is below target {decimal_to_str(thresholds.target_window_hours)}h.",
            )
        )
    if carry_forward_warnings["submitted_amount_adjustments"]:
        alerts.append(warning_alert("Submitted amount adjusted", "Carry forward Hummingbot paper amount adjustment warnings."))
    if carry_forward_warnings["price_warnings"]:
        alerts.append(warning_alert("Fill price drift", "Carry forward fill price drift warnings into the next runbook."))
    if carry_forward_warnings["fee_warnings"]:
        alerts.append(warning_alert("Fee drift", "Carry forward Hummingbot paper fee drift warnings into the next runbook."))
    if carry_forward_warnings["balance_status"] == "skipped":
        alerts.append(warning_alert("Balance reconciliation skipped", "Hummingbot paper account balances were exported but not quantity-reconciled."))

    alerts.append(
        info_alert(
            "Direct paper batch mode",
            "Phase 5.8 authorizes a longer sandbox observation only; live trading remains disabled.",
        )
    )
    return alerts


def _decision_alert(alerts: list[Alert], label: str, decision: str, allow_warnings: bool) -> None:
    if decision == "blocked":
        alerts.append(critical_alert(f"{label} blocked", f"{label} decision is blocked."))
    elif decision.endswith("_with_warnings"):
        alert_fn = warning_alert if allow_warnings else critical_alert
        alerts.append(alert_fn(f"{label} has warnings", f"{label} decision is {decision}."))
    elif decision in {"", "unknown"}:
        alerts.append(critical_alert(f"{label} missing", f"{label} decision is missing."))


def _limit_alert(
    alerts: list[Alert],
    summary: dict[str, object],
    key: str,
    limit: int,
    title: str,
) -> None:
    value = int(summary[key])
    if value > limit:
        alerts.append(critical_alert(title, f"{key}={value} exceeds limit {limit}."))


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "hummingbot_observation_window_ready_with_warnings"
    return "hummingbot_observation_window_ready"


def _runbook(decision: str, thresholds: HummingbotObservationThresholds) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not start a longer Hummingbot paper observation window.",
            "Fix every CRITICAL alert and rerun Phase 5.8.",
            "Keep live trading disabled.",
        )
    return (
        "Regenerate a fresh sandbox manifest from the latest approved paper ledger before the next order batch; do not blindly resubmit an old manifest.",
        "Regenerate and reinstall the Phase 5.7 direct paper handoff script/config before starting Hummingbot.",
        "Archive or remove the prior Hummingbot event JSONL so the next export contains only the new window.",
        "Start Hummingbot headless with binance_paper_trade and a unique container name for the observation window.",
        f"Keep the window open for at least {decimal_to_str(thresholds.target_window_hours)} hours or document why the direct paper batch completed sooner.",
        "Run Phase 5.4 export acceptance and Phase 5.8 observation review immediately after the window.",
        "Carry forward accepted WARN items explicitly; any failed/canceled/unknown/missing order blocks the next phase.",
        "Keep LIVE_TRADING_ENABLED=false and do not load live connector credentials.",
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _int(value: object) -> int:
    if value is None:
        return 0
    return int(value)
