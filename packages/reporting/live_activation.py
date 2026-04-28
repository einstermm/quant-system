"""Phase 6.2 live activation checklist gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str
from packages.data.simple_yaml import load_simple_yaml


@dataclass(frozen=True, slots=True)
class ActivationChecklistItem:
    item_id: str
    title: str
    status: str
    details: str
    evidence: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "status": self.status,
            "details": self.details,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class LiveActivationChecklist:
    decision: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    checklist: tuple[ActivationChecklistItem, ...]
    environment: dict[str, object]
    risk_summary: dict[str, object]
    runbook: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "checklist": [item.to_dict() for item in self.checklist],
            "environment": self.environment,
            "risk_summary": _json_safe(self.risk_summary),
            "runbook": list(self.runbook),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.2 Live Activation Checklist",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            "",
            "## Checklist",
            "",
        ]
        lines.extend(
            f"- `{item.status}` {item.title}: {item.details}"
            + (f" Evidence: `{item.evidence}`" if item.evidence else "")
            for item in self.checklist
        )
        lines.extend(
            [
                "",
                "## Environment",
                "",
                f"- Live trading enabled: `{self.environment['live_trading_enabled']}`",
                f"- Global kill switch: `{self.environment['global_kill_switch']}`",
                f"- Alert channel configured: `{self.environment['alert_channel_configured']}`",
                f"- Exchange key env detected: `{self.environment['exchange_key_env_detected']}`",
                "",
                "## Risk Summary",
                "",
                f"`{_json_safe(self.risk_summary)}`",
                "",
                "## Activation Runbook",
                "",
            ]
        )
        lines.extend(f"- {step}" for step in self.runbook)
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_activation_checklist(
    *,
    live_readiness: dict[str, Any],
    daily_report: dict[str, Any],
    tax_export_summary: dict[str, Any],
    live_risk_config: dict[str, Any],
    environment: dict[str, object],
    session_id: str,
    strategy_id: str,
    max_initial_live_order_notional: Decimal,
    manual_credentials_reviewed: bool = False,
    manual_exchange_allowlist_reviewed: bool = False,
    manual_operator_signoff: bool = False,
    artifacts: dict[str, str] | None = None,
) -> LiveActivationChecklist:
    risk_summary = _risk_summary(live_risk_config)
    checklist = _checklist(
        live_readiness=live_readiness,
        daily_report=daily_report,
        tax_export_summary=tax_export_summary,
        risk_summary=risk_summary,
        environment=environment,
        max_initial_live_order_notional=max_initial_live_order_notional,
        manual_credentials_reviewed=manual_credentials_reviewed,
        manual_exchange_allowlist_reviewed=manual_exchange_allowlist_reviewed,
        manual_operator_signoff=manual_operator_signoff,
    )
    decision = _decision(checklist)
    return LiveActivationChecklist(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=strategy_id,
        checklist=tuple(checklist),
        environment=environment,
        risk_summary=risk_summary,
        runbook=_runbook(decision),
        artifacts=artifacts or {},
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_risk_config(path: str | Path) -> dict[str, Any]:
    return load_simple_yaml(path)


def write_activation_checklist_json(report: LiveActivationChecklist, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_activation_checklist_markdown(report: LiveActivationChecklist, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def _checklist(
    *,
    live_readiness: dict[str, Any],
    daily_report: dict[str, Any],
    tax_export_summary: dict[str, Any],
    risk_summary: dict[str, object],
    environment: dict[str, object],
    max_initial_live_order_notional: Decimal,
    manual_credentials_reviewed: bool,
    manual_exchange_allowlist_reviewed: bool,
    manual_operator_signoff: bool,
) -> list[ActivationChecklistItem]:
    readiness_decision = str(live_readiness.get("decision", "unknown"))
    daily_status = str(daily_report.get("status", "unknown"))
    tax_status = str(tax_export_summary.get("status", "unknown"))
    expected_fills = _int(_dict(live_readiness.get("observation_summary")).get("filled_orders"))
    tax_rows = _int(tax_export_summary.get("row_count"))
    max_order_notional = risk_summary.get("max_order_notional_decimal")

    return [
        _auto_item(
            "phase_6_1_readiness",
            "Phase 6.1 readiness available",
            readiness_decision in {"live_preflight_ready", "live_preflight_ready_with_warnings"},
            f"Live readiness decision is {readiness_decision}.",
            str(_dict(live_readiness.get("artifacts")).get("observation_review_json", "")),
        ),
        _auto_item(
            "daily_report",
            "Daily report generated",
            daily_status in {"daily_report_ready", "daily_report_ready_with_warnings"},
            f"Daily report status is {daily_status}.",
        ),
        _auto_item(
            "tax_export",
            "Trade tax export generated",
            tax_status in {"tax_export_ready", "tax_export_ready_with_warnings"} and tax_rows >= expected_fills,
            f"Tax export status is {tax_status}; rows={tax_rows}, expected_filled_orders={expected_fills}.",
        ),
        _auto_item(
            "live_risk_cap",
            "Strict live risk cap configured",
            isinstance(max_order_notional, Decimal) and max_order_notional <= max_initial_live_order_notional,
            (
                f"max_order_notional={_decimal_or_unknown(max_order_notional)}; "
                f"approved_initial_cap={decimal_to_str(max_initial_live_order_notional)}."
            ),
        ),
        _auto_item(
            "live_disabled",
            "Live trading remains disabled",
            not bool(environment.get("live_trading_enabled")),
            "LIVE_TRADING_ENABLED must stay false until final manual signoff.",
        ),
        _auto_item(
            "kill_switch_enabled",
            "Global kill switch enabled",
            bool(environment.get("global_kill_switch")),
            "GLOBAL_KILL_SWITCH must stay true before activation.",
        ),
        _auto_item(
            "alert_channel",
            "External alert channel configured",
            bool(environment.get("alert_channel_configured")),
            "Configure and verify at least one alert channel before live activation.",
        ),
        _manual_item(
            "credential_scope",
            "Credential scope reviewed",
            manual_credentials_reviewed,
            "Confirm exchange keys are read-only/spot-trading scoped as intended, withdrawal disabled, and IP allowlist enabled where supported.",
        ),
        _manual_item(
            "exchange_allowlist",
            "Exchange allowlist reviewed",
            manual_exchange_allowlist_reviewed,
            "Confirm allowed symbols, quote asset, account, and connector are exactly the Phase 6 activation target.",
        ),
        _manual_item(
            "operator_signoff",
            "Operator activation signoff",
            manual_operator_signoff,
            "Human operator signs off the first live order batch size, kill switch procedure, and rollback plan.",
        ),
    ]


def _auto_item(item_id: str, title: str, passed: bool, details: str, evidence: str = "") -> ActivationChecklistItem:
    return ActivationChecklistItem(
        item_id=item_id,
        title=title,
        status="PASS" if passed else "FAIL",
        details=details,
        evidence=evidence,
    )


def _manual_item(item_id: str, title: str, signed: bool, details: str) -> ActivationChecklistItem:
    return ActivationChecklistItem(
        item_id=item_id,
        title=title,
        status="PASS" if signed else "MANUAL_REQUIRED",
        details=details,
    )


def _risk_summary(config: dict[str, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in (
        "max_order_notional",
        "max_symbol_notional",
        "max_gross_notional",
        "max_daily_loss",
        "max_drawdown_pct",
    ):
        value = config.get(key)
        result[key] = str(value) if value is not None else ""
        try:
            result[f"{key}_decimal"] = Decimal(str(value))
        except Exception:
            result[f"{key}_decimal"] = None
    return result


def _decision(checklist: list[ActivationChecklistItem]) -> str:
    if any(item.status == "FAIL" for item in checklist):
        return "live_activation_blocked"
    if any(item.status == "MANUAL_REQUIRED" for item in checklist):
        return "live_activation_pending_manual_signoff"
    return "live_activation_ready"


def _runbook(decision: str) -> tuple[str, ...]:
    if decision == "live_activation_blocked":
        return (
            "Do not enable live trading.",
            "Fix every FAIL checklist item and rerun Phase 6.2.",
            "Keep GLOBAL_KILL_SWITCH=true and LIVE_TRADING_ENABLED=false.",
        )
    if decision == "live_activation_pending_manual_signoff":
        return (
            "Do not enable live trading until all MANUAL_REQUIRED checklist items are signed off.",
            "Send and verify an external alert test before activation.",
            "Re-run Phase 6.2 with manual signoff flags only after operator review is complete.",
        )
    return (
        "Enable live trading only for the approved small-funds batch.",
        "Submit one controlled live batch and immediately rerun daily report, reconciliation, and tax export.",
        "If any alert fires, activate kill switch and follow the risk-off runbook.",
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _decimal_or_unknown(value: object) -> str:
    return decimal_to_str(value) if isinstance(value, Decimal) else "unknown"


def _json_safe(values: dict[str, object]) -> dict[str, object]:
    return {
        key: decimal_to_str(value) if isinstance(value, Decimal) else value
        for key, value in values.items()
    }
