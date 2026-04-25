"""Map system order intents into Hummingbot-facing payloads."""

from packages.execution.order_intent import OrderIntent


class OrderMapper:
    def to_hummingbot_payload(self, intent: OrderIntent) -> dict[str, object]:
        request = intent.request
        return {
            "client_order_id": request.client_order_id,
            "strategy_id": request.strategy_id,
            "symbol": request.symbol,
            "side": request.side.value,
            "order_type": request.order_type.value,
            "quantity": str(request.quantity),
            "limit_price": str(request.limit_price) if request.limit_price is not None else None,
            "time_in_force": request.time_in_force.value,
            "reduce_only": request.reduce_only,
            "estimated_price": str(intent.estimated_price),
        }
