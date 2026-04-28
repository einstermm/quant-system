"""Phase 6.8 cooldown review after the first live batch."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class LiveCooldownReview:
    status: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    account_id: str
    cooldown_window: dict[str, object]
    post_trade_summary: dict[str, object]
    manual_checks: dict[str, object]
    operational_checks: dict[str, object]
    expansion_controls: dict[str, object]
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "cooldown_window": self.cooldown_window,
            "post_trade_summary": self.post_trade_summary,
            "manual_checks": self.manual_checks,
            "operational_checks": self.operational_checks,
            "expansion_controls": self.expansion_controls,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.8 Live Cooldown Review",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Status: `{self.status}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Account: `{self.account_id}`",
            "",
            "## Cooldown",
            "",
            f"- Completed at: `{self.cooldown_window['completed_at']}`",
            f"- Minimum cooldown hours: `{self.cooldown_window['minimum_cooldown_hours']}`",
            f"- Elapsed hours: `{self.cooldown_window['elapsed_hours']}`",
            f"- Next review not before: `{self.cooldown_window['next_review_not_before']}`",
            f"- Cooldown elapsed: `{self.cooldown_window['cooldown_elapsed']}`",
            "",
            "## Post Trade",
            "",
            f"- Post-trade status: `{self.post_trade_summary['post_trade_status']}`",
            f"- Submitted / filled / DB fills: `{self.post_trade_summary['submitted_filled_db']}`",
            f"- Gross quote notional: `{self.post_trade_summary['gross_quote_notional']}`",
            f"- Net base quantity: `{self.post_trade_summary['net_base_quantity']}`",
            f"- Balance mismatches: `{self.post_trade_summary['balance_mismatches']}`",
            f"- Risk caps passed: `{self.post_trade_summary['risk_caps_passed']}`",
            "",
            "## Manual Checks",
            "",
            f"- Open orders check status: `{self.manual_checks['open_orders_check_status']}`",
            f"- Abnormal open orders found: `{self.manual_checks['abnormal_open_orders_found']}`",
            f"- Checked at: `{self.manual_checks['checked_at']}`",
            f"- Evidence: `{self.manual_checks['evidence']}`",
            "",
            "## Operational",
            "",
            f"- Runner container status: `{self.operational_checks['runner_container_status']}`",
            "- Hummingbot container status: "
            f"`{self.operational_checks['hummingbot_container_status']}`",
            f"- Event log lines: `{self.operational_checks['event_log_lines']}`",
            f"- Event log last event: `{self.operational_checks['event_log_last_event_type']}`",
            f"- Runner config armed: `{self.operational_checks['runner_config_armed']}`",
            "",
            "## Expansion Controls",
            "",
            f"- Allowlist locked: `{self.expansion_controls['allowlist_locked']}`",
            f"- Allowed pairs: `{self.expansion_controls['allowed_pairs']}`",
            f"- Max batch notional: `{self.expansion_controls['max_batch_notional']}`",
            f"- Max order notional: `{self.expansion_controls['max_order_notional']}`",
            f"- Expansion allowed: `{self.expansion_controls['expansion_allowed']}`",
            "",
            "## Alerts",
            "",
        ]
        if self.alerts:
            lines.extend(
                f"- `{alert.severity}` {alert.title}: {alert.message}"
                for alert in self.alerts
            )
        else:
            lines.append("- None")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_cooldown_review(
    *,
    post_trade_report: dict[str, Any],
    event_jsonl: str | Path,
    runner_config_yml: str | Path,
    session_id: str,
    minimum_cooldown_hours: Decimal,
    generated_at: datetime | None = None,
    manual_open_orders_check: dict[str, Any] | None = None,
    runner_container_status: str = "",
    hummingbot_container_status: str = "",
    artifacts: dict[str, str] | None = None,
) -> LiveCooldownReview:
    generated = generated_at or datetime.now(tz=UTC)
    event_stats = _event_log_stats(event_jsonl)
    cooldown_window = _cooldown_window(
        completed_at=event_stats["last_event_at"],
        generated_at=generated,
        minimum_cooldown_hours=minimum_cooldown_hours,
    )
    post_trade_summary = _post_trade_summary(post_trade_report)
    manual_checks = _manual_checks(manual_open_orders_check)
    operational_checks = {
        "runner_container_status": runner_container_status,
        "hummingbot_container_status": hummingbot_container_status,
        "event_log_lines": event_stats["line_count"],
        "event_log_last_event_type": event_stats["last_event_type"],
        "event_log_last_event_at": event_stats["last_event_at"].isoformat(),
        "runner_config_armed": _runner_config_armed(runner_config_yml),
    }
    expansion_controls = _expansion_controls(post_trade_report)
    alerts = _alerts(
        cooldown_window=cooldown_window,
        post_trade_summary=post_trade_summary,
        manual_checks=manual_checks,
        operational_checks=operational_checks,
        expansion_controls=expansion_controls,
        post_trade_alerts=_post_trade_alerts(post_trade_report),
    )
    review = LiveCooldownReview(
        status=_status(alerts, cooldown_elapsed=bool(cooldown_window["cooldown_elapsed"])),
        generated_at=generated,
        session_id=session_id,
        strategy_id=str(post_trade_report.get("strategy_id", "")),
        account_id=str(post_trade_report.get("account_id", "")),
        cooldown_window=cooldown_window,
        post_trade_summary=post_trade_summary,
        manual_checks=manual_checks,
        operational_checks=operational_checks,
        expansion_controls=expansion_controls,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(cooldown_window, manual_checks, alerts),
        artifacts=artifacts or {},
    )
    return review


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_review_json(review: LiveCooldownReview, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_review_markdown(review: LiveCooldownReview, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(review.to_markdown(), encoding="utf-8")
    return output_path


def _event_log_stats(path: str | Path) -> dict[str, object]:
    last_event: dict[str, Any] | None = None
    line_count = 0
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            line_count += 1
            last_event = json.loads(stripped)
    if last_event is None:
        raise ValueError(f"event log is empty: {path}")
    return {
        "line_count": line_count,
        "last_event_type": str(last_event.get("event_type", "")),
        "last_event_at": _parse_datetime(str(last_event.get("created_at", ""))),
    }


def _cooldown_window(
    *,
    completed_at: datetime,
    generated_at: datetime,
    minimum_cooldown_hours: Decimal,
) -> dict[str, object]:
    minimum_seconds = int(minimum_cooldown_hours * Decimal("3600"))
    next_review = completed_at + timedelta(seconds=minimum_seconds)
    elapsed_hours = Decimal(str((generated_at - completed_at).total_seconds())) / Decimal("3600")
    return {
        "completed_at": completed_at.isoformat(),
        "generated_at": generated_at.isoformat(),
        "minimum_cooldown_hours": decimal_to_str(minimum_cooldown_hours),
        "elapsed_hours": decimal_to_str(elapsed_hours),
        "next_review_not_before": next_review.isoformat(),
        "cooldown_elapsed": generated_at >= next_review,
    }


def _post_trade_summary(report: dict[str, Any]) -> dict[str, object]:
    order_checks = _dict(report.get("order_checks"))
    balance_checks = _dict(report.get("balance_checks"))
    risk_checks = _dict(report.get("risk_checks"))
    fill_summary = _dict(report.get("fill_summary"))
    submitted_filled_db = (
        f"{order_checks.get('submitted_orders', 0)} / "
        f"{order_checks.get('filled_orders', 0)} / "
        f"{order_checks.get('db_fills', 0)}"
    )
    risk_caps_passed = all(
        bool(risk_checks.get(key))
        for key in (
            "total_notional_inside_cap",
            "order_count_inside_cap",
            "price_deviation_inside_cap",
        )
    )
    return {
        "post_trade_status": str(report.get("status", "")),
        "submitted_filled_db": submitted_filled_db,
        "gross_quote_notional": str(fill_summary.get("gross_quote_notional", "")),
        "net_base_quantity": str(fill_summary.get("net_base_quantity", "")),
        "balance_mismatches": list(balance_checks.get("mismatches", [])),
        "risk_caps_passed": risk_caps_passed,
        "missing_submissions": list(order_checks.get("missing_submissions", [])),
        "missing_fills": list(order_checks.get("missing_fills", [])),
        "missing_db_fills": list(order_checks.get("missing_db_fills", [])),
    }


def _manual_checks(manual_open_orders_check: dict[str, Any] | None) -> dict[str, object]:
    if manual_open_orders_check is None:
        return {
            "open_orders_check_status": "pending",
            "abnormal_open_orders_found": None,
            "checked_at": "",
            "evidence": "",
        }
    abnormal = bool(manual_open_orders_check.get("abnormal_open_orders_found"))
    status = "confirmed_clean" if not abnormal else "abnormal_open_orders_found"
    return {
        "open_orders_check_status": status,
        "abnormal_open_orders_found": abnormal,
        "checked_at": str(manual_open_orders_check.get("checked_at", "")),
        "evidence": str(manual_open_orders_check.get("evidence", "")),
    }


def _expansion_controls(report: dict[str, Any]) -> dict[str, object]:
    risk_checks = _dict(report.get("risk_checks"))
    return {
        "allowlist_locked": True,
        "allowed_pairs": list(risk_checks.get("allowed_pairs", [])),
        "max_batch_notional": str(risk_checks.get("max_batch_notional", "")),
        "max_order_notional": str(risk_checks.get("max_order_notional", "")),
        "expansion_allowed": False,
        "reason": "Phase 6.8 is cooldown review only; no pair or notional expansion is allowed.",
    }


def _alerts(
    *,
    cooldown_window: dict[str, object],
    post_trade_summary: dict[str, object],
    manual_checks: dict[str, object],
    operational_checks: dict[str, object],
    expansion_controls: dict[str, object],
    post_trade_alerts: tuple[dict[str, object], ...],
) -> list[Alert]:
    alerts: list[Alert] = []
    if not str(post_trade_summary["post_trade_status"]).startswith("live_post_trade_reconciled"):
        alerts.append(critical_alert("Post-trade not reconciled", "Phase 6.7 is not reconciled."))
    if post_trade_summary["missing_submissions"] or post_trade_summary["missing_fills"]:
        alerts.append(
            critical_alert("Order evidence incomplete", "Live order evidence is incomplete.")
        )
    if post_trade_summary["missing_db_fills"]:
        alerts.append(
            critical_alert("DB fill missing", "Hummingbot SQLite fill evidence is missing.")
        )
    if manual_checks["open_orders_check_status"] == "pending":
        alerts.append(
            warning_alert(
                "Manual open orders check pending",
                "Operator has not yet recorded the Binance open orders check.",
            )
        )
    if manual_checks["abnormal_open_orders_found"]:
        alerts.append(
            critical_alert(
                "Abnormal open orders found",
                "Operator reported abnormal open orders after the live batch.",
            )
        )
    if post_trade_summary["balance_mismatches"]:
        alerts.append(critical_alert("Balance mismatch", "Phase 6.7 reported balance mismatches."))
    if not post_trade_summary["risk_caps_passed"]:
        alerts.append(
            critical_alert("Risk cap check failed", "Phase 6.7 risk cap checks did not pass.")
        )
    if operational_checks["event_log_last_event_type"] != "session_completed":
        alerts.append(
            critical_alert("Event log still open", "Last live event is not session_completed.")
        )
    if _container_running(str(operational_checks["runner_container_status"])):
        alerts.append(
            critical_alert("Live runner still running", "One-shot live runner is still running.")
        )
    if _container_running(str(operational_checks["hummingbot_container_status"])):
        alerts.append(
            warning_alert("Hummingbot container running", "Hummingbot is running during cooldown.")
        )
    if operational_checks["runner_config_armed"]:
        alerts.append(
            warning_alert("Runner config armed", "Installed one-shot live config remains armed.")
        )
    if not cooldown_window["cooldown_elapsed"]:
        alerts.append(
            warning_alert(
                "Cooldown active",
                "Minimum cooldown window has not elapsed; do not start another live batch.",
            )
        )
    for alert in post_trade_alerts:
        if alert.get("severity") == "WARN":
            alerts.append(
                warning_alert(
                    f"Carried post-trade warning: {alert.get('title', '')}",
                    str(alert.get("message", "")),
                )
            )
    if expansion_controls["expansion_allowed"]:
        alerts.append(
            critical_alert("Expansion enabled", "Expansion must remain disabled in Phase 6.8.")
        )
    if not alerts:
        alerts.append(
            info_alert("Cooldown review ready", "Cooldown review has no blocking issues.")
        )
    return alerts


def _recommended_actions(
    cooldown_window: dict[str, object],
    manual_checks: dict[str, object],
    alerts: tuple[Alert, ...] | list[Alert],
) -> tuple[str, ...]:
    actions = [
        "Do not run another live batch until the cooldown window has elapsed.",
        "Do not expand beyond BTC-USDT / ETH-USDT or the 50 USDT low-funds cap.",
        "Keep the Phase 6.6 one-shot runner config disarmed unless a new activation is approved.",
        "Fix or intentionally disable the MQTT bridge before any larger live session.",
        "Replace validation-only FX with a real CAD FX source before using exports for tax filing.",
    ]
    if cooldown_window["cooldown_elapsed"]:
        actions[0] = "Cooldown elapsed; perform a manual operator review before any new activation."
    if manual_checks["open_orders_check_status"] != "confirmed_clean":
        actions.insert(
            2,
            "Manually confirm Binance has no unexpected open orders after the live batch.",
        )
    else:
        actions.insert(
            2,
            "Open orders manual check is complete; keep the evidence with Phase 6.8 artifacts.",
        )
    if any(alert.severity == "CRITICAL" for alert in alerts):
        actions.insert(0, "Treat Phase 6.8 as blocked until all CRITICAL alerts are resolved.")
    return tuple(actions)


def _status(alerts: tuple[Alert, ...] | list[Alert], *, cooldown_elapsed: bool) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "live_cooldown_blocked"
    if cooldown_elapsed:
        if any(alert.severity == "WARN" for alert in alerts):
            return "live_cooldown_elapsed_with_warnings"
        return "live_cooldown_elapsed"
    if any(alert.severity == "WARN" for alert in alerts):
        return "live_cooldown_active_with_warnings"
    return "live_cooldown_active"


def _post_trade_alerts(report: dict[str, Any]) -> tuple[dict[str, object], ...]:
    raw_alerts = report.get("alerts", [])
    if not isinstance(raw_alerts, list):
        return ()
    return tuple(alert for alert in raw_alerts if isinstance(alert, dict))


def _runner_config_armed(path: str | Path) -> bool:
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("live_order_submission_armed:"):
            return line.split(":", 1)[1].strip().lower() == "true"
    return False


def _container_running(status: str) -> bool:
    return status.startswith("Up ")


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_datetime(raw: str) -> datetime:
    if not raw:
        return datetime.fromtimestamp(0, tz=UTC)
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
