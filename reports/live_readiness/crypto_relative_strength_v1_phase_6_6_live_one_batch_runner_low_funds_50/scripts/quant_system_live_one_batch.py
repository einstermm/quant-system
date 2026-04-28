"""Quant system one-batch live runner for Hummingbot CLI."""

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
            file.write(json.dumps(event, sort_keys=True) + "\n")

    def format_status(self) -> str:
        return (
            f"Quant system live one-batch runner\n"
            f"Submitted: {len(self._submitted_client_ids)} / {len(self.config.orders)}\n"
            f"Filled: {len(self._filled_client_ids)} / {len(self.config.orders)}\n"
            f"Terminal: {len(self._terminal_client_ids)} / {len(self.config.orders)}\n"
            f"Submitted notional: {self._submitted_notional}\n"
            f"Event log: {self.config.event_log_path}"
        )
