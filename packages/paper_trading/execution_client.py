"""Paper execution client that records immediate simulated fills."""

from __future__ import annotations

from decimal import Decimal

from packages.core.enums import OrderStatus
from packages.execution.order_intent import OrderIntent
from packages.paper_trading.ledger import PaperLedger, PaperOrderRecord, make_paper_order_id


class PaperExecutionClient:
    def __init__(self, ledger: PaperLedger, *, fee_rate: Decimal = Decimal("0")) -> None:
        self._ledger = ledger
        self._fee_rate = fee_rate

    def submit_order_intent(self, intent: OrderIntent) -> str:
        paper_order_id = make_paper_order_id(intent.intent_id)
        notional = abs(intent.notional)
        record = PaperOrderRecord(
            paper_order_id=paper_order_id,
            intent_id=intent.intent_id,
            account_id=intent.account_id,
            strategy_id=intent.request.strategy_id,
            symbol=intent.symbol,
            side=intent.request.side,
            order_type=intent.request.order_type,
            quantity=intent.request.quantity,
            fill_price=intent.estimated_price,
            notional=notional,
            fee=notional * self._fee_rate,
            status=OrderStatus.FILLED,
            created_at=intent.created_at,
        )
        self._ledger.append(record)
        return paper_order_id
