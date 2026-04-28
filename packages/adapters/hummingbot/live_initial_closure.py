"""Phase 6.9 initial-version closure and position lifecycle plan."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class InitialClosureReport:
    status: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    account_id: str
    closure_summary: dict[str, object]
    next_live_decision: dict[str, object]
    position_lifecycle_plan: dict[str, object]
    remaining_work: tuple[dict[str, object], ...]
    alerts: tuple[Alert, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "closure_summary": self.closure_summary,
            "next_live_decision": self.next_live_decision,
            "position_lifecycle_plan": self.position_lifecycle_plan,
            "remaining_work": list(self.remaining_work),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.9 Initial Closure and Position Lifecycle Plan",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Status: `{self.status}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Account: `{self.account_id}`",
            "",
            "## Closure",
            "",
            f"- Initial flow closed: `{self.closure_summary['initial_flow_closed']}`",
            f"- Evidence complete: `{self.closure_summary['evidence_complete']}`",
            f"- Post-trade reconciled: `{self.closure_summary['post_trade_reconciled']}`",
            f"- Manual open orders clean: `{self.closure_summary['manual_open_orders_clean']}`",
            f"- Runner disarmed: `{self.closure_summary['runner_disarmed']}`",
            "",
            "## Next Live Decision",
            "",
            f"- Decision: `{self.next_live_decision['decision']}`",
            f"- Reason: `{self.next_live_decision['reason']}`",
            f"- Cooldown elapsed: `{self.next_live_decision['cooldown_elapsed']}`",
            f"- Next review not before: `{self.next_live_decision['next_review_not_before']}`",
            "",
            "## Position Lifecycle",
            "",
            f"- Stance: `{self.position_lifecycle_plan['stance']}`",
            f"- Trading pair: `{self.position_lifecycle_plan['trading_pair']}`",
            "- Strategy net base quantity: "
            f"`{self.position_lifecycle_plan['strategy_net_base_quantity']}`",
            f"- Entry cost basis quote: `{self.position_lifecycle_plan['entry_cost_basis_quote']}`",
            "- Account ending base balance: "
            f"`{self.position_lifecycle_plan['account_ending_base_balance']}`",
            "- Exit requires activation: "
            f"`{self.position_lifecycle_plan['exit_requires_activation']}`",
            "",
            "## Remaining Work",
            "",
        ]
        lines.extend(
            f"- `{item['priority']}` {item['title']}: {item['details']}"
            for item in self.remaining_work
        )
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(
                f"- `{alert.severity}` {alert.title}: {alert.message}"
                for alert in self.alerts
            )
        else:
            lines.append("- None")
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_initial_closure_report(
    *,
    post_trade_report: dict[str, Any],
    cooldown_review: dict[str, Any],
    session_id: str,
    generated_at: datetime | None = None,
    artifacts: dict[str, str] | None = None,
) -> InitialClosureReport:
    generated = generated_at or datetime.now(tz=UTC)
    closure_summary = _closure_summary(post_trade_report, cooldown_review)
    next_live_decision = _next_live_decision(cooldown_review)
    position_lifecycle_plan = _position_lifecycle_plan(post_trade_report)
    remaining_work = _remaining_work(next_live_decision)
    alerts = _alerts(
        closure_summary=closure_summary,
        next_live_decision=next_live_decision,
        position_lifecycle_plan=position_lifecycle_plan,
    )
    return InitialClosureReport(
        status=_status(alerts, closure_summary),
        generated_at=generated,
        session_id=session_id,
        strategy_id=str(post_trade_report.get("strategy_id", "")),
        account_id=str(post_trade_report.get("account_id", "")),
        closure_summary=closure_summary,
        next_live_decision=next_live_decision,
        position_lifecycle_plan=position_lifecycle_plan,
        remaining_work=remaining_work,
        alerts=tuple(alerts),
        artifacts=artifacts or {},
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_report_json(report: InitialClosureReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_report_markdown(report: InitialClosureReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def _closure_summary(
    post_trade_report: dict[str, Any],
    cooldown_review: dict[str, Any],
) -> dict[str, object]:
    post_trade_status = str(post_trade_report.get("status", ""))
    order_checks = _dict(post_trade_report.get("order_checks"))
    balance_checks = _dict(post_trade_report.get("balance_checks"))
    risk_checks = _dict(post_trade_report.get("risk_checks"))
    operational = _dict(cooldown_review.get("operational_checks"))
    manual_checks = _dict(cooldown_review.get("manual_checks"))
    post_trade_reconciled = post_trade_status.startswith("live_post_trade_reconciled")
    order_evidence_complete = (
        int(order_checks.get("submitted_orders", 0)) == 1
        and int(order_checks.get("filled_orders", 0)) == 1
        and int(order_checks.get("db_fills", 0)) == 1
        and not order_checks.get("missing_submissions")
        and not order_checks.get("missing_fills")
        and not order_checks.get("missing_db_fills")
    )
    balance_clean = (
        balance_checks.get("status") == "checked"
        and not balance_checks.get("mismatches")
    )
    risk_caps_passed = all(
        bool(risk_checks.get(key))
        for key in (
            "total_notional_inside_cap",
            "order_count_inside_cap",
            "price_deviation_inside_cap",
        )
    )
    runner_disarmed = operational.get("runner_config_armed") is False
    manual_clean = manual_checks.get("open_orders_check_status") == "confirmed_clean"
    evidence_complete = all(
        (
            post_trade_reconciled,
            order_evidence_complete,
            balance_clean,
            risk_caps_passed,
            manual_clean,
        )
    )
    return {
        "initial_flow_closed": evidence_complete and runner_disarmed,
        "evidence_complete": evidence_complete,
        "post_trade_reconciled": post_trade_reconciled,
        "order_evidence_complete": order_evidence_complete,
        "balance_clean": balance_clean,
        "risk_caps_passed": risk_caps_passed,
        "manual_open_orders_clean": manual_clean,
        "runner_disarmed": runner_disarmed,
        "tax_export_final": False,
        "mqtt_bridge_ready": False,
    }


def _next_live_decision(cooldown_review: dict[str, Any]) -> dict[str, object]:
    cooldown_window = _dict(cooldown_review.get("cooldown_window"))
    expansion = _dict(cooldown_review.get("expansion_controls"))
    cooldown_elapsed = bool(cooldown_window.get("cooldown_elapsed"))
    expansion_allowed = bool(expansion.get("expansion_allowed"))
    if not cooldown_elapsed:
        decision = "NO_GO_COOLDOWN_ACTIVE"
        reason = "24 hour cooldown window has not elapsed."
    elif expansion_allowed:
        decision = "NO_GO_EXPANSION_FLAG_UNEXPECTED"
        reason = "Expansion must remain disabled for this initial version."
    else:
        decision = "GO_FOR_OPERATOR_REVIEW_ONLY"
        reason = "Cooldown elapsed; a new operator signoff is still required before live trading."
    return {
        "decision": decision,
        "reason": reason,
        "cooldown_elapsed": cooldown_elapsed,
        "next_review_not_before": str(cooldown_window.get("next_review_not_before", "")),
        "expansion_allowed": expansion_allowed,
        "allowed_pairs": list(expansion.get("allowed_pairs", [])),
        "max_batch_notional": str(expansion.get("max_batch_notional", "")),
        "max_order_notional": str(expansion.get("max_order_notional", "")),
        "new_live_batch_requires_operator_signoff": True,
    }


def _position_lifecycle_plan(post_trade_report: dict[str, Any]) -> dict[str, object]:
    fills = _dict(post_trade_report.get("fill_summary"))
    balance_checks = _dict(post_trade_report.get("balance_checks"))
    fill_rows = fills.get("fills", [])
    first_fill = fill_rows[0] if isinstance(fill_rows, list) and fill_rows else {}
    if not isinstance(first_fill, dict):
        first_fill = {}
    return {
        "stance": "HOLD_UNDER_OBSERVATION",
        "trading_pair": str(first_fill.get("trading_pair", "BTC-USDT")),
        "side_opened": str(first_fill.get("side", "buy")),
        "strategy_net_base_quantity": str(fills.get("net_base_quantity", "")),
        "strategy_gross_base_quantity": str(fills.get("gross_base_quantity", "")),
        "entry_average_price_quote": str(fills.get("average_price_quote", "")),
        "entry_gross_quote_notional": str(fills.get("gross_quote_notional", "")),
        "entry_cost_basis_quote": str(fills.get("cost_basis_quote_estimate", "")),
        "fee_asset": str(fills.get("fee_asset", "")),
        "fee_amount": str(fills.get("fee_amount", "")),
        "account_ending_base_balance": str(
            _dict(balance_checks.get("ending_balances")).get("BTC", "")
        ),
        "exit_requires_activation": True,
        "exit_plan": (
            "No automatic exit is armed. If the operator chooses to close this position, "
            "generate a separate one-shot sell runner capped by available BTC and risk limits."
        ),
        "hold_until": "Next completed cooldown review or explicit operator exit signoff.",
    }


def _remaining_work(next_live_decision: dict[str, object]) -> tuple[dict[str, object], ...]:
    return (
        _item(
            "P0",
            "Complete cooldown review",
            f"Wait until {next_live_decision['next_review_not_before']} and rerun Phase 6.8.",
        ),
        _item(
            "P0",
            "Keep live expansion disabled",
            "Do not increase pair coverage, order count, or notional caps in the initial version.",
        ),
        _item(
            "P1",
            "Decide BTC position lifecycle",
            "Hold the small BTC position under observation or create a separately "
            "approved exit plan.",
        ),
        _item(
            "P1",
            "Resolve MQTT bridge warning",
            "Fix or intentionally disable MQTT before any longer live-running Hummingbot session.",
        ),
        _item(
            "P2",
            "Replace validation tax FX",
            "Use a real CAD FX source and ACB lot matching before relying on tax exports.",
        ),
        _item(
            "P2",
            "Freeze v0 runbook",
            "Document the exact data-to-live-to-reconciliation command sequence for "
            "the initial version.",
        ),
    )


def _alerts(
    *,
    closure_summary: dict[str, object],
    next_live_decision: dict[str, object],
    position_lifecycle_plan: dict[str, object],
) -> list[Alert]:
    alerts: list[Alert] = []
    if not closure_summary["initial_flow_closed"]:
        alerts.append(
            critical_alert("Initial flow not closed", "Required closure evidence is incomplete.")
        )
    if next_live_decision["decision"] != "GO_FOR_OPERATOR_REVIEW_ONLY":
        alerts.append(
            warning_alert(
                "Next live batch not allowed",
                str(next_live_decision["reason"]),
            )
        )
    if not closure_summary["tax_export_final"]:
        alerts.append(
            warning_alert(
                "Tax export not final",
                "Tax export still uses validation-only assumptions.",
            )
        )
    if not closure_summary["mqtt_bridge_ready"]:
        alerts.append(
            warning_alert("MQTT bridge not ready", "MQTT bridge warning remains unresolved.")
        )
    if position_lifecycle_plan["stance"] == "HOLD_UNDER_OBSERVATION":
        alerts.append(
            info_alert(
                "Position hold plan",
                "The initial BTC position remains held under observation; no exit is armed.",
            )
        )
    return alerts


def _status(alerts: tuple[Alert, ...] | list[Alert], closure_summary: dict[str, object]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "initial_closure_blocked"
    if not closure_summary["initial_flow_closed"]:
        return "initial_closure_blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "initial_v0_flow_closed_with_warnings"
    return "initial_v0_flow_closed"


def _item(priority: str, title: str, details: str) -> dict[str, object]:
    return {"priority": priority, "title": title, "details": details}


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
