"""Build direct Hummingbot CLI paper-order script handoff files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.cli_paper_handoff import _write_json, _write_text, _yaml
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert

SCRIPT_NAME = "quant_system_cli_paper_orders.py"
SCRIPT_CONFIG_NAME = "crypto_relative_strength_v1_phase_5_7_direct_paper.yml"
EVENT_LOG_NAME = "crypto_relative_strength_v1_phase_5_7_hummingbot_events.jsonl"


@dataclass(frozen=True, slots=True)
class CliDirectPaperHandoffResult:
    decision: str
    generated_at: datetime
    session_id: str
    output_dir: str
    script_config_name: str
    event_log_path: str
    artifacts: dict[str, str]
    install_targets: dict[str, str]
    summary: dict[str, object]
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "output_dir": self.output_dir,
            "script_config_name": self.script_config_name,
            "event_log_path": self.event_log_path,
            "artifacts": self.artifacts,
            "install_targets": self.install_targets,
            "summary": self.summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot CLI Direct Paper Handoff",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Script: `{SCRIPT_NAME}`",
            f"- Script config: `{self.script_config_name}`",
            f"- Orders: `{self.summary['order_count']}`",
            f"- Event log path in container: `{self.event_log_path}`",
            "",
            "## Artifacts",
            "",
        ]
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.extend(["", "## Install Targets", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.install_targets.items())
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def build_cli_direct_paper_handoff(
    *,
    manifest: dict[str, Any],
    runtime_preflight: dict[str, Any],
    output_dir: str | Path,
    session_id: str,
    hummingbot_root: str | Path,
    allow_warnings: bool,
    event_log_path: str = f"/home/hummingbot/data/{EVENT_LOG_NAME}",
    script_config_name: str = SCRIPT_CONFIG_NAME,
    observation_min_runtime_seconds: int = 0,
    heartbeat_interval_seconds: int = 60,
    balance_snapshot_interval_seconds: int = 300,
) -> CliDirectPaperHandoffResult:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    orders = _orders(manifest)
    script_config = {
        "script_file_name": SCRIPT_NAME,
        "connector_name": str(manifest.get("connector_name", "binance_paper_trade")),
        "event_log_path": event_log_path,
        "order_interval_seconds": 5,
        "observation_min_runtime_seconds": observation_min_runtime_seconds,
        "heartbeat_interval_seconds": heartbeat_interval_seconds,
        "balance_snapshot_interval_seconds": balance_snapshot_interval_seconds,
        "stop_after_terminal_orders": True,
        "orders": [_script_order(order) for order in orders],
    }
    summary = _summary(manifest, runtime_preflight, orders)
    summary.update(
        {
            "observation_min_runtime_seconds": observation_min_runtime_seconds,
            "heartbeat_interval_seconds": heartbeat_interval_seconds,
            "balance_snapshot_interval_seconds": balance_snapshot_interval_seconds,
        }
    )
    alerts = _build_alerts(summary=summary, runtime_preflight=runtime_preflight, allow_warnings=allow_warnings)
    decision = _decision(alerts)
    artifacts = {
        "script_source": str(_write_text(_script_source(), output_path / "scripts" / SCRIPT_NAME)),
        "script_config": str(_write_text(_yaml(script_config), output_path / "conf" / "scripts" / script_config_name)),
        "expected_event_log_host_path": str(Path(hummingbot_root) / "data" / EVENT_LOG_NAME),
    }
    install_targets = {
        "script_source": str(Path(hummingbot_root) / "scripts" / SCRIPT_NAME),
        "script_config": str(Path(hummingbot_root) / "conf" / "scripts" / script_config_name),
        "event_log_host_path": str(_host_event_log_path(Path(hummingbot_root), event_log_path)),
    }
    artifacts["expected_event_log_host_path"] = install_targets["event_log_host_path"]
    result = CliDirectPaperHandoffResult(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        output_dir=str(output_path),
        script_config_name=script_config_name,
        event_log_path=event_log_path,
        artifacts=artifacts,
        install_targets=install_targets,
        summary=summary,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision),
    )
    artifacts["handoff_json"] = str(output_path / "handoff.json")
    artifacts["handoff_md"] = str(output_path / "handoff.md")
    _write_json(result.to_dict(), output_path / "handoff.json")
    _write_text(result.to_markdown(), output_path / "handoff.md")
    return result


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _host_event_log_path(hummingbot_root: Path, container_event_log_path: str) -> Path:
    prefix = "/home/hummingbot/"
    if container_event_log_path.startswith(prefix):
        return hummingbot_root / container_event_log_path.removeprefix(prefix)
    return hummingbot_root / "data" / Path(container_event_log_path).name


def _orders(manifest: dict[str, Any]) -> list[dict[str, object]]:
    payload = manifest.get("orders", [])
    if not isinstance(payload, list):
        raise TypeError("manifest orders must be a list")
    return [order for order in payload if isinstance(order, dict)]


def _script_order(order: dict[str, object]) -> dict[str, object]:
    return {
        "client_order_id": str(order["client_order_id"]),
        "trading_pair": str(order["trading_pair"]),
        "side": str(order["side"]).lower(),
        "amount": str(order["amount"]),
        "price": str(order["price"]),
        "notional_quote": str(order["notional_quote"]),
        "expected_fee_quote": str(order.get("expected_fee_quote", "0")),
        "source_intent_id": str(order.get("source_intent_id", "")),
    }


def _summary(
    manifest: dict[str, Any],
    runtime_preflight: dict[str, Any],
    orders: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "strategy_id": str(manifest.get("strategy_id", "")),
        "connector_name": str(manifest.get("connector_name", "")),
        "live_trading_enabled": bool(manifest.get("live_trading_enabled")),
        "order_count": len(orders),
        "runtime_preflight_decision": str(runtime_preflight.get("decision", "unknown")),
        "paper_trade_connectors": runtime_preflight.get("paper_trade_connectors", []),
    }


def _build_alerts(
    *,
    summary: dict[str, object],
    runtime_preflight: dict[str, Any],
    allow_warnings: bool,
) -> list[Alert]:
    alerts: list[Alert] = []
    if summary["live_trading_enabled"]:
        alerts.append(critical_alert("Manifest live trading enabled", "Direct paper handoff requires live_trading_enabled=false."))
    if summary["connector_name"] != "binance_paper_trade":
        alerts.append(warning_alert("Unexpected connector", f"Expected binance_paper_trade, got {summary['connector_name']}."))
    if int(summary["order_count"]) == 0:
        alerts.append(critical_alert("No orders", "Manifest contains no orders for Hummingbot paper mode."))
    preflight_decision = str(summary["runtime_preflight_decision"])
    if preflight_decision == "blocked":
        alerts.append(critical_alert("Runtime preflight blocked", "Phase 5.5 runtime preflight is blocked."))
    elif preflight_decision.endswith("_with_warnings") and not allow_warnings:
        alerts.append(critical_alert("Runtime preflight warnings", f"Runtime preflight is {preflight_decision}."))
    elif preflight_decision.endswith("_with_warnings"):
        alerts.append(warning_alert("Runtime preflight warnings", f"Runtime preflight is {preflight_decision}."))
    if "binance_paper_trade" not in runtime_preflight.get("paper_trade_connectors", []):
        alerts.append(critical_alert("Paper connector missing", "binance_paper_trade is not enabled in Hummingbot conf_client.yml."))
    alerts.append(info_alert("Direct CLI paper mode", "Generated script uses Hummingbot direct buy/sell paper orders and keeps live trading disabled."))
    return alerts


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "cli_direct_paper_handoff_ready_with_warnings"
    return "cli_direct_paper_handoff_ready"


def _recommended_actions(decision: str) -> tuple[str, ...]:
    if decision == "blocked":
        return ("Do not install or start the direct paper script.", "Fix all CRITICAL alerts and regenerate.", "Keep live trading disabled.")
    return (
        "Install the generated script and script config into the Hummingbot CLI mounts.",
        "Delete the prior direct paper event JSONL before a fresh dry run.",
        "Start Hummingbot headless with the generated SCRIPT_CONFIG.",
        "Run Phase 5.4 export acceptance on the direct paper event JSONL.",
    )


def _script_source() -> str:
    return '''"""Quant system direct paper order script for Hummingbot CLI."""

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
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class QuantSystemCliPaperOrdersConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    controllers_config: List[str] = []
    connector_name: str = "binance_paper_trade"
    orders: List[Dict[str, Any]] = Field(default_factory=list)
    event_log_path: str = "/home/hummingbot/data/crypto_relative_strength_v1_phase_5_7_hummingbot_events.jsonl"
    order_interval_seconds: int = 5
    sell_balance_safety_factor: str = "0.998"
    observation_min_runtime_seconds: int = 0
    heartbeat_interval_seconds: int = 60
    balance_snapshot_interval_seconds: int = 300
    stop_after_terminal_orders: bool = True

    def update_markets(self, markets: MarketDict) -> MarketDict:
        for order in self.orders:
            markets.add_or_update(self.connector_name, str(order["trading_pair"]))
        return markets


class QuantSystemCliPaperOrders(StrategyV2Base):
    def __init__(self, connectors: Dict[str, ConnectorBase], config: QuantSystemCliPaperOrdersConfig):
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
        self._final_balance_snapshot_written = False
        self._stop_requested = False

    def on_tick(self):
        if not self.ready_to_trade:
            return
        if self._started_ts == 0:
            self._started_ts = self.current_timestamp
            self._append_event("session_started", self._system_payload(), order_count=len(self.config.orders))
        self._append_periodic_observation_events()
        if len(self._terminal_client_ids) >= len(self.config.orders):
            self._maybe_stop_if_done()
            return
        if self._next_order_index >= len(self.config.orders):
            return
        if self.current_timestamp - self._last_submit_ts < self.config.order_interval_seconds:
            return
        order = self.config.orders[self._next_order_index]
        self._next_order_index += 1
        self._place_manifest_order(order)
        self._last_submit_ts = self.current_timestamp

    def _place_manifest_order(self, order: Dict[str, Any]):
        client_order_id = str(order["client_order_id"])
        side = TradeType.BUY if str(order["side"]).lower() == "buy" else TradeType.SELL
        requested_amount = Decimal(str(order["amount"]))
        amount = self._paper_safe_amount(side, str(order["trading_pair"]), requested_amount)
        price = Decimal(str(order["price"]))
        source_order = dict(order)
        source_order["requested_amount"] = str(requested_amount)
        source_order["submitted_amount"] = str(amount)
        if amount != requested_amount:
            source_order["amount_adjustment_reason"] = "paper_available_balance_cap"
        if amount <= Decimal("0"):
            self._submitted_client_ids.add(client_order_id)
            self._terminal_client_ids.add(client_order_id)
            self._append_event("failed", source_order, reason="non_positive_adjusted_amount")
            self._maybe_stop_if_done()
            return
        if side == TradeType.BUY:
            hb_order_id = self.buy(self.config.connector_name, str(order["trading_pair"]), amount, OrderType.MARKET, price)
        else:
            hb_order_id = self.sell(self.config.connector_name, str(order["trading_pair"]), amount, OrderType.MARKET, price)
        source_order["hb_order_id"] = hb_order_id
        self._hb_order_to_source[hb_order_id] = source_order
        self._submitted_client_ids.add(client_order_id)
        self._append_event("submitted", source_order, hb_order_id=hb_order_id)
        self.logger().info(f"Submitted quant system paper order {client_order_id} as {hb_order_id}")

    def _paper_safe_amount(self, side: TradeType, trading_pair: str, requested_amount: Decimal) -> Decimal:
        if side != TradeType.SELL:
            return requested_amount
        base_asset = trading_pair.split("-", 1)[0]
        try:
            available = Decimal(str(self.connectors[self.config.connector_name].get_available_balance(base_asset)))
        except Exception as exc:
            self.logger().warning(f"Could not read available {base_asset} balance before sell sizing: {exc}")
            return requested_amount
        if available <= Decimal("0") or available >= requested_amount:
            return requested_amount
        safety_factor = Decimal(str(self.config.sell_balance_safety_factor))
        adjusted = available * safety_factor
        self.logger().warning(
            f"Capping paper sell amount for {trading_pair}: requested={requested_amount} "
            f"available={available} adjusted={adjusted}"
        )
        return adjusted

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
        self.log_with_clock(logging.INFO, f"Filled quant system paper order {client_order_id} via {event.order_id}")
        self._terminal_client_ids.add(client_order_id)
        self._maybe_stop_if_done()

    def _maybe_stop_if_done(self):
        if len(self._terminal_client_ids) < len(self.config.orders):
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
                {"client_order_id": f"balance-{asset}", "trading_pair": f"{asset}-USDT", "side": "balance", "amount": "0", "price": "0", "notional_quote": "0"},
                balance_asset=asset,
                balance_total=str(balance),
                snapshot_type=snapshot_type,
            )

    def _system_payload(self) -> Dict[str, Any]:
        return {
            "client_order_id": "session",
            "trading_pair": "SESSION-USDT",
            "side": "system",
            "amount": "0",
            "price": "0",
            "notional_quote": "0",
        }

    def _append_event(self, event_type: str, order: Dict[str, Any], **extra):
        event = {
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "client_order_id": str(order["client_order_id"]),
            "connector_name": self.config.connector_name,
            "trading_pair": str(order["trading_pair"]),
            "side": str(order.get("side", "")),
            "amount": str(order.get("amount", "0")),
            "price": str(order.get("price", "0")),
            "notional_quote": str(order.get("notional_quote", "0")),
        }
        for key in ("requested_amount", "submitted_amount", "amount_adjustment_reason"):
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
            f"Quant system direct paper orders\\n"
            f"Submitted: {len(self._submitted_client_ids)} / {len(self.config.orders)}\\n"
            f"Filled: {len(self._filled_client_ids)} / {len(self.config.orders)}\\n"
            f"Terminal: {len(self._terminal_client_ids)} / {len(self.config.orders)}\\n"
            f"Runtime seconds: {self.current_timestamp - self._started_ts if self._started_ts else 0}\\n"
            f"Event log: {self.config.event_log_path}"
        )
'''
