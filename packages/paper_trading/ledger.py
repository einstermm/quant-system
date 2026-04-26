"""JSONL paper order ledger."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from packages.core.enums import OrderSide, OrderStatus, OrderType
from packages.core.models import AccountSnapshot, PortfolioPosition, utc_now
from packages.backtesting.result import decimal_to_str


@dataclass(frozen=True, slots=True)
class PaperOrderRecord:
    paper_order_id: str
    intent_id: str
    account_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    fill_price: Decimal
    notional: Decimal
    fee: Decimal
    status: OrderStatus
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "paper_order_id": self.paper_order_id,
            "intent_id": self.intent_id,
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": decimal_to_str(self.quantity),
            "fill_price": decimal_to_str(self.fill_price),
            "notional": decimal_to_str(self.notional),
            "fee": decimal_to_str(self.fee),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "PaperOrderRecord":
        return cls(
            paper_order_id=str(payload["paper_order_id"]),
            intent_id=str(payload["intent_id"]),
            account_id=str(payload["account_id"]),
            strategy_id=str(payload["strategy_id"]),
            symbol=str(payload["symbol"]),
            side=OrderSide(str(payload["side"])),
            order_type=OrderType(str(payload["order_type"])),
            quantity=Decimal(str(payload["quantity"])),
            fill_price=Decimal(str(payload["fill_price"])),
            notional=Decimal(str(payload["notional"])),
            fee=Decimal(str(payload["fee"])),
            status=OrderStatus(str(payload["status"])),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
        )


class PaperLedger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: PaperOrderRecord) -> None:
        with self._path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.to_dict(), sort_keys=True))
            file.write("\n")

    def records(self) -> tuple[PaperOrderRecord, ...]:
        if not self._path.exists():
            return ()
        records = []
        with self._path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                records.append(PaperOrderRecord.from_dict(json.loads(stripped)))
        return tuple(records)

    def account_snapshot(
        self,
        *,
        account_id: str,
        initial_equity: Decimal,
        mark_prices: dict[str, Decimal],
    ) -> AccountSnapshot:
        cash = initial_equity
        quantities: dict[str, Decimal] = {}
        entry_prices: dict[str, Decimal] = {}
        for record in self.records():
            if record.account_id != account_id or record.status is not OrderStatus.FILLED:
                continue
            signed_quantity = record.quantity if record.side is OrderSide.BUY else -record.quantity
            quantities[record.symbol] = quantities.get(record.symbol, Decimal("0")) + signed_quantity
            entry_prices[record.symbol] = record.fill_price
            if record.side is OrderSide.BUY:
                cash -= record.notional + record.fee
            else:
                cash += record.notional - record.fee

        positions = []
        for symbol, quantity in quantities.items():
            if quantity == Decimal("0"):
                continue
            mark_price = mark_prices[symbol]
            positions.append(
                PortfolioPosition(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=entry_prices.get(symbol, mark_price),
                    mark_price=mark_price,
                )
            )
        equity = cash + sum((position.notional for position in positions), Decimal("0"))
        return AccountSnapshot(
            account_id=account_id,
            equity=equity,
            cash=cash,
            positions=tuple(positions),
        )


def make_paper_order_id(intent_id: str) -> str:
    return f"paper-{intent_id}-{utc_now().strftime('%Y%m%d%H%M%S%f')}"
