"""Hummingbot sandbox event ingestion and reconciliation."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert

ORDER_TERMINAL_EVENT_TYPES = {"completed", "canceled", "failed"}
ORDER_EVENT_TYPES = {"submitted", "filled", "completed", "canceled", "failed"}


@dataclass(frozen=True, slots=True)
class SandboxRuntimeEvent:
    event_id: str
    event_type: str
    created_at: datetime
    client_order_id: str | None = None
    trading_pair: str | None = None
    side: str | None = None
    filled_amount: Decimal | None = None
    average_fill_price: Decimal | None = None
    fee_quote: Decimal = Decimal("0")
    balance_asset: str | None = None
    balance_total: Decimal | None = None
    message: str | None = None
    raw: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "created_at": self.created_at.isoformat(),
            "client_order_id": self.client_order_id,
            "trading_pair": self.trading_pair,
            "side": self.side,
            "filled_amount": _optional_decimal_to_str(self.filled_amount),
            "average_fill_price": _optional_decimal_to_str(self.average_fill_price),
            "fee_quote": decimal_to_str(self.fee_quote),
            "balance_asset": self.balance_asset,
            "balance_total": _optional_decimal_to_str(self.balance_total),
            "message": self.message,
            "raw": self.raw,
        }


@dataclass(frozen=True, slots=True)
class SandboxReconciliationThresholds:
    amount_tolerance: Decimal = Decimal("0.00000001")
    price_warning_bps: Decimal = Decimal("50")
    fee_tolerance: Decimal = Decimal("0.000001")
    balance_tolerance: Decimal = Decimal("0.000001")
    require_balance_event: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "amount_tolerance": decimal_to_str(self.amount_tolerance),
            "price_warning_bps": decimal_to_str(self.price_warning_bps),
            "fee_tolerance": decimal_to_str(self.fee_tolerance),
            "balance_tolerance": decimal_to_str(self.balance_tolerance),
            "require_balance_event": self.require_balance_event,
        }


@dataclass(frozen=True, slots=True)
class SandboxReconciliationResult:
    generated_at: datetime
    decision: str
    strategy_id: str
    account_id: str
    manifest_summary: dict[str, object]
    event_counts: dict[str, int]
    order_checks: dict[str, object]
    fill_checks: dict[str, object]
    balance_checks: dict[str, object]
    thresholds: SandboxReconciliationThresholds
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "decision": self.decision,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "manifest_summary": self.manifest_summary,
            "event_counts": self.event_counts,
            "order_checks": self.order_checks,
            "fill_checks": self.fill_checks,
            "balance_checks": self.balance_checks,
            "thresholds": self.thresholds.to_dict(),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Sandbox Reconciliation",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Account: `{self.account_id}`",
            f"- Connector: `{self.manifest_summary['connector_name']}`",
            f"- Live trading enabled: `{self.manifest_summary['live_trading_enabled']}`",
            "",
            "## Orders",
            "",
            f"- Expected orders: `{self.order_checks['expected_orders']}`",
            f"- Submitted orders: `{self.order_checks['submitted_orders']}`",
            f"- Terminal orders: `{self.order_checks['terminal_orders']}`",
            f"- Filled orders: `{self.order_checks['filled_orders']}`",
            f"- Failed orders: `{self.order_checks['failed_orders']}`",
            f"- Canceled orders: `{self.order_checks['canceled_orders']}`",
            f"- Unknown order ids: `{self.order_checks['unknown_client_order_ids']}`",
            f"- Missing submissions: `{self.order_checks['missing_submissions']}`",
            f"- Missing terminal orders: `{self.order_checks['missing_terminal_orders']}`",
            "",
            "## Fills",
            "",
            f"- Fill events reconciled: `{self.fill_checks['fill_events_reconciled']}`",
            f"- Amount mismatches: `{self.fill_checks['amount_mismatches']}`",
            f"- Submitted amount adjustments: `{self.fill_checks['submitted_amount_adjustments']}`",
            f"- Price warnings: `{self.fill_checks['price_warnings']}`",
            f"- Fee warnings: `{self.fill_checks['fee_warnings']}`",
            "",
            "## Balances",
            "",
            f"- Status: `{self.balance_checks['status']}`",
            f"- Balance events: `{self.balance_checks['balance_events']}`",
            f"- Missing balance assets: `{self.balance_checks['missing_balance_assets']}`",
            f"- Balance mismatches: `{self.balance_checks['balance_mismatches']}`",
            "",
            "## Event Counts",
            "",
            f"`{self.event_counts}`",
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
        lines.append("")
        return "\n".join(lines)


def build_sandbox_reconciliation(
    *,
    manifest: dict[str, Any],
    events: tuple[SandboxRuntimeEvent, ...],
    starting_quote_balance: Decimal | None,
    quote_asset: str = "USDT",
    thresholds: SandboxReconciliationThresholds | None = None,
) -> SandboxReconciliationResult:
    limits = thresholds or SandboxReconciliationThresholds()
    orders = _manifest_orders(manifest)
    orders_by_id = {str(order["client_order_id"]): order for order in orders}
    event_counts = dict(Counter(event.event_type for event in events))
    order_checks = _order_checks(orders_by_id, events)
    fill_checks = _fill_checks(orders_by_id, events, limits)
    balance_checks = _balance_checks(
        orders_by_id=orders_by_id,
        events=events,
        starting_quote_balance=starting_quote_balance,
        quote_asset=quote_asset,
        thresholds=limits,
    )
    manifest_summary = {
        "schema_version": manifest.get("schema_version"),
        "connector_name": manifest.get("connector_name"),
        "controller_name": manifest.get("controller_name"),
        "live_trading_enabled": bool(manifest.get("live_trading_enabled")),
        "expected_orders": len(orders),
        "total_notional": manifest.get("total_notional"),
    }
    alerts = _build_alerts(
        manifest_summary=manifest_summary,
        order_checks=order_checks,
        fill_checks=fill_checks,
        balance_checks=balance_checks,
    )
    decision = _decision(alerts)
    return SandboxReconciliationResult(
        generated_at=datetime.now(tz=UTC),
        decision=decision,
        strategy_id=str(manifest.get("strategy_id", "")),
        account_id=str(manifest.get("account_id", "")),
        manifest_summary=manifest_summary,
        event_counts=event_counts,
        order_checks=order_checks,
        fill_checks=fill_checks,
        balance_checks=balance_checks,
        thresholds=limits,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision, alerts),
    )


def replay_sandbox_events_from_manifest(
    *,
    manifest: dict[str, Any],
    starting_quote_balance: Decimal | None = None,
    quote_asset: str = "USDT",
) -> tuple[SandboxRuntimeEvent, ...]:
    orders = _manifest_orders(manifest)
    base_time = _manifest_time(manifest)
    events: list[SandboxRuntimeEvent] = []
    for index, order in enumerate(orders):
        client_order_id = str(order["client_order_id"])
        created_at = base_time + timedelta(milliseconds=index)
        events.append(
            SandboxRuntimeEvent(
                event_id=f"{client_order_id}:submitted",
                event_type="submitted",
                created_at=created_at,
                client_order_id=client_order_id,
                trading_pair=str(order["trading_pair"]),
                side=str(order["side"]),
            )
        )
        events.append(
            SandboxRuntimeEvent(
                event_id=f"{client_order_id}:filled",
                event_type="filled",
                created_at=created_at + timedelta(milliseconds=1),
                client_order_id=client_order_id,
                trading_pair=str(order["trading_pair"]),
                side=str(order["side"]),
                filled_amount=Decimal(str(order["amount"])),
                average_fill_price=Decimal(str(order["price"])),
                fee_quote=Decimal(str(order.get("expected_fee_quote", "0"))),
            )
        )

    if starting_quote_balance is not None:
        balances = _expected_balances_from_fills(
            orders_by_id={str(order["client_order_id"]): order for order in orders},
            events=tuple(events),
            starting_quote_balance=starting_quote_balance,
            quote_asset=quote_asset,
        )
        for index, (asset, balance) in enumerate(sorted(balances.items())):
            events.append(
                SandboxRuntimeEvent(
                    event_id=f"balance:{asset}",
                    event_type="balance",
                    created_at=base_time + timedelta(seconds=1, milliseconds=index),
                    balance_asset=asset,
                    balance_total=balance,
                )
            )

    return tuple(events)


def normalize_sandbox_event(payload: dict[str, Any]) -> SandboxRuntimeEvent:
    event_type = _normalize_event_type(
        _optional_str(_first_value(payload, "event_type", "eventType", "type", "name")) or "unknown"
    )
    created_at = _parse_datetime(_first_value(payload, "created_at", "timestamp", "time"))
    client_order_id = _optional_str(
        _first_value(payload, "client_order_id", "clientOrderId", "order_id", "orderId")
    )
    event_id = _optional_str(_first_value(payload, "event_id", "eventId", "id"))
    if event_id is None:
        event_id = _derived_event_id(event_type, client_order_id, created_at)
    return SandboxRuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        created_at=created_at,
        client_order_id=client_order_id,
        trading_pair=_optional_str(_first_value(payload, "trading_pair", "tradingPair", "symbol")),
        side=_optional_str(_first_value(payload, "side", "trade_type", "tradeType")),
        filled_amount=_optional_decimal(
            _first_value(payload, "filled_amount", "filled_quantity", "executed_amount", "amount")
        ),
        average_fill_price=_optional_decimal(
            _first_value(payload, "average_fill_price", "average_price", "avg_price", "price")
        ),
        fee_quote=_optional_decimal(_first_value(payload, "fee_quote", "fee", "cumulative_fee")) or Decimal("0"),
        balance_asset=_optional_str(_first_value(payload, "balance_asset", "asset", "currency")),
        balance_total=_optional_decimal(
            _first_value(payload, "balance_total", "total_balance", "total", "balance")
        ),
        message=_optional_str(_first_value(payload, "message", "reason", "error")),
        raw=dict(payload),
    )


def normalize_sandbox_events(payload: dict[str, Any]) -> tuple[SandboxRuntimeEvent, ...]:
    event = normalize_sandbox_event(payload)
    balances = _first_value(payload, "balances", "total_balances", "balance_snapshot")
    if event.event_type != "balance" or not isinstance(balances, dict):
        return (event,)

    events = []
    for asset, balance_payload in sorted(balances.items()):
        balance_total = _balance_total_from_payload(balance_payload)
        if balance_total is None:
            continue
        events.append(
            SandboxRuntimeEvent(
                event_id=f"{event.event_id}:{asset}",
                event_type="balance",
                created_at=event.created_at,
                balance_asset=str(asset),
                balance_total=balance_total,
                message=event.message,
                raw=dict(payload),
            )
        )
    return tuple(events) if events else (event,)


def load_event_jsonl(path: str | Path) -> tuple[SandboxRuntimeEvent, ...]:
    records = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                records.extend(normalize_sandbox_events(json.loads(stripped)))
    return tuple(records)


def write_events_jsonl(events: tuple[SandboxRuntimeEvent, ...], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event.to_dict(), sort_keys=True))
            file.write("\n")
    return output_path


def write_reconciliation_json(result: SandboxReconciliationResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_reconciliation_markdown(result: SandboxReconciliationResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return output_path


def _order_checks(
    orders_by_id: dict[str, dict[str, object]],
    events: tuple[SandboxRuntimeEvent, ...],
) -> dict[str, object]:
    expected_ids = set(orders_by_id)
    event_order_ids = {
        str(event.client_order_id)
        for event in events
        if event.client_order_id is not None and event.event_type in ORDER_EVENT_TYPES
    }
    unknown_ids = sorted(event_order_ids - expected_ids)
    submitted_ids = Counter(
        str(event.client_order_id)
        for event in events
        if event.event_type == "submitted" and event.client_order_id is not None
    )
    explicit_terminal_ids = Counter(
        str(event.client_order_id)
        for event in events
        if event.event_type in ORDER_TERMINAL_EVENT_TYPES and event.client_order_id is not None
    )
    fill_ids = Counter(
        str(event.client_order_id)
        for event in events
        if event.event_type == "filled" and event.client_order_id is not None
    )
    terminal_ids = set(explicit_terminal_ids) | {client_id for client_id in fill_ids if client_id not in explicit_terminal_ids}
    failed_ids = sorted(
        {
            str(event.client_order_id)
            for event in events
            if event.event_type == "failed" and event.client_order_id is not None
        }
    )
    canceled_ids = sorted(
        {
            str(event.client_order_id)
            for event in events
            if event.event_type == "canceled" and event.client_order_id is not None
        }
    )
    return {
        "expected_orders": len(expected_ids),
        "submitted_orders": len(set(submitted_ids) & expected_ids),
        "terminal_orders": len(terminal_ids & expected_ids),
        "filled_orders": len(set(fill_ids) & expected_ids),
        "failed_orders": len(set(failed_ids) & expected_ids),
        "canceled_orders": len(set(canceled_ids) & expected_ids),
        "missing_submissions": sorted(expected_ids - set(submitted_ids)),
        "missing_terminal_orders": sorted(expected_ids - terminal_ids),
        "unknown_client_order_ids": unknown_ids,
        "duplicate_submissions": sum(max(0, count - 1) for count in submitted_ids.values()),
        "duplicate_terminal_events": sum(max(0, count - 1) for count in explicit_terminal_ids.values()),
        "failed_client_order_ids": failed_ids,
        "canceled_client_order_ids": canceled_ids,
        "disconnect_events": sum(1 for event in events if event.event_type == "disconnect"),
        "order_exception_events": sum(1 for event in events if event.event_type == "order_exception"),
        "balance_anomaly_events": sum(1 for event in events if event.event_type == "balance_anomaly"),
    }


def _fill_checks(
    orders_by_id: dict[str, dict[str, object]],
    events: tuple[SandboxRuntimeEvent, ...],
    thresholds: SandboxReconciliationThresholds,
) -> dict[str, object]:
    fill_events = _fill_event_by_order_id(orders_by_id, events)
    missing_fill_fields: list[str] = []
    amount_mismatches: list[dict[str, object]] = []
    submitted_amount_adjustments: list[dict[str, object]] = []
    price_warnings: list[dict[str, object]] = []
    fee_warnings: list[dict[str, object]] = []
    for client_order_id, event in fill_events.items():
        expected = orders_by_id[client_order_id]
        if event.filled_amount is None or event.average_fill_price is None:
            missing_fill_fields.append(client_order_id)
            continue
        manifest_amount = Decimal(str(expected["amount"]))
        expected_amount = _expected_fill_amount(event, manifest_amount)
        if expected_amount != manifest_amount:
            submitted_amount_adjustments.append(
                {
                    "client_order_id": client_order_id,
                    "manifest_amount": decimal_to_str(manifest_amount),
                    "submitted_amount": decimal_to_str(expected_amount),
                    "diff": decimal_to_str(abs(expected_amount - manifest_amount)),
                    "reason": str(event.raw.get("amount_adjustment_reason", "runtime_submitted_amount")),
                }
            )
        expected_price = Decimal(str(expected["price"]))
        expected_fee = Decimal(str(expected.get("expected_fee_quote", "0")))
        amount_diff = abs(event.filled_amount - expected_amount)
        if amount_diff > thresholds.amount_tolerance:
            amount_mismatches.append(
                {
                    "client_order_id": client_order_id,
                    "expected": decimal_to_str(expected_amount),
                    "actual": decimal_to_str(event.filled_amount),
                    "diff": decimal_to_str(amount_diff),
                }
            )
        if expected_price > Decimal("0"):
            price_diff_bps = abs(event.average_fill_price - expected_price) / expected_price * Decimal("10000")
            if price_diff_bps > thresholds.price_warning_bps:
                price_warnings.append(
                    {
                        "client_order_id": client_order_id,
                        "expected_price": decimal_to_str(expected_price),
                        "actual_price": decimal_to_str(event.average_fill_price),
                        "diff_bps": decimal_to_str(price_diff_bps),
                    }
                )
        fee_diff = abs(event.fee_quote - expected_fee)
        if fee_diff > thresholds.fee_tolerance:
            fee_warnings.append(
                {
                    "client_order_id": client_order_id,
                    "expected_fee": decimal_to_str(expected_fee),
                    "actual_fee": decimal_to_str(event.fee_quote),
                    "diff": decimal_to_str(fee_diff),
                }
            )

    return {
        "fill_events_reconciled": len(fill_events),
        "missing_fill_fields": missing_fill_fields,
        "amount_mismatches": amount_mismatches,
        "submitted_amount_adjustments": submitted_amount_adjustments,
        "price_warnings": price_warnings,
        "fee_warnings": fee_warnings,
    }


def _balance_checks(
    *,
    orders_by_id: dict[str, dict[str, object]],
    events: tuple[SandboxRuntimeEvent, ...],
    starting_quote_balance: Decimal | None,
    quote_asset: str,
    thresholds: SandboxReconciliationThresholds,
) -> dict[str, object]:
    balance_events = [event for event in events if event.event_type == "balance"]
    latest_balances = _latest_balance_by_asset(balance_events)
    if starting_quote_balance is None:
        return {
            "status": "skipped",
            "balance_events": len(balance_events),
            "quote_asset": quote_asset,
            "starting_quote_balance": None,
            "expected_balances": {},
            "observed_balances": {
                asset: decimal_to_str(balance) for asset, balance in sorted(latest_balances.items())
            },
            "missing_balance_assets": [],
            "balance_mismatches": [],
            "require_balance_event": thresholds.require_balance_event,
        }

    expected_balances = _expected_balances_from_fills(
        orders_by_id=orders_by_id,
        events=events,
        starting_quote_balance=starting_quote_balance,
        quote_asset=quote_asset,
    )
    missing_assets = sorted(asset for asset in expected_balances if asset not in latest_balances)
    balance_mismatches = []
    for asset, expected_balance in expected_balances.items():
        actual_balance = latest_balances.get(asset)
        if actual_balance is None:
            continue
        diff = abs(actual_balance - expected_balance)
        if diff > thresholds.balance_tolerance:
            balance_mismatches.append(
                {
                    "asset": asset,
                    "expected": decimal_to_str(expected_balance),
                    "actual": decimal_to_str(actual_balance),
                    "diff": decimal_to_str(diff),
                }
            )

    return {
        "status": "checked",
        "balance_events": len(balance_events),
        "quote_asset": quote_asset,
        "starting_quote_balance": decimal_to_str(starting_quote_balance),
        "expected_balances": {
            asset: decimal_to_str(balance) for asset, balance in sorted(expected_balances.items())
        },
        "observed_balances": {
            asset: decimal_to_str(balance) for asset, balance in sorted(latest_balances.items())
        },
        "missing_balance_assets": missing_assets,
        "balance_mismatches": balance_mismatches,
        "require_balance_event": thresholds.require_balance_event,
    }


def _build_alerts(
    *,
    manifest_summary: dict[str, object],
    order_checks: dict[str, object],
    fill_checks: dict[str, object],
    balance_checks: dict[str, object],
) -> list[Alert]:
    alerts: list[Alert] = []
    if manifest_summary["live_trading_enabled"]:
        alerts.append(critical_alert("Live trading enabled", "Sandbox reconciliation requires live_trading_enabled=false."))
    if int(order_checks["expected_orders"]) == 0:
        alerts.append(critical_alert("No expected orders", "Sandbox manifest contains no expected orders."))
    if int(order_checks["submitted_orders"]) != int(order_checks["expected_orders"]):
        alerts.append(
            critical_alert(
                "Submission mismatch",
                f"Submitted {order_checks['submitted_orders']} of {order_checks['expected_orders']} expected orders.",
            )
        )
    if int(order_checks["terminal_orders"]) != int(order_checks["expected_orders"]):
        alerts.append(
            critical_alert(
                "Terminal mismatch",
                f"Terminal {order_checks['terminal_orders']} of {order_checks['expected_orders']} expected orders.",
            )
        )
    if order_checks["unknown_client_order_ids"]:
        alerts.append(
            critical_alert(
                "Unknown order ids",
                f"Observed unknown client order ids: {order_checks['unknown_client_order_ids']}.",
            )
        )
    if int(order_checks["duplicate_submissions"]):
        alerts.append(
            critical_alert(
                "Duplicate submissions",
                f"Observed {order_checks['duplicate_submissions']} duplicate submission events.",
            )
        )
    if int(order_checks["duplicate_terminal_events"]):
        alerts.append(
            critical_alert(
                "Duplicate terminal events",
                f"Observed {order_checks['duplicate_terminal_events']} duplicate terminal events.",
            )
        )
    if order_checks["failed_client_order_ids"]:
        alerts.append(
            critical_alert(
                "Failed sandbox orders",
                f"Failed orders: {order_checks['failed_client_order_ids']}.",
            )
        )
    if order_checks["canceled_client_order_ids"]:
        alerts.append(
            critical_alert(
                "Canceled sandbox orders",
                f"Canceled orders: {order_checks['canceled_client_order_ids']}.",
            )
        )
    for key, title in (
        ("disconnect_events", "Hummingbot disconnect events"),
        ("order_exception_events", "Hummingbot order exceptions"),
        ("balance_anomaly_events", "Hummingbot balance anomalies"),
    ):
        if int(order_checks[key]):
            alerts.append(critical_alert(title, f"Observed {order_checks[key]} {key}."))
    if fill_checks["missing_fill_fields"]:
        alerts.append(
            critical_alert(
                "Fill fields missing",
                f"Fill events missing amount or price: {fill_checks['missing_fill_fields']}.",
            )
        )
    if fill_checks["amount_mismatches"]:
        alerts.append(
            critical_alert(
                "Fill amount mismatch",
                f"Fill amount mismatches: {fill_checks['amount_mismatches']}.",
            )
        )
    if fill_checks["submitted_amount_adjustments"]:
        alerts.append(
            warning_alert(
                "Submitted amount adjusted",
                f"Hummingbot submitted adjusted paper amounts: {fill_checks['submitted_amount_adjustments']}.",
            )
        )
    if fill_checks["price_warnings"]:
        alerts.append(
            warning_alert(
                "Fill price drift",
                f"Fill prices drifted beyond warning threshold: {fill_checks['price_warnings']}.",
            )
        )
    if fill_checks["fee_warnings"]:
        alerts.append(
            warning_alert(
                "Fee drift",
                f"Fees drifted beyond tolerance: {fill_checks['fee_warnings']}.",
            )
        )

    if balance_checks["require_balance_event"] and int(balance_checks["balance_events"]) == 0:
        alerts.append(critical_alert("Balance events missing", "No Hummingbot balance event was observed."))
    if balance_checks["status"] == "skipped":
        alerts.append(
            warning_alert(
                "Balance reconciliation skipped",
                "Starting quote balance was not provided, so balance quantities were not reconciled.",
            )
        )
    if balance_checks["missing_balance_assets"]:
        alerts.append(
            critical_alert(
                "Balance assets missing",
                f"Missing balance assets: {balance_checks['missing_balance_assets']}.",
            )
        )
    if balance_checks["balance_mismatches"]:
        alerts.append(
            critical_alert(
                "Balance mismatch",
                f"Balance mismatches: {balance_checks['balance_mismatches']}.",
            )
        )
    alerts.append(
        info_alert(
            "Live trading remains disabled",
            "Phase 5.1 validates sandbox event ingestion and reconciliation only.",
        )
    )
    return alerts


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "sandbox_reconciled_with_warnings"
    return "sandbox_reconciled"


def _recommended_actions(decision: str, alerts: list[Alert]) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not advance Hummingbot sandbox.",
            "Fix every CRITICAL reconciliation alert and rerun Phase 5.1.",
            "Keep live trading disabled.",
        )
    actions = [
        "Keep collecting Hummingbot sandbox submitted, filled, canceled, failed, disconnect, and balance events.",
        "Rerun reconciliation after every sandbox session.",
        "Do not enable live credentials from Phase 5.1 results.",
    ]
    if any(alert.severity == "WARN" for alert in alerts):
        actions.append("Resolve or explicitly carry forward WARN items before Phase 5.2.")
    else:
        actions.append("Proceed to a longer Hummingbot sandbox observation only after operator review.")
    return tuple(actions)


def _manifest_orders(manifest: dict[str, Any]) -> list[dict[str, object]]:
    orders = manifest.get("orders", [])
    if not isinstance(orders, list):
        raise TypeError("manifest orders must be a list")
    return [order for order in orders if isinstance(order, dict)]


def _manifest_time(manifest: dict[str, Any]) -> datetime:
    value = manifest.get("source_review_generated_at")
    if value:
        return datetime.fromisoformat(str(value))
    return datetime.now(tz=UTC)


def _fill_event_by_order_id(
    orders_by_id: dict[str, dict[str, object]],
    events: tuple[SandboxRuntimeEvent, ...],
) -> dict[str, SandboxRuntimeEvent]:
    fill_events: dict[str, SandboxRuntimeEvent] = {}
    completed_events: dict[str, SandboxRuntimeEvent] = {}
    for event in events:
        if event.client_order_id is None or event.client_order_id not in orders_by_id:
            continue
        client_order_id = str(event.client_order_id)
        if event.event_type == "filled":
            fill_events[client_order_id] = event
        elif event.event_type == "completed":
            completed_events[client_order_id] = event
    for client_order_id, event in completed_events.items():
        fill_events.setdefault(client_order_id, event)
    return fill_events


def _expected_balances_from_fills(
    *,
    orders_by_id: dict[str, dict[str, object]],
    events: tuple[SandboxRuntimeEvent, ...],
    starting_quote_balance: Decimal,
    quote_asset: str,
) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = {quote_asset: starting_quote_balance}
    fill_events = _fill_event_by_order_id(orders_by_id, events)
    for client_order_id, event in fill_events.items():
        order = orders_by_id[client_order_id]
        if event.filled_amount is None or event.average_fill_price is None:
            continue
        trading_pair = str(order["trading_pair"])
        base_asset, pair_quote_asset = _split_trading_pair(trading_pair)
        balances.setdefault(base_asset, Decimal("0"))
        balances.setdefault(pair_quote_asset, Decimal("0"))
        side = str(event.side or order["side"])
        notional = event.filled_amount * event.average_fill_price
        if side == "buy":
            balances[base_asset] += event.filled_amount
            balances[pair_quote_asset] -= notional + event.fee_quote
        else:
            balances[base_asset] -= event.filled_amount
            balances[pair_quote_asset] += notional - event.fee_quote
    return balances


def _expected_fill_amount(event: SandboxRuntimeEvent, manifest_amount: Decimal) -> Decimal:
    submitted_amount = event.raw.get("submitted_amount")
    if submitted_amount is None:
        return manifest_amount
    try:
        return Decimal(str(submitted_amount))
    except Exception:
        return manifest_amount


def _latest_balance_by_asset(events: list[SandboxRuntimeEvent]) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = {}
    for event in events:
        if event.balance_asset is not None and event.balance_total is not None:
            balances[event.balance_asset] = event.balance_total
    return balances


def _split_trading_pair(trading_pair: str) -> tuple[str, str]:
    parts = trading_pair.split("-", 1)
    if len(parts) != 2:
        return trading_pair, "USDT"
    return parts[0], parts[1]


def _normalize_event_type(value: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = normalized.removesuffix("_event")
    mapping = {
        "submitted": "submitted",
        "created": "submitted",
        "order_submitted": "submitted",
        "buy_order_created": "submitted",
        "sell_order_created": "submitted",
        "filled": "filled",
        "fill": "filled",
        "order_filled": "filled",
        "completed": "completed",
        "order_completed": "completed",
        "buy_order_completed": "completed",
        "sell_order_completed": "completed",
        "canceled": "canceled",
        "cancelled": "canceled",
        "order_canceled": "canceled",
        "order_cancelled": "canceled",
        "failed": "failed",
        "failure": "failed",
        "order_failed": "failed",
        "disconnect": "disconnect",
        "disconnected": "disconnect",
        "network_disconnect": "disconnect",
        "order_exception": "order_exception",
        "order_failure_exception": "order_exception",
        "balance": "balance",
        "balance_update": "balance",
        "balance_snapshot": "balance",
        "balance_anomaly": "balance_anomaly",
    }
    return mapping.get(normalized, normalized)


def _parse_datetime(value: object) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=UTC)
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(tz=UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _derived_event_id(event_type: str, client_order_id: str | None, created_at: datetime) -> str:
    subject = client_order_id or "system"
    return f"{subject}:{event_type}:{created_at.isoformat()}"


def _first_value(payload: dict[str, Any], *keys: str) -> object | None:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return _balance_total_from_payload(value)
    return Decimal(str(value))


def _optional_decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return decimal_to_str(value)


def _balance_total_from_payload(value: object | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("total", "balance_total", "total_balance", "amount", "free"):
            if key in value:
                return _optional_decimal(value[key])
        return None
    return Decimal(str(value))
