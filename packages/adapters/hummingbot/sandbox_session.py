"""Hummingbot sandbox session preflight gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class SandboxSessionGateResult:
    decision: str
    generated_at: datetime
    session_id: str
    event_source: str
    manifest_summary: dict[str, object]
    prepare_summary: dict[str, object]
    reconciliation_summary: dict[str, object]
    environment: dict[str, object]
    artifacts: dict[str, object]
    alerts: tuple[Alert, ...]
    operator_checklist: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "event_source": self.event_source,
            "manifest_summary": self.manifest_summary,
            "prepare_summary": self.prepare_summary,
            "reconciliation_summary": self.reconciliation_summary,
            "environment": self.environment,
            "artifacts": self.artifacts,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "operator_checklist": list(self.operator_checklist),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Sandbox Session Gate",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Event source: `{self.event_source}`",
            f"- Strategy: `{self.manifest_summary['strategy_id']}`",
            f"- Account: `{self.manifest_summary['account_id']}`",
            f"- Connector: `{self.manifest_summary['connector_name']}`",
            f"- Live trading enabled: `{self.manifest_summary['live_trading_enabled']}`",
            "",
            "## Upstream Gates",
            "",
            f"- Sandbox prepare decision: `{self.prepare_summary['decision']}`",
            f"- Reconciliation decision: `{self.reconciliation_summary['decision']}`",
            f"- Expected orders: `{self.manifest_summary['expected_orders']}`",
            f"- Submitted orders: `{self.reconciliation_summary['submitted_orders']}`",
            f"- Terminal orders: `{self.reconciliation_summary['terminal_orders']}`",
            f"- Balance events: `{self.reconciliation_summary['balance_events']}`",
            "",
            "## Environment",
            "",
            f"- LIVE_TRADING_ENABLED: `{self.environment['live_trading_enabled']}`",
            f"- GLOBAL_KILL_SWITCH: `{self.environment['global_kill_switch']}`",
            f"- Exchange key env detected: `{self.environment['exchange_key_env_detected']}`",
            "",
            "## Artifacts",
            "",
        ]
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(
                f"- `{alert.severity}` {alert.title}: {alert.message}"
                for alert in self.alerts
            )
        else:
            lines.append("- None")
        lines.extend(["", "## Operator Checklist", ""])
        lines.extend(f"- {item}" for item in self.operator_checklist)
        lines.append("")
        return "\n".join(lines)


def build_sandbox_session_gate(
    *,
    manifest: dict[str, Any],
    prepare_report: dict[str, Any],
    reconciliation_report: dict[str, Any],
    session_id: str,
    event_source: str,
    artifacts: dict[str, object],
    environment: dict[str, object],
    allow_warnings: bool,
) -> SandboxSessionGateResult:
    manifest_summary = _manifest_summary(manifest)
    prepare_summary = _prepare_summary(prepare_report)
    reconciliation_summary = _reconciliation_summary(reconciliation_report)
    alerts = _build_alerts(
        manifest_summary=manifest_summary,
        prepare_summary=prepare_summary,
        reconciliation_summary=reconciliation_summary,
        event_source=event_source,
        artifacts=artifacts,
        environment=environment,
        allow_warnings=allow_warnings,
    )
    decision = _decision(alerts)
    return SandboxSessionGateResult(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        event_source=event_source,
        manifest_summary=manifest_summary,
        prepare_summary=prepare_summary,
        reconciliation_summary=reconciliation_summary,
        environment=environment,
        artifacts=artifacts,
        alerts=tuple(alerts),
        operator_checklist=_operator_checklist(decision, event_source),
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_session_gate_json(result: SandboxSessionGateResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_session_gate_markdown(result: SandboxSessionGateResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return output_path


def _manifest_summary(manifest: dict[str, Any]) -> dict[str, object]:
    orders = manifest.get("orders", [])
    controllers = manifest.get("controller_configs", [])
    return {
        "schema_version": manifest.get("schema_version"),
        "strategy_id": manifest.get("strategy_id", ""),
        "account_id": manifest.get("account_id", ""),
        "connector_name": manifest.get("connector_name", ""),
        "controller_name": manifest.get("controller_name", ""),
        "live_trading_enabled": bool(manifest.get("live_trading_enabled")),
        "expected_orders": len(orders) if isinstance(orders, list) else 0,
        "controller_configs": len(controllers) if isinstance(controllers, list) else 0,
        "total_notional": manifest.get("total_notional", "0"),
    }


def _prepare_summary(report: dict[str, Any]) -> dict[str, object]:
    alerts = report.get("alerts", [])
    return {
        "decision": report.get("decision", "unknown"),
        "alert_counts": _alert_counts(alerts if isinstance(alerts, list) else []),
    }


def _reconciliation_summary(report: dict[str, Any]) -> dict[str, object]:
    order_checks = report.get("order_checks", {})
    balance_checks = report.get("balance_checks", {})
    event_counts = report.get("event_counts", {})
    return {
        "decision": report.get("decision", "unknown"),
        "event_counts": event_counts if isinstance(event_counts, dict) else {},
        "submitted_orders": int(order_checks.get("submitted_orders", 0)) if isinstance(order_checks, dict) else 0,
        "terminal_orders": int(order_checks.get("terminal_orders", 0)) if isinstance(order_checks, dict) else 0,
        "filled_orders": int(order_checks.get("filled_orders", 0)) if isinstance(order_checks, dict) else 0,
        "unknown_client_order_ids": order_checks.get("unknown_client_order_ids", []) if isinstance(order_checks, dict) else [],
        "missing_terminal_orders": order_checks.get("missing_terminal_orders", []) if isinstance(order_checks, dict) else [],
        "balance_events": int(balance_checks.get("balance_events", 0)) if isinstance(balance_checks, dict) else 0,
        "balance_mismatches": balance_checks.get("balance_mismatches", []) if isinstance(balance_checks, dict) else [],
    }


def _build_alerts(
    *,
    manifest_summary: dict[str, object],
    prepare_summary: dict[str, object],
    reconciliation_summary: dict[str, object],
    event_source: str,
    artifacts: dict[str, object],
    environment: dict[str, object],
    allow_warnings: bool,
) -> list[Alert]:
    alerts: list[Alert] = []
    if manifest_summary["live_trading_enabled"]:
        alerts.append(critical_alert("Manifest live trading enabled", "Sandbox manifest must keep live_trading_enabled=false."))
    if environment.get("live_trading_enabled"):
        alerts.append(critical_alert("Environment live trading enabled", "LIVE_TRADING_ENABLED must remain false for Phase 5.2."))
    if environment.get("exchange_key_env_detected"):
        alerts.append(critical_alert("Exchange key env detected", "Do not run Phase 5.2 with exchange API key environment variables loaded."))
    if not environment.get("global_kill_switch", True):
        alerts.append(warning_alert("Global kill switch disabled", "GLOBAL_KILL_SWITCH is not enabled in the current environment."))

    _upstream_alerts(alerts, "Sandbox prepare", str(prepare_summary["decision"]), allow_warnings)
    _upstream_alerts(alerts, "Sandbox reconciliation", str(reconciliation_summary["decision"]), allow_warnings)

    if int(manifest_summary["expected_orders"]) == 0:
        alerts.append(critical_alert("No expected orders", "Manifest contains no sandbox orders."))
    if int(reconciliation_summary["submitted_orders"]) != int(manifest_summary["expected_orders"]):
        alerts.append(critical_alert("Submission count mismatch", "Reconciliation did not submit every expected order."))
    if int(reconciliation_summary["terminal_orders"]) != int(manifest_summary["expected_orders"]):
        alerts.append(critical_alert("Terminal count mismatch", "Reconciliation did not terminally resolve every expected order."))
    if reconciliation_summary["unknown_client_order_ids"]:
        alerts.append(critical_alert("Unknown order ids", "Reconciliation observed unknown client order ids."))
    if reconciliation_summary["missing_terminal_orders"]:
        alerts.append(critical_alert("Missing terminal orders", "Some expected orders have no terminal event."))
    if reconciliation_summary["balance_mismatches"]:
        alerts.append(critical_alert("Balance mismatches", "Reconciliation reported balance mismatches."))

    if event_source == "replay":
        alerts.append(
            warning_alert(
                "External Hummingbot runtime pending",
                "Current gate uses replay events; run again with a real Hummingbot sandbox event export.",
            )
        )
    elif event_source == "hummingbot_export":
        if not artifacts.get("event_jsonl_exists"):
            alerts.append(critical_alert("Event JSONL missing", "The Hummingbot sandbox event JSONL file does not exist."))
    else:
        alerts.append(critical_alert("Invalid event source", f"Unsupported event source: {event_source}."))

    alerts.append(
        info_alert(
            "Live trading remains disabled",
            "Phase 5.2 is a sandbox session gate only and must not submit live orders.",
        )
    )
    return alerts


def _upstream_alerts(alerts: list[Alert], label: str, decision: str, allow_warnings: bool) -> None:
    if decision == "blocked":
        alerts.append(critical_alert(f"{label} blocked", f"{label} decision is blocked."))
    elif decision.endswith("_with_warnings"):
        alert_fn = warning_alert if allow_warnings else critical_alert
        alerts.append(alert_fn(f"{label} has warnings", f"{label} decision is {decision}."))
    elif decision in {"unknown", ""}:
        alerts.append(critical_alert(f"{label} unknown", f"{label} decision is missing."))


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "sandbox_session_ready_with_warnings"
    return "sandbox_session_ready"


def _operator_checklist(decision: str, event_source: str) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not start or continue the Hummingbot sandbox session.",
            "Fix every CRITICAL alert and regenerate the Phase 5.2 gate report.",
            "Keep live trading disabled.",
        )
    checklist = [
        "Start Hummingbot only in sandbox or paper mode.",
        "Load only the generated sandbox manifest; do not configure live exchange credentials.",
        "Export submitted, filled, completed, canceled, failed, disconnect, order exception, and balance events as JSONL.",
        "Run Phase 5.1 reconciliation on the exported JSONL before extending the session.",
        "Keep LIVE_TRADING_ENABLED=false.",
    ]
    if event_source == "replay":
        checklist.insert(0, "Repeat this gate with event_source=hummingbot_export after the real sandbox event export exists.")
    return tuple(checklist)


def _alert_counts(alerts: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        severity = str(alert.get("severity", "UNKNOWN"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts
