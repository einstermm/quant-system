"""Generate Phase 6.6 Hummingbot live one-batch runner files."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.cli_paper_handoff import _write_json, _write_text, _yaml

SCRIPT_NAME = "quant_system_live_one_batch.py"
SCRIPT_CONFIG_NAME = "crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml"
EVENT_LOG_NAME = "crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl"


@dataclass(frozen=True, slots=True)
class LiveOneBatchRunnerPackage:
    decision: str
    generated_at: datetime
    session_id: str
    output_dir: str
    script_config_name: str
    event_log_path: str
    launch_command: str
    summary: dict[str, object]
    artifacts: dict[str, str]
    install_targets: dict[str, str]
    checklist: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "output_dir": self.output_dir,
            "script_config_name": self.script_config_name,
            "event_log_path": self.event_log_path,
            "launch_command": self.launch_command,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "install_targets": self.install_targets,
            "checklist": list(self.checklist),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.6 Live One-Batch Runner",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Script config: `{self.script_config_name}`",
            f"- Event log path: `{self.event_log_path}`",
            f"- Orders: `{self.summary['order_count']}`",
            f"- Connector: `{self.summary['connector_name']}`",
            f"- Live order submission armed: `{self.summary['live_order_submission_armed']}`",
            "",
            "## Summary",
            "",
        ]
        lines.extend(f"- {key}: `{value}`" for key, value in self.summary.items())
        lines.extend(["", "## Checklist", ""])
        lines.extend(
            f"- `{item['status']}` {item['title']}: {item['details']}"
            + (f" Evidence: `{item['evidence']}`" if item.get("evidence") else "")
            for item in self.checklist
        )
        lines.extend(["", "## Install Targets", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.install_targets.items())
        lines.extend(
            [
                "",
                "## Launch Command",
                "",
                "Do not run this unless you intend to place the live order.",
                "",
            ]
        )
        lines.extend(["```bash", self.launch_command, "```", ""])
        lines.extend(["## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_one_batch_runner_package(
    *,
    candidate_package: dict[str, Any],
    output_dir: str | Path,
    hummingbot_root: str | Path,
    session_id: str,
    exchange_state_confirmed: bool,
    install: bool = True,
    script_config_name: str = SCRIPT_CONFIG_NAME,
    event_log_path: str = f"/home/hummingbot/data/{EVENT_LOG_NAME}",
) -> LiveOneBatchRunnerPackage:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    root = Path(hummingbot_root)
    orders = _orders(candidate_package)
    script_config = _script_config(
        candidate_package=candidate_package,
        orders=orders,
        script_config_name=script_config_name,
        event_log_path=event_log_path,
    )
    summary = _summary(candidate_package, orders, script_config)
    event_log_host_path = _host_event_log_path(root, event_log_path)
    checklist = _checklist(
        candidate_package=candidate_package,
        orders=orders,
        exchange_state_confirmed=exchange_state_confirmed,
        event_log_host_path=event_log_host_path,
    )
    decision = _decision(checklist)

    artifacts = {
        "script_source": str(_write_text(_script_source(), output_path / "scripts" / SCRIPT_NAME)),
        "script_config": str(
            _write_text(
                _yaml(script_config),
                output_path / "conf" / "scripts" / script_config_name,
            )
        ),
        "event_log_host_path": str(event_log_host_path),
    }
    install_targets = {
        "script_source": str(root / "scripts" / SCRIPT_NAME),
        "script_config": str(root / "conf" / "scripts" / script_config_name),
        "event_log_host_path": str(event_log_host_path),
    }
    if decision == "live_one_batch_runner_ready" and install:
        _write_text(_script_source(), install_targets["script_source"])
        _write_text(_yaml(script_config), install_targets["script_config"])

    package = LiveOneBatchRunnerPackage(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        output_dir=str(output_path),
        script_config_name=script_config_name,
        event_log_path=event_log_path,
        launch_command=_launch_command(script_config_name),
        summary=summary,
        artifacts={},
        install_targets=install_targets,
        checklist=tuple(checklist),
    )
    artifacts["package_json"] = str(output_path / "package.json")
    artifacts["package_md"] = str(output_path / "package.md")
    package = replace(package, artifacts=artifacts)
    _write_json(package.to_dict(), output_path / "package.json")
    _write_text(package.to_markdown(), output_path / "package.md")
    return package


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _orders(candidate_package: dict[str, Any]) -> list[dict[str, object]]:
    raw_orders = candidate_package.get("candidate_orders", [])
    if not isinstance(raw_orders, list):
        raise ValueError("candidate_orders must be a list")
    return [order for order in raw_orders if isinstance(order, dict)]


def _script_config(
    *,
    candidate_package: dict[str, Any],
    orders: list[dict[str, object]],
    script_config_name: str,
    event_log_path: str,
) -> dict[str, object]:
    return {
        "script_file_name": SCRIPT_NAME,
        "connector_name": str(candidate_package.get("connector", "binance")),
        "event_log_path": event_log_path,
        "live_order_submission_armed": True,
        "exchange_state_confirmed": True,
        "allowed_pairs": candidate_package.get("allowed_pairs", []),
        "max_batch_notional": str(_risk(candidate_package, "max_batch_notional")),
        "max_order_notional": str(_risk(candidate_package, "max_batch_notional")),
        "quote_balance_safety_factor": "1.02",
        "amount_safety_factor": "0.99",
        "max_price_deviation_pct": "0.02",
        "order_interval_seconds": "5",
        "heartbeat_interval_seconds": "10",
        "balance_snapshot_interval_seconds": "30",
        "observation_min_runtime_seconds": "30",
        "stop_after_terminal_orders": True,
        "script_config_name": script_config_name,
        "orders": [_script_order(order) for order in orders],
    }


def _script_order(order: dict[str, object]) -> dict[str, object]:
    return {
        "client_order_id": str(order["client_order_id"]),
        "trading_pair": str(order["trading_pair"]),
        "side": str(order["side"]).lower(),
        "order_type": "market",
        "requested_quote_notional": str(order["notional_quote"]),
        "estimated_price": str(order["estimated_price"]),
        "estimated_quantity": str(order["estimated_quantity"]),
        "signal_momentum": str(order.get("signal_momentum", "")),
        "signal_timestamp": str(order.get("signal_timestamp", "")),
    }


def _summary(
    candidate_package: dict[str, Any],
    orders: list[dict[str, object]],
    script_config: dict[str, object],
) -> dict[str, object]:
    total_notional = sum((_decimal(order["notional_quote"]) for order in orders), Decimal("0"))
    return {
        "candidate_package_decision": str(candidate_package.get("decision", "")),
        "strategy_id": str(candidate_package.get("strategy_id", "")),
        "batch_id": str(candidate_package.get("batch_id", "")),
        "connector_name": str(script_config["connector_name"]),
        "order_count": len(orders),
        "total_requested_quote_notional": str(total_notional),
        "max_batch_notional": str(script_config["max_batch_notional"]),
        "max_order_notional": str(script_config["max_order_notional"]),
        "allowed_pairs": list(candidate_package.get("allowed_pairs", [])),
        "live_order_submission_armed": bool(script_config["live_order_submission_armed"]),
        "exchange_state_confirmed": bool(script_config["exchange_state_confirmed"]),
        "amount_safety_factor": str(script_config["amount_safety_factor"]),
        "quote_balance_safety_factor": str(script_config["quote_balance_safety_factor"]),
        "max_price_deviation_pct": str(script_config["max_price_deviation_pct"]),
    }


def _checklist(
    *,
    candidate_package: dict[str, Any],
    orders: list[dict[str, object]],
    exchange_state_confirmed: bool,
    event_log_host_path: Path,
) -> list[dict[str, str]]:
    allowed_pairs = set(str(pair) for pair in candidate_package.get("allowed_pairs", []))
    max_batch_notional = _risk(candidate_package, "max_batch_notional")
    max_order_notional = _risk(candidate_package, "max_batch_notional")
    total_notional = sum((_decimal(order["notional_quote"]) for order in orders), Decimal("0"))
    return [
        _item(
            "candidate_package_ready",
            "Phase 6.5 candidate package ready",
            "PASS"
            if candidate_package.get("decision")
            == "live_batch_execution_package_ready_pending_exchange_state_check"
            else "FAIL",
            f"Phase 6.5 decision is {candidate_package.get('decision', 'unknown')}.",
        ),
        _item(
            "exchange_state_confirmed",
            "Exchange state manually confirmed",
            "PASS" if exchange_state_confirmed else "MANUAL_REQUIRED",
            "Operator confirmed Binance spot balance, open orders, and exposure constraints.",
        ),
        _item(
            "single_order_only",
            "One live order only",
            "PASS" if len(orders) == 1 else "FAIL",
            f"orders={len(orders)}.",
        ),
        _item(
            "allowlist",
            "All orders are inside allowlist",
            "PASS"
            if all(str(order["trading_pair"]) in allowed_pairs for order in orders)
            else "FAIL",
            f"allowed_pairs={sorted(allowed_pairs)}.",
        ),
        _item(
            "order_notional",
            "All orders are inside order cap",
            "PASS"
            if all(_decimal(order["notional_quote"]) <= max_order_notional for order in orders)
            else "FAIL",
            f"max_order_notional={max_order_notional}.",
        ),
        _item(
            "batch_notional",
            "Batch is inside notional cap",
            "PASS" if total_notional <= max_batch_notional else "FAIL",
            f"total_notional={total_notional}; max_batch_notional={max_batch_notional}.",
        ),
        _item(
            "event_log_absent",
            "Event log path is clear",
            "PASS" if not event_log_host_path.exists() else "FAIL",
            "Existing event logs must be archived before a live run.",
            str(event_log_host_path),
        ),
    ]


def _decision(checklist: list[dict[str, str]]) -> str:
    if any(item["status"] == "FAIL" for item in checklist):
        return "live_one_batch_runner_blocked"
    if any(item["status"] == "MANUAL_REQUIRED" for item in checklist):
        return "live_one_batch_runner_pending_exchange_state"
    return "live_one_batch_runner_ready"


def _item(
    item_id: str,
    title: str,
    status: str,
    details: str,
    evidence: str = "",
) -> dict[str, str]:
    return {
        "item_id": item_id,
        "title": title,
        "status": status,
        "details": details,
        "evidence": evidence,
    }


def _risk(candidate_package: dict[str, Any], key: str) -> Decimal:
    return _decimal(_dict(candidate_package.get("risk_summary")).get(key, "0"))


def _host_event_log_path(hummingbot_root: Path, container_event_log_path: str) -> Path:
    prefix = "/home/hummingbot/"
    if container_event_log_path.startswith(prefix):
        return hummingbot_root / container_event_log_path.removeprefix(prefix)
    return hummingbot_root / "data" / Path(container_event_log_path).name


def _launch_command(script_config_name: str) -> str:
    return (
        "if docker ps --format '{{.Names}}' | grep -qx hummingbot; then "
        "echo 'Stop the existing hummingbot container first: docker stop hummingbot'; "
        "exit 1; "
        "fi; "
        "read -rsp 'Hummingbot password: ' HBOT_PASSWORD; echo; "
        "docker run --rm --name quant-phase-6-6-live-one-batch-low-funds-50 "
        "-v /Users/albertlz/Downloads/private_proj/hummingbot/conf:/home/hummingbot/conf "
        "-v /Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors:/home/hummingbot/conf/connectors "
        "-v /Users/albertlz/Downloads/private_proj/hummingbot/conf/scripts:/home/hummingbot/conf/scripts "
        "-v /Users/albertlz/Downloads/private_proj/hummingbot/data:/home/hummingbot/data "
        "-v /Users/albertlz/Downloads/private_proj/hummingbot/logs:/home/hummingbot/logs "
        "-v /Users/albertlz/Downloads/private_proj/hummingbot/scripts:/home/hummingbot/scripts "
        "hummingbot/hummingbot:latest "
        f"/bin/bash -lc \"conda activate hummingbot && ./bin/hummingbot_quickstart.py "
        f"--headless --config-password \\\"$HBOT_PASSWORD\\\" --v2 {script_config_name}\""
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _script_source() -> str:
    return '''"""Quant system one-batch live runner for Hummingbot CLI."""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import Field

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict, OrderType, TradeType
from hummingbot.core.event.events import MarketOrderFailureEvent, OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class QuantSystemLiveOneBatchConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    controllers_config: List[str] = []
    connector_name: str = "binance"
    event_log_path: str = "/home/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl"
    live_order_submission_armed: bool = False
    exchange_state_confirmed: bool = False
    allowed_pairs: List[str] = Field(default_factory=list)
    max_batch_notional: str = "0"
    max_order_notional: str = "0"
    quote_balance_safety_factor: str = "1.02"
    amount_safety_factor: str = "0.99"
    max_price_deviation_pct: str = "0.02"
    order_interval_seconds: int = 5
    heartbeat_interval_seconds: int = 10
    balance_snapshot_interval_seconds: int = 30
    observation_min_runtime_seconds: int = 30
    stop_after_terminal_orders: bool = True
    script_config_name: str = ""
    orders: List[Dict[str, Any]] = Field(default_factory=list)

    def update_markets(self, markets: MarketDict) -> MarketDict:
        for order in self.orders:
            markets.add_or_update(self.connector_name, str(order["trading_pair"]))
        return markets


class QuantSystemLiveOneBatch(StrategyV2Base):
    def __init__(self, connectors: Dict[str, ConnectorBase], config: QuantSystemLiveOneBatchConfig):
        super().__init__(connectors, config)
        self.config = config
        self._next_order_index = 0
        self._last_submit_ts = 0
        self._submitted_client_ids = set()
        self._filled_client_ids = set()
        self._terminal_client_ids = set()
        self._hb_order_to_source: Dict[str, Dict[str, Any]] = {}
        self._started_ts = 0
        self._last_heartbeat_ts = 0
        self._last_balance_snapshot_ts = 0
        self._submitted_notional = Decimal("0")
        self._final_balance_snapshot_written = False
        self._stop_requested = False

    def on_tick(self):
        if not self.ready_to_trade:
            return
        if self._started_ts == 0:
            self._started_ts = self.current_timestamp
            self._append_event("session_started", self._system_payload(), order_count=len(self.config.orders))
            self._append_balance_snapshot(snapshot_type="initial")
        self._append_periodic_observation_events()
        if not self.config.live_order_submission_armed or not self.config.exchange_state_confirmed:
            self._append_event("blocked", self._system_payload(), reason="live_runner_not_armed")
            self._terminal_client_ids.add("session")
            self._maybe_stop_if_done()
            return
        if len(self._terminal_client_ids) >= len(self.config.orders):
            self._maybe_stop_if_done()
            return
        if self._next_order_index >= len(self.config.orders):
            return
        if self.current_timestamp - self._last_submit_ts < self.config.order_interval_seconds:
            return
        order = self.config.orders[self._next_order_index]
        self._next_order_index += 1
        self._place_live_order(order)
        self._last_submit_ts = self.current_timestamp

    def _place_live_order(self, order: Dict[str, Any]):
        client_order_id = str(order["client_order_id"])
        trading_pair = str(order["trading_pair"])
        if trading_pair not in self.config.allowed_pairs:
            self._fail_order(order, reason="trading_pair_not_allowed")
            return
        side = TradeType.BUY if str(order["side"]).lower() == "buy" else TradeType.SELL
        connector = self.connectors[self.config.connector_name]
        current_price = Decimal(str(connector.get_price(trading_pair, side == TradeType.BUY)))
        if current_price <= Decimal("0"):
            self._fail_order(order, reason="non_positive_live_price")
            return
        estimated_price = Decimal(str(order["estimated_price"]))
        max_deviation = Decimal(str(self.config.max_price_deviation_pct))
        if side == TradeType.BUY and current_price > estimated_price * (Decimal("1") + max_deviation):
            self._fail_order(order, reason="buy_price_deviation_exceeded", current_price=current_price)
            return
        if side == TradeType.SELL and current_price < estimated_price * (Decimal("1") - max_deviation):
            self._fail_order(order, reason="sell_price_deviation_exceeded", current_price=current_price)
            return

        requested_notional = Decimal(str(order["requested_quote_notional"]))
        remaining_batch = Decimal(str(self.config.max_batch_notional)) - self._submitted_notional
        target_notional = min(requested_notional, Decimal(str(self.config.max_order_notional)), remaining_batch)
        target_notional = target_notional * Decimal(str(self.config.amount_safety_factor))
        if target_notional <= Decimal("0"):
            self._fail_order(order, reason="non_positive_target_notional")
            return
        amount = target_notional / current_price
        if side == TradeType.BUY and not self._has_quote_balance(trading_pair, target_notional):
            self._fail_order(order, reason="insufficient_quote_balance", current_price=current_price)
            return
        if side == TradeType.SELL:
            amount = self._cap_to_available_base(trading_pair, amount)
            if amount <= Decimal("0"):
                self._fail_order(order, reason="insufficient_base_balance", current_price=current_price)
                return

        source_order = dict(order)
        source_order["current_price"] = str(current_price)
        source_order["submitted_amount"] = str(amount)
        source_order["submitted_notional_quote"] = str(target_notional)
        try:
            if side == TradeType.BUY:
                hb_order_id = self.buy(self.config.connector_name, trading_pair, amount, OrderType.MARKET, current_price)
            else:
                hb_order_id = self.sell(self.config.connector_name, trading_pair, amount, OrderType.MARKET, current_price)
        except Exception as exc:
            self._fail_order(source_order, reason=f"submission_exception:{exc}")
            return
        source_order["hb_order_id"] = hb_order_id
        self._hb_order_to_source[hb_order_id] = source_order
        self._submitted_client_ids.add(client_order_id)
        self._submitted_notional += target_notional
        self._append_event("submitted", source_order, hb_order_id=hb_order_id)
        self.logger().info(f"Submitted quant system live order {client_order_id} as {hb_order_id}")

    def _has_quote_balance(self, trading_pair: str, target_notional: Decimal) -> bool:
        quote_asset = trading_pair.split("-", 1)[1]
        available = Decimal(str(self.connectors[self.config.connector_name].get_available_balance(quote_asset)))
        required = target_notional * Decimal(str(self.config.quote_balance_safety_factor))
        return available >= required

    def _cap_to_available_base(self, trading_pair: str, requested_amount: Decimal) -> Decimal:
        base_asset = trading_pair.split("-", 1)[0]
        available = Decimal(str(self.connectors[self.config.connector_name].get_available_balance(base_asset)))
        if available >= requested_amount:
            return requested_amount
        return available * Decimal("0.998")

    def did_fill_order(self, event: OrderFilledEvent):
        order = self._hb_order_to_source.get(event.order_id)
        if order is None:
            return
        client_order_id = str(order["client_order_id"])
        self._filled_client_ids.add(client_order_id)
        fee_quote = Decimal("0")
        try:
            fee_quote = event.trade_fee.percent * event.price * event.amount
        except Exception:
            fee_quote = Decimal("0")
        self._append_event(
            "filled",
            order,
            hb_order_id=event.order_id,
            filled_amount=str(event.amount),
            average_fill_price=str(event.price),
            fee_quote=str(fee_quote),
            exchange_trade_id=str(getattr(event, "exchange_trade_id", "")),
        )
        self.log_with_clock(logging.INFO, f"Filled quant system live order {client_order_id} via {event.order_id}")
        self._terminal_client_ids.add(client_order_id)
        self._maybe_stop_if_done()

    def did_fail_order(self, event: MarketOrderFailureEvent):
        order = self._hb_order_to_source.get(event.order_id, self._system_payload())
        self._append_event("failed", order, hb_order_id=event.order_id, reason=str(getattr(event, "error_message", "")))
        self._terminal_client_ids.add(str(order["client_order_id"]))
        self._maybe_stop_if_done()

    def _fail_order(self, order: Dict[str, Any], **extra):
        self._submitted_client_ids.add(str(order["client_order_id"]))
        self._terminal_client_ids.add(str(order["client_order_id"]))
        self._append_event("failed", order, **extra)
        self._maybe_stop_if_done()

    def _maybe_stop_if_done(self):
        expected_terminals = max(1, len(self.config.orders))
        if len(self._terminal_client_ids) < expected_terminals:
            return
        if not self._final_balance_snapshot_written:
            self._append_balance_snapshot(snapshot_type="final")
            self._final_balance_snapshot_written = True
        if not self.config.stop_after_terminal_orders:
            return
        if self.current_timestamp - self._started_ts < self.config.observation_min_runtime_seconds:
            return
        if not self._stop_requested:
            self._stop_requested = True
            self._append_event(
                "session_completed",
                self._system_payload(),
                submitted_orders=len(self._submitted_client_ids),
                filled_orders=len(self._filled_client_ids),
                terminal_orders=len(self._terminal_client_ids),
                runtime_seconds=self.current_timestamp - self._started_ts,
            )
            HummingbotApplication.main_application().stop()

    def _append_periodic_observation_events(self):
        if (
            self.config.heartbeat_interval_seconds > 0
            and self.current_timestamp - self._last_heartbeat_ts >= self.config.heartbeat_interval_seconds
        ):
            self._last_heartbeat_ts = self.current_timestamp
            self._append_event(
                "heartbeat",
                self._system_payload(),
                submitted_orders=len(self._submitted_client_ids),
                filled_orders=len(self._filled_client_ids),
                terminal_orders=len(self._terminal_client_ids),
                next_order_index=self._next_order_index,
                runtime_seconds=self.current_timestamp - self._started_ts,
            )
        if (
            self.config.balance_snapshot_interval_seconds > 0
            and self.current_timestamp - self._last_balance_snapshot_ts >= self.config.balance_snapshot_interval_seconds
        ):
            self._last_balance_snapshot_ts = self.current_timestamp
            self._append_balance_snapshot(snapshot_type="periodic")

    def _append_balance_snapshot(self, snapshot_type: str):
        connector = self.connectors[self.config.connector_name]
        for asset, balance in sorted(connector.get_all_balances().items()):
            self._append_event(
                "balance",
                {
                    "client_order_id": f"balance-{asset}",
                    "trading_pair": f"{asset}-USDT",
                    "side": "balance",
                    "requested_quote_notional": "0",
                    "estimated_price": "0",
                },
                balance_asset=asset,
                balance_total=str(balance),
                balance_available=str(connector.get_available_balance(asset)),
                snapshot_type=snapshot_type,
            )

    def _system_payload(self) -> Dict[str, Any]:
        return {
            "client_order_id": "session",
            "trading_pair": "SESSION-USDT",
            "side": "system",
            "requested_quote_notional": "0",
            "estimated_price": "0",
        }

    def _append_event(self, event_type: str, order: Dict[str, Any], **extra):
        event = {
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "client_order_id": str(order["client_order_id"]),
            "connector_name": self.config.connector_name,
            "trading_pair": str(order["trading_pair"]),
            "side": str(order.get("side", "")),
            "requested_quote_notional": str(order.get("requested_quote_notional", "0")),
            "estimated_price": str(order.get("estimated_price", "0")),
            "signal_timestamp": str(order.get("signal_timestamp", "")),
        }
        for key in ("current_price", "submitted_amount", "submitted_notional_quote", "hb_order_id"):
            if key in order:
                event[key] = str(order[key])
        event.update({key: str(value) for key, value in extra.items()})
        directory = os.path.dirname(self.config.event_log_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.config.event_log_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(event, sort_keys=True) + "\\n")

    def format_status(self) -> str:
        return (
            f"Quant system live one-batch runner\\n"
            f"Submitted: {len(self._submitted_client_ids)} / {len(self.config.orders)}\\n"
            f"Filled: {len(self._filled_client_ids)} / {len(self.config.orders)}\\n"
            f"Terminal: {len(self._terminal_client_ids)} / {len(self.config.orders)}\\n"
            f"Submitted notional: {self._submitted_notional}\\n"
            f"Event log: {self.config.event_log_path}"
        )
'''
