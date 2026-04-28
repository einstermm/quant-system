"""Build Hummingbot CLI paper-mode handoff files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert

CONTROLLER_MODULE_NAME = "quant_system_sandbox_order_controller"
SCRIPT_CONFIG_NAME = "crypto_relative_strength_v1_phase_5_6_v2_with_controllers.yml"
EVENT_LOG_NAME = "crypto_relative_strength_v1_phase_5_6_hummingbot_events.jsonl"


@dataclass(frozen=True, slots=True)
class CliPaperHandoffResult:
    decision: str
    generated_at: datetime
    session_id: str
    output_dir: str
    script_config_name: str
    event_log_path: str
    install_targets: dict[str, str]
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
            "script_config_name": self.script_config_name,
            "event_log_path": self.event_log_path,
            "install_targets": self.install_targets,
            "artifacts": self.artifacts,
            "summary": self.summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot CLI Paper Handoff",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.summary['strategy_id']}`",
            f"- Connector: `{self.summary['connector_name']}`",
            f"- Controller module: `{CONTROLLER_MODULE_NAME}`",
            f"- Controller configs: `{self.summary['controller_config_count']}`",
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


def build_cli_paper_handoff(
    *,
    manifest: dict[str, Any],
    runtime_preflight: dict[str, Any],
    output_dir: str | Path,
    session_id: str,
    hummingbot_root: str | Path,
    allow_warnings: bool,
    event_log_path: str = f"/home/hummingbot/data/{EVENT_LOG_NAME}",
) -> CliPaperHandoffResult:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(tz=UTC)
    orders = _orders(manifest)
    grouped_orders = _orders_by_pair(orders)
    controller_configs = _controller_configs(
        manifest=manifest,
        grouped_orders=grouped_orders,
        event_log_path=event_log_path,
    )
    script_config = {
        "script_file_name": "v2_with_controllers.py",
        "controllers_config": [config["filename"] for config in controller_configs],
    }
    summary = _summary(manifest, runtime_preflight, controller_configs, orders)
    alerts = _build_alerts(summary=summary, runtime_preflight=runtime_preflight, allow_warnings=allow_warnings)
    decision = _decision(alerts)

    controller_source = _controller_source()
    artifacts: dict[str, str] = {}
    controller_source_path = output_path / "controllers" / "generic" / f"{CONTROLLER_MODULE_NAME}.py"
    artifacts["controller_source"] = str(_write_text(controller_source, controller_source_path))

    controller_config_dir = output_path / "conf" / "controllers"
    controller_config_paths: list[str] = []
    for config in controller_configs:
        config_path = controller_config_dir / str(config["filename"])
        controller_config_paths.append(str(_write_text(str(config["yaml"]), config_path)))
    artifacts["controller_config_dir"] = str(controller_config_dir)
    artifacts["controller_config_files"] = json.dumps(controller_config_paths, sort_keys=True)

    script_config_path = output_path / "conf" / "scripts" / SCRIPT_CONFIG_NAME
    artifacts["script_config"] = str(_write_text(_yaml(script_config), script_config_path))
    artifacts["expected_event_log_host_path"] = str(Path(hummingbot_root) / "data" / EVENT_LOG_NAME)
    artifacts["operator_runbook_md"] = str(
        _write_text(
            _runbook(
                session_id=session_id,
                script_config_name=SCRIPT_CONFIG_NAME,
                event_log_path=event_log_path,
                host_event_log_path=artifacts["expected_event_log_host_path"],
            ),
            output_path / "operator_runbook.md",
        )
    )

    install_targets = {
        "controller_source": str(Path(hummingbot_root) / "controllers" / "generic" / f"{CONTROLLER_MODULE_NAME}.py"),
        "controller_config_dir": str(Path(hummingbot_root) / "conf" / "controllers"),
        "script_config": str(Path(hummingbot_root) / "conf" / "scripts" / SCRIPT_CONFIG_NAME),
        "event_log_host_path": artifacts["expected_event_log_host_path"],
    }
    result = CliPaperHandoffResult(
        decision=decision,
        generated_at=generated_at,
        session_id=session_id,
        output_dir=str(output_path),
        script_config_name=SCRIPT_CONFIG_NAME,
        event_log_path=event_log_path,
        install_targets=install_targets,
        artifacts=artifacts,
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


def write_handoff_json(result: CliPaperHandoffResult, path: str | Path) -> Path:
    return _write_json(result.to_dict(), path)


def _orders(manifest: dict[str, Any]) -> list[dict[str, object]]:
    payload = manifest.get("orders", [])
    if not isinstance(payload, list):
        raise TypeError("manifest orders must be a list")
    return [order for order in payload if isinstance(order, dict)]


def _orders_by_pair(orders: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for order in orders:
        grouped.setdefault(str(order["trading_pair"]), []).append(order)
    return dict(sorted(grouped.items()))


def _controller_configs(
    *,
    manifest: dict[str, Any],
    grouped_orders: dict[str, list[dict[str, object]]],
    event_log_path: str,
) -> list[dict[str, object]]:
    configs: list[dict[str, object]] = []
    connector_name = str(manifest.get("connector_name", ""))
    for trading_pair, orders in grouped_orders.items():
        safe_pair = _safe_name(trading_pair)
        total_amount_quote = sum(Decimal(str(order.get("notional_quote", "0"))) for order in orders)
        payload = {
            "id": f"quant_system_phase_5_6_{safe_pair}",
            "controller_name": CONTROLLER_MODULE_NAME,
            "controller_type": "generic",
            "connector_name": connector_name,
            "trading_pair": trading_pair,
            "total_amount_quote": str(total_amount_quote),
            "max_orders_per_tick": 1,
            "order_interval_seconds": 5,
            "event_log_path": event_log_path,
            "orders": [_controller_order(order) for order in orders],
        }
        configs.append(
            {
                "filename": f"crypto_relative_strength_v1_phase_5_6_{safe_pair}.yml",
                "payload": payload,
                "yaml": _yaml(payload),
            }
        )
    return configs


def _controller_order(order: dict[str, object]) -> dict[str, object]:
    return {
        "client_order_id": str(order["client_order_id"]),
        "side": str(order["side"]).lower(),
        "order_type": str(order["order_type"]).lower(),
        "amount": str(order["amount"]),
        "price": str(order["price"]),
        "notional_quote": str(order["notional_quote"]),
        "expected_fee_quote": str(order.get("expected_fee_quote", "0")),
        "reduce_only": bool(order.get("reduce_only", False)),
        "source_intent_id": str(order.get("source_intent_id", "")),
    }


def _summary(
    manifest: dict[str, Any],
    runtime_preflight: dict[str, Any],
    controller_configs: list[dict[str, object]],
    orders: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "strategy_id": str(manifest.get("strategy_id", "")),
        "connector_name": str(manifest.get("connector_name", "")),
        "live_trading_enabled": bool(manifest.get("live_trading_enabled")),
        "controller_config_count": len(controller_configs),
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
        alerts.append(critical_alert("Manifest live trading enabled", "CLI paper handoff requires live_trading_enabled=false."))
    if summary["connector_name"] != "binance_paper_trade":
        alerts.append(warning_alert("Unexpected connector", f"Expected binance_paper_trade, got {summary['connector_name']}."))
    if int(summary["controller_config_count"]) == 0:
        alerts.append(critical_alert("No controller configs", "No controller configs can be generated without manifest orders."))
    if int(summary["order_count"]) == 0:
        alerts.append(critical_alert("No orders", "Manifest contains no orders for Hummingbot paper mode."))

    preflight_decision = str(summary["runtime_preflight_decision"])
    if preflight_decision == "blocked":
        alerts.append(critical_alert("Runtime preflight blocked", "Phase 5.5 runtime preflight is blocked."))
    elif preflight_decision.endswith("_with_warnings") and not allow_warnings:
        alerts.append(critical_alert("Runtime preflight warnings", f"Runtime preflight is {preflight_decision}."))
    elif preflight_decision.endswith("_with_warnings"):
        alerts.append(warning_alert("Runtime preflight warnings", f"Runtime preflight is {preflight_decision}."))
    elif preflight_decision in {"unknown", ""}:
        alerts.append(critical_alert("Runtime preflight missing", "Phase 5.5 runtime preflight decision is missing."))

    paper_trade_connectors = runtime_preflight.get("paper_trade_connectors", [])
    if isinstance(paper_trade_connectors, list) and "binance_paper_trade" not in paper_trade_connectors:
        alerts.append(critical_alert("Paper connector missing", "binance_paper_trade is not enabled in Hummingbot conf_client.yml."))

    alerts.append(
        info_alert(
            "CLI paper mode only",
            "Generated files target Hummingbot CLI paper mode and do not enable live trading.",
        )
    )
    return alerts


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "cli_paper_handoff_ready_with_warnings"
    return "cli_paper_handoff_ready"


def _recommended_actions(decision: str) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not install or start the generated Hummingbot CLI files.",
            "Fix all CRITICAL alerts and regenerate Phase 5.6.",
            "Keep live trading disabled.",
        )
    return (
        "Install the generated controller source, controller configs, and script config into the Hummingbot CLI mounts.",
        "Delete the prior event JSONL before a fresh dry run.",
        "Start Hummingbot CLI with CONFIG_FILE_NAME=v2_with_controllers.py and the generated SCRIPT_CONFIG.",
        "After the run stops, pass the generated event JSONL to Phase 5.4 export acceptance.",
    )


def _controller_source() -> str:
    return '''"""Quant system one-shot sandbox order controller for Hummingbot CLI paper mode."""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PriceType, TradeType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class QuantSystemSandboxOrderControllerConfig(ControllerConfigBase):
    controller_name: str = "quant_system_sandbox_order_controller"
    controller_type: str = "generic"
    connector_name: str = "binance_paper_trade"
    trading_pair: str
    orders: List[Dict[str, Any]] = Field(default_factory=list)
    max_orders_per_tick: int = 1
    order_interval_seconds: int = 5
    event_log_path: str = "/home/hummingbot/data/crypto_relative_strength_v1_phase_5_6_hummingbot_events.jsonl"

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class QuantSystemSandboxOrderController(ControllerBase):
    def __init__(self, config: QuantSystemSandboxOrderControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self._next_order_index = 0
        self._last_submit_ts = 0
        self._submitted_ids = set()
        self._terminal_ids = set()

    async def update_processed_data(self):
        self._capture_terminal_events()
        active = [executor for executor in self.executors_info if executor.is_active]
        self.processed_data = {
            "active_executors": len(active),
            "submitted_orders": len(self._submitted_ids),
            "remaining_orders": max(0, len(self.config.orders) - self._next_order_index),
            "terminal_orders": len(self._terminal_ids),
        }

    def determine_executor_actions(self) -> List[ExecutorAction]:
        if self.config.manual_kill_switch:
            return []
        now = self.market_data_provider.time()
        if now - self._last_submit_ts < self.config.order_interval_seconds:
            return []
        actions = []
        while self._next_order_index < len(self.config.orders) and len(actions) < self.config.max_orders_per_tick:
            order = self.config.orders[self._next_order_index]
            self._next_order_index += 1
            client_order_id = str(order["client_order_id"])
            if client_order_id in self._submitted_ids:
                continue
            action = self._create_action(order)
            actions.append(action)
            self._submitted_ids.add(client_order_id)
            self._last_submit_ts = now
            self._append_event("submitted", order, executor_id=client_order_id)
        return actions

    def _create_action(self, order: Dict[str, Any]) -> CreateExecutorAction:
        side = TradeType.BUY if str(order["side"]).lower() == "buy" else TradeType.SELL
        amount = Decimal(str(order["amount"]))
        price = self._current_price(fallback=Decimal(str(order["price"])))
        config = OrderExecutorConfig(
            id=str(order["client_order_id"]),
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            side=side,
            amount=amount,
            execution_strategy=ExecutionStrategy.MARKET,
            price=price,
            level_id=str(order["client_order_id"]),
        )
        return CreateExecutorAction(controller_id=self.config.id, executor_config=config)

    def _current_price(self, fallback: Decimal) -> Decimal:
        try:
            price = self.market_data_provider.get_price_by_type(
                self.config.connector_name,
                self.config.trading_pair,
                PriceType.MidPrice,
            )
            return price if price and price > Decimal("0") else fallback
        except Exception:
            return fallback

    def _capture_terminal_events(self):
        orders_by_id = {str(order["client_order_id"]): order for order in self.config.orders}
        for executor in self.executors_info:
            if executor.id in self._terminal_ids or executor.id not in self._submitted_ids:
                continue
            if not executor.is_done:
                continue
            order = orders_by_id.get(executor.id)
            if order is None:
                continue
            custom_info = executor.custom_info or {}
            filled_amount = custom_info.get("executed_amount_base") or order.get("amount")
            average_price = custom_info.get("average_executed_price") or order.get("price")
            self._append_event(
                "filled",
                order,
                executor_id=executor.id,
                filled_amount=str(filled_amount),
                average_fill_price=str(average_price),
                fee_quote=str(executor.cum_fees_quote),
            )
            self._terminal_ids.add(executor.id)

    def _append_event(self, event_type: str, order: Dict[str, Any], **extra):
        if not self.config.event_log_path:
            return
        event = {
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "controller_id": self.config.id,
            "client_order_id": str(order["client_order_id"]),
            "connector_name": self.config.connector_name,
            "trading_pair": self.config.trading_pair,
            "side": str(order["side"]).lower(),
            "amount": str(order["amount"]),
            "price": str(order["price"]),
            "notional_quote": str(order.get("notional_quote", "0")),
        }
        event.update({key: str(value) for key, value in extra.items()})
        directory = os.path.dirname(self.config.event_log_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.config.event_log_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(event, sort_keys=True) + "\\n")

    def to_format_status(self) -> List[str]:
        return [
            f"Quant system paper controller: {self.config.trading_pair}",
            f"Submitted: {len(self._submitted_ids)} / {len(self.config.orders)}",
            f"Terminal: {len(self._terminal_ids)} / {len(self.config.orders)}",
            f"Event log: {self.config.event_log_path}",
        ]

    def get_custom_info(self) -> dict:
        return {
            "trading_pair": self.config.trading_pair,
            "submitted_orders": len(self._submitted_ids),
            "terminal_orders": len(self._terminal_ids),
            "total_orders": len(self.config.orders),
            "event_log_path": self.config.event_log_path,
        }
'''


def _runbook(
    *,
    session_id: str,
    script_config_name: str,
    event_log_path: str,
    host_event_log_path: str,
) -> str:
    return "\n".join(
        [
            "# Phase 5.6 Hummingbot CLI Paper Runbook",
            "",
            f"- Session id: `{session_id}`",
            f"- Script config: `{script_config_name}`",
            f"- Container event log: `{event_log_path}`",
            f"- Host event log: `{host_event_log_path}`",
            "",
            "## Start",
            "",
            "```bash",
            "cd /Users/albertlz/Downloads/private_proj/hummingbot",
            "docker compose run --rm \\",
            "  -e CONFIG_FILE_NAME=v2_with_controllers.py \\",
            f"  -e SCRIPT_CONFIG={script_config_name} \\",
            "  hummingbot",
            "```",
            "",
            "For a headless run, pass the password as an environment variable:",
            "",
            "```bash",
            "cd /Users/albertlz/Downloads/private_proj/hummingbot",
            "docker compose run --rm \\",
            "  -e CONFIG_PASSWORD='<your_hummingbot_password>' \\",
            "  -e HEADLESS_MODE=true \\",
            "  -e CONFIG_FILE_NAME=v2_with_controllers.py \\",
            f"  -e SCRIPT_CONFIG={script_config_name} \\",
            "  hummingbot",
            "```",
            "",
            "Enter the Hummingbot password when prompted. Do not configure live exchange connectors.",
            "",
            "## After Run",
            "",
            "Use the host event log as Phase 5.4 `--events-jsonl`. For a fresh run, delete the old event log first.",
            "",
        ]
    )


def _yaml(payload: dict[str, object]) -> str:
    lines = _yaml_lines(payload, indent=0)
    return "\n".join(lines) + "\n"


def _yaml_lines(value: object, *, indent: int) -> list[str]:
    prefix = " " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    return lines


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{escaped}\""


def _safe_name(value: str) -> str:
    return value.lower().replace("-", "_").replace("/", "_")


def _write_text(text: str, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path


def _write_json(payload: dict[str, object], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path
