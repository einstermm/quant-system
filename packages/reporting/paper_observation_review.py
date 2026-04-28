"""Review a 24h paper observation run and produce a sandbox decision."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class PaperObservationReviewThresholds:
    min_duration_hours: Decimal = Decimal("23.5")
    min_ok_cycle_ratio: Decimal = Decimal("0.99")
    max_failed_cycles: int = 0
    max_market_data_incomplete_cycles: int = 0
    max_refresh_failed_events: int = 0
    max_rejected_orders: int = 0
    max_drawdown: Decimal = Decimal("0.02")

    def to_dict(self) -> dict[str, object]:
        return {
            "min_duration_hours": decimal_to_str(self.min_duration_hours),
            "min_ok_cycle_ratio": decimal_to_str(self.min_ok_cycle_ratio),
            "max_failed_cycles": self.max_failed_cycles,
            "max_market_data_incomplete_cycles": self.max_market_data_incomplete_cycles,
            "max_refresh_failed_events": self.max_refresh_failed_events,
            "max_rejected_orders": self.max_rejected_orders,
            "max_drawdown": decimal_to_str(self.max_drawdown),
        }


@dataclass(frozen=True, slots=True)
class PaperObservationReview:
    strategy_id: str
    account_id: str
    generated_at: datetime
    decision: str
    observation: dict[str, object]
    trading: dict[str, object]
    market_data: dict[str, object]
    readiness: dict[str, object]
    thresholds: PaperObservationReviewThresholds
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "generated_at": self.generated_at.isoformat(),
            "decision": self.decision,
            "observation": self.observation,
            "trading": self.trading,
            "market_data": self.market_data,
            "readiness": self.readiness,
            "thresholds": self.thresholds.to_dict(),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Paper Observation Review: {self.strategy_id}",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Account: `{self.account_id}`",
            "",
            "## Observation",
            "",
            f"- Started at: `{self.observation['started_at']}`",
            f"- Completed at: `{self.observation['completed_at']}`",
            f"- Duration hours: `{self.observation['duration_hours']}`",
            f"- Cycles: `{self.observation['cycles']}`",
            f"- OK cycles: `{self.observation['ok_cycles']}`",
            f"- Failed cycles: `{self.observation['failed_cycles']}`",
            f"- OK cycle ratio: `{_pct(Decimal(str(self.observation['ok_cycle_ratio'])))}`",
            "",
            "## Equity",
            "",
            f"- Initial equity: `{self.trading['initial_equity']}`",
            f"- Final equity: `{self.trading['final_equity']}`",
            f"- Net PnL: `{self.trading['net_pnl']}`",
            f"- Net return: `{_pct(Decimal(str(self.trading['net_return'])))}`",
            f"- Minimum equity: `{self.trading['min_equity']}`",
            f"- Maximum drawdown: `{_pct(Decimal(str(self.trading['max_drawdown'])))}`",
            f"- Total fees: `{self.trading['total_fees']}`",
            "",
            "## Orders",
            "",
            f"- Routed orders: `{self.trading['routed_orders']}`",
            f"- Approved orders: `{self.trading['approved_orders']}`",
            f"- Rejected orders: `{self.trading['rejected_orders']}`",
            f"- Filled paper orders: `{self.trading['filled_orders']}`",
            f"- Buy notional: `{self.trading['buy_notional']}`",
            f"- Sell notional: `{self.trading['sell_notional']}`",
            "",
            "## Market Data",
            "",
            f"- Market data incomplete cycles: `{self.market_data['incomplete_cycles']}`",
            f"- Refresh failed events: `{self.market_data['refresh_failed_events']}`",
            f"- Refresh status counts: `{self.market_data['refresh_status_counts']}`",
            f"- Last runtime end: `{self.market_data['last_runtime_end']}`",
            f"- Last candle by symbol: `{self.market_data['last_candle_by_symbol']}`",
            "",
            "## Readiness",
            "",
            f"- Prior readiness status: `{self.readiness['status']}`",
            f"- Prior readiness alerts: `{self.readiness['alert_counts']}`",
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


def build_paper_observation_review(
    *,
    observation_records: tuple[dict[str, Any], ...],
    ledger_records: tuple[dict[str, Any], ...],
    readiness_payload: dict[str, Any] | None,
    initial_equity: Decimal,
    thresholds: PaperObservationReviewThresholds | None = None,
) -> PaperObservationReview:
    if not observation_records:
        raise ValueError("observation records cannot be empty")
    limits = thresholds or PaperObservationReviewThresholds()
    observation = _observation_metrics(observation_records)
    trading = _trading_metrics(
        observation_records=observation_records,
        ledger_records=ledger_records,
        initial_equity=initial_equity,
    )
    market_data = _market_data_metrics(observation_records)
    readiness = _readiness_metrics(readiness_payload)
    alerts = _build_alerts(
        observation=observation,
        trading=trading,
        market_data=market_data,
        readiness=readiness,
        thresholds=limits,
    )
    decision = _decision(alerts)
    first_ok = _first_ok_record(observation_records)
    return PaperObservationReview(
        strategy_id=str(first_ok.get("strategy_id", "")),
        account_id=str(first_ok.get("account", {}).get("account_id", "")),
        generated_at=datetime.now(tz=UTC),
        decision=decision,
        observation=observation,
        trading=trading,
        market_data=market_data,
        readiness=readiness,
        thresholds=limits,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision, alerts),
    )


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


def write_review_json(review: PaperObservationReview, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(review.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_review_markdown(review: PaperObservationReview, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(review.to_markdown(), encoding="utf-8")
    return output_path


def _observation_metrics(records: tuple[dict[str, Any], ...]) -> dict[str, object]:
    started_at = datetime.fromisoformat(str(records[0]["started_at"]))
    completed_at = datetime.fromisoformat(str(records[-1]["completed_at"]))
    cycles = len(records)
    ok_cycles = sum(1 for record in records if record.get("status") == "ok")
    failed_cycles = cycles - ok_cycles
    duration_hours = Decimal(str((completed_at - started_at).total_seconds())) / Decimal("3600")
    return {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_hours": decimal_to_str(duration_hours),
        "cycles": cycles,
        "ok_cycles": ok_cycles,
        "failed_cycles": failed_cycles,
        "ok_cycle_ratio": decimal_to_str(Decimal(ok_cycles) / Decimal(cycles)),
    }


def _trading_metrics(
    *,
    observation_records: tuple[dict[str, Any], ...],
    ledger_records: tuple[dict[str, Any], ...],
    initial_equity: Decimal,
) -> dict[str, object]:
    ok_records = [record for record in observation_records if record.get("status") == "ok"]
    first_ok = ok_records[0]
    last_ok = ok_records[-1]
    equities = [_record_equity(record) for record in ok_records]
    final_equity = _record_equity(last_ok)
    min_equity = min(equities)
    max_equity = max(equities)
    max_drawdown = _max_drawdown(equities)
    total_fees = sum((Decimal(str(record["fee"])) for record in ledger_records), Decimal("0"))
    buy_notional = sum(
        (Decimal(str(record["notional"])) for record in ledger_records if record["side"] == "buy"),
        Decimal("0"),
    )
    sell_notional = sum(
        (Decimal(str(record["notional"])) for record in ledger_records if record["side"] == "sell"),
        Decimal("0"),
    )
    symbol_stats = _symbol_order_stats(ledger_records)
    return {
        "initial_equity": decimal_to_str(initial_equity),
        "first_observed_equity": decimal_to_str(_record_equity(first_ok)),
        "final_equity": decimal_to_str(final_equity),
        "net_pnl": decimal_to_str(final_equity - initial_equity),
        "net_return": decimal_to_str((final_equity / initial_equity) - Decimal("1")),
        "min_equity": decimal_to_str(min_equity),
        "max_equity": decimal_to_str(max_equity),
        "max_drawdown": decimal_to_str(max_drawdown),
        "routed_orders": sum(int(record.get("routed_order_count", 0)) for record in observation_records),
        "approved_orders": sum(int(record.get("approved_order_count", 0)) for record in observation_records),
        "rejected_orders": sum(int(record.get("rejected_order_count", 0)) for record in observation_records),
        "filled_orders": len(ledger_records),
        "buy_notional": decimal_to_str(buy_notional),
        "sell_notional": decimal_to_str(sell_notional),
        "traded_notional": decimal_to_str(buy_notional + sell_notional),
        "total_fees": decimal_to_str(total_fees),
        "orders_by_symbol": symbol_stats,
        "final_positions": last_ok.get("account", {}).get("positions", []),
        "final_target_weights": last_ok.get("target_weights", {}),
    }


def _market_data_metrics(records: tuple[dict[str, Any], ...]) -> dict[str, object]:
    refresh_status_counts: Counter[str] = Counter()
    fetched_by_symbol: defaultdict[str, int] = defaultdict(int)
    last_candle_by_symbol: dict[str, str] = {}
    last_runtime_end: str | None = None
    refresh_failed_events = 0
    for record in records:
        pre_cycle = record.get("pre_cycle")
        if not isinstance(pre_cycle, dict):
            continue
        if bool(pre_cycle.get("refresh_failed")):
            refresh_failed_events += 1
        runtime_end = pre_cycle.get("runtime_end")
        if runtime_end:
            last_runtime_end = str(runtime_end)
        refresh_results = pre_cycle.get("market_data_refresh", [])
        if not isinstance(refresh_results, list):
            continue
        for result in refresh_results:
            if not isinstance(result, dict):
                continue
            status = str(result.get("status", "unknown"))
            symbol = str(result.get("trading_pair", "unknown"))
            refresh_status_counts[status] += 1
            fetched_by_symbol[symbol] += int(result.get("fetched_candles", 0))
            latest_after = result.get("latest_after")
            if latest_after:
                last_candle_by_symbol[symbol] = str(latest_after)

    return {
        "incomplete_cycles": sum(
            1 for record in records if not bool(record.get("market_data_complete", False))
        ),
        "refresh_failed_events": refresh_failed_events,
        "refresh_status_counts": dict(refresh_status_counts),
        "fetched_candles_by_symbol": dict(fetched_by_symbol),
        "last_candle_by_symbol": last_candle_by_symbol,
        "last_runtime_end": last_runtime_end,
    }


def _readiness_metrics(payload: dict[str, Any] | None) -> dict[str, object]:
    if payload is None:
        return {"status": "not_provided", "alert_counts": {}, "alerts": []}
    alert_counts = Counter(str(alert["severity"]) for alert in payload.get("alerts", []))
    return {
        "status": str(payload.get("status", "unknown")),
        "alert_counts": dict(alert_counts),
        "alerts": payload.get("alerts", []),
    }


def _build_alerts(
    *,
    observation: dict[str, object],
    trading: dict[str, object],
    market_data: dict[str, object],
    readiness: dict[str, object],
    thresholds: PaperObservationReviewThresholds,
) -> list[Alert]:
    alerts: list[Alert] = []
    if Decimal(str(observation["duration_hours"])) < thresholds.min_duration_hours:
        alerts.append(
            critical_alert(
                "Observation duration too short",
                f"Duration {observation['duration_hours']}h is below {thresholds.min_duration_hours}h.",
            )
        )
    if int(observation["failed_cycles"]) > thresholds.max_failed_cycles:
        alerts.append(
            critical_alert(
                "Failed paper cycles",
                f"Failed cycles {observation['failed_cycles']} exceeds allowed {thresholds.max_failed_cycles}.",
            )
        )
    if Decimal(str(observation["ok_cycle_ratio"])) < thresholds.min_ok_cycle_ratio:
        alerts.append(
            critical_alert(
                "OK cycle ratio below threshold",
                f"OK cycle ratio {observation['ok_cycle_ratio']} is below {thresholds.min_ok_cycle_ratio}.",
            )
        )
    if int(market_data["incomplete_cycles"]) > thresholds.max_market_data_incomplete_cycles:
        alerts.append(
            critical_alert(
                "Market data incomplete",
                f"Incomplete data cycles {market_data['incomplete_cycles']} exceeds allowed {thresholds.max_market_data_incomplete_cycles}.",
            )
        )
    if int(market_data["refresh_failed_events"]) > thresholds.max_refresh_failed_events:
        alerts.append(
            critical_alert(
                "Market data refresh failures",
                f"Refresh failures {market_data['refresh_failed_events']} exceeds allowed {thresholds.max_refresh_failed_events}.",
            )
        )
    if int(trading["rejected_orders"]) > thresholds.max_rejected_orders:
        alerts.append(
            critical_alert(
                "Rejected orders observed",
                f"Rejected orders {trading['rejected_orders']} exceeds allowed {thresholds.max_rejected_orders}.",
            )
        )
    if Decimal(str(trading["max_drawdown"])) > thresholds.max_drawdown:
        alerts.append(
            warning_alert(
                "Paper drawdown above watch level",
                f"Max drawdown {trading['max_drawdown']} exceeds watch level {thresholds.max_drawdown}.",
            )
        )
    if Decimal(str(trading["net_return"])) < Decimal("0"):
        alerts.append(
            warning_alert(
                "Negative paper PnL",
                "The 24h paper observation ended with negative PnL.",
            )
        )
    if readiness["status"] != "paper_ready":
        severity = "CRITICAL" if readiness["status"] == "blocked" else "WARN"
        alert_fn = critical_alert if severity == "CRITICAL" else warning_alert
        alerts.append(
            alert_fn(
                "Prior readiness not clean",
                f"Prior readiness status is {readiness['status']}.",
            )
        )
    alerts.append(
        info_alert(
            "Live trading remains disabled",
            "This review can only approve Hummingbot Sandbox preparation, not live trading.",
        )
    )
    return alerts


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "sandbox_ready_with_warnings"
    return "sandbox_ready"


def _recommended_actions(decision: str, alerts: list[Alert]) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not enter Hummingbot Sandbox.",
            "Fix all CRITICAL alerts and rerun the 24h paper observation.",
            "Keep live trading disabled.",
        )
    actions = [
        "Prepare Phase 5 Hummingbot Sandbox integration only; keep live trading disabled.",
        "Carry forward all WARN items into the Phase 5 runbook.",
        "Keep the same readiness gate and kill switch behavior in sandbox.",
        "Do not increase capital or enable live keys based on this 24h paper result.",
    ]
    if any(alert.title == "Prior readiness not clean" for alert in alerts):
        actions.append("Review Phase 3.9 readiness WARN items before every sandbox session.")
    return tuple(actions)


def _first_ok_record(records: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    for record in records:
        if record.get("status") == "ok":
            return record
    raise ValueError("at least one ok observation record is required")


def _record_equity(record: dict[str, Any]) -> Decimal:
    return Decimal(str(record["account"]["equity"]))


def _max_drawdown(equities: list[Decimal]) -> Decimal:
    peak = equities[0]
    max_drawdown = Decimal("0")
    for equity in equities:
        if equity > peak:
            peak = equity
        if peak > Decimal("0"):
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown


def _symbol_order_stats(records: tuple[dict[str, Any], ...]) -> dict[str, dict[str, object]]:
    stats: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "orders": 0,
            "buy_notional": Decimal("0"),
            "sell_notional": Decimal("0"),
            "fees": Decimal("0"),
        }
    )
    for record in records:
        symbol = str(record["symbol"])
        stats[symbol]["orders"] = int(stats[symbol]["orders"]) + 1
        if record["side"] == "buy":
            stats[symbol]["buy_notional"] = Decimal(str(stats[symbol]["buy_notional"])) + Decimal(
                str(record["notional"])
            )
        else:
            stats[symbol]["sell_notional"] = Decimal(str(stats[symbol]["sell_notional"])) + Decimal(
                str(record["notional"])
            )
        stats[symbol]["fees"] = Decimal(str(stats[symbol]["fees"])) + Decimal(str(record["fee"]))
    return {
        symbol: {
            "orders": values["orders"],
            "buy_notional": decimal_to_str(Decimal(str(values["buy_notional"]))),
            "sell_notional": decimal_to_str(Decimal(str(values["sell_notional"]))),
            "fees": decimal_to_str(Decimal(str(values["fees"]))),
        }
        for symbol, values in sorted(stats.items())
    }


def _pct(value: Decimal) -> str:
    return f"{decimal_to_str(value * Decimal('100'))}%"
