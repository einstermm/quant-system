"""Execution policy abstractions."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from packages.core.enums import OrderSide, OrderType
from packages.core.models import OrderRequest
from packages.execution.order_intent import OrderIntent


class ExecutionPolicy(Protocol):
    def build_intent(
        self,
        *,
        intent_id: str,
        account_id: str,
        strategy_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        reference_price: Decimal,
    ) -> OrderIntent:
        """Convert a portfolio target change into a normalized order intent."""


class MarketOrderPolicy:
    def build_intent(
        self,
        *,
        intent_id: str,
        account_id: str,
        strategy_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        reference_price: Decimal,
    ) -> OrderIntent:
        request = OrderRequest(
            client_order_id=intent_id,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
        )
        return OrderIntent(intent_id, account_id, request, reference_price)
