"""Post-trade reconciliation for the first low-funds live batch."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert

HUMMINGBOT_DB_SCALE = Decimal("1000000")
TRADE_EXPORT_COLUMNS = (
    "trade_date",
    "timestamp",
    "account_id",
    "strategy_id",
    "source",
    "connector",
    "trading_pair",
    "side",
    "order_type",
    "client_order_id",
    "hb_order_id",
    "exchange_order_id",
    "exchange_trade_id",
    "base_asset",
    "quote_asset",
    "gross_base_quantity",
    "fee_asset",
    "fee_amount",
    "net_base_quantity",
    "price_quote",
    "gross_quote_notional",
    "fee_quote_estimate",
    "cash_flow_quote",
    "cost_basis_quote_estimate",
    "cad_fx_rate",
    "cost_basis_cad_estimate",
    "fees_cad_estimate",
    "fx_source",
    "notes",
)


@dataclass(frozen=True, slots=True)
class LiveTradeFill:
    timestamp: datetime
    account_id: str
    strategy_id: str
    source: str
    connector: str
    trading_pair: str
    side: str
    order_type: str
    client_order_id: str
    hb_order_id: str
    exchange_order_id: str
    exchange_trade_id: str
    base_asset: str
    quote_asset: str
    gross_base_quantity: Decimal
    fee_asset: str
    fee_amount: Decimal
    net_base_quantity: Decimal
    price_quote: Decimal
    gross_quote_notional: Decimal
    fee_quote_estimate: Decimal
    cash_flow_quote: Decimal
    cost_basis_quote_estimate: Decimal
    cad_fx_rate: Decimal
    fx_source: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.timestamp.date().isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "source": self.source,
            "connector": self.connector,
            "trading_pair": self.trading_pair,
            "side": self.side,
            "order_type": self.order_type,
            "client_order_id": self.client_order_id,
            "hb_order_id": self.hb_order_id,
            "exchange_order_id": self.exchange_order_id,
            "exchange_trade_id": self.exchange_trade_id,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "gross_base_quantity": decimal_to_str(self.gross_base_quantity),
            "fee_asset": self.fee_asset,
            "fee_amount": decimal_to_str(self.fee_amount),
            "net_base_quantity": decimal_to_str(self.net_base_quantity),
            "price_quote": decimal_to_str(self.price_quote),
            "gross_quote_notional": decimal_to_str(self.gross_quote_notional),
            "fee_quote_estimate": decimal_to_str(self.fee_quote_estimate),
            "cash_flow_quote": decimal_to_str(self.cash_flow_quote),
            "cost_basis_quote_estimate": decimal_to_str(self.cost_basis_quote_estimate),
            "cad_fx_rate": decimal_to_str(self.cad_fx_rate),
            "cost_basis_cad_estimate": decimal_to_str(
                self.cost_basis_quote_estimate * self.cad_fx_rate
            ),
            "fees_cad_estimate": decimal_to_str(self.fee_quote_estimate * self.cad_fx_rate),
            "fx_source": self.fx_source,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class LivePostTradeReport:
    status: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    account_id: str
    event_counts: dict[str, int]
    order_checks: dict[str, object]
    fill_summary: dict[str, object]
    balance_checks: dict[str, object]
    risk_checks: dict[str, object]
    operational_checks: dict[str, object]
    tax_summary: dict[str, object]
    alerts: tuple[Alert, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "event_counts": self.event_counts,
            "order_checks": self.order_checks,
            "fill_summary": self.fill_summary,
            "balance_checks": self.balance_checks,
            "risk_checks": self.risk_checks,
            "operational_checks": self.operational_checks,
            "tax_summary": self.tax_summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.7 Live Post-Trade Reconciliation",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Status: `{self.status}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Account: `{self.account_id}`",
            "",
            "## Orders",
            "",
            f"- Expected orders: `{self.order_checks['expected_orders']}`",
            f"- Submitted orders: `{self.order_checks['submitted_orders']}`",
            f"- Filled orders: `{self.order_checks['filled_orders']}`",
            f"- DB fills: `{self.order_checks['db_fills']}`",
            f"- Session completed: `{self.order_checks['session_completed']}`",
            f"- Missing submissions: `{self.order_checks['missing_submissions']}`",
            f"- Missing fills: `{self.order_checks['missing_fills']}`",
            "",
            "## Fill",
            "",
            f"- Gross quote notional: `{self.fill_summary['gross_quote_notional']}`",
            f"- Gross base quantity: `{self.fill_summary['gross_base_quantity']}`",
            f"- Net base quantity: `{self.fill_summary['net_base_quantity']}`",
            f"- Average price: `{self.fill_summary['average_price_quote']}`",
            f"- Fee: `{self.fill_summary['fee_amount']} {self.fill_summary['fee_asset']}`",
            f"- Fee quote estimate: `{self.fill_summary['fee_quote_estimate']}`",
            "",
            "## Balances",
            "",
            f"- Status: `{self.balance_checks['status']}`",
            f"- Quote delta: `{self.balance_checks['quote_delta']}`",
            f"- Base delta: `{self.balance_checks['base_delta']}`",
            f"- Mismatches: `{self.balance_checks['mismatches']}`",
            "",
            "## Risk",
            "",
            f"- Total notional inside cap: `{self.risk_checks['total_notional_inside_cap']}`",
            f"- Order count inside cap: `{self.risk_checks['order_count_inside_cap']}`",
            f"- Price deviation bps: `{self.risk_checks['price_deviation_bps']}`",
            f"- Price deviation inside cap: `{self.risk_checks['price_deviation_inside_cap']}`",
            "",
            "## Operational",
            "",
            f"- MQTT bridge failures: `{self.operational_checks['mqtt_bridge_failures']}`",
            f"- Hummingbot stop observed: `{self.operational_checks['hummingbot_stop_observed']}`",
            f"- Runner container status: `{self.operational_checks['runner_container_status']}`",
            "",
            "## Tax Export",
            "",
            f"- Rows: `{self.tax_summary['row_count']}`",
            f"- Gross quote notional: `{self.tax_summary['gross_quote_notional']}`",
            f"- Fee quote estimate: `{self.tax_summary['fee_quote_estimate']}`",
            f"- Cost basis quote estimate: `{self.tax_summary['cost_basis_quote_estimate']}`",
            f"- FX source: `{self.tax_summary['fx_source']}`",
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
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_post_trade_report(
    *,
    event_jsonl: str | Path,
    sqlite_db: str | Path,
    log_file: str | Path,
    candidate_package: dict[str, Any],
    runner_package: dict[str, Any],
    session_id: str,
    account_id: str,
    strategy_id: str,
    cad_fx_rate: Decimal,
    fx_source: str,
    runner_container_status: str = "",
    artifacts: dict[str, str] | None = None,
) -> tuple[LivePostTradeReport, tuple[LiveTradeFill, ...]]:
    runtime_events = _load_runtime_events(event_jsonl)
    event_counts = dict(
        Counter(str(event.get("event_type", "unknown")) for event in runtime_events)
    )
    expected_orders = _candidate_orders(candidate_package)
    hb_to_client = _hb_to_client_order_id(runtime_events)
    fills = _load_trade_fills(
        sqlite_db=sqlite_db,
        hb_to_client=hb_to_client,
        account_id=account_id,
        strategy_id=strategy_id,
        cad_fx_rate=cad_fx_rate,
        fx_source=fx_source,
    )
    order_checks = _order_checks(expected_orders, runtime_events, fills)
    fill_summary = _fill_summary(fills)
    balance_checks = _balance_checks(runtime_events, fills)
    risk_checks = _risk_checks(
        expected_orders=expected_orders,
        runner_package=runner_package,
        fills=fills,
    )
    operational_checks = _operational_checks(
        log_file=log_file,
        runner_container_status=runner_container_status,
    )
    tax_summary = _tax_summary(fills, cad_fx_rate=cad_fx_rate, fx_source=fx_source)
    alerts = _alerts(
        order_checks=order_checks,
        balance_checks=balance_checks,
        risk_checks=risk_checks,
        operational_checks=operational_checks,
        tax_summary=tax_summary,
    )
    report = LivePostTradeReport(
        status=_status(alerts),
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=strategy_id,
        account_id=account_id,
        event_counts=event_counts,
        order_checks=order_checks,
        fill_summary=fill_summary,
        balance_checks=balance_checks,
        risk_checks=risk_checks,
        operational_checks=operational_checks,
        tax_summary=tax_summary,
        alerts=tuple(alerts),
        artifacts=artifacts or {},
    )
    return report, fills


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_report_json(report: LivePostTradeReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_report_markdown(report: LivePostTradeReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def write_trades_jsonl(fills: tuple[LiveTradeFill, ...], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for fill in fills:
            file.write(json.dumps(fill.to_dict(), sort_keys=True))
            file.write("\n")
    return output_path


def write_trade_tax_csv(fills: tuple[LiveTradeFill, ...], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_EXPORT_COLUMNS)
        writer.writeheader()
        for fill in fills:
            writer.writerow(fill.to_dict())
    return output_path


def write_daily_report_json(report: LivePostTradeReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_daily_report_dict(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_daily_report_markdown(report: LivePostTradeReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    daily = _daily_report_dict(report)
    trading = daily["trading_summary"]
    balances = daily["balance_summary"]
    lines = [
        "# Phase 6.7 Live Daily Report",
        "",
        f"- Generated at: `{daily['generated_at']}`",
        f"- Status: `{daily['status']}`",
        f"- Session id: `{daily['session_id']}`",
        f"- Strategy: `{daily['strategy_id']}`",
        f"- Account: `{daily['account_id']}`",
        "",
        "## Trading",
        "",
        f"- Submitted orders: `{trading['submitted_orders']}`",
        f"- Filled orders: `{trading['filled_orders']}`",
        f"- Gross quote notional: `{trading['gross_quote_notional']}`",
        f"- Average price quote: `{trading['average_price_quote']}`",
        f"- Gross base quantity: `{trading['gross_base_quantity']}`",
        f"- Net base quantity: `{trading['net_base_quantity']}`",
        f"- Fee quote estimate: `{trading['fee_quote_estimate']}`",
        "",
        "## Balances",
        "",
        f"- Starting balances: `{balances['starting_balances']}`",
        f"- Ending balances: `{balances['ending_balances']}`",
        f"- Quote delta: `{balances['quote_delta']}`",
        f"- Base delta: `{balances['base_delta']}`",
        "",
        "## Alerts",
        "",
    ]
    if daily["alerts"]:
        lines.extend(
            f"- `{alert['severity']}` {alert['title']}: {alert['message']}"
            for alert in daily["alerts"]
        )
    else:
        lines.append("- None")
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def write_tax_summary_json(report: LivePostTradeReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.tax_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_tax_summary_markdown(report: LivePostTradeReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 6.7 Live Trade Tax Export Summary",
        "",
        f"- Rows: `{report.tax_summary['row_count']}`",
        f"- Gross quote notional: `{report.tax_summary['gross_quote_notional']}`",
        f"- Fee quote estimate: `{report.tax_summary['fee_quote_estimate']}`",
        f"- Cost basis quote estimate: `{report.tax_summary['cost_basis_quote_estimate']}`",
        f"- CAD FX rate: `{report.tax_summary['cad_fx_rate']}`",
        f"- FX source: `{report.tax_summary['fx_source']}`",
        "",
        "## Notes",
        "",
        f"- {report.tax_summary['notes']}",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _daily_report_dict(report: LivePostTradeReport) -> dict[str, object]:
    return {
        "status": report.status,
        "generated_at": report.generated_at.isoformat(),
        "session_id": report.session_id,
        "strategy_id": report.strategy_id,
        "account_id": report.account_id,
        "event_counts": report.event_counts,
        "trading_summary": {
            "submitted_orders": report.order_checks["submitted_orders"],
            "filled_orders": report.order_checks["filled_orders"],
            "gross_quote_notional": report.fill_summary["gross_quote_notional"],
            "average_price_quote": report.fill_summary["average_price_quote"],
            "gross_base_quantity": report.fill_summary["gross_base_quantity"],
            "net_base_quantity": report.fill_summary["net_base_quantity"],
            "fee_quote_estimate": report.fill_summary["fee_quote_estimate"],
        },
        "balance_summary": {
            "starting_balances": report.balance_checks["starting_balances"],
            "ending_balances": report.balance_checks["ending_balances"],
            "quote_delta": report.balance_checks["quote_delta"],
            "base_delta": report.balance_checks["base_delta"],
            "mismatches": report.balance_checks["mismatches"],
        },
        "alerts": [alert.to_dict() for alert in report.alerts],
    }


def _load_runtime_events(path: str | Path) -> tuple[dict[str, Any], ...]:
    records = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return tuple(records)


def _candidate_orders(candidate_package: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_orders = candidate_package.get("candidate_orders", [])
    if not isinstance(raw_orders, list):
        return ()
    return tuple(order for order in raw_orders if isinstance(order, dict))


def _hb_to_client_order_id(events: tuple[dict[str, Any], ...]) -> dict[str, str]:
    mapping = {}
    for event in events:
        hb_order_id = event.get("hb_order_id")
        client_order_id = event.get("client_order_id")
        if hb_order_id and client_order_id:
            mapping[str(hb_order_id)] = str(client_order_id)
    return mapping


def _load_trade_fills(
    *,
    sqlite_db: str | Path,
    hb_to_client: dict[str, str],
    account_id: str,
    strategy_id: str,
    cad_fx_rate: Decimal,
    fx_source: str,
) -> tuple[LiveTradeFill, ...]:
    connection = sqlite3.connect(sqlite_db)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            select
                tf.*,
                o.exchange_order_id as exchange_order_id,
                o.last_status as order_last_status
            from TradeFill tf
            left join "Order" o on tf.order_id = o.id
            order by tf.timestamp, tf.exchange_trade_id
            """
        ).fetchall()
    finally:
        connection.close()

    fills = []
    for row in rows:
        price = _decode_hummingbot_decimal(row["price"])
        amount = _decode_hummingbot_decimal(row["amount"])
        fee_asset, fee_amount = _fee_from_json(str(row["trade_fee"]))
        base_asset = str(row["base_asset"])
        quote_asset = str(row["quote_asset"])
        side = str(row["trade_type"]).lower()
        fee_quote = _fee_quote_estimate(
            fee_asset=fee_asset,
            fee_amount=fee_amount,
            base_asset=base_asset,
            quote_asset=quote_asset,
            price=price,
            db_fee_quote=_decode_optional_hummingbot_decimal(row["trade_fee_in_quote"]),
        )
        gross_notional = amount * price
        net_base = amount
        if side == "buy" and fee_asset == base_asset:
            net_base = amount - fee_amount
        elif side == "sell" and fee_asset == base_asset:
            net_base = amount + fee_amount
        if side == "buy":
            cash_flow = -gross_notional
            cost_basis = gross_notional if fee_asset == base_asset else gross_notional + fee_quote
            notes = (
                "Validation export only. Fee was deducted from base returns; cost basis estimate "
                "uses quote spent and net base quantity. Confirm final tax treatment before filing."
            )
        else:
            cash_flow = gross_notional
            cost_basis = Decimal("0")
            notes = "Validation export only. Sell rows require ACB lot matching before filing."
        fills.append(
            LiveTradeFill(
                timestamp=datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=UTC),
                account_id=account_id,
                strategy_id=strategy_id,
                source="hummingbot_live",
                connector=str(row["market"]),
                trading_pair=str(row["symbol"]),
                side=side,
                order_type=str(row["order_type"]).lower(),
                client_order_id=hb_to_client.get(str(row["order_id"]), ""),
                hb_order_id=str(row["order_id"]),
                exchange_order_id=str(row["exchange_order_id"] or ""),
                exchange_trade_id=str(row["exchange_trade_id"]),
                base_asset=base_asset,
                quote_asset=quote_asset,
                gross_base_quantity=amount,
                fee_asset=fee_asset,
                fee_amount=fee_amount,
                net_base_quantity=net_base,
                price_quote=price,
                gross_quote_notional=gross_notional,
                fee_quote_estimate=fee_quote,
                cash_flow_quote=cash_flow,
                cost_basis_quote_estimate=cost_basis,
                cad_fx_rate=cad_fx_rate,
                fx_source=fx_source,
                notes=notes,
            )
        )
    return tuple(fills)


def _order_checks(
    expected_orders: tuple[dict[str, Any], ...],
    runtime_events: tuple[dict[str, Any], ...],
    fills: tuple[LiveTradeFill, ...],
) -> dict[str, object]:
    expected_ids = {str(order.get("client_order_id")) for order in expected_orders}
    submitted_ids = {
        str(event.get("client_order_id"))
        for event in runtime_events
        if event.get("event_type") == "submitted" and event.get("client_order_id")
    }
    filled_event_ids = {
        str(event.get("client_order_id"))
        for event in runtime_events
        if event.get("event_type") == "filled" and event.get("client_order_id")
    }
    db_fill_ids = {fill.client_order_id for fill in fills if fill.client_order_id}
    session_completed = any(
        event.get("event_type") == "session_completed" for event in runtime_events
    )
    return {
        "expected_orders": len(expected_ids),
        "submitted_orders": len(submitted_ids & expected_ids),
        "filled_orders": len(filled_event_ids & expected_ids),
        "db_fills": len(db_fill_ids & expected_ids),
        "session_completed": session_completed,
        "missing_submissions": sorted(expected_ids - submitted_ids),
        "missing_fills": sorted(expected_ids - filled_event_ids),
        "missing_db_fills": sorted(expected_ids - db_fill_ids),
        "unknown_submissions": sorted(submitted_ids - expected_ids),
        "unknown_fills": sorted(filled_event_ids - expected_ids),
        "unknown_db_fills": sorted(db_fill_ids - expected_ids),
    }


def _fill_summary(fills: tuple[LiveTradeFill, ...]) -> dict[str, object]:
    gross_notional = sum((fill.gross_quote_notional for fill in fills), Decimal("0"))
    gross_base = sum((fill.gross_base_quantity for fill in fills), Decimal("0"))
    net_base = sum((fill.net_base_quantity for fill in fills), Decimal("0"))
    fee_quote = sum((fill.fee_quote_estimate for fill in fills), Decimal("0"))
    cost_basis = sum((fill.cost_basis_quote_estimate for fill in fills), Decimal("0"))
    average_price = gross_notional / gross_base if gross_base else Decimal("0")
    first_fill = fills[0] if fills else None
    return {
        "gross_quote_notional": decimal_to_str(gross_notional),
        "gross_base_quantity": decimal_to_str(gross_base),
        "net_base_quantity": decimal_to_str(net_base),
        "average_price_quote": decimal_to_str(average_price),
        "fee_asset": first_fill.fee_asset if first_fill else "",
        "fee_amount": decimal_to_str(sum((fill.fee_amount for fill in fills), Decimal("0"))),
        "fee_quote_estimate": decimal_to_str(fee_quote),
        "cost_basis_quote_estimate": decimal_to_str(cost_basis),
        "fills": [fill.to_dict() for fill in fills],
    }


def _balance_checks(
    runtime_events: tuple[dict[str, Any], ...],
    fills: tuple[LiveTradeFill, ...],
) -> dict[str, object]:
    first: dict[str, Decimal] = {}
    last: dict[str, Decimal] = {}
    for event in sorted(runtime_events, key=lambda item: str(item.get("created_at", ""))):
        if event.get("event_type") != "balance" or event.get("balance_asset") is None:
            continue
        asset = str(event["balance_asset"])
        total = Decimal(str(event.get("balance_total", "0")))
        first.setdefault(asset, total)
        last[asset] = total
    if not fills:
        return {
            "status": "blocked",
            "quote_delta": "0",
            "base_delta": "0",
            "expected_quote_delta": "0",
            "expected_base_delta": "0",
            "mismatches": ["no fills"],
        }
    quote_asset = fills[0].quote_asset
    base_asset = fills[0].base_asset
    quote_delta = last.get(quote_asset, Decimal("0")) - first.get(quote_asset, Decimal("0"))
    base_delta = last.get(base_asset, Decimal("0")) - first.get(base_asset, Decimal("0"))
    expected_quote_delta = sum((fill.cash_flow_quote for fill in fills), Decimal("0"))
    expected_base_delta = sum((fill.net_base_quantity for fill in fills), Decimal("0"))
    mismatches = []
    if abs(quote_delta - expected_quote_delta) > Decimal("0.000001"):
        mismatches.append(
            {
                "asset": quote_asset,
                "expected": decimal_to_str(expected_quote_delta),
                "actual": decimal_to_str(quote_delta),
            }
        )
    if abs(base_delta - expected_base_delta) > Decimal("0.00000001"):
        mismatches.append(
            {
                "asset": base_asset,
                "expected": decimal_to_str(expected_base_delta),
                "actual": decimal_to_str(base_delta),
            }
        )
    return {
        "status": "checked" if not mismatches else "mismatch",
        "quote_asset": quote_asset,
        "base_asset": base_asset,
        "starting_balances": _selected_balances(first, {base_asset, quote_asset}),
        "ending_balances": _selected_balances(last, {base_asset, quote_asset}),
        "quote_delta": decimal_to_str(quote_delta),
        "base_delta": decimal_to_str(base_delta),
        "expected_quote_delta": decimal_to_str(expected_quote_delta),
        "expected_base_delta": decimal_to_str(expected_base_delta),
        "mismatches": mismatches,
    }


def _risk_checks(
    *,
    expected_orders: tuple[dict[str, Any], ...],
    runner_package: dict[str, Any],
    fills: tuple[LiveTradeFill, ...],
) -> dict[str, object]:
    summary = runner_package.get("summary", {})
    max_batch_notional = Decimal(str(summary.get("max_batch_notional", "0")))
    max_order_notional = Decimal(str(summary.get("max_order_notional", "0")))
    max_price_deviation_pct = Decimal(str(summary.get("max_price_deviation_pct", "0")))
    max_price_deviation_bps = max_price_deviation_pct * Decimal("10000")
    allowed_pairs = set(str(pair) for pair in summary.get("allowed_pairs", []))
    expected_by_client = {str(order.get("client_order_id")): order for order in expected_orders}
    total_notional = sum((fill.gross_quote_notional for fill in fills), Decimal("0"))
    order_notional_violations = [
        fill.client_order_id
        for fill in fills
        if max_order_notional > 0 and fill.gross_quote_notional > max_order_notional
    ]
    pair_violations = [
        fill.trading_pair
        for fill in fills
        if allowed_pairs and fill.trading_pair not in allowed_pairs
    ]
    price_deviation_bps = Decimal("0")
    price_deviation_inside_cap = True
    if fills:
        expected = expected_by_client.get(fills[0].client_order_id, {})
        estimated_price = Decimal(str(expected.get("estimated_price", "0")))
        if estimated_price > 0:
            price_deviation_bps = (
                abs(fills[0].price_quote - estimated_price) / estimated_price * Decimal("10000")
            )
            price_deviation_inside_cap = price_deviation_bps <= max_price_deviation_bps
    return {
        "max_batch_notional": decimal_to_str(max_batch_notional),
        "max_order_notional": decimal_to_str(max_order_notional),
        "allowed_pairs": sorted(allowed_pairs),
        "actual_total_notional": decimal_to_str(total_notional),
        "total_notional_inside_cap": (
            max_batch_notional <= 0 or total_notional <= max_batch_notional
        ),
        "order_count_inside_cap": len(fills) <= len(expected_orders),
        "order_notional_violations": order_notional_violations,
        "pair_violations": pair_violations,
        "price_deviation_bps": decimal_to_str(price_deviation_bps),
        "max_price_deviation_bps": decimal_to_str(max_price_deviation_bps),
        "price_deviation_inside_cap": price_deviation_inside_cap,
    }


def _selected_balances(balances: dict[str, Decimal], assets: set[str]) -> dict[str, str]:
    return {
        asset: decimal_to_str(value)
        for asset, value in sorted(balances.items())
        if asset in assets
    }


def _operational_checks(
    *,
    log_file: str | Path,
    runner_container_status: str,
) -> dict[str, object]:
    text = Path(log_file).read_text(encoding="utf-8") if Path(log_file).exists() else ""
    return {
        "mqtt_bridge_failures": text.count("Failed to connect MQTT Bridge"),
        "hummingbot_stop_observed": "Hummingbot stopped." in text,
        "runner_container_status": runner_container_status,
    }


def _tax_summary(
    fills: tuple[LiveTradeFill, ...],
    *,
    cad_fx_rate: Decimal,
    fx_source: str,
) -> dict[str, object]:
    gross_quote = sum((fill.gross_quote_notional for fill in fills), Decimal("0"))
    fee_quote = sum((fill.fee_quote_estimate for fill in fills), Decimal("0"))
    cost_basis = sum((fill.cost_basis_quote_estimate for fill in fills), Decimal("0"))
    return {
        "row_count": len(fills),
        "gross_quote_notional": decimal_to_str(gross_quote),
        "fee_quote_estimate": decimal_to_str(fee_quote),
        "cost_basis_quote_estimate": decimal_to_str(cost_basis),
        "cad_fx_rate": decimal_to_str(cad_fx_rate),
        "cost_basis_cad_estimate": decimal_to_str(cost_basis * cad_fx_rate),
        "fees_cad_estimate": decimal_to_str(fee_quote * cad_fx_rate),
        "fx_source": fx_source,
        "notes": (
            "Validation export only; confirm CAD FX and Canadian ACB treatment before "
            "tax filing."
        ),
    }


def _alerts(
    *,
    order_checks: dict[str, object],
    balance_checks: dict[str, object],
    risk_checks: dict[str, object],
    operational_checks: dict[str, object],
    tax_summary: dict[str, object],
) -> list[Alert]:
    alerts: list[Alert] = []
    if not order_checks["session_completed"]:
        alerts.append(
            critical_alert("Session incomplete", "Live event log has no session_completed event.")
        )
    reconcile_keys = (
        "missing_submissions",
        "missing_fills",
        "missing_db_fills",
        "unknown_submissions",
        "unknown_fills",
        "unknown_db_fills",
    )
    for key in reconcile_keys:
        if order_checks[key]:
            alerts.append(
                critical_alert("Order reconciliation mismatch", f"{key}: {order_checks[key]}")
            )
    if balance_checks["mismatches"]:
        alerts.append(
            critical_alert(
                "Balance mismatch",
                f"Observed mismatches: {balance_checks['mismatches']}",
            )
        )
    if not risk_checks["total_notional_inside_cap"] or not risk_checks["order_count_inside_cap"]:
        alerts.append(
            critical_alert("Live risk cap breached", "Order count or total notional exceeded cap.")
        )
    if risk_checks["order_notional_violations"] or risk_checks["pair_violations"]:
        alerts.append(
            critical_alert("Live order violation", "Observed pair or order notional violation.")
        )
    if not risk_checks["price_deviation_inside_cap"]:
        alerts.append(
            critical_alert(
                "Price deviation cap breached",
                "Fill price exceeded runtime deviation cap.",
            )
        )
    if int(operational_checks["mqtt_bridge_failures"]):
        alerts.append(
            warning_alert(
                "MQTT bridge unavailable",
                "Hummingbot completed the live order, but the MQTT bridge failed to "
                "connect during the run.",
            )
        )
    if "validation" in str(tax_summary["fx_source"]).lower():
        alerts.append(
            warning_alert(
                "Validation tax export",
                "Tax export uses validation-only FX/source assumptions and is not final "
                "tax filing output.",
            )
        )
    if not alerts:
        alerts.append(
            info_alert("Live batch reconciled", "Live batch reconciled without blocking issues.")
        )
    return alerts


def _status(alerts: tuple[Alert, ...] | list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "live_post_trade_blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "live_post_trade_reconciled_with_warnings"
    return "live_post_trade_reconciled"


def _decode_hummingbot_decimal(value: object) -> Decimal:
    return Decimal(str(value)) / HUMMINGBOT_DB_SCALE


def _decode_optional_hummingbot_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return _decode_hummingbot_decimal(value)


def _fee_from_json(raw: str) -> tuple[str, Decimal]:
    payload = json.loads(raw)
    flat_fees = payload.get("flat_fees", [])
    if isinstance(flat_fees, list) and flat_fees:
        fee = flat_fees[0]
        return str(fee.get("token", "")), Decimal(str(fee.get("amount", "0")))
    return str(payload.get("percent_token", "")), Decimal("0")


def _fee_quote_estimate(
    *,
    fee_asset: str,
    fee_amount: Decimal,
    base_asset: str,
    quote_asset: str,
    price: Decimal,
    db_fee_quote: Decimal | None,
) -> Decimal:
    if fee_asset == quote_asset:
        return fee_amount
    if fee_asset == base_asset:
        return fee_amount * price
    return db_fee_quote or Decimal("0")
