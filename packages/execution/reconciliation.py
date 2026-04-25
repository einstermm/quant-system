"""Execution reconciliation contracts."""

from packages.core.models import OrderState


class ReconciliationStore:
    def __init__(self) -> None:
        self._orders: dict[str, OrderState] = {}

    def upsert(self, order_state: OrderState) -> None:
        self._orders[order_state.client_order_id] = order_state

    def get(self, client_order_id: str) -> OrderState | None:
        return self._orders.get(client_order_id)
