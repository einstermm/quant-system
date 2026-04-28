"""Phase 6.5 candidate first live batch execution package."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from packages.backtesting.config import BacktestConfig, load_backtest_config
from packages.backtesting.result import decimal_to_str
from packages.data.simple_yaml import load_simple_yaml
from packages.data.sqlite_candle_repository import SQLiteCandleRepository
from packages.data.timeframes import interval_to_timedelta


@dataclass(frozen=True, slots=True)
class CandidateLiveOrder:
    client_order_id: str
    trading_pair: str
    side: str
    order_type: str
    estimated_price: Decimal
    estimated_quantity: Decimal
    notional_quote: Decimal
    signal_momentum: Decimal
    signal_timestamp: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "client_order_id": self.client_order_id,
            "trading_pair": self.trading_pair,
            "side": self.side,
            "order_type": self.order_type,
            "estimated_price": decimal_to_str(self.estimated_price),
            "estimated_quantity": decimal_to_str(self.estimated_quantity),
            "notional_quote": decimal_to_str(self.notional_quote),
            "signal_momentum": decimal_to_str(self.signal_momentum),
            "signal_timestamp": self.signal_timestamp.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class LiveBatchExecutionPackage:
    decision: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    batch_id: str
    connector: str
    allowed_pairs: tuple[str, ...]
    signal_summary: dict[str, object]
    candidate_orders: tuple[CandidateLiveOrder, ...]
    risk_summary: dict[str, object]
    checklist: tuple[dict[str, str], ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "batch_id": self.batch_id,
            "connector": self.connector,
            "allowed_pairs": list(self.allowed_pairs),
            "signal_summary": self.signal_summary,
            "candidate_orders": [order.to_dict() for order in self.candidate_orders],
            "risk_summary": self.risk_summary,
            "checklist": list(self.checklist),
            "artifacts": self.artifacts,
            "execution_runner_generated": False,
            "live_order_submission_armed": False,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.5 Candidate Live Batch Execution Package",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Batch id: `{self.batch_id}`",
            f"- Connector: `{self.connector}`",
            f"- Allowed pairs: `{', '.join(self.allowed_pairs)}`",
            f"- Candidate orders: `{len(self.candidate_orders)}`",
            f"- Execution runner generated: `False`",
            f"- Live order submission armed: `False`",
            "",
            "## Signal Summary",
            "",
        ]
        lines.extend(f"- {key}: `{value}`" for key, value in self.signal_summary.items())
        lines.extend(["", "## Candidate Orders", ""])
        if self.candidate_orders:
            lines.append(
                "| Client Order Id | Pair | Side | Notional | Est Qty | Est Price | Momentum |"
            )
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            for order in self.candidate_orders:
                lines.append(
                    f"| `{order.client_order_id}` | `{order.trading_pair}` | `{order.side}` | "
                    f"`{decimal_to_str(order.notional_quote)}` | "
                    f"`{decimal_to_str(order.estimated_quantity)}` | "
                    f"`{decimal_to_str(order.estimated_price)}` | "
                    f"`{decimal_to_str(order.signal_momentum)}` |"
                )
        else:
            lines.append("- No live candidate orders were generated.")
        lines.extend(["", "## Risk Summary", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.risk_summary.items())
        lines.extend(["", "## Checklist", ""])
        lines.extend(
            f"- `{item['status']}` {item['title']}: {item['details']}"
            + (f" Evidence: `{item['evidence']}`" if item.get("evidence") else "")
            for item in self.checklist
        )
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_batch_execution_package(
    *,
    activation_plan: dict[str, Any],
    market_data_refresh: list[dict[str, Any]],
    live_risk_config: dict[str, Any],
    strategy_dir: str | Path,
    db_path: str | Path,
    output_dir: str | Path,
    session_id: str,
    allowed_pairs: Iterable[str],
) -> LiveBatchExecutionPackage:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    config = load_backtest_config(strategy_dir)
    risk_summary = _risk_summary(live_risk_config, activation_plan)
    pair_tuple = tuple(allowed_pairs)
    signal_summary, orders = _candidate_orders(
        config=config,
        db_path=Path(db_path),
        activation_plan=activation_plan,
        allowed_pairs=pair_tuple,
        risk_summary=risk_summary,
    )
    checklist = _checklist(
        activation_plan=activation_plan,
        market_data_refresh=market_data_refresh,
        risk_summary=risk_summary,
        signal_summary=signal_summary,
        orders=orders,
        allowed_pairs=pair_tuple,
    )
    decision = _decision(checklist, orders)
    package = LiveBatchExecutionPackage(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=str(activation_plan.get("strategy_id", config.strategy_id)),
        batch_id=str(activation_plan.get("batch_id", "")),
        connector=str(activation_plan.get("connector", "")),
        allowed_pairs=pair_tuple,
        signal_summary=signal_summary,
        candidate_orders=tuple(orders),
        risk_summary=risk_summary,
        checklist=tuple(checklist),
        artifacts={},
    )
    orders_jsonl = _write_orders_jsonl(orders, output_path / "candidate_orders.jsonl")
    package_json = output_path / "package.json"
    package_md = output_path / "package.md"
    artifacts = {
        "candidate_orders_jsonl": str(orders_jsonl),
        "package_json": str(package_json),
        "package_md": str(package_md),
    }
    package = replace(package, artifacts=artifacts)
    package_json.write_text(
        json.dumps(package.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    package_md.write_text(package.to_markdown(), encoding="utf-8")
    return package


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_json_list(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected JSON list: {path}")
    return [item for item in payload if isinstance(item, dict)]


def load_risk_config(path: str | Path) -> dict[str, Any]:
    return load_simple_yaml(path)


def _candidate_orders(
    *,
    config: BacktestConfig,
    db_path: Path,
    activation_plan: dict[str, Any],
    allowed_pairs: tuple[str, ...],
    risk_summary: dict[str, object],
) -> tuple[dict[str, object], list[CandidateLiveOrder]]:
    lookback = config.signal.lookback_window
    if lookback is None:
        raise ValueError("relative strength live batch requires lookback_window")
    min_momentum = config.signal.min_momentum
    candles_by_pair = {}
    with SQLiteCandleRepository(db_path) as repository:
        for pair in allowed_pairs:
            candles = repository.list(
                exchange=config.exchange,
                trading_pair=pair,
                interval=config.interval,
            )
            candles_by_pair[pair] = candles[-(lookback + 1) :]

    ranked: list[tuple[str, Decimal, Decimal, datetime]] = []
    stale_pairs: list[str] = []
    latest_timestamp: datetime | None = None
    interval_delta = interval_to_timedelta(config.interval)
    for pair, candles in candles_by_pair.items():
        if len(candles) <= lookback:
            stale_pairs.append(pair)
            continue
        current = candles[-1]
        lookback_candle = candles[-1 - lookback]
        latest_timestamp = (
            current.timestamp
            if latest_timestamp is None
            else max(latest_timestamp, current.timestamp)
        )
        if current.timestamp - lookback_candle.timestamp < interval_delta * lookback:
            stale_pairs.append(pair)
            continue
        momentum = current.close / lookback_candle.close - Decimal("1")
        if momentum >= min_momentum:
            ranked.append((pair, momentum, current.close, current.timestamp))

    ranked.sort(key=lambda item: item[1], reverse=True)
    max_orders = int(_dict(activation_plan.get("batch_scope")).get("max_orders", 0))
    selected = ranked[:max_orders]
    max_order_notional = _decimal(risk_summary["max_order_notional"])
    max_batch_notional = _decimal(risk_summary["max_batch_notional"])
    per_order_notional = min(
        max_order_notional,
        max_batch_notional / Decimal(max(1, len(selected))),
    )

    orders = [
        CandidateLiveOrder(
            client_order_id=(
                f"{activation_plan.get('batch_id')}-"
                f"{pair.replace('-', '_').lower()}-{index}"
            ),
            trading_pair=pair,
            side="buy",
            order_type="market",
            estimated_price=price,
            estimated_quantity=per_order_notional / price,
            notional_quote=per_order_notional,
            signal_momentum=momentum,
            signal_timestamp=timestamp,
        )
        for index, (pair, momentum, price, timestamp) in enumerate(selected, start=1)
    ]
    signal_summary = {
        "signal_type": config.signal.signal_type,
        "lookback_window": lookback,
        "min_momentum": decimal_to_str(min_momentum),
        "top_n": config.signal.top_n,
        "allowed_pairs": list(allowed_pairs),
        "ranked_pairs": [
            {
                "trading_pair": pair,
                "momentum": decimal_to_str(momentum),
                "estimated_price": decimal_to_str(price),
                "signal_timestamp": timestamp.isoformat(),
            }
            for pair, momentum, price, timestamp in ranked
        ],
        "selected_pairs": [order.trading_pair for order in orders],
        "latest_signal_timestamp": latest_timestamp.isoformat() if latest_timestamp else None,
        "stale_or_insufficient_pairs": stale_pairs,
    }
    return signal_summary, orders


def _risk_summary(
    live_risk_config: dict[str, Any],
    activation_plan: dict[str, Any],
) -> dict[str, object]:
    batch_scope = _dict(activation_plan.get("batch_scope"))
    return {
        "max_batch_orders": int(batch_scope.get("max_orders", 0)),
        "max_batch_notional": str(batch_scope.get("max_total_notional", "0")),
        "max_order_notional": str(live_risk_config.get("max_order_notional", "0")),
        "max_symbol_notional": str(live_risk_config.get("max_symbol_notional", "0")),
        "max_gross_notional": str(live_risk_config.get("max_gross_notional", "0")),
        "max_daily_loss": str(live_risk_config.get("max_daily_loss", "0")),
        "max_drawdown_pct": str(live_risk_config.get("max_drawdown_pct", "0")),
    }


def _checklist(
    *,
    activation_plan: dict[str, Any],
    market_data_refresh: list[dict[str, Any]],
    risk_summary: dict[str, object],
    signal_summary: dict[str, object],
    orders: list[CandidateLiveOrder],
    allowed_pairs: tuple[str, ...],
) -> list[dict[str, str]]:
    total_notional = sum((order.notional_quote for order in orders), Decimal("0"))
    return [
        _item(
            "phase_6_4_approved",
            "Phase 6.4 activation plan approved",
            "PASS"
            if activation_plan.get("decision") == "live_batch_activation_plan_approved"
            else "FAIL",
            f"Phase 6.4 decision is {activation_plan.get('decision', 'unknown')}.",
        ),
        _item(
            "market_data_refresh",
            "BTC/ETH market data refresh succeeded",
            "PASS"
            if market_data_refresh
            and all(item.get("status") == "ok" for item in market_data_refresh)
            else "FAIL",
            f"refresh_statuses={[item.get('status') for item in market_data_refresh]}.",
        ),
        _item(
            "allowlist",
            "Candidate orders are inside allowlist",
            "PASS" if all(order.trading_pair in allowed_pairs for order in orders) else "FAIL",
            f"allowed_pairs={allowed_pairs}; orders={[order.trading_pair for order in orders]}.",
        ),
        _item(
            "order_count",
            "Candidate order count is inside batch cap",
            "PASS" if len(orders) <= int(risk_summary["max_batch_orders"]) else "FAIL",
            f"orders={len(orders)}; cap={risk_summary['max_batch_orders']}.",
        ),
        _item(
            "order_notional",
            "Candidate order notionals are inside single-order cap",
            "PASS"
            if all(
                order.notional_quote <= _decimal(risk_summary["max_order_notional"])
                for order in orders
            )
            else "FAIL",
            f"single_order_cap={risk_summary['max_order_notional']}.",
        ),
        _item(
            "batch_notional",
            "Candidate batch notional is inside batch cap",
            "PASS" if total_notional <= _decimal(risk_summary["max_batch_notional"]) else "FAIL",
            (
                f"total_notional={decimal_to_str(total_notional)}; "
                f"cap={risk_summary['max_batch_notional']}."
            ),
        ),
        _item(
            "signal_available",
            "BTC/ETH-only signal produced candidate orders",
            "PASS" if orders else "WARN",
            f"selected_pairs={signal_summary.get('selected_pairs')}.",
        ),
        _item(
            "exchange_state_check",
            "Exchange balances and open orders reviewed",
            "MANUAL_REQUIRED",
            "Verify Binance spot balances and no unexpected open orders before runner generation.",
        ),
    ]


def _decision(checklist: list[dict[str, str]], orders: list[CandidateLiveOrder]) -> str:
    if any(item["status"] == "FAIL" for item in checklist):
        return "live_batch_execution_package_blocked"
    if not orders:
        return "live_batch_execution_package_no_orders"
    return "live_batch_execution_package_ready_pending_exchange_state_check"


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


def _write_orders_jsonl(orders: list[CandidateLiveOrder], path: Path) -> Path:
    payload = "\n".join(json.dumps(order.to_dict(), sort_keys=True) for order in orders)
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
    return path


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))
