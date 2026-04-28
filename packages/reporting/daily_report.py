"""Daily report builders."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.sandbox_reconciliation import SandboxRuntimeEvent
from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class DailyReport:
    account_id: str
    ending_equity: Decimal
    gross_exposure: Decimal
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HummingbotDailyReport:
    status: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    event_window: dict[str, object]
    trading_summary: dict[str, object]
    balance_summary: dict[str, object]
    carried_warnings: tuple[dict[str, str], ...]
    alerts: tuple[Alert, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "event_window": self.event_window,
            "trading_summary": self.trading_summary,
            "balance_summary": self.balance_summary,
            "carried_warnings": list(self.carried_warnings),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Daily Report",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Status: `{self.status}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            "",
            "## Event Window",
            "",
            f"- Started at: `{self.event_window['started_at']}`",
            f"- Completed at: `{self.event_window['completed_at']}`",
            f"- Duration hours: `{self.event_window['duration_hours']}`",
            f"- Event counts: `{self.event_window['event_counts']}`",
            "",
            "## Trading",
            "",
            f"- Submitted orders: `{self.trading_summary['submitted_orders']}`",
            f"- Filled orders: `{self.trading_summary['filled_orders']}`",
            f"- Buy orders: `{self.trading_summary['buy_orders']}`",
            f"- Sell orders: `{self.trading_summary['sell_orders']}`",
            f"- Gross notional quote: `{self.trading_summary['gross_notional_quote']}`",
            f"- Buy notional quote: `{self.trading_summary['buy_notional_quote']}`",
            f"- Sell notional quote: `{self.trading_summary['sell_notional_quote']}`",
            f"- Total fee quote: `{self.trading_summary['total_fee_quote']}`",
            f"- Net quote trade flow after fees: `{self.trading_summary['net_quote_trade_flow_after_fees']}`",
            "",
            "## Balances",
            "",
            f"- Balance assets: `{self.balance_summary['assets']}`",
            f"- Quote asset: `{self.balance_summary['quote_asset']}`",
            f"- Quote balance delta: `{self.balance_summary['quote_balance_delta']}`",
            f"- Balance deltas: `{self.balance_summary['balance_deltas']}`",
            "",
            "## Carried Warnings",
            "",
        ]
        if self.carried_warnings:
            lines.extend(
                f"- `{warning['severity']}` {warning['title']}: {warning['message']}"
                for warning in self.carried_warnings
            )
        else:
            lines.append("- None")
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_hummingbot_daily_report(
    *,
    events: tuple[SandboxRuntimeEvent, ...],
    observation_review: dict[str, Any],
    session_id: str,
    strategy_id: str,
    quote_asset: str = "USDT",
    artifacts: dict[str, str] | None = None,
) -> HummingbotDailyReport:
    event_window = _event_window(events)
    trading_summary = _trading_summary(events)
    balance_summary = _balance_summary(events, quote_asset=quote_asset)
    carried_warnings = _carried_warnings(observation_review)
    alerts = _build_alerts(
        event_window=event_window,
        trading_summary=trading_summary,
        balance_summary=balance_summary,
        carried_warnings=carried_warnings,
    )
    return HummingbotDailyReport(
        status=_status(alerts),
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=strategy_id,
        event_window=event_window,
        trading_summary=trading_summary,
        balance_summary=balance_summary,
        carried_warnings=carried_warnings,
        alerts=tuple(alerts),
        artifacts=artifacts or {},
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_hummingbot_daily_report_json(report: HummingbotDailyReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_hummingbot_daily_report_markdown(report: HummingbotDailyReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def _event_window(events: tuple[SandboxRuntimeEvent, ...]) -> dict[str, object]:
    timestamps = [event.created_at for event in events]
    event_counts = dict(Counter(event.event_type for event in events))
    if not timestamps:
        return {
            "started_at": "",
            "completed_at": "",
            "duration_hours": "0",
            "event_count": 0,
            "event_counts": event_counts,
        }
    started_at = min(timestamps)
    completed_at = max(timestamps)
    duration_hours = Decimal(str((completed_at - started_at).total_seconds())) / Decimal("3600")
    return {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_hours": decimal_to_str(duration_hours),
        "event_count": len(events),
        "event_counts": event_counts,
    }


def _trading_summary(events: tuple[SandboxRuntimeEvent, ...]) -> dict[str, object]:
    submitted_orders = sum(1 for event in events if event.event_type == "submitted")
    fills = [event for event in events if event.event_type == "filled"]
    buy_notional = Decimal("0")
    sell_notional = Decimal("0")
    total_fee = Decimal("0")
    buy_orders = 0
    sell_orders = 0
    for event in fills:
        notional = Decimal("0")
        if event.filled_amount is not None and event.average_fill_price is not None:
            notional = abs(event.filled_amount * event.average_fill_price)
        total_fee += event.fee_quote
        if event.side == "sell":
            sell_orders += 1
            sell_notional += notional
        else:
            buy_orders += 1
            buy_notional += notional
    gross_notional = buy_notional + sell_notional
    return {
        "submitted_orders": submitted_orders,
        "filled_orders": len(fills),
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "gross_notional_quote": decimal_to_str(gross_notional),
        "buy_notional_quote": decimal_to_str(buy_notional),
        "sell_notional_quote": decimal_to_str(sell_notional),
        "total_fee_quote": decimal_to_str(total_fee),
        "net_quote_trade_flow_after_fees": decimal_to_str(sell_notional - buy_notional - total_fee),
    }


def _balance_summary(events: tuple[SandboxRuntimeEvent, ...], *, quote_asset: str) -> dict[str, object]:
    first: dict[str, Decimal] = {}
    last: dict[str, Decimal] = {}
    for event in sorted(events, key=lambda item: item.created_at):
        if event.event_type != "balance" or event.balance_asset is None or event.balance_total is None:
            continue
        first.setdefault(event.balance_asset, event.balance_total)
        last[event.balance_asset] = event.balance_total
    deltas = {
        asset: decimal_to_str(last_total - first.get(asset, Decimal("0")))
        for asset, last_total in sorted(last.items())
    }
    return {
        "quote_asset": quote_asset,
        "assets": sorted(last),
        "starting_balances": {asset: decimal_to_str(value) for asset, value in sorted(first.items())},
        "ending_balances": {asset: decimal_to_str(value) for asset, value in sorted(last.items())},
        "balance_deltas": deltas,
        "quote_balance_delta": deltas.get(quote_asset, "0"),
    }


def _carried_warnings(observation_review: dict[str, Any]) -> tuple[dict[str, str], ...]:
    warnings: list[dict[str, str]] = []
    for raw_alert in observation_review.get("alerts", []):
        if not isinstance(raw_alert, dict) or raw_alert.get("severity") != "WARN":
            continue
        warnings.append(
            {
                "severity": str(raw_alert.get("severity", "")),
                "title": str(raw_alert.get("title", "")),
                "message": str(raw_alert.get("message", "")),
            }
        )
    return tuple(warnings)


def _build_alerts(
    *,
    event_window: dict[str, object],
    trading_summary: dict[str, object],
    balance_summary: dict[str, object],
    carried_warnings: tuple[dict[str, str], ...],
) -> list[Alert]:
    alerts: list[Alert] = []
    if int(event_window["event_count"]) == 0:
        alerts.append(critical_alert("No events", "Daily report cannot be built without Hummingbot events."))
    event_counts = event_window["event_counts"]
    if isinstance(event_counts, dict) and int(event_counts.get("session_completed", 0)) == 0:
        alerts.append(critical_alert("Session incomplete", "Hummingbot event export does not include session_completed."))
    if int(trading_summary["submitted_orders"]) != int(trading_summary["filled_orders"]):
        alerts.append(warning_alert("Unfilled orders", "Submitted and filled order counts differ."))
    if not balance_summary["assets"]:
        alerts.append(warning_alert("No balances", "Daily report did not find balance snapshots."))
    if carried_warnings:
        alerts.append(warning_alert("Observation warnings carried", "Observation review warnings are carried into this daily report."))
    if not any(alert.severity in {"CRITICAL", "WARN"} for alert in alerts):
        alerts.append(info_alert("Daily report ready", "Hummingbot daily report generated without blocking issues."))
    return alerts


def _status(alerts: tuple[Alert, ...] | list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "daily_report_ready_with_warnings"
    return "daily_report_ready"
