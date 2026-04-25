"""Order routing through risk and execution adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.core.models import AccountSnapshot
from packages.execution.order_intent import OrderIntent
from packages.risk.risk_decision import RiskDecision
from packages.risk.risk_engine import RiskEngine


class ExecutionClient(Protocol):
    def submit_order_intent(self, intent: OrderIntent) -> str:
        """Submit an already risk-approved order intent and return external order id."""


@dataclass(frozen=True, slots=True)
class RoutedOrder:
    intent_id: str
    risk_decision: RiskDecision
    external_order_id: str | None = None


class OrderRouter:
    def __init__(self, risk_engine: RiskEngine, execution_client: ExecutionClient) -> None:
        self._risk_engine = risk_engine
        self._execution_client = execution_client

    def submit(self, intent: OrderIntent, account: AccountSnapshot) -> RoutedOrder:
        decision = self._risk_engine.evaluate_order_intent(intent, account)
        if not decision.approved:
            return RoutedOrder(intent.intent_id, decision)

        external_order_id = self._execution_client.submit_order_intent(intent)
        return RoutedOrder(intent.intent_id, decision, external_order_id)
