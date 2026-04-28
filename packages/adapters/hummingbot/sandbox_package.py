"""Build a handoff package for a Hummingbot sandbox session."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class SandboxPackageResult:
    decision: str
    generated_at: datetime
    session_id: str
    output_dir: str
    artifacts: dict[str, str]
    summary: dict[str, object]
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "output_dir": self.output_dir,
            "artifacts": self.artifacts,
            "summary": self.summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Sandbox Session Package",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.summary['strategy_id']}`",
            f"- Account: `{self.summary['account_id']}`",
            f"- Connector: `{self.summary['connector_name']}`",
            f"- Live trading enabled: `{self.summary['live_trading_enabled']}`",
            f"- Controller configs: `{self.summary['controller_config_count']}`",
            f"- Orders: `{self.summary['order_count']}`",
            f"- Total notional: `{self.summary['total_notional']}`",
            "",
            "## Artifacts",
            "",
        ]
        lines.extend(f"- {name}: `{path}`" for name, path in self.artifacts.items())
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


def build_sandbox_package(
    *,
    manifest: dict[str, Any],
    session_gate: dict[str, Any],
    output_dir: str | Path,
    allow_warnings: bool,
) -> SandboxPackageResult:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    session_id = str(session_gate.get("session_id", "hummingbot_sandbox_session"))
    controller_configs = _list_payload(manifest.get("controller_configs", []))
    orders = _list_payload(manifest.get("orders", []))
    summary = _summary(manifest, session_gate, controller_configs, orders)
    alerts = _build_alerts(summary=summary, session_gate=session_gate, allow_warnings=allow_warnings)
    decision = _decision(alerts)

    controller_dir = output_path / "controller_configs"
    controller_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}
    artifacts["manifest_json"] = str(_write_json(manifest, output_path / "manifest.json"))
    artifacts["controller_configs_json"] = str(
        _write_json(controller_configs, output_path / "controller_configs.json")
    )
    for controller_config in controller_configs:
        trading_pair = str(controller_config.get("trading_pair", "unknown"))
        filename = f"{_safe_name(trading_pair)}.json"
        _write_json(controller_config, controller_dir / filename)
    artifacts["orders_jsonl"] = str(_write_jsonl(orders, output_path / "orders.jsonl"))
    artifacts["expected_event_schema_json"] = str(
        _write_json(_expected_event_schema(), output_path / "expected_event_schema.json")
    )
    artifacts["event_capture_template_jsonl"] = str(
        _write_jsonl(_event_capture_templates(orders), output_path / "event_capture_template.jsonl")
    )
    artifacts["operator_runbook_md"] = str(
        _write_text(
            _runbook_markdown(
                session_id=session_id,
                summary=summary,
                artifacts=artifacts,
            ),
            output_path / "operator_runbook.md",
        )
    )

    generated_at = datetime.now(tz=UTC)
    artifacts["package_summary_json"] = str(output_path / "package_summary.json")
    artifacts["package_summary_md"] = str(output_path / "package_summary.md")
    result = SandboxPackageResult(
        decision=decision,
        generated_at=generated_at,
        session_id=session_id,
        output_dir=str(output_path),
        artifacts=artifacts,
        summary=summary,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision, summary),
    )
    _write_json(result.to_dict(), output_path / "package_summary.json")
    _write_text(result.to_markdown(), output_path / "package_summary.md")
    return result


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _summary(
    manifest: dict[str, Any],
    session_gate: dict[str, Any],
    controller_configs: list[dict[str, object]],
    orders: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "strategy_id": str(manifest.get("strategy_id", "")),
        "account_id": str(manifest.get("account_id", "")),
        "connector_name": str(manifest.get("connector_name", "")),
        "controller_name": str(manifest.get("controller_name", "")),
        "live_trading_enabled": bool(manifest.get("live_trading_enabled")),
        "controller_config_count": len(controller_configs),
        "order_count": len(orders),
        "total_notional": str(manifest.get("total_notional", "0")),
        "session_gate_decision": str(session_gate.get("decision", "unknown")),
        "session_gate_event_source": str(session_gate.get("event_source", "unknown")),
    }


def _build_alerts(
    *,
    summary: dict[str, object],
    session_gate: dict[str, Any],
    allow_warnings: bool,
) -> list[Alert]:
    alerts: list[Alert] = []
    if summary["live_trading_enabled"]:
        alerts.append(critical_alert("Live trading enabled", "Package manifest must keep live_trading_enabled=false."))
    if int(summary["controller_config_count"]) == 0:
        alerts.append(critical_alert("No controller configs", "Package cannot be built without controller configs."))
    if int(summary["order_count"]) == 0:
        alerts.append(critical_alert("No orders", "Package cannot be built without sandbox orders."))

    gate_decision = str(summary["session_gate_decision"])
    if gate_decision == "blocked":
        alerts.append(critical_alert("Session gate blocked", "Phase 5.2 session gate is blocked."))
    elif gate_decision.endswith("_with_warnings"):
        alert_fn = warning_alert if allow_warnings else critical_alert
        alerts.append(alert_fn("Session gate has warnings", f"Phase 5.2 session gate is {gate_decision}."))
    elif gate_decision in {"unknown", ""}:
        alerts.append(critical_alert("Session gate missing", "Phase 5.2 session gate decision is missing."))

    if str(summary["session_gate_event_source"]) == "replay":
        alerts.append(
            warning_alert(
                "Replay package only",
                "This package is based on replay gate output; rerun with real Hummingbot event export after the first sandbox session.",
            )
        )

    gate_alerts = session_gate.get("alerts", [])
    if isinstance(gate_alerts, list) and any(
        isinstance(alert, dict) and alert.get("severity") == "CRITICAL" for alert in gate_alerts
    ):
        alerts.append(critical_alert("Gate critical alerts", "Phase 5.2 gate contains CRITICAL alerts."))

    alerts.append(
        info_alert(
            "Package is not live execution",
            "Phase 5.3 exports sandbox handoff files only and does not submit orders.",
        )
    )
    return alerts


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "sandbox_package_ready_with_warnings"
    return "sandbox_package_ready"


def _recommended_actions(decision: str, summary: dict[str, object]) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not hand this package to a Hummingbot sandbox session.",
            "Fix all CRITICAL alerts and regenerate the package.",
            "Keep live trading disabled.",
        )
    actions = [
        "Review operator_runbook.md before starting Hummingbot.",
        "Load only the controller and order files from this package into Hummingbot sandbox or paper mode.",
        "Do not configure live exchange credentials.",
        "Export Hummingbot events to JSONL and rerun Phase 5.1 reconciliation.",
        "Rerun Phase 5.2 session gate with event_source=hummingbot_export.",
    ]
    if summary["session_gate_event_source"] == "replay":
        actions.insert(0, "Use this package for the first external sandbox dry run only.")
    return tuple(actions)


def _expected_event_schema() -> dict[str, object]:
    return {
        "schema_version": "hummingbot_sandbox_event_schema_v1",
        "required_order_event_fields": [
            "event_type",
            "created_at",
            "client_order_id",
            "trading_pair",
        ],
        "required_fill_fields": [
            "filled_amount",
            "average_fill_price",
        ],
        "required_balance_fields": [
            "event_type",
            "created_at",
            "balance_asset",
            "balance_total",
        ],
        "supported_event_types": [
            "submitted",
            "filled",
            "completed",
            "canceled",
            "failed",
            "disconnect",
            "order_exception",
            "balance",
            "balance_anomaly",
        ],
    }


def _event_capture_templates(orders: list[dict[str, object]]) -> list[dict[str, object]]:
    templates: list[dict[str, object]] = []
    for order in orders:
        templates.append(
            {
                "event_type": "submitted",
                "created_at": "<iso8601>",
                "client_order_id": order.get("client_order_id"),
                "trading_pair": order.get("trading_pair"),
                "side": order.get("side"),
            }
        )
        templates.append(
            {
                "event_type": "filled",
                "created_at": "<iso8601>",
                "client_order_id": order.get("client_order_id"),
                "trading_pair": order.get("trading_pair"),
                "side": order.get("side"),
                "filled_amount": "<actual filled amount>",
                "average_fill_price": "<actual fill price>",
                "fee_quote": "<fee in quote asset>",
            }
        )
    templates.append(
        {
            "event_type": "balance",
            "created_at": "<iso8601>",
            "balance_asset": "USDT",
            "balance_total": "<post-session total balance>",
        }
    )
    return templates


def _runbook_markdown(
    *,
    session_id: str,
    summary: dict[str, object],
    artifacts: dict[str, str],
) -> str:
    return "\n".join(
        [
            "# Hummingbot Sandbox Operator Runbook",
            "",
            f"- Session id: `{session_id}`",
            f"- Strategy: `{summary['strategy_id']}`",
            f"- Connector: `{summary['connector_name']}`",
            f"- Controller configs: `{summary['controller_config_count']}`",
            f"- Orders: `{summary['order_count']}`",
            f"- Live trading enabled: `{summary['live_trading_enabled']}`",
            "",
            "## Before Start",
            "",
            "- Confirm Hummingbot is in sandbox or paper mode.",
            "- Confirm no live exchange credentials are loaded.",
            "- Confirm `LIVE_TRADING_ENABLED=false` in this project.",
            "- Review controller configs and orders before loading them into Hummingbot.",
            "",
            "## Package Files",
            "",
            f"- Controller configs: `{artifacts.get('controller_configs_json')}`",
            f"- Orders JSONL: `{artifacts.get('orders_jsonl')}`",
            f"- Event schema: `{artifacts.get('expected_event_schema_json')}`",
            f"- Event template: `{artifacts.get('event_capture_template_jsonl')}`",
            "",
            "## After Session",
            "",
            "- Export Hummingbot submitted, filled, completed, canceled, failed, disconnect, order exception, and balance events as JSONL.",
            "- Run Phase 5.1 reconciliation using the exported JSONL.",
            "- Run Phase 5.2 session gate with `--event-source hummingbot_export`.",
            "- Do not proceed to longer sandbox observation if either command is blocked.",
            "",
        ]
    )


def _list_payload(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _write_json(payload: object, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_jsonl(records: list[dict[str, object]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, sort_keys=True))
            file.write("\n")
    return path


def _write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_").lower()
