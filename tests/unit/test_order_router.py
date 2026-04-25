from decimal import Decimal
from unittest import TestCase

from packages.core.enums import OrderSide, OrderType, RiskDecisionStatus
from packages.core.models import AccountSnapshot, OrderRequest
from packages.execution.order_intent import OrderIntent
from packages.execution.order_router import OrderRouter
from packages.risk.account_limits import AccountRiskLimits
from packages.risk.risk_engine import RiskEngine


class FakeExecutionClient:
    def __init__(self) -> None:
        self.submitted: list[OrderIntent] = []

    def submit_order_intent(self, intent: OrderIntent) -> str:
        self.submitted.append(intent)
        return f"external-{intent.intent_id}"


class OrderRouterTest(TestCase):
    def make_router(self, *, max_order_notional: Decimal) -> tuple[OrderRouter, FakeExecutionClient]:
        limits = AccountRiskLimits(
            max_order_notional=max_order_notional,
            max_symbol_notional=Decimal("2000"),
            max_gross_notional=Decimal("5000"),
            max_daily_loss=Decimal("250"),
            max_drawdown_pct=Decimal("0.10"),
        )
        client = FakeExecutionClient()
        return OrderRouter(RiskEngine(limits), client), client

    def make_intent(self, quantity: Decimal) -> OrderIntent:
        request = OrderRequest(
            client_order_id="order-1",
            strategy_id="test_strategy",
            symbol="ETH-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=quantity,
        )
        return OrderIntent("intent-1", "main", request, Decimal("100"))

    def test_submits_approved_order(self) -> None:
        router, client = self.make_router(max_order_notional=Decimal("1000"))
        account = AccountSnapshot("main", Decimal("10000"), Decimal("10000"))

        routed = router.submit(self.make_intent(Decimal("2")), account)

        self.assertEqual(RiskDecisionStatus.APPROVED, routed.risk_decision.status)
        self.assertEqual("external-intent-1", routed.external_order_id)
        self.assertEqual(1, len(client.submitted))

    def test_does_not_submit_rejected_order(self) -> None:
        router, client = self.make_router(max_order_notional=Decimal("100"))
        account = AccountSnapshot("main", Decimal("10000"), Decimal("10000"))

        routed = router.submit(self.make_intent(Decimal("2")), account)

        self.assertEqual(RiskDecisionStatus.REJECTED, routed.risk_decision.status)
        self.assertIsNone(routed.external_order_id)
        self.assertEqual([], client.submitted)
