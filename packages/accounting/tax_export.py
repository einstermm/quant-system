"""Trade and tax export helpers."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.sandbox_reconciliation import SandboxRuntimeEvent
from packages.backtesting.result import decimal_to_str
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class TaxLotRow:
    trade_date: date
    symbol: str
    quantity: Decimal
    proceeds_cad: Decimal
    cost_basis_cad: Decimal
    fees_cad: Decimal


@dataclass(frozen=True, slots=True)
class TradeTaxExportRow:
    trade_date: date
    timestamp: datetime
    account_id: str
    strategy_id: str
    source: str
    client_order_id: str
    trading_pair: str
    side: str
    base_asset: str
    quote_asset: str
    quantity: Decimal
    price_quote: Decimal
    notional_quote: Decimal
    fee_quote: Decimal
    proceeds_quote: Decimal
    cost_basis_quote: Decimal
    cad_fx_rate: Decimal
    proceeds_cad: Decimal
    cost_basis_cad: Decimal
    fees_cad: Decimal
    fx_source: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "source": self.source,
            "client_order_id": self.client_order_id,
            "trading_pair": self.trading_pair,
            "side": self.side,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "quantity": decimal_to_str(self.quantity),
            "price_quote": decimal_to_str(self.price_quote),
            "notional_quote": decimal_to_str(self.notional_quote),
            "fee_quote": decimal_to_str(self.fee_quote),
            "proceeds_quote": decimal_to_str(self.proceeds_quote),
            "cost_basis_quote": decimal_to_str(self.cost_basis_quote),
            "cad_fx_rate": decimal_to_str(self.cad_fx_rate),
            "proceeds_cad": decimal_to_str(self.proceeds_cad),
            "cost_basis_cad": decimal_to_str(self.cost_basis_cad),
            "fees_cad": decimal_to_str(self.fees_cad),
            "fx_source": self.fx_source,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class TradeTaxExportSummary:
    status: str
    generated_at: datetime
    strategy_id: str
    account_id: str
    row_count: int
    source: str
    quote_asset: str
    cad_fx_rate: Decimal
    fx_source: str
    totals: dict[str, Decimal]
    alerts: tuple[Alert, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "row_count": self.row_count,
            "source": self.source,
            "quote_asset": self.quote_asset,
            "cad_fx_rate": decimal_to_str(self.cad_fx_rate),
            "fx_source": self.fx_source,
            "totals": {key: decimal_to_str(value) for key, value in self.totals.items()},
            "alerts": [alert.to_dict() for alert in self.alerts],
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Trade Tax Export Summary",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Status: `{self.status}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Account: `{self.account_id}`",
            f"- Rows: `{self.row_count}`",
            f"- Source: `{self.source}`",
            f"- Quote asset: `{self.quote_asset}`",
            f"- CAD FX rate: `{decimal_to_str(self.cad_fx_rate)}`",
            f"- FX source: `{self.fx_source}`",
            "",
            "## Totals",
            "",
        ]
        lines.extend(f"- {key}: `{decimal_to_str(value)}`" for key, value in self.totals.items())
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


CSV_COLUMNS = (
    "trade_date",
    "timestamp",
    "account_id",
    "strategy_id",
    "source",
    "client_order_id",
    "trading_pair",
    "side",
    "base_asset",
    "quote_asset",
    "quantity",
    "price_quote",
    "notional_quote",
    "fee_quote",
    "proceeds_quote",
    "cost_basis_quote",
    "cad_fx_rate",
    "proceeds_cad",
    "cost_basis_cad",
    "fees_cad",
    "fx_source",
    "notes",
)


def build_trade_tax_export_rows_from_hummingbot_events(
    *,
    events: Iterable[SandboxRuntimeEvent],
    account_id: str,
    strategy_id: str,
    cad_fx_rate: Decimal,
    fx_source: str,
    source: str = "hummingbot_export",
) -> tuple[TradeTaxExportRow, ...]:
    rows: list[TradeTaxExportRow] = []
    for event in sorted(events, key=lambda item: item.created_at):
        if event.event_type != "filled":
            continue
        if event.trading_pair is None or event.filled_amount is None or event.average_fill_price is None:
            continue
        base_asset, quote_asset = _split_pair(event.trading_pair)
        quantity = abs(event.filled_amount)
        price = event.average_fill_price
        notional = abs(quantity * price)
        fee = abs(event.fee_quote)
        side = (event.side or "").lower()
        if side == "sell":
            proceeds_quote = notional - fee
            cost_basis_quote = Decimal("0")
            notes = "Sell row requires ACB lot matching before tax filing."
        else:
            proceeds_quote = Decimal("0")
            cost_basis_quote = notional + fee
            notes = "Buy row contributes to ACB cost basis before tax filing."
        rows.append(
            TradeTaxExportRow(
                trade_date=event.created_at.date(),
                timestamp=event.created_at,
                account_id=account_id,
                strategy_id=strategy_id,
                source=source,
                client_order_id=event.client_order_id or "",
                trading_pair=event.trading_pair,
                side=side or "unknown",
                base_asset=base_asset,
                quote_asset=quote_asset,
                quantity=quantity,
                price_quote=price,
                notional_quote=notional,
                fee_quote=fee,
                proceeds_quote=proceeds_quote,
                cost_basis_quote=cost_basis_quote,
                cad_fx_rate=cad_fx_rate,
                proceeds_cad=proceeds_quote * cad_fx_rate,
                cost_basis_cad=cost_basis_quote * cad_fx_rate,
                fees_cad=fee * cad_fx_rate,
                fx_source=fx_source,
                notes=notes,
            )
        )
    return tuple(rows)


def build_trade_tax_export_summary(
    *,
    rows: tuple[TradeTaxExportRow, ...],
    strategy_id: str,
    account_id: str,
    source: str,
    quote_asset: str,
    cad_fx_rate: Decimal,
    fx_source: str,
    artifacts: dict[str, str] | None = None,
) -> TradeTaxExportSummary:
    totals = {
        "notional_quote": sum((row.notional_quote for row in rows), Decimal("0")),
        "fee_quote": sum((row.fee_quote for row in rows), Decimal("0")),
        "proceeds_quote": sum((row.proceeds_quote for row in rows), Decimal("0")),
        "cost_basis_quote": sum((row.cost_basis_quote for row in rows), Decimal("0")),
        "proceeds_cad": sum((row.proceeds_cad for row in rows), Decimal("0")),
        "cost_basis_cad": sum((row.cost_basis_cad for row in rows), Decimal("0")),
        "fees_cad": sum((row.fees_cad for row in rows), Decimal("0")),
    }
    alerts = _build_alerts(rows=rows, cad_fx_rate=cad_fx_rate, fx_source=fx_source)
    return TradeTaxExportSummary(
        status=_status(alerts),
        generated_at=datetime.now(tz=UTC),
        strategy_id=strategy_id,
        account_id=account_id,
        row_count=len(rows),
        source=source,
        quote_asset=quote_asset,
        cad_fx_rate=cad_fx_rate,
        fx_source=fx_source,
        totals=totals,
        alerts=tuple(alerts),
        artifacts=artifacts or {},
    )


def write_trade_tax_export_csv(rows: tuple[TradeTaxExportRow, ...], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())
    return output_path


def write_trade_tax_export_summary_json(summary: TradeTaxExportSummary, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_trade_tax_export_summary_markdown(summary: TradeTaxExportSummary, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary.to_markdown(), encoding="utf-8")
    return output_path


def _build_alerts(
    *,
    rows: tuple[TradeTaxExportRow, ...],
    cad_fx_rate: Decimal,
    fx_source: str,
) -> list[Alert]:
    alerts: list[Alert] = []
    if not rows:
        alerts.append(critical_alert("No trade rows", "No filled trades were available for tax export."))
    if cad_fx_rate <= Decimal("0"):
        alerts.append(critical_alert("Invalid CAD FX", "CAD FX rate must be positive."))
    if "validation" in fx_source.lower() or "placeholder" in fx_source.lower():
        alerts.append(
            warning_alert(
                "Validation FX source",
                "FX source is suitable for pipeline validation only, not final tax filing.",
            )
        )
    if any(row.cost_basis_quote == Decimal("0") for row in rows if row.side == "sell"):
        alerts.append(
            warning_alert(
                "ACB lot matching required",
                "Sell rows need adjusted cost base lot matching before Canadian tax filing.",
            )
        )
    if not alerts:
        alerts.append(info_alert("Tax export ready", "Trade tax export rows generated."))
    return alerts


def _status(alerts: tuple[Alert, ...] | list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "tax_export_blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "tax_export_ready_with_warnings"
    return "tax_export_ready"


def _split_pair(trading_pair: str) -> tuple[str, str]:
    if "-" not in trading_pair:
        return trading_pair, ""
    base_asset, quote_asset = trading_pair.split("-", 1)
    return base_asset, quote_asset
