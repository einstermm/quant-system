"""Hummingbot sandbox preparation and local lifecycle checks."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str


@dataclass(frozen=True, slots=True)
class SandboxPrepareResult:
    decision: str
    generated_at: datetime
    manifest: dict[str, object]
    lifecycle: dict[str, object]
    alerts: tuple[dict[str, object], ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "manifest": self.manifest,
            "lifecycle": self.lifecycle,
            "alerts": list(self.alerts),
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        order_count = len(self.manifest.get("orders", []))
        controller_count = len(self.manifest.get("controller_configs", []))
        lifecycle_checks = self.lifecycle.get("checks", {})
        lines = [
            "# Hummingbot Sandbox Preparation",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Strategy: `{self.manifest.get('strategy_id')}`",
            f"- Account: `{self.manifest.get('account_id')}`",
            f"- Connector: `{self.manifest.get('connector_name')}`",
            f"- Controller: `{self.manifest.get('controller_name')}`",
            f"- Live trading enabled: `{self.manifest.get('live_trading_enabled')}`",
            f"- Source review decision: `{self.manifest.get('source_review_decision')}`",
            "",
            "## Orders",
            "",
            f"- Controller configs: `{controller_count}`",
            f"- Sandbox order configs: `{order_count}`",
            f"- Buy notional: `{self.manifest.get('buy_notional')}`",
            f"- Sell notional: `{self.manifest.get('sell_notional')}`",
            f"- Total notional: `{self.manifest.get('total_notional')}`",
            "",
            "## Lifecycle Checks",
            "",
            f"- Submitted orders: `{lifecycle_checks.get('submitted_orders')}`",
            f"- Terminal orders: `{lifecycle_checks.get('terminal_orders')}`",
            f"- Filled orders: `{lifecycle_checks.get('filled_orders')}`",
            f"- Duplicate client ids: `{lifecycle_checks.get('duplicate_client_ids')}`",
            f"- Disconnect events: `{lifecycle_checks.get('disconnect_events')}`",
            f"- Order exception events: `{lifecycle_checks.get('order_exception_events')}`",
            f"- Balance anomaly events: `{lifecycle_checks.get('balance_anomaly_events')}`",
            "",
            "## Alerts",
            "",
        ]
        if self.alerts:
            lines.extend(
                f"- `{alert['severity']}` {alert['title']}: {alert['message']}"
                for alert in self.alerts
            )
        else:
            lines.append("- None")

        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def prepare_hummingbot_sandbox(
    *,
    review_payload: dict[str, Any],
    ledger_records: tuple[dict[str, Any], ...],
    connector_name: str,
    controller_name: str,
    allow_warnings: bool,
) -> SandboxPrepareResult:
    manifest = build_sandbox_manifest(
        review_payload=review_payload,
        ledger_records=ledger_records,
        connector_name=connector_name,
        controller_name=controller_name,
    )
    lifecycle = simulate_sandbox_lifecycle(manifest)
    alerts = _build_alerts(
        review_payload=review_payload,
        manifest=manifest,
        lifecycle=lifecycle,
        allow_warnings=allow_warnings,
    )
    decision = _decision(alerts)
    return SandboxPrepareResult(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        manifest=manifest,
        lifecycle=lifecycle,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision, alerts),
    )


def build_sandbox_manifest(
    *,
    review_payload: dict[str, Any],
    ledger_records: tuple[dict[str, Any], ...],
    connector_name: str,
    controller_name: str,
) -> dict[str, object]:
    trading = review_payload["trading"]
    orders = [_sandbox_order(record, connector_name) for record in ledger_records]
    controller_configs = _controller_configs(
        orders=orders,
        controller_name=controller_name,
        connector_name=connector_name,
    )
    buy_notional = sum(
        (Decimal(str(order["notional_quote"])) for order in orders if order["side"] == "buy"),
        Decimal("0"),
    )
    sell_notional = sum(
        (Decimal(str(order["notional_quote"])) for order in orders if order["side"] == "sell"),
        Decimal("0"),
    )
    return {
        "schema_version": "hummingbot_sandbox_manifest_v1",
        "strategy_id": review_payload["strategy_id"],
        "account_id": review_payload["account_id"],
        "connector_name": connector_name,
        "controller_name": controller_name,
        "live_trading_enabled": False,
        "precision_and_min_order_checks": "delegated_to_hummingbot",
        "source_review_decision": review_payload["decision"],
        "source_review_generated_at": review_payload["generated_at"],
        "final_target_weights": trading["final_target_weights"],
        "final_positions": trading["final_positions"],
        "controller_configs": controller_configs,
        "orders": orders,
        "buy_notional": decimal_to_str(buy_notional),
        "sell_notional": decimal_to_str(sell_notional),
        "total_notional": decimal_to_str(buy_notional + sell_notional),
    }


def simulate_sandbox_lifecycle(manifest: dict[str, object]) -> dict[str, object]:
    orders = manifest.get("orders", [])
    if not isinstance(orders, list):
        raise TypeError("manifest orders must be a list")

    events: list[dict[str, object]] = []
    for order in orders:
        if not isinstance(order, dict):
            continue
        client_order_id = str(order["client_order_id"])
        events.append(
            {
                "event_type": "submitted",
                "client_order_id": client_order_id,
                "trading_pair": order["trading_pair"],
            }
        )
        events.append(
            {
                "event_type": "filled",
                "client_order_id": client_order_id,
                "trading_pair": order["trading_pair"],
                "filled_amount": order["amount"],
                "average_fill_price": order["price"],
            }
        )

    event_counts = Counter(str(event["event_type"]) for event in events)
    client_ids = [str(order["client_order_id"]) for order in orders if isinstance(order, dict)]
    duplicate_client_ids = len(client_ids) - len(set(client_ids))
    return {
        "events": events,
        "checks": {
            "submitted_orders": event_counts["submitted"],
            "terminal_orders": event_counts["filled"] + event_counts["canceled"] + event_counts["failed"],
            "filled_orders": event_counts["filled"],
            "duplicate_client_ids": duplicate_client_ids,
            "disconnect_events": event_counts["disconnect"],
            "order_exception_events": event_counts["order_exception"],
            "balance_anomaly_events": event_counts["balance_anomaly"],
        },
    }


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> tuple[dict[str, Any], ...]:
    records = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return tuple(records)


def write_manifest(manifest: dict[str, object], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_prepare_result_json(result: SandboxPrepareResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_prepare_result_markdown(result: SandboxPrepareResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return output_path


def _sandbox_order(record: dict[str, Any], connector_name: str) -> dict[str, object]:
    side = str(record["side"])
    notional = Decimal(str(record["notional"]))
    fee = Decimal(str(record["fee"]))
    return {
        "client_order_id": str(record["paper_order_id"]),
        "source_intent_id": str(record["intent_id"]),
        "source_paper_order_id": str(record["paper_order_id"]),
        "connector_name": connector_name,
        "trading_pair": str(record["symbol"]),
        "side": side,
        "order_type": str(record["order_type"]),
        "amount": str(record["quantity"]),
        "price": str(record["fill_price"]),
        "notional_quote": decimal_to_str(notional),
        "expected_fee_quote": decimal_to_str(fee),
        "reduce_only": side == "sell",
        "status": "ready_for_sandbox",
    }


def _controller_configs(
    *,
    orders: list[dict[str, object]],
    controller_name: str,
    connector_name: str,
) -> list[dict[str, object]]:
    by_symbol: dict[str, list[dict[str, object]]] = {}
    for order in orders:
        by_symbol.setdefault(str(order["trading_pair"]), []).append(order)

    configs = []
    for trading_pair, symbol_orders in sorted(by_symbol.items()):
        total_notional = sum(
            (Decimal(str(order["notional_quote"])) for order in symbol_orders),
            Decimal("0"),
        )
        configs.append(
            {
                "controller_name": controller_name,
                "connector_name": connector_name,
                "trading_pair": trading_pair,
                "total_amount_quote": decimal_to_str(total_notional),
                "executor_count": len(symbol_orders),
                "executor_client_order_ids": [
                    str(order["client_order_id"]) for order in symbol_orders
                ],
                "mode": "sandbox",
            }
        )
    return configs


def _build_alerts(
    *,
    review_payload: dict[str, Any],
    manifest: dict[str, object],
    lifecycle: dict[str, object],
    allow_warnings: bool,
) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []
    source_decision = str(review_payload["decision"])
    if source_decision == "blocked":
        alerts.append(_alert("CRITICAL", "Source review blocked", "Phase 4.3 review is blocked."))
    if source_decision.endswith("_with_warnings"):
        severity = "WARN" if allow_warnings else "CRITICAL"
        alerts.append(
            _alert(
                severity,
                "Source review has warnings",
                "Phase 4.3 warnings must be carried into the sandbox runbook.",
            )
        )
    if bool(manifest.get("live_trading_enabled")):
        alerts.append(_alert("CRITICAL", "Live trading enabled", "Sandbox manifest must not enable live trading."))

    orders = manifest.get("orders", [])
    if not isinstance(orders, list) or not orders:
        alerts.append(_alert("CRITICAL", "No sandbox orders", "Sandbox manifest contains no order configs."))

    checks = lifecycle["checks"]
    if int(checks["duplicate_client_ids"]):
        alerts.append(_alert("CRITICAL", "Duplicate client ids", "Sandbox order client ids must be unique."))
    if int(checks["submitted_orders"]) != len(orders):
        alerts.append(_alert("CRITICAL", "Submission count mismatch", "Lifecycle did not submit every sandbox order."))
    if int(checks["terminal_orders"]) != len(orders):
        alerts.append(_alert("CRITICAL", "Terminal count mismatch", "Lifecycle did not terminally resolve every sandbox order."))
    for key, title in (
        ("disconnect_events", "Disconnect events"),
        ("order_exception_events", "Order exceptions"),
        ("balance_anomaly_events", "Balance anomalies"),
    ):
        if int(checks[key]):
            alerts.append(_alert("CRITICAL", title, f"Lifecycle check observed {checks[key]} {key}."))

    alerts.append(
        _alert(
            "INFO",
            "Exchange precision delegated",
            "Sandbox order precision and minimum order checks are delegated to Hummingbot.",
        )
    )
    return alerts


def _decision(alerts: list[dict[str, object]]) -> str:
    if any(alert["severity"] == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert["severity"] == "WARN" for alert in alerts):
        return "sandbox_prepared_with_warnings"
    return "sandbox_prepared"


def _recommended_actions(decision: str, alerts: list[dict[str, object]]) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not start Hummingbot Sandbox.",
            "Fix all CRITICAL alerts and regenerate the sandbox manifest.",
            "Keep live trading disabled.",
        )
    actions = [
        "Load only the generated sandbox manifest into Hummingbot sandbox or paper mode.",
        "Keep exchange live credentials disabled.",
        "Verify Hummingbot reports accepted precision and minimum order sizes for every order.",
        "Capture Hummingbot submitted, filled, canceled, failed, disconnect, and balance events.",
        "Run reconciliation before any Phase 5.1 extension.",
    ]
    if any(alert["title"] == "Source review has warnings" for alert in alerts):
        actions.append("Carry Phase 4.3 WARN items into the sandbox runbook.")
    return tuple(actions)


def _alert(severity: str, title: str, message: str) -> dict[str, object]:
    return {
        "severity": severity,
        "title": title,
        "message": message,
        "created_at": datetime.now(tz=UTC).isoformat(),
    }
