"""Accept a Hummingbot sandbox event export and regenerate downstream gates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.sandbox_package import build_sandbox_package
from packages.adapters.hummingbot.sandbox_reconciliation import (
    SandboxReconciliationThresholds,
    SandboxRuntimeEvent,
    build_sandbox_reconciliation,
    write_events_jsonl,
    write_reconciliation_json,
    write_reconciliation_markdown,
)
from packages.adapters.hummingbot.sandbox_session import (
    build_sandbox_session_gate,
    write_session_gate_json,
    write_session_gate_markdown,
)
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class SandboxExportAcceptanceResult:
    decision: str
    generated_at: datetime
    session_id: str
    event_source: str
    output_dir: str
    artifacts: dict[str, str]
    reconciliation_summary: dict[str, object]
    session_gate_summary: dict[str, object]
    package_summary: dict[str, object]
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "event_source": self.event_source,
            "output_dir": self.output_dir,
            "artifacts": self.artifacts,
            "reconciliation_summary": self.reconciliation_summary,
            "session_gate_summary": self.session_gate_summary,
            "package_summary": self.package_summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Sandbox Export Acceptance",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Event source: `{self.event_source}`",
            "",
            "## Reconciliation",
            "",
            f"- Decision: `{self.reconciliation_summary['decision']}`",
            f"- Events: `{self.reconciliation_summary['event_count']}`",
            f"- Submitted orders: `{self.reconciliation_summary['submitted_orders']}`",
            f"- Terminal orders: `{self.reconciliation_summary['terminal_orders']}`",
            f"- Balance events: `{self.reconciliation_summary['balance_events']}`",
            "",
            "## Session Gate",
            "",
            f"- Decision: `{self.session_gate_summary['decision']}`",
            f"- Live trading enabled: `{self.session_gate_summary['live_trading_enabled']}`",
            f"- Exchange key env detected: `{self.session_gate_summary['exchange_key_env_detected']}`",
            "",
            "## Package",
            "",
            f"- Decision: `{self.package_summary['decision']}`",
            f"- Output dir: `{self.package_summary['output_dir']}`",
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
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def build_sandbox_export_acceptance(
    *,
    manifest: dict[str, Any],
    prepare_report: dict[str, Any],
    events: tuple[SandboxRuntimeEvent, ...],
    event_jsonl: str | Path,
    output_dir: str | Path,
    session_id: str,
    event_source: str,
    starting_quote_balance: Decimal | None,
    quote_asset: str,
    environment: dict[str, object],
    allow_warnings: bool,
    thresholds: SandboxReconciliationThresholds | None = None,
) -> SandboxExportAcceptanceResult:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    event_path = Path(event_jsonl)
    artifacts: dict[str, str] = {
        "event_jsonl": str(event_path),
        "normalized_events_jsonl": str(output_path / "normalized_events.jsonl"),
        "reconciliation_json": str(output_path / "reconciliation.json"),
        "reconciliation_md": str(output_path / "reconciliation.md"),
        "session_gate_json": str(output_path / "session_gate.json"),
        "session_gate_md": str(output_path / "session_gate.md"),
        "session_package_dir": str(output_path / "session_package"),
        "acceptance_json": str(output_path / "acceptance.json"),
        "acceptance_md": str(output_path / "acceptance.md"),
    }

    write_events_jsonl(events, artifacts["normalized_events_jsonl"])
    reconciliation = build_sandbox_reconciliation(
        manifest=manifest,
        events=events,
        starting_quote_balance=starting_quote_balance,
        quote_asset=quote_asset,
        thresholds=thresholds,
    )
    write_reconciliation_json(reconciliation, artifacts["reconciliation_json"])
    write_reconciliation_markdown(reconciliation, artifacts["reconciliation_md"])

    session_gate = build_sandbox_session_gate(
        manifest=manifest,
        prepare_report=prepare_report,
        reconciliation_report=reconciliation.to_dict(),
        session_id=session_id,
        event_source=event_source,
        artifacts={
            "event_jsonl": str(event_path),
            "event_jsonl_exists": event_path.exists(),
            "reconciliation_json": artifacts["reconciliation_json"],
        },
        environment=environment,
        allow_warnings=allow_warnings,
    )
    write_session_gate_json(session_gate, artifacts["session_gate_json"])
    write_session_gate_markdown(session_gate, artifacts["session_gate_md"])

    package = build_sandbox_package(
        manifest=manifest,
        session_gate=session_gate.to_dict(),
        output_dir=artifacts["session_package_dir"],
        allow_warnings=allow_warnings,
    )
    reconciliation_summary = _reconciliation_summary(reconciliation.to_dict(), events)
    session_gate_summary = _session_gate_summary(session_gate.to_dict())
    package_summary = {
        "decision": package.decision,
        "output_dir": package.output_dir,
        "artifact_count": len(package.artifacts),
    }
    alerts = _build_alerts(
        event_source=event_source,
        reconciliation_decision=reconciliation.decision,
        session_gate_decision=session_gate.decision,
        package_decision=package.decision,
        allow_warnings=allow_warnings,
    )
    decision = _decision(alerts)
    result = SandboxExportAcceptanceResult(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        event_source=event_source,
        output_dir=str(output_path),
        artifacts=artifacts,
        reconciliation_summary=reconciliation_summary,
        session_gate_summary=session_gate_summary,
        package_summary=package_summary,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision, event_source),
    )
    write_acceptance_json(result, artifacts["acceptance_json"])
    write_acceptance_markdown(result, artifacts["acceptance_md"])
    return result


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_acceptance_json(result: SandboxExportAcceptanceResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_acceptance_markdown(result: SandboxExportAcceptanceResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return output_path


def _build_alerts(
    *,
    event_source: str,
    reconciliation_decision: str,
    session_gate_decision: str,
    package_decision: str,
    allow_warnings: bool,
) -> list[Alert]:
    alerts: list[Alert] = []
    _decision_alert(alerts, "Reconciliation", reconciliation_decision, allow_warnings)
    _decision_alert(alerts, "Session gate", session_gate_decision, allow_warnings)
    _decision_alert(alerts, "Handoff package", package_decision, allow_warnings)
    if event_source == "replay":
        alerts.append(
            warning_alert(
                "Replay acceptance only",
                "This acceptance run used replay events, not a real Hummingbot sandbox export.",
            )
        )
    elif event_source != "hummingbot_export":
        alerts.append(critical_alert("Invalid event source", f"Unsupported event source: {event_source}."))
    alerts.append(
        info_alert(
            "Live trading remains disabled",
            "Phase 5.4 accepts sandbox exports only and does not submit live orders.",
        )
    )
    return alerts


def _decision_alert(alerts: list[Alert], label: str, decision: str, allow_warnings: bool) -> None:
    if decision == "blocked":
        alerts.append(critical_alert(f"{label} blocked", f"{label} decision is blocked."))
    elif decision.endswith("_with_warnings"):
        alert_fn = warning_alert if allow_warnings else critical_alert
        alerts.append(alert_fn(f"{label} has warnings", f"{label} decision is {decision}."))
    elif decision in {"unknown", ""}:
        alerts.append(critical_alert(f"{label} missing", f"{label} decision is missing."))


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "sandbox_export_accepted_with_warnings"
    return "sandbox_export_accepted"


def _recommended_actions(decision: str, event_source: str) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not extend the Hummingbot sandbox session.",
            "Fix all CRITICAL alerts and rerun Phase 5.4.",
            "Keep live trading disabled.",
        )
    actions = [
        "Review reconciliation.md and session_gate.md.",
        "Use the regenerated session_package only for sandbox or paper mode.",
        "Keep live trading disabled.",
    ]
    if event_source == "replay":
        actions.insert(0, "Repeat Phase 5.4 with event_source=hummingbot_export after a real sandbox dry run.")
    else:
        actions.append("If operator review passes, proceed to a longer sandbox observation window.")
    return tuple(actions)


def _reconciliation_summary(payload: dict[str, object], events: tuple[SandboxRuntimeEvent, ...]) -> dict[str, object]:
    order_checks = payload.get("order_checks", {})
    balance_checks = payload.get("balance_checks", {})
    if not isinstance(order_checks, dict):
        order_checks = {}
    if not isinstance(balance_checks, dict):
        balance_checks = {}
    return {
        "decision": payload.get("decision", "unknown"),
        "event_count": len(events),
        "submitted_orders": order_checks.get("submitted_orders", 0),
        "terminal_orders": order_checks.get("terminal_orders", 0),
        "filled_orders": order_checks.get("filled_orders", 0),
        "balance_events": balance_checks.get("balance_events", 0),
    }


def _session_gate_summary(payload: dict[str, object]) -> dict[str, object]:
    environment = payload.get("environment", {})
    if not isinstance(environment, dict):
        environment = {}
    return {
        "decision": payload.get("decision", "unknown"),
        "live_trading_enabled": environment.get("live_trading_enabled", "unknown"),
        "exchange_key_env_detected": environment.get("exchange_key_env_detected", "unknown"),
    }
